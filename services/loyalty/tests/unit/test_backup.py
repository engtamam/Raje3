"""Export and import a service's data.

The happy-path roundtrip is the least of it. The tests that matter are the ones that decide whether
a restore can be trusted: a corrupt archive refused rather than restored as garbage, a wrong backup
key refused rather than producing nonsense, a re-run that changes nothing, and a restore that does
not bulldoze rows written since the backup. Those are the failures that turn "we have backups" into
a false statement.
"""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core import backup as B

DECL = {
    "object_prefix": "",
    "collections": [
        {"name": "widgets", "tenant_scoped": True},
        {"name": "catalog", "tenant_scoped": False},
    ],
    "excluded": [],
}


def run(c):
    return asyncio.run(c)


def _seed(st, tenant="acme"):
    for i in range(3):
        run(st.put("widgets", f"w_{tenant}_{i}",
                   {"id": f"w_{tenant}_{i}", "tenant": tenant, "n": i, "created": f"2026-07-0{i+1}"}))
    run(st.put("catalog", "c1", {"id": "c1", "name": "Basic", "created": "2026-07-01"}))
    return st


def _export(st, tenant="", kek="backup-key"):
    seal, _ = B.make_sealer(kek)
    return run(B.export(st, DECL, service="thing-service", version="1.0.0",
                        taken_at="2026-07-22T00:00:00Z", seal=seal, tenant=tenant, scan_cap=1000))


# ── roundtrip ─────────────────────────────────────────────────────────────────
def test_a_backup_restores_into_an_empty_store():
    src = _seed(MemoryDataStore())
    archive = _export(src)

    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    report = run(B.import_archive(dst, archive, unseal=unseal))

    assert report["inserted"] == 4      # 3 widgets + 1 catalog row
    assert run(dst.get("widgets", "w_acme_1"))["n"] == 1
    assert run(dst.get("catalog", "c1"))["name"] == "Basic"


def test_the_payload_is_not_in_the_clear():
    """A backup at rest must be ciphertext. Row COUNTS are exposed on purpose; values are not."""
    archive = _export(_seed(MemoryDataStore()))
    blob = str(archive)
    assert "Basic" not in blob and "w_acme_1" not in blob
    assert archive["row_counts"] == {"widgets": 3, "catalog": 1}


# ── corruption is refused, not restored ───────────────────────────────────────
def test_a_truncated_archive_is_refused():
    """A process that died mid-write must not produce something a restore will happily apply."""
    archive = _export(_seed(MemoryDataStore()))
    archive["sealed"] = archive["sealed"][:-20]        # the tail was never written
    with pytest.raises(B.BackupError, match="checksum"):
        B.verify(archive)


def test_a_missing_checksum_is_refused():
    archive = _export(_seed(MemoryDataStore()))
    del archive["checksum"]
    with pytest.raises(B.BackupError, match="truncated"):
        B.verify(archive)


def test_a_foreign_format_is_refused():
    with pytest.raises(B.BackupError, match="not a"):
        B.verify({"format": "someone-elses/v9", "sealed": "x", "checksum": "y"})


def test_a_corrupt_archive_never_reaches_the_datastore():
    archive = _export(_seed(MemoryDataStore()))
    archive["checksum"] = "sha256:0000"
    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    with pytest.raises(B.BackupError):
        run(B.import_archive(dst, archive, unseal=unseal))
    assert run(dst.get("catalog", "c1")) is None, "a refused archive wrote rows anyway"


# ── the wrong key is refused clearly ──────────────────────────────────────────
def test_restoring_with_the_wrong_backup_key_is_refused():
    """A KEK rotated since the backup must fail loudly, not decrypt to nonsense and write it."""
    archive = _export(_seed(MemoryDataStore()), kek="the-old-key")
    _, wrong = B.make_sealer("a-different-key")
    with pytest.raises(B.BackupError, match="key does not match"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=wrong))


def test_an_empty_backup_key_is_refused_rather_than_sealing_in_the_clear():
    with pytest.raises(B.BackupError, match="required"):
        B.make_sealer("")


# ── idempotent, and does not clobber ──────────────────────────────────────────
def test_restoring_twice_changes_nothing_the_second_time():
    archive = _export(_seed(MemoryDataStore()))
    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    run(B.import_archive(dst, archive, unseal=unseal))
    second = run(B.import_archive(dst, archive, unseal=unseal))
    assert second["inserted"] == 0 and second["skipped"] == 4


def test_a_row_written_since_the_backup_is_not_bulldozed():
    """A restore into a partly-existing tenant must not overwrite what was written after the backup
    — that is what makes a half-finished restore safe to re-run."""
    archive = _export(_seed(MemoryDataStore()))
    _, unseal = B.make_sealer("backup-key")

    dst = MemoryDataStore()
    run(dst.put("widgets", "w_acme_1", {"id": "w_acme_1", "tenant": "acme", "n": 999}))
    report = run(B.import_archive(dst, archive, unseal=unseal))

    assert run(dst.get("widgets", "w_acme_1"))["n"] == 999, "a newer row was clobbered"
    assert report["skipped"] >= 1 and report["inserted"] >= 1


def test_overwrite_replaces_when_the_operator_asks():
    archive = _export(_seed(MemoryDataStore()))
    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    run(dst.put("widgets", "w_acme_1", {"id": "w_acme_1", "tenant": "acme", "n": 999}))
    report = run(B.import_archive(dst, archive, unseal=unseal, overwrite=True))
    assert run(dst.get("widgets", "w_acme_1"))["n"] == 1
    assert report["overwritten"] >= 1


def test_a_row_with_no_identity_is_refused():
    """Restoring an id-less row twice would duplicate it — refuse rather than double-write."""
    seal, unseal = B.make_sealer("backup-key")
    st = MemoryDataStore()
    run(st.put("widgets", "ok", {"id": "ok", "tenant": "acme"}))
    # Forge an archive whose sealed body contains an id-less row.
    import json
    body = json.dumps({"service": "s", "tenant": "", "collections": {"widgets": [{"tenant": "acme"}]}})
    archive = {"format": B.ARCHIVE_FORMAT, "service": "s", "sealed": seal(body)}
    archive["checksum"] = B._checksum(archive["sealed"])
    # Upstream improved this message and did not update its own test — `_template` ships
    # with this failing. Matched on the stable part rather than the sentence.
    with pytest.raises(B.BackupError, match="stable per-row key"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=unseal))


# ── per-tenant scope ──────────────────────────────────────────────────────────
def test_a_per_tenant_backup_holds_only_that_tenant():
    st = MemoryDataStore()
    _seed(st, tenant="acme")
    _seed(st, tenant="globex")
    archive = _export(st, tenant="acme")

    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    run(B.import_archive(dst, archive, unseal=unseal))

    rows, _ = run(dst.find("widgets", {"tenant": "acme"}, limit=100))
    assert rows and all(r["tenant"] == "acme" for r in rows)
    other, _ = run(dst.find("widgets", {"tenant": "globex"}, limit=100))
    assert other == [], "a per-tenant backup leaked another tenant's rows"


def test_a_per_tenant_backup_still_includes_global_collections():
    """A shared catalogue is not one tenant's to omit — a tenant restored without it is broken."""
    st = MemoryDataStore()
    _seed(st, tenant="acme")
    archive = _export(st, tenant="acme")
    assert archive["row_counts"]["catalog"] == 1


# ── verify_restore: prove the archive actually restores (Phase 46.4) ──────────
def _verify(st, archive, kek="backup-key", token="t1"):
    _, unseal = B.make_sealer(kek)
    return run(B.verify_restore(st, archive, unseal=unseal, token=token))


def test_verify_passes_for_a_good_archive_and_leaves_nothing_behind():
    src = _seed(MemoryDataStore())
    archive = _export(src)
    scratch = MemoryDataStore()

    verdict = _verify(scratch, archive)

    assert verdict["verified"] is True
    assert verdict["checked"] == verdict["expected"] == 4
    # The throwaway namespace is torn down — a verification never leaves probe rows in the store.
    leftover = run(scratch.scan_all("__bkpverify__t1__widgets", 1000))
    assert leftover == [], "verify left throwaway rows behind"
    assert run(scratch.scan_all("__bkpverify__t1__catalog", 1000)) == []


def test_verify_refuses_a_corrupt_archive_before_touching_the_store():
    src = _seed(MemoryDataStore())
    archive = _export(src)
    archive["checksum"] = "sha256:deadbeef"
    scratch = MemoryDataStore()
    with pytest.raises(B.BackupError):
        _verify(scratch, archive)


def test_verify_refuses_an_archive_the_key_cannot_open():
    """A KEK rotated since the backup: it decrypts to nothing usable, so it is NOT restorable."""
    src = _seed(MemoryDataStore())
    archive = _export(src, kek="the-old-key")
    with pytest.raises(B.BackupError):
        _verify(MemoryDataStore(), archive, kek="a-different-key")


class _TamperingStore(MemoryDataStore):
    """A store whose read-back does not match the write — stands in for a schema/serialisation drift
    that a checksum cannot see but a test-restore-and-compare must."""
    async def get(self, collection, key):
        row = await super().get(collection, key)
        if row is not None and collection.startswith("__bkpverify__"):
            row = {**row, "n": (row.get("n", 0) + 999)}   # not what was written
        return row


def test_verify_fails_when_a_row_does_not_round_trip():
    src = _seed(MemoryDataStore())
    archive = _export(src)
    verdict = _verify(_TamperingStore(), archive)
    assert verdict["verified"] is False
    assert verdict["mismatches"], "a row that restored differently was reported as verified"


# ── authoritative undo (backup-r2-01/02/04) ──────────────────────────────────────────────────────
def test_prune_deletes_rows_the_archive_never_had():
    """Overwrite alone puts back changed rows but leaves whatever a bad restore INSERTED — prune is
    what makes `undo` a true rollback rather than a partial one."""
    src = _seed(MemoryDataStore())
    archive = _export(src)
    _, unseal = B.make_sealer("backup-key")

    dst = MemoryDataStore()
    run(B.import_archive(dst, archive, unseal=unseal))
    # A row the archive never described — exactly what a wrong restore since the backup would leave.
    run(dst.put("widgets", "w_acme_ROGUE", {"id": "w_acme_ROGUE", "tenant": "acme", "n": 99}))

    report = run(B.import_archive(dst, archive, unseal=unseal, overwrite=True,
                                  prune=True, scan_cap=1000))
    assert report["pruned"] == 1
    assert run(dst.get("widgets", "w_acme_ROGUE")) is None
    assert run(dst.get("widgets", "w_acme_1")) is not None   # the archive's own rows survive


def test_prune_refuses_without_a_positive_scan_cap():
    src = _seed(MemoryDataStore())
    archive = _export(src)
    _, unseal = B.make_sealer("backup-key")
    with pytest.raises(B.BackupError, match="scan_cap"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=unseal, prune=True))


def test_prune_refuses_alongside_into_tenant():
    """A clone is additive; it must never delete the destination tenant's own rows."""
    src = _seed(MemoryDataStore())
    archive = _export(src)
    _, unseal = B.make_sealer("backup-key")
    with pytest.raises(B.BackupError, match="into_tenant"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=unseal,
                             prune=True, scan_cap=1000, into_tenant="acme2"))


def test_a_tenant_scoped_export_past_scan_cap_fails_loud_not_truncated():
    src = _seed(MemoryDataStore())
    seal, _ = B.make_sealer("backup-key")
    with pytest.raises(B.BackupError, match="scan_cap"):
        run(B.export(src, DECL, service="thing-service", version="1.0.0",
                     taken_at="2026-07-22T00:00:00Z", seal=seal, tenant="acme", scan_cap=2))


def test_a_global_sweep_past_scan_cap_fails_loud_not_truncated():
    src = _seed(MemoryDataStore())
    seal, _ = B.make_sealer("backup-key")
    with pytest.raises(B.BackupError, match="scan_cap"):
        run(B.export(src, DECL, service="thing-service", version="1.0.0",
                     taken_at="2026-07-22T00:00:00Z", seal=seal, scan_cap=1))   # catalog has 1 row


def test_into_tenant_refuses_an_archive_spanning_multiple_source_tenants():
    st = MemoryDataStore()
    _seed(st, tenant="acme")
    _seed(st, tenant="globex")
    archive = _export(st)   # whole-service archive — TWO tenants inside
    _, unseal = B.make_sealer("backup-key")
    with pytest.raises(B.BackupError, match="multiple source tenants"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=unseal, into_tenant="acme3"))


def test_into_tenant_still_clones_a_single_tenant_archive():
    src = _seed(MemoryDataStore(), tenant="acme")
    archive = _export(src, tenant="acme")
    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    report = run(B.import_archive(dst, archive, unseal=unseal, into_tenant="acme-clone"))
    assert report["remapped"] == 3
    assert run(dst.get("widgets", "w_acme_1"))["tenant"] == "acme-clone"


# ── the AAD upgrade path (2026-09-19) — an archive sealed before AAD binding must still restore ─
def _legacy_export(st, tenant="", kek="backup-key", service="thing-service"):
    """An archive shaped exactly like export()'s own output, but sealed the OLD way
    (associated_data=None) — reproducing a real archive written before this file bound the AAD."""
    import json as _json
    seal, _ = B.make_sealer(kek)
    body = _json.dumps({"service": service, "version": "1.0.0", "taken_at": "2026-07-22T00:00:00Z",
                        "tenant": tenant, "collections": {
                            "widgets": [run(st.get("widgets", f"w_{tenant or 'acme'}_{i}")) for i in range(3)],
                            "catalog": [run(st.get("catalog", "c1"))],
                        }}, separators=(",", ":"), sort_keys=True)
    sealed = seal(body)   # no aad kwarg — the legacy, pre-AAD shape
    return {
        "format": B.ARCHIVE_FORMAT, "service": service, "taken_at": "2026-07-22T00:00:00Z",
        "tenant": tenant, "row_counts": {"widgets": 3, "catalog": 1},
        "sealed": sealed, "checksum": B._checksum(sealed),
    }


def test_a_legacy_no_aad_archive_still_restores_after_the_upgrade():
    """The exact incident this exists to prevent, at the archive layer: an archive sealed before
    AAD binding shipped must still restore with no migration needed."""
    src = _seed(MemoryDataStore())
    archive = _legacy_export(src)
    _, unseal = B.make_sealer("backup-key")
    dst = MemoryDataStore()
    report = run(B.import_archive(dst, archive, unseal=unseal))
    assert report["inserted"] == 4
    assert run(dst.get("catalog", "c1"))["name"] == "Basic"


def test_a_legacy_archive_with_the_wrong_key_still_fails_loudly():
    src = _seed(MemoryDataStore())
    archive = _legacy_export(src, kek="the-old-key")
    _, wrong = B.make_sealer("a-different-key")
    with pytest.raises(B.BackupError, match="key does not match"):
        run(B.import_archive(MemoryDataStore(), archive, unseal=wrong))
