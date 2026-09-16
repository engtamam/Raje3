"""What the counter needs from `loyalty`, on behalf of a till that holds no loyalty capability.

WHY OPERATIONS ASKS AND NOT THE TILL. A point-of-sale integration is written once, by a vendor,
against whatever we published that quarter — and every extra hop is a hop they get wrong: they
must resolve a pseudonym, then call a second host, then reconcile two error shapes. So the till
asks us one question with a phone number in it and gets one answer back. The fan-out is ours.

AND THE CREDENTIAL STAYS SMALL. A till's token carries `operations.record` and nothing else, on
purpose (see api/v1/till.py). Widening it to read the points ledger directly would hand a third
party a capability over a customer's balance for the sake of saving us a function; this file is
that function.

A FAILURE IS ANSWERED, NEVER GUESSED. An unreachable peer returns None and the caller says so —
«تعذّرت قراءة النقاط» — because a cashier told "0 points" for a customer with 300 gives away a
grievance, and one told "he has a reward" when we could not check gives away a service.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any

from starlette.concurrency import run_in_threadpool
from app.adapters import internal_http


class LoyaltyDesk:
    """The two calls the counter makes: what does he hold, and hand it over."""

    def __init__(self, *, base_url: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        # FIVE SECONDS, and it is the whole budget: a customer is standing at the till while this
        # runs (§1.1). Past that the right answer is "we could not check", not a longer wait.
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _call(self, path: str, *, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            # Content-Type travels on the GET too, exactly as it did when this request was built
            # here: harmless, and dropping it would be a change to what goes on the wire.
            status, raw = internal_http.send(
                self._base + path, timeout=self._timeout,
                body=json.dumps(body).encode() if body is not None else None,
                method="POST" if body is not None else "GET",
                content_type=internal_http.JSON, token=self._token)
            if not 200 <= status < 300:
                return None
            return json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            # THE REFUSAL IS THE ANSWER, and it has to survive the trip. A redemption declined for
            # insufficient points (409) is a sentence the cashier must read to the customer; a
            # dead peer is not. Collapsing both to None would make the two indistinguishable.
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            return {"_status": exc.code,
                    "_reason": payload.get("detail") or payload.get("reason") or ""}
        except Exception:                                                       # noqa: BLE001
            return None

    async def balance(self, *, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        """His points, what he can afford now, and how far the next reward is.

        THE SAME CALL THE CUSTOMER'S OWN PAGE MAKES. Two balance calculations would disagree the
        first time a rule changed, and the disagreement would be between what he reads at home and
        what he is told at the counter — which is the one place he can argue about it.
        """
        if not self.configured:
            return None
        q = f"?tenant={urllib.parse.quote(tenant)}&subject_ref={urllib.parse.quote(subject_ref)}"
        # OFF THE EVENT LOOP (ك-9). `_call` blocks on `urlopen` for up to `self._timeout` seconds,
        # and this runs while a customer stands at the till. An unthreaded call here freezes the
        # whole worker — other shops' counters and the field screen stall on ONE slow loyalty read,
        # not just this one customer's balance.
        out = await run_in_threadpool(self._call, "/internal/loyalty/portal/balance" + q)
        return None if out is None or "_status" in out else out

    async def redeem(self, *, tenant: str, subject_ref: str, reward_id: str,
                     idempotency_key: str, actor: str = "", approved_by: str = "",
                     branch_id: str = "") -> dict[str, Any] | None:
        """Hand the reward over, and answer with what the receipt must carry.

        THE TILL'S OWN KEY, PASSED THROUGH UNTOUCHED. Only their system knows whether two calls are
        the same sale; a key minted here would be new on every retry, which is the doubling this
        exists to prevent — and a doubled redemption is a customer's points spent twice.
        """
        if not self.configured:
            return None
        # OFF THE EVENT LOOP, same reason as `balance` above.
        return await run_in_threadpool(self._call, "/internal/loyalty/redeem", body={
            "tenant": tenant, "subject_ref": subject_ref, "reward_id": reward_id,
            "idempotency_key": idempotency_key, "actor": actor, "branch_id": branch_id,
            # PASSED THROUGH, NEVER INVENTED HERE. It names the person who took responsibility;
            # a default supplied by a middle layer would be a signature nobody wrote.
            "approved_by": approved_by})

    async def rating_bonus(self, *, tenant: str, subject_ref: str, visit_id: str, points: int,
                           actor: str = "", branch_id: str = "") -> dict[str, Any] | None:
        """Credit the rating app's own incentive for one just-submitted rating.

        BEST-EFFORT, LIKE THE REST OF THIS FILE'S WRITES TO A PEER. `None` on an unreachable
        loyalty (see `_call`) is handed back to the caller, which does not undo the rating it just
        wrote — the rating happened and is real regardless of whether the credit landed; nothing
        in this product retries a lost credit today, the same accepted gap `RatingConsumer`'s own
        docstring already names for a missed reply.
        """
        if not self.configured or points <= 0:
            return None
        return await run_in_threadpool(self._call, "/internal/loyalty/rating-bonus", body={
            "tenant": tenant, "subject_ref": subject_ref, "visit_id": visit_id, "points": points,
            "actor": actor, "branch_id": branch_id})


def build_loyalty_desk(settings) -> LoyaltyDesk:
    return LoyaltyDesk(base_url=settings.LOYALTY_SERVICE_URL,
                       token=settings.INTERNAL_SERVICE_TOKEN)
