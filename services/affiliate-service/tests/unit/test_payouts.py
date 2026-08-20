"""The withdrawal itself (spec §5) — the properties worth a test:

  * a request locks SPECIFIC commissions, so two requests can never claim the same money
  * a rejected request releases exactly what it locked, never more, never less
  * completing without a receipt is refused — the receipt IS the compliance proof
  * a bank IBAN and an intermediary platform are the same mechanism, not two flows
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.models import (
    ACTIVE, AFFILIATES, COMMISSIONS, COMPLETED, CONFIRMED, CONVERSION, PENDING, REQUESTED,
    WITHDRAWAL_REJECTED, Affiliate, Commission,
)
from app.core.payouts import PayoutError, PayoutService

AFF = "aff-1"


async def _seed_affiliate(store) -> None:
    row = Affiliate(id=AFF, person_id="p1", phone="+966501234567", name="مسوّق",
                    role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, AFF, row.to_dict())


async def _seed_commission(store, *, id: str, amount: int, status: str = CONFIRMED) -> None:
    c = Commission(id=id, tenant=f"t-{id}", affiliate_id=AFF, kind=CONVERSION,
                   amount_halalas=amount, status=status)
    await store.put(COMMISSIONS, id, c.to_dict())


def build(min_withdrawal=0) -> tuple[PayoutService, MemoryDataStore]:
    store = MemoryDataStore()
    return PayoutService(store=store, min_withdrawal_halalas=min_withdrawal), store


# ── payout method ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_setting_a_bank_iban_method():
    svc, store = build()
    await _seed_affiliate(store)
    out = await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA0000000000000000000000")
    assert out["channel"] == "bank_iban"
    assert out["channel_name"] == ""


@pytest.mark.anyio
async def test_setting_an_intermediary_method_needs_a_platform_name():
    svc, store = build()
    await _seed_affiliate(store)
    with pytest.raises(PayoutError) as exc:
        await svc.set_payout_method(AFF, channel="intermediary", account_ref="0501234567")
    assert exc.value.reason == "missing_channel_name"


@pytest.mark.anyio
async def test_an_intermediary_method_with_a_name_works():
    svc, store = build()
    await _seed_affiliate(store)
    out = await svc.set_payout_method(
        AFF, channel="intermediary", channel_name="بحر", account_ref="0501234567")
    assert out == {"channel": "intermediary", "channel_name": "بحر", "account_ref": "0501234567"}


@pytest.mark.anyio
async def test_an_unknown_channel_is_refused():
    svc, store = build()
    await _seed_affiliate(store)
    with pytest.raises(PayoutError) as exc:
        await svc.set_payout_method(AFF, channel="crypto", account_ref="x")
    assert exc.value.reason == "bad_channel"


# ── requesting a withdrawal ──────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_cannot_request_with_no_payout_method_set():
    svc, store = build()
    await _seed_affiliate(store)
    await _seed_commission(store, id="c1", amount=4000)
    with pytest.raises(PayoutError) as exc:
        await svc.request_withdrawal(AFF)
    assert exc.value.reason == "no_payout_method"


@pytest.mark.anyio
async def test_a_request_locks_every_available_confirmed_commission():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    await _seed_commission(store, id="c2", amount=5000)
    await _seed_commission(store, id="c3", amount=1000, status=PENDING)   # not confirmed yet

    out = await svc.request_withdrawal(AFF)
    assert out["amount_halalas"] == 9000
    assert set(out["commission_ids"]) == {"c1", "c2"}

    c1 = Commission.from_dict(await store.get(COMMISSIONS, "c1"))
    assert c1.withdrawal_id == out["id"]


@pytest.mark.anyio
async def test_a_second_request_cannot_claim_already_locked_commissions():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    await svc.request_withdrawal(AFF)

    with pytest.raises(PayoutError) as exc:
        await svc.request_withdrawal(AFF)
    assert exc.value.reason == "already_pending"


@pytest.mark.anyio
async def test_below_the_minimum_is_refused():
    svc, store = build(min_withdrawal=10000)
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    with pytest.raises(PayoutError) as exc:
        await svc.request_withdrawal(AFF)
    assert exc.value.reason == "below_minimum"


@pytest.mark.anyio
async def test_the_request_locks_the_current_payout_method_not_a_future_one():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)

    # He changes his method AFTER requesting — must not rewrite the already-made request.
    await svc.set_payout_method(AFF, channel="intermediary", channel_name="بحر",
                                account_ref="0501234567")
    rows = await svc.of_affiliate(AFF)
    assert rows[0].payout_channel == "bank_iban"
    assert rows[0].payout_account_ref == "SA00"


# ── admin: complete / reject ─────────────────────────────────────────────────────────────────
@pytest.mark.anyio
async def test_completing_without_a_receipt_is_refused():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)
    with pytest.raises(PayoutError) as exc:
        await svc.complete(out["id"], decided_by="admin1", receipt_reference="")
    assert exc.value.reason == "receipt_required"


@pytest.mark.anyio
async def test_completing_with_a_receipt_succeeds_and_is_idempotent():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)

    first = await svc.complete(out["id"], decided_by="admin1", receipt_reference="receipt-1")
    second = await svc.complete(out["id"], decided_by="admin2", receipt_reference="receipt-2")
    assert first["already_completed"] is False
    assert second["already_completed"] is True

    rows = await svc.of_affiliate(AFF)
    assert rows[0].status == COMPLETED
    assert rows[0].receipt_reference == "receipt-1"   # the SECOND call never overwrote it


@pytest.mark.anyio
async def test_rejecting_releases_the_locked_commissions_back_to_available():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)

    await svc.reject(out["id"], decided_by="admin1", reason="آيبان غير صحيح")

    c1 = Commission.from_dict(await store.get(COMMISSIONS, "c1"))
    assert c1.withdrawal_id == ""
    assert c1.status == CONFIRMED   # untouched — still earned, just not claimed by anything now

    balance = await svc.balance(AFF)
    assert balance["confirmed_available_halalas"] == 4000


@pytest.mark.anyio
async def test_rejecting_lets_a_new_request_be_made_afterward():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    first = await svc.request_withdrawal(AFF)
    await svc.reject(first["id"], decided_by="admin1")

    second = await svc.request_withdrawal(AFF)   # must not raise "already_pending"
    assert second["commission_ids"] == ["c1"]


@pytest.mark.anyio
async def test_rejecting_twice_is_idempotent():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)
    first = await svc.reject(out["id"], decided_by="admin1")
    second = await svc.reject(out["id"], decided_by="admin1")
    assert first["already_rejected"] is False
    assert second["already_rejected"] is True


@pytest.mark.anyio
async def test_cannot_complete_an_already_rejected_request():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)
    await svc.reject(out["id"], decided_by="admin1")
    with pytest.raises(PayoutError) as exc:
        await svc.complete(out["id"], decided_by="admin1", receipt_reference="r")
    assert exc.value.reason == "already_rejected"


@pytest.mark.anyio
async def test_cannot_reject_an_already_completed_request():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)
    await svc.complete(out["id"], decided_by="admin1", receipt_reference="r")
    with pytest.raises(PayoutError) as exc:
        await svc.reject(out["id"], decided_by="admin1")
    assert exc.value.reason == "already_completed"


@pytest.mark.anyio
async def test_balance_splits_pending_confirmed_and_withdrawn():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c-pending", amount=1000, status=PENDING)
    await _seed_commission(store, id="c-confirmed", amount=2000, status=CONFIRMED)
    await _seed_commission(store, id="c-withdrawn", amount=3000, status=CONFIRMED)
    row = await store.get(COMMISSIONS, "c-withdrawn")
    row["withdrawal_id"] = "some-past-request"
    await store.put(COMMISSIONS, "c-withdrawn", row)

    balance = await svc.balance(AFF)
    assert balance == {"pending_halalas": 1000, "confirmed_available_halalas": 2000,
                       "withdrawn_halalas": 3000}


# ── receipt upload marker (core/payouts.py::save_receipt_upload) ────────────────────────────────
from app.core.payouts import is_uploaded_receipt, receipt_key, receipt_object_key


def test_receipt_key_is_deterministic_per_withdrawal():
    assert receipt_key("wd-1") == "withdrawals/wd-1/receipt"
    assert receipt_key("wd-1") == receipt_key("wd-1")


def test_is_uploaded_receipt_distinguishes_object_from_url():
    assert is_uploaded_receipt("object:withdrawals/wd-1/receipt") is True
    assert is_uploaded_receipt("https://example.com/r.pdf") is False


def test_receipt_object_key_strips_the_marker():
    assert receipt_object_key("object:withdrawals/wd-1/receipt") == "withdrawals/wd-1/receipt"


@pytest.mark.anyio
async def test_save_receipt_upload_sets_the_reference_and_content_type():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)

    updated = await svc.save_receipt_upload(out["id"], content_type="image/png")
    assert updated.receipt_reference == f"object:{receipt_key(out['id'])}"
    assert updated.receipt_content_type == "image/png"


@pytest.mark.anyio
async def test_save_receipt_upload_refuses_for_an_unknown_withdrawal():
    svc, _store = build()
    with pytest.raises(PayoutError) as exc:
        await svc.save_receipt_upload("no-such-id", content_type="image/png")
    assert exc.value.reason == "not_found"


@pytest.mark.anyio
async def test_save_receipt_upload_refuses_once_the_request_is_no_longer_pending():
    svc, store = build()
    await _seed_affiliate(store)
    await svc.set_payout_method(AFF, channel="bank_iban", account_ref="SA00")
    await _seed_commission(store, id="c1", amount=4000)
    out = await svc.request_withdrawal(AFF)
    await svc.complete(out["id"], decided_by="admin1", receipt_reference="https://x")

    with pytest.raises(PayoutError) as exc:
        await svc.save_receipt_upload(out["id"], content_type="image/png")
    assert exc.value.reason == "not_pending"


@pytest.mark.anyio
async def test_get_returns_none_for_an_unknown_withdrawal():
    svc, _store = build()
    assert await svc.get("no-such-id") is None
