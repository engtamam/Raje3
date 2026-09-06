"""The wallet top-up reconcile sweep — see app/core/wallet_topup_reconcile.py's own header for
why it exists (TuwaiqPay has no signed webhook, so this poll is the only path that credits the
wallet after a hosted-checkout top-up)."""
from __future__ import annotations

import asyncio

from app.core.wallet_topup_reconcile import HttpWalletTopups, WalletTopupReconciler


def run(c):
    return asyncio.run(c)


class FakeTopups:
    """Never touches the network — a fake standing in for `HttpWalletTopups`."""

    def __init__(self, rows: list[dict] | None, *, fails: set[str] = frozenset()):
        self._rows = rows
        self._fails = fails
        self.reconciled_ids: list[str] = []

    async def pending(self):
        return self._rows

    async def reconcile(self, payment_id: str) -> bool:
        self.reconciled_ids.append(payment_id)
        return payment_id not in self._fails


def test_an_unreachable_billing_service_scans_nothing_and_is_told_apart_from_an_empty_list():
    """`None` (could not ask) must never be confused with `[]` (asked, and there were none) — the
    sweep would otherwise look identical whether billing-service is down or genuinely caught up."""
    topups = FakeTopups(None)
    out = run(WalletTopupReconciler(topups=topups).run())
    assert out.unreachable is True
    assert out.scanned == 0
    assert topups.reconciled_ids == []


def test_an_empty_pending_list_is_the_ordinary_quiet_case():
    topups = FakeTopups([])
    out = run(WalletTopupReconciler(topups=topups).run())
    assert out.unreachable is False
    assert out.scanned == 0
    assert out.reconciled == 0


def test_every_pending_payment_is_reconciled_and_counted():
    topups = FakeTopups([{"payment_id": "pay_1"}, {"payment_id": "pay_2"}])
    out = run(WalletTopupReconciler(topups=topups).run())
    assert out.scanned == 2
    assert out.reconciled == 2
    assert out.failed == 0
    assert topups.reconciled_ids == ["pay_1", "pay_2"]


def test_one_failed_reconcile_does_not_stop_the_sweep_from_trying_the_rest():
    topups = FakeTopups([{"payment_id": "pay_1"}, {"payment_id": "pay_2"}, {"payment_id": "pay_3"}],
                        fails={"pay_2"})
    out = run(WalletTopupReconciler(topups=topups).run())
    assert out.scanned == 3
    assert out.reconciled == 2
    assert out.failed == 1
    # ALL THREE WERE ATTEMPTED — the middle one failing did not stop pay_3 from being tried.
    assert topups.reconciled_ids == ["pay_1", "pay_2", "pay_3"]


def test_a_row_with_no_payment_id_is_skipped_rather_than_reconciled_blindly():
    topups = FakeTopups([{"payment_id": ""}, {"tenant": "t1"}, {"payment_id": "pay_1"}])
    out = run(WalletTopupReconciler(topups=topups).run())
    assert out.scanned == 3
    assert out.reconciled == 1
    assert topups.reconciled_ids == ["pay_1"]


# ── HttpWalletTopups: no credential, no poll — same fail-closed gate settlements.py's own
#    SettlementsSource.configured uses, since both routes are platform.billing (ADMIN tier). ──────
def real_topups(**overrides):
    args = dict(billing_url="http://billing-service:8000", identity_url="http://identity-service:8000",
               client_id="", client_secret="", pending_path="/api/v1/billing/admin/wallet-topups/pending",
               reconcile_path="/api/v1/billing/payments/{payment_id}/reconcile")
    args.update(overrides)
    return HttpWalletTopups(**args)


def test_with_no_client_credential_configured_is_false():
    assert real_topups().configured is False
    assert real_topups(client_id="cid").configured is False           # secret alone is not enough
    assert real_topups(client_secret="sec").configured is False        # nor id alone
    assert real_topups(client_id="cid", client_secret="sec").configured is True


def test_with_no_client_credential_pending_answers_unreachable_rather_than_calling_out():
    """No credential means nothing to poll WITH — the sweep must not attempt a mint that can only
    fail, since `configured` already knows the answer without a network call."""
    out = run(real_topups().pending())
    assert out is None
