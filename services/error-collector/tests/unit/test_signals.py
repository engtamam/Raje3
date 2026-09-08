"""The signal contract and the store behind it, exercised directly.

The routes get their own file. This one is about the rules that must hold no matter which door a
signal came through — because both doors validate the same model, and a rule enforced only in a
route is a rule the other route does not have.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.adapters.datastore.memory import MemoryDataStore
from app.core.erasure import TemplateErasure
from app.core.models import SIGNALS
from app.core.signals import MAX_BLOB_BYTES, SignalIn, SignalStore, public

DAY = 86_400


def _sig(**over) -> SignalIn:
    base = {"source": "server_log", "severity": "error", "service": "loyalty",
            "message": "boom"}
    base.update(over)
    return SignalIn(**base)


# ── the contract ──────────────────────────────────────────────────────────────────────────────
def test_the_four_required_fields_are_required():
    for missing in ("source", "severity", "service", "message"):
        payload = {"source": "browser", "severity": "error", "service": "console",
                   "message": "x"}
        payload.pop(missing)
        with pytest.raises(ValidationError):
            SignalIn(**payload)


def test_source_and_severity_are_free_form_not_an_enum():
    """THE WHOLE DESIGN IN ONE TEST. A value nobody has written before must be accepted, or every
    new emitter is a migration."""
    s = _sig(source="mobile_app", severity="warning", service="ios")
    assert (s.source, s.severity) == ("mobile_app", "warning")
    assert _sig(severity="info").severity == "info"


def test_a_blank_or_oversized_name_is_refused():
    with pytest.raises(ValidationError):
        _sig(source="   ")
    with pytest.raises(ValidationError):
        _sig(severity="e" * 65)
    with pytest.raises(ValidationError):
        _sig(service="s" * 129)


def test_the_blobs_are_bounded_by_serialised_size():
    # Just under, and just over. A dict has no max_length, so this bound is the only thing
    # standing between a runaway client and a 40 MB row.
    ok = {"stack": "x" * (MAX_BLOB_BYTES - 200)}
    assert _sig(detail=ok).detail == ok
    with pytest.raises(ValidationError):
        _sig(detail={"stack": "x" * (MAX_BLOB_BYTES + 100)})
    with pytest.raises(ValidationError):
        _sig(context={"url": "u" * (MAX_BLOB_BYTES + 100)})


def test_optional_fields_default_to_absent_not_to_a_guess():
    s = _sig()
    assert (s.occurred_at, s.status_code, s.request_id, s.detail, s.context) == \
        (None, None, None, None, None)


# ── the store ─────────────────────────────────────────────────────────────────────────────────
@pytest.fixture()
def store():
    return SignalStore(MemoryDataStore(), retention_days=10, reap_limit=5000)


async def test_received_at_is_server_set_and_occurred_at_defaults_to_it(store):
    row = await store.record(_sig(), now=1_000_000)
    assert row["received_at"] == 1_000_000
    assert row["occurred_at"] == 1_000_000

    row2 = await store.record(_sig(occurred_at=999_000), now=1_000_000)
    assert row2["received_at"] == 1_000_000      # the caller cannot move this
    assert row2["occurred_at"] == 999_000        # and its own claim is kept, separately


async def test_both_sources_land_in_one_collection(store):
    await store.record(_sig(source="server_log", service="loyalty"), now=10)
    await store.record(_sig(source="browser", service="console"), now=20)
    rows = await store._s.scan_all(SIGNALS, 100)
    assert len(rows) == 2
    assert {r["source"] for r in rows} == {"server_log", "browser"}


async def test_browse_is_newest_first(store):
    for i in range(5):
        await store.record(_sig(message=f"m{i}"), now=1000 + i)
    rows, _ = await store.browse()
    assert [r["message"] for r in rows] == ["m4", "m3", "m2", "m1", "m0"]


async def test_browse_filters_push_down_and_combine(store):
    await store.record(_sig(source="browser", severity="error", service="console"), now=10)
    await store.record(_sig(source="server_log", severity="warning", service="loyalty"), now=20)
    await store.record(_sig(source="server_log", severity="error", service="loyalty"), now=30)

    rows, _ = await store.browse(sources=["browser"])
    assert len(rows) == 1 and rows[0]["source"] == "browser"

    # A MEMBERSHIP FILTER, which is the shape the free-form column exists for.
    rows, _ = await store.browse(severities=["error", "warning"])
    assert len(rows) == 3

    rows, _ = await store.browse(service="loyalty", severities=["error"])
    assert len(rows) == 1 and rows[0]["received_at"] == 30


async def test_browse_window_and_free_text(store):
    await store.record(_sig(message="connection refused"), now=100)
    await store.record(_sig(message="TIMEOUT talking to postgres"), now=200)
    await store.record(_sig(message="connection reset"), now=300)

    rows, _ = await store.browse(since=150, until=250)
    assert [r["received_at"] for r in rows] == [200]

    # Case-insensitive, because nobody types a stack trace's capitalisation from memory.
    rows, _ = await store.browse(q="TIMEOUT")
    assert len(rows) == 1
    rows, _ = await store.browse(q="connection")
    assert len(rows) == 2


async def test_browse_pages_without_skipping_or_repeating(store):
    for i in range(25):
        await store.record(_sig(message=f"m{i}"), now=1000 + i)
    seen = []
    cursor = ""
    for _ in range(10):
        rows, cursor = await store.browse(limit=7, after=cursor or "")
        seen.extend(r["message"] for r in rows)
        if not cursor:
            break
    assert len(seen) == 25
    assert len(set(seen)) == 25


async def test_distinct_is_built_from_the_data(store):
    await store.record(_sig(source="browser"), now=1)
    await store.record(_sig(source="server_log"), now=2)
    await store.record(_sig(source="mobile_app"), now=3)
    assert await store.distinct("source") == ["browser", "mobile_app", "server_log"]


# ── retention ─────────────────────────────────────────────────────────────────────────────────
async def test_reap_removes_only_what_is_past_the_window(store):
    now = 100 * DAY
    await store.record(_sig(message="old"), now=now - 11 * DAY)
    await store.record(_sig(message="edge"), now=now - 10 * DAY + 60)   # inside, barely
    await store.record(_sig(message="fresh"), now=now - 1 * DAY)

    assert await store.reap(now=now) == 1
    rows, _ = await store.browse()
    assert sorted(r["message"] for r in rows) == ["edge", "fresh"]

    # IDEMPOTENT AND SELF-TERMINATING: the cron calls until this answers 0.
    assert await store.reap(now=now) == 0


async def test_reap_is_bounded_per_call_and_makes_progress(store):
    now = 100 * DAY
    for i in range(12):
        await store.record(_sig(message=f"old{i}"), now=now - 20 * DAY + i)

    # BOUNDED. Each pass takes its budget, oldest first — never the same page twice.
    total = 0
    for _ in range(10):
        n = await store.reap(now=now, limit=5)
        total += n
        if n == 0:
            break
    assert total == 12
    rows, _ = await store.browse()
    assert rows == []


async def test_reap_walks_oldest_first_so_a_bound_reaches_the_old_rows(store):
    """Descending order would page through every fresh row first and delete nothing under a bound —
    perfectly correct, and doing nothing at all."""
    now = 100 * DAY
    for i in range(50):
        await store.record(_sig(message=f"fresh{i}"), now=now - 60)
    await store.record(_sig(message="ancient"), now=now - 30 * DAY)

    assert await store.reap(now=now, limit=1) == 1
    rows, _ = await store.browse(limit=500)
    assert "ancient" not in [r["message"] for r in rows]
    assert len(rows) == 50


# ── erasure ───────────────────────────────────────────────────────────────────────────────────
async def test_erasure_deletes_attributed_rows_and_reports_the_rest_honestly():
    ds = MemoryDataStore()
    store = SignalStore(ds)
    salt = "s" * 40
    from app.core.pii import subject_ref
    ref = subject_ref(salt, "t1", "u1")

    await store.record(_sig(source="browser"), now=10, tenant="t1", subject_ref=ref)
    await store.record(_sig(source="browser"), now=11, tenant="t1", subject_ref=ref)
    await store.record(_sig(source="browser"), now=12, tenant="t1", subject_ref="someone-else")
    await store.record(_sig(source="server_log"), now=13)   # unattributed

    ack = await TemplateErasure(store=ds, pii_salt=salt).erase("t1", "u1")
    assert ack["service"] == "error-collector"
    assert ack["erased"] == ["signals:2"]
    assert ack["already_absent"] is False
    assert ack["truncated"] is False
    # The residue is NAMED with a basis, never counted as erased and never silently omitted.
    assert ack["retained"][0]["basis"] == "no_identifier_to_match"
    assert "10 days" in ack["retained"][0]["why"]
    # Nobody else's rows moved.
    assert len(await ds.scan_all(SIGNALS, 100)) == 2


async def test_erasure_is_idempotent_and_a_ref_is_not_hashed_twice():
    ds = MemoryDataStore()
    store = SignalStore(ds)
    salt = "s" * 40
    from app.core.pii import subject_ref
    ref = subject_ref(salt, "t1", "u1")
    await store.record(_sig(), now=10, tenant="t1", subject_ref=ref)

    eraser = TemplateErasure(store=ds, pii_salt=salt)
    first = await eraser.erase("t1", "u1")
    assert first["erased"] == ["signals:1"]

    # A retry finds nothing and SAYS it looked — never a 500 on the second call.
    second = await eraser.erase("t1", "u1")
    assert second["already_absent"] is True and second["erased"] == []

    # AND THE REF ITSELF, handed back in — the common case, not the bug. It must fold to itself,
    # or the erasure would search for the ref of a ref and report success over untouched data.
    assert (await eraser.erase("t1", ref))["subject_ref"] == ref


async def test_erasure_without_a_subject_refuses_rather_than_claiming_success():
    ack = await TemplateErasure(store=MemoryDataStore(), pii_salt="s" * 40).erase("t1", "")
    assert ack["already_absent"] is True
    assert "nothing was scanned" in ack["note"]


# ── the wire shape ────────────────────────────────────────────────────────────────────────────
async def test_public_hides_storage_mechanics(store):
    row = await store.record(_sig(status_code=502, request_id="r-1",
                                  detail={"stack": "..."}, context={"pod": "p"}), now=42)
    out = public(row)
    assert "kind" not in out and "created" not in out
    assert "tenant" not in out and "subject_ref" not in out
    assert out["status_code"] == 502 and out["request_id"] == "r-1"
    assert out["detail"] == {"stack": "..."} and out["context"] == {"pod": "p"}


async def test_a_null_status_code_stays_null_rather_than_becoming_zero(store):
    row = await store.record(_sig(), now=1)
    assert public(row)["status_code"] is None
