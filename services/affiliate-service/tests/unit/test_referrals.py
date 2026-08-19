"""Which establishment which affiliate brought — first wins, permanent, and the commission is
locked at the moment of the stamp, not re-read from config afterward."""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import ACTIVE, AFFILIATES, Affiliate
from app.core.models import LAPSED, REFERRED
from app.core.referrals import ReferralError, ReferralRegistry


async def _seed_affiliate(store, affiliate_id="aff-1", status=ACTIVE) -> None:
    row = Affiliate(id=affiliate_id, person_id="p1", phone="+966501234567", name="مسوّق",
                    role="affiliate_manager", status=status)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())


def build(amount=4000, window_days=90) -> tuple[ReferralRegistry, MemoryDataStore]:
    store = MemoryDataStore()
    return ReferralRegistry(store=store, commission_amount_halalas=amount,
                            conversion_window_days=window_days), store


@pytest.mark.anyio
async def test_stamping_locks_the_commission_amount_at_that_moment():
    reg, store = build(amount=4000)
    await _seed_affiliate(store)
    out = await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_name="بنشر النور")
    assert out["commission_amount_halalas"] == 4000
    assert out["affiliate_id"] == "aff-1"


@pytest.mark.anyio
async def test_a_second_stamp_on_the_same_tenant_never_overwrites_the_first():
    reg, store = build()
    await _seed_affiliate(store, affiliate_id="aff-1")
    await _seed_affiliate(store, affiliate_id="aff-2")
    first = await reg.stamp(tenant="t-1", affiliate_id="aff-1")
    second = await reg.stamp(tenant="t-1", affiliate_id="aff-2")
    assert second["affiliate_id"] == "aff-1" == first["affiliate_id"]


@pytest.mark.anyio
async def test_an_unknown_affiliate_id_is_refused_not_silently_dropped():
    reg, _store = build()
    with pytest.raises(ReferralError):
        await reg.stamp(tenant="t-1", affiliate_id="does-not-exist")


@pytest.mark.anyio
async def test_an_inactive_affiliate_cannot_earn_a_new_referral():
    reg, store = build()
    await _seed_affiliate(store, affiliate_id="aff-1", status="suspended")
    with pytest.raises(ReferralError):
        await reg.stamp(tenant="t-1", affiliate_id="aff-1")


@pytest.mark.anyio
async def test_a_late_config_change_does_not_reprice_an_already_stamped_referral():
    reg, store = build(amount=4000)
    await _seed_affiliate(store)
    await reg.stamp(tenant="t-1", affiliate_id="aff-1")

    reg2 = ReferralRegistry(store=store, commission_amount_halalas=5000)
    unchanged = await reg2.stamp(tenant="t-1", affiliate_id="aff-1")
    assert unchanged["commission_amount_halalas"] == 4000


@pytest.mark.anyio
async def test_expires_at_is_locked_at_the_configured_window_from_the_stamp():
    reg, store = build(window_days=90)
    await _seed_affiliate(store)
    out = await reg.stamp(tenant="t-1", affiliate_id="aff-1")
    assert out["expires_at"] - out["stamped_at"] == 90 * 24 * 60 * 60


@pytest.mark.anyio
async def test_a_conversion_inside_the_window_stays_referred_and_payable():
    reg, store = build(window_days=90)
    await _seed_affiliate(store)
    stamped = await reg.stamp(tenant="t-1", affiliate_id="aff-1")
    checked = await reg.lapse_if_expired("t-1", now=stamped["stamped_at"] + 30 * 24 * 60 * 60)
    assert checked.status == REFERRED


@pytest.mark.anyio
async def test_a_conversion_after_the_window_lapses_but_the_record_survives():
    """spec/Tamam, 2026-08-19: a shop that registered through an affiliate and converts two
    years later must not be an open-ended, undocumented claim — the referral itself (who brought
    whom, when) stays true forever; only the money stops being possible."""
    reg, store = build(window_days=90)
    await _seed_affiliate(store)
    stamped = await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_name="بنشر النور")
    late = stamped["stamped_at"] + 400 * 24 * 60 * 60   # well over a year later
    checked = await reg.lapse_if_expired("t-1", now=late)

    assert checked.status == LAPSED
    # THE RECORD SURVIVES — who, when, for how much it would have been. Nothing here is erased;
    # only the status changed, exactly the platform's own "retain, don't delete" principle.
    still_there = await reg.of_tenant("t-1")
    assert still_there.affiliate_id == "aff-1"
    assert still_there.shop_name == "بنشر النور"
    assert still_there.status == LAPSED


@pytest.mark.anyio
async def test_lapsing_is_idempotent_a_second_check_does_not_re_decide_anything():
    reg, store = build(window_days=90)
    await _seed_affiliate(store)
    stamped = await reg.stamp(tenant="t-1", affiliate_id="aff-1")
    late = stamped["stamped_at"] + 400 * 24 * 60 * 60
    first = await reg.lapse_if_expired("t-1", now=late)
    second = await reg.lapse_if_expired("t-1", now=late + 1000)
    assert first.status == second.status == LAPSED


@pytest.mark.anyio
async def test_lapsing_an_unknown_tenant_is_a_harmless_none():
    reg, _store = build()
    assert await reg.lapse_if_expired("no-such-tenant") is None


@pytest.mark.anyio
async def test_of_affiliate_lists_every_establishment_that_affiliate_brought():
    reg, store = build()
    await _seed_affiliate(store, affiliate_id="aff-1")
    await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_name="أ")
    await reg.stamp(tenant="t-2", affiliate_id="aff-1", shop_name="ب")
    rows = await reg.of_affiliate("aff-1")
    assert {r.tenant for r in rows} == {"t-1", "t-2"}


# ── self-referral (spec §2) ───────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_an_affiliate_cannot_refer_his_own_establishment():
    reg, store = build()
    row = Affiliate(id="aff-1", person_id="p1", phone="+966501234567", name="مسوّق", role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, "aff-1", row.to_dict())
    with pytest.raises(ReferralError):
        await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_owner_phone="0501234567")


@pytest.mark.anyio
async def test_the_same_number_written_differently_is_still_caught():
    reg, store = build()
    row = Affiliate(id="aff-1", person_id="p1", phone="0501234567", name="مسوّق", role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, "aff-1", row.to_dict())
    with pytest.raises(ReferralError):
        await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_owner_phone="+966501234567")


@pytest.mark.anyio
async def test_a_different_owner_is_a_real_referral_not_blocked():
    reg, store = build()
    await _seed_affiliate(store)
    out = await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_owner_phone="0509999999")
    assert out["affiliate_id"] == "aff-1"


@pytest.mark.anyio
async def test_an_empty_owner_phone_does_not_block_a_legitimate_referral():
    """An old caller that predates this field (or a stamp made before operations was updated to
    send it) must not have every referral refused over data that simply is not there yet."""
    reg, store = build()
    await _seed_affiliate(store)
    out = await reg.stamp(tenant="t-1", affiliate_id="aff-1", shop_owner_phone="")
    assert out["affiliate_id"] == "aff-1"
