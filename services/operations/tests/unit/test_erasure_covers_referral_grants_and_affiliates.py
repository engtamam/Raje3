"""Phase 5b security sweep finding: core/erasure.py::OperationsErasure went live in Phases 3/4
with GRANTS (core/referral_redemption.py) and AFFILIATES/SETTLEMENTS (core/affiliates.py) already
storing real phone numbers, and no erasure coverage for either — a customer's DSAR erased their
Customer row and left their phone sitting untouched in every referral grant and affiliate row that
ever mentioned them."""
from __future__ import annotations

import asyncio

from app.adapters.datastore.memory import MemoryDataStore
from app.core.affiliates import AFFILIATES, SETTLEMENTS
from app.core.erasure import OperationsErasure
from app.core.pii import subject_ref
from app.core.referral_redemption import GRANTS

SALT = "s" * 32
TENANT = "t1"
CC = "966"
REFERRER_PHONE = "0511111111"           # what a caller/cashier types in
CANON_REFERRER = "+966511111111"        # what canonical_phone() actually stores
BENEFICIARY_PHONE = "0522222222"
CANON_BENEFICIARY = "+966522222222"


def run(c):
    return asyncio.run(c)


async def _seed_grant(store, **over) -> None:
    base = dict(
        id="g1", tenant=TENANT, code="AB123", referrer_phone=CANON_REFERRER,
        beneficiary_phone=CANON_BENEFICIARY, campaign_id="camp_1", mode="once", created=1000,
        new_customer_reward_type="discount_percent", new_customer_reward_params={"percent": 10},
        referrer_reward_type="fixed_points", referrer_reward_params={"points": 50},
        invoice_minor=5000, redeemed_at=2000, redeemed_visit_id="v1",
        referrer_reward_credited=True, referrer_points_credited=50, source="referral",
        affiliate_id="",
    )
    base.update(over)
    await store.put(GRANTS, f"{base['tenant']}|{base['id']}", base)


async def _seed_affiliate(store, **over) -> dict:
    base = dict(id="aff1", tenant=TENANT, phone=CANON_REFERRER, code="BLOGR",
               discount_percent=15, reward_type="fixed_points", reward_params={"points": 40},
               created_at=1000, active=True, unsettled_points=10, total_earned_points=50)
    base.update(over)
    await store.put(AFFILIATES, f"{base['tenant']}|{base['id']}", base)
    return base


async def _seed_settlement(store, *, affiliate_id="aff1", affiliate_phone=CANON_REFERRER) -> None:
    row = {"id": "s1", "tenant": TENANT, "affiliate_id": affiliate_id,
          "affiliate_phone": affiliate_phone, "points_settled": 40, "full": True, "note": "",
          "actor": "owner1", "created_at": 3000}
    await store.put(SETTLEMENTS, f"{TENANT}|s1", row)


def _eraser(store) -> OperationsErasure:
    return OperationsErasure(store=store, pii_salt=SALT, default_cc=CC)


# ── grants: both phone roles get found and blanked ───────────────────────────────────────────────
def test_erasure_by_the_referrers_own_phone_blanks_both_phone_fields_on_their_grant():
    store = MemoryDataStore()
    run(_seed_grant(store))
    out = run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    assert "referral_grants:1" in out["erased"]
    row = run(store.get(GRANTS, f"{TENANT}|g1"))
    assert row["referrer_phone"] == "" and row["beneficiary_phone"] == ""


def test_erasure_by_the_beneficiarys_own_phone_also_finds_and_blanks_the_same_grant():
    store = MemoryDataStore()
    run(_seed_grant(store))
    out = run(_eraser(store).erase(TENANT, BENEFICIARY_PHONE))
    assert "referral_grants:1" in out["erased"]
    row = run(store.get(GRANTS, f"{TENANT}|g1"))
    assert row["referrer_phone"] == "" and row["beneficiary_phone"] == ""


def test_erasure_never_double_counts_a_grant_matched_by_both_phone_fields():
    # A grant where (hypothetically, e.g. legacy data) referrer and beneficiary phone are the
    # same value must still be counted ONCE, not twice, in the erased tally.
    store = MemoryDataStore()
    run(_seed_grant(store, beneficiary_phone=CANON_REFERRER))
    out = run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    assert "referral_grants:1" in out["erased"]


def test_erasure_retains_the_reward_terms_and_amounts_on_the_grant():
    store = MemoryDataStore()
    run(_seed_grant(store))
    run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    row = run(store.get(GRANTS, f"{TENANT}|g1"))
    assert row["invoice_minor"] == 5000
    assert row["referrer_reward_params"] == {"points": 50}
    assert row["redeemed_at"] == 2000


def test_erasure_of_an_unrelated_phone_touches_no_grant_at_all():
    store = MemoryDataStore()
    run(_seed_grant(store))
    out = run(_eraser(store).erase(TENANT, "0599999999"))
    assert not any(e.startswith("referral_grants") for e in out["erased"])
    row = run(store.get(GRANTS, f"{TENANT}|g1"))
    assert row["referrer_phone"] == CANON_REFERRER   # untouched


def test_erasure_never_leaks_across_tenants_for_grants():
    store = MemoryDataStore()
    run(_seed_grant(store, tenant="other_tenant"))
    out = run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    assert not any(e.startswith("referral_grants") for e in out["erased"])
    row = run(store.get(GRANTS, "other_tenant|g1"))
    assert row["referrer_phone"] == CANON_REFERRER   # a different tenant's row, untouched


# ── affiliates + settlements ────────────────────────────────────────────────────────────────────
def test_erasure_blanks_an_affiliates_own_phone():
    store = MemoryDataStore()
    run(_seed_affiliate(store))
    out = run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    assert "affiliates:1" in out["erased"]
    row = run(store.get(AFFILIATES, f"{TENANT}|aff1"))
    assert row["phone"] == ""


def test_erasure_retains_an_affiliates_balance_and_code():
    store = MemoryDataStore()
    run(_seed_affiliate(store))
    run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    row = run(store.get(AFFILIATES, f"{TENANT}|aff1"))
    assert row["code"] == "BLOGR"
    assert row["unsettled_points"] == 10
    assert row["total_earned_points"] == 50


def test_erasure_cascades_from_an_affiliate_to_their_own_settlement_records():
    store = MemoryDataStore()
    run(_seed_affiliate(store))
    run(_seed_settlement(store))
    out = run(_eraser(store).erase(TENANT, REFERRER_PHONE))
    assert "affiliate_settlements:1" in out["erased"]
    row = run(store.get(SETTLEMENTS, f"{TENANT}|s1"))
    assert row["affiliate_phone"] == ""
    assert row["points_settled"] == 40    # the amount itself is retained


def test_erasure_of_an_unrelated_phone_touches_no_affiliate_or_settlement():
    store = MemoryDataStore()
    run(_seed_affiliate(store))
    run(_seed_settlement(store))
    out = run(_eraser(store).erase(TENANT, "0599999999"))
    assert not any(e.startswith("affiliate") for e in out["erased"])


# ── an empty/pseudonym subject never scans these collections at all ────────────────────────────
def test_erasure_by_pseudonym_alone_cannot_reach_a_grant_or_affiliate():
    # A genuine, documented data-model limit (see erasure.py's own module docstring): these rows
    # store a raw phone, never a subject_ref, so a caller holding only the pseudonym cannot be
    # matched against them — this test proves that limit is what actually happens, not a crash.
    store = MemoryDataStore()
    run(_seed_grant(store))
    run(_seed_affiliate(store))
    ref = subject_ref(SALT, TENANT, REFERRER_PHONE)
    out = run(_eraser(store).erase(TENANT, ref))
    assert not any(e.startswith("referral_grants") or e.startswith("affiliate")
                  for e in out["erased"])
    # untouched
    grant = run(store.get(GRANTS, f"{TENANT}|g1"))
    assert grant["referrer_phone"] == CANON_REFERRER


def test_erasure_by_an_unresolvable_phone_string_touches_nothing_not_a_crash():
    store = MemoryDataStore()
    run(_seed_grant(store))
    out = run(_eraser(store).erase(TENANT, "not-a-phone-at-all"))
    assert not any(e.startswith("referral_grants") for e in out["erased"])
