"""The branch-domain registry is the authority (`core/branch_domains.py`'s own module docstring)
— which means a silent edit that drops, renames or duplicates a domain must fail loudly here,
not quietly ship as a screen that suddenly can't find its own domain id.
"""
from __future__ import annotations

from app.core.branch_domains import (BRANCH_DOMAINS, BRANCH_DOMAINS_BY_ID, is_branch_scoped)

# The owner-approved classification this session settled, verbatim — a future edit that silently
# drops or renames one of these must fail this test rather than ship unnoticed.
EXPECTED_IDS = {
    "visit", "customers", "rating", "bookings", "shop_insights", "team",
    "whatsapp_connect", "campaigns_send_log", "mobile_requests",
    "services_catalogue", "loyalty_points", "partner_loyalty", "referral_partnership",
    "whatsapp_assistant", "mobile_ai_assistant", "support", "billing_account",
    "campaigns_authoring",
}


def test_every_domain_id_is_unique():
    ids = [d.id for d in BRANCH_DOMAINS]
    assert len(ids) == len(set(ids))


def test_the_id_set_matches_the_owner_approved_list_exactly():
    ids = {d.id for d in BRANCH_DOMAINS}
    assert ids == EXPECTED_IDS


def test_every_branch_scoped_entry_carries_real_evidence():
    """`evidence` backs the claim — an empty string would be an unbacked one."""
    for d in BRANCH_DOMAINS:
        if d.branch_scoped:
            assert d.evidence and d.evidence.strip(), f"{d.id} has no evidence"


def test_only_mobile_requests_is_derived_rather_than_a_plain_branch_id():
    derived = {d.id for d in BRANCH_DOMAINS if d.derived_from is not None}
    assert derived == {"mobile_requests"}
    assert BRANCH_DOMAINS_BY_ID["mobile_requests"].derived_from == "assigned_operator_branch"


def test_every_domain_carries_a_non_empty_arabic_label():
    for d in BRANCH_DOMAINS:
        assert d.label_ar and d.label_ar.strip()


def test_lookup_by_id_matches_the_tuple():
    assert set(BRANCH_DOMAINS_BY_ID.keys()) == {d.id for d in BRANCH_DOMAINS}
    for d in BRANCH_DOMAINS:
        assert BRANCH_DOMAINS_BY_ID[d.id] is d


def test_is_branch_scoped_reads_true_and_false_correctly():
    assert is_branch_scoped("visit") is True
    assert is_branch_scoped("customers") is True
    assert is_branch_scoped("loyalty_points") is False
    assert is_branch_scoped("billing_account") is False


def test_is_branch_scoped_raises_on_unknown_id_instead_of_guessing():
    import pytest
    with pytest.raises(KeyError):
        is_branch_scoped("not_a_real_domain")


def test_mobile_requests_is_classified_branch_scoped_despite_being_derived():
    assert BRANCH_DOMAINS_BY_ID["mobile_requests"].branch_scoped is True
