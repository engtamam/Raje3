"""Marketing consent — the record we would have to produce if somebody asked."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.consent import (CONSENT, GRANTED, NEVER_ASKED, STATEMENT_VERSION, WITHDRAWN,
                              Consent, ConsentError, statement_for)

T = "shop"
S = "ref_abcdef123456"
NOW = 1_800_000_000


def run(c):
    return asyncio.run(c)


def fresh():
    store = MemoryDataStore()
    return store, Consent(store)


# ── the three states ───────────────────────────────────────────────────────────────────────────
def test_somebody_we_never_asked_is_not_somebody_who_agreed():
    """The whole reason this file exists. Before it, absence of a refusal read as agreement."""
    _, c = fresh()
    assert run(c.state(T, S)) == NEVER_ASKED
    assert run(c.allows_marketing(T, S)) is False


def test_a_grant_is_recorded_and_allows():
    _, c = fresh()
    run(c.record(T, S, state=GRANTED, source="customer_page", shop="مغسلة النخيل"))
    assert run(c.state(T, S)) == GRANTED
    assert run(c.allows_marketing(T, S)) is True


def test_a_withdrawal_supersedes_and_refuses():
    _, c = fresh()
    run(c.record(T, S, state=GRANTED, source="customer_page", shop="م", now=NOW))
    run(c.record(T, S, state=WITHDRAWN, source="customer_page", now=NOW + 10))
    assert run(c.state(T, S)) == WITHDRAWN
    assert run(c.allows_marketing(T, S)) is False


def test_a_withdrawal_is_a_new_row_and_never_an_edit():
    """A record you can edit proves nothing: "granted" would be a claim about today rather than
    about the moment they agreed. The history IS the evidence."""
    store, c = fresh()
    run(c.record(T, S, state=GRANTED, source="customer_page", shop="م", now=NOW))
    run(c.record(T, S, state=WITHDRAWN, source="customer_page", now=NOW + 10))
    rows = run(store.scan_all(CONSENT, 100))
    assert len(rows) == 2
    assert sorted(r["state"] for r in rows) == ["granted", "withdrawn"]


def test_granting_again_after_a_withdrawal_is_allowed_and_keeps_both():
    """Somebody may change their mind twice. What must survive is the sequence."""
    store, c = fresh()
    run(c.record(T, S, state=GRANTED, source="customer_page", shop="م", now=NOW))
    run(c.record(T, S, state=WITHDRAWN, source="customer_page", now=NOW + 10))
    run(c.record(T, S, state=GRANTED, source="customer_page", shop="م", now=NOW + 20))
    assert run(c.state(T, S)) == GRANTED
    assert len(run(store.scan_all(CONSENT, 100))) == 3


# ── the evidence a record has to carry ─────────────────────────────────────────────────────────
def test_a_grant_stores_the_sentence_they_were_shown():
    """Consent is to a specific statement. Storing a pointer to one we can edit is storing a
    pointer to something that may no longer be what they read."""
    _, c = fresh()
    rec = run(c.record(T, S, state=GRANTED, source="customer_page", shop="مغسلة النخيل"))
    assert "مغسلة النخيل" in rec.statement
    assert rec.statement_version == STATEMENT_VERSION


def test_the_sentence_names_the_shop_and_not_us():
    """"I agree to receive offers" with no subject is consent to nobody — the exact ambiguity that
    makes a bought list look lawful on paper."""
    s = statement_for("ورشة الخليج")
    assert "ورشة الخليج" in s and "راجع" not in s and "راجِع" not in s


def test_the_sentence_says_how_often_and_how_to_stop():
    s = statement_for("م")
    assert "أربع" in s and "الإيقاف" in s


def test_a_withdrawal_carries_no_statement():
    """It is not agreement to anything, and attaching the words of a consent to the record of its
    refusal would misrepresent both."""
    _, c = fresh()
    rec = run(c.record(T, S, state=WITHDRAWN, source="customer_page"))
    assert rec.statement == ""


def test_the_source_is_recorded_because_it_is_the_first_question_asked():
    _, c = fresh()
    rec = run(c.record(T, S, state=GRANTED, source="field_screen", shop="م", actor="emp-3"))
    assert rec.source == "field_screen" and rec.actor == "emp-3"


def test_an_unknown_source_is_refused_rather_than_stored():
    """A consent of unknown provenance is how an unlawful list enters the record."""
    _, c = fresh()
    with pytest.raises(ConsentError):
        run(c.record(T, S, state=GRANTED, source="somewhere", shop="م"))


def test_a_state_that_is_not_a_transition_is_refused():
    _, c = fresh()
    with pytest.raises(ConsentError):
        run(c.record(T, S, state=NEVER_ASKED, source="customer_page"))


# ── the count the owner sees ───────────────────────────────────────────────────────────────────
def test_the_count_is_of_people_not_of_grants():
    """Somebody who granted twice is one person, and somebody who granted then withdrew is none."""
    _, c = fresh()
    run(c.record(T, "ref_a", state=GRANTED, source="customer_page", shop="م", now=NOW))
    run(c.record(T, "ref_a", state=GRANTED, source="customer_page", shop="م", now=NOW + 1))
    run(c.record(T, "ref_b", state=GRANTED, source="customer_page", shop="م", now=NOW))
    run(c.record(T, "ref_b", state=WITHDRAWN, source="customer_page", now=NOW + 5))
    run(c.record(T, "ref_c", state=GRANTED, source="customer_page", shop="م", now=NOW))
    assert run(c.count_granted(T)) == 2


def test_the_count_never_leaks_another_establishment():
    _, c = fresh()
    run(c.record("a", "ref_x", state=GRANTED, source="customer_page", shop="م"))
    run(c.record("b", "ref_y", state=GRANTED, source="customer_page", shop="م"))
    assert run(c.count_granted("a")) == 1


def test_a_shop_nobody_has_answered_counts_zero_rather_than_everybody():
    """THE DEFECT THIS REPLACES. Computed from refusals, the number was every customer he had —
    worse than showing nothing, because the first campaign disproves it."""
    _, c = fresh()
    assert run(c.count_granted(T)) == 0
