"""Peer client for platform's wallet-service — the real operational stop condition, using the
same authorization-HOLD pattern payment gateways and metered-subscription systems use for any
action that costs money before its exact cost is known: reserve an estimated ceiling BEFORE the
costed action runs, confirm the hold (or release it) once the action's outcome is known. Never a
bare "read the balance, then spend" — that has a check-then-act race between two concurrent turns
for the same tenant, and wallet-service's own `/internal/wallet/reserve` is already atomic
(compare-and-set against the held balance), closing exactly that race server-side.

NOT AN ESCALATION. Escalation (core/conversation.py::_escalate_to_human) hands a customer to a
human because the CONVERSATION needs one. A depleted wallet is a BILLING fact about the shop, true
for every customer of that shop simultaneously — the AI does not decide to stop because this one
conversation went badly, it is simply unable to run another turn until the shop tops up.

THE HARD RULE: THE BALANCE MUST NEVER GO NEGATIVE, UNDER ANY CIRCUMSTANCE — no race, no cost
misestimate. Two things make that true here:

  1. `reserve()` asks wallet-service to hold an ESTIMATED CEILING (a generous per-turn token
     estimate at the configured rate, plus WALLET_SAFETY_MARGIN_HALALAS on top if that is ever
     set above its own default of 0 — see config.py's own note on why 0 is the right value, not a
     placeholder) before the LLM is ever called. wallet-service refuses the reserve outright (402
     INSUFFICIENT_FUNDS) if the post-hold balance would not cover it — the check IS the hold,
     atomically, so no other concurrent turn can spend the same halala twice.
  2. `confirm()` charges the REAL, usually-smaller token cost once it is known — wallet-service
     v0.19.2's own `confirm(hold_id, final_net=...)` (its own core/wallet_service.py::confirm),
     requested and shipped for exactly this use case. `final_net` is ALWAYS clamped to the
     reserved amount by the caller (core/conversation.py's own compose_reply) before this call —
     wallet-service refuses (mutating nothing) a `final_net` above what was reserved, since a hold
     exists precisely to bound what a confirm may ever spend; the clamp is what guarantees this
     call can never itself trigger that refusal. `final_net=None` (the default) still confirms the
     full reserved amount — the ORIGINAL, pre-v0.19.2 behaviour, kept for any caller that has not
     computed a real cost of its own (there is none today, but the port stays honest either way).

FAILS CLOSED, UNLIKE EVERY OTHER OPTIONAL PEER THIS SERVICE CALLS. customer_lookup.py, points.py,
service_catalog.py all fail OPEN on a peer outage because an unreachable read degrades to "less
personalised", never to money. A reserve is a MONEY-SAFETY operation: an uncertain outcome (peer
unreachable, malformed response, unexpected exception) is treated as "reservation not obtained",
which stops the AI exactly as a genuine 402 would — the one case this module refuses to guess.
"""
from __future__ import annotations

import asyncio
import json
import math
import urllib.error
import urllib.request
import uuid
from typing import Any

from app.core.ai_unit_pricing import TOKENS_PER_PRICING_UNIT


class NullWalletBalance:
    """No wallet-service configured (dev/test default, or a deployment that has not wired billing
    yet). Never blocks replies — the same "zero-infra default that still works" posture as every
    other optional peer in this service. `reserve` still returns a hold id so callers do not need
    a special-case branch for "no wallet configured" vs. "reserved for free"."""
    driver = "null"

    async def reserve(self, *, tenant: str, amount_halalas: int, source: str) -> str | None:
        return f"null_hold_{source}"

    async def confirm(self, hold_id: str, *, final_net: int | None = None) -> None:
        return None

    async def release(self, hold_id: str) -> None:
        return None


class HttpWalletBalance:
    driver = "http"

    def __init__(self, *, url: str, reserve_path: str, confirm_path: str, release_path: str,
                token: str, timeout: int = 8, reserve_funds: tuple[str, ...] = ()) -> None:
        self._url = url.rstrip("/")
        self._reserve_path = reserve_path
        self._confirm_path = confirm_path
        self._release_path = release_path
        self._token = token
        self._timeout = timeout
        # SCOPED TO A NAMED FUND (wallet-service v0.18.42's own fund-scoping) — the AI-usage
        # credit is a fund this bot's own hold must never wander past, into a shop's commission
        # balance or its subscription-renewal top-up. Empty means the historical all-funds
        # behaviour (a deployment that has not declared a dedicated fund yet).
        self._reserve_funds = tuple(reserve_funds)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        req = urllib.request.Request(
            f"{self._url}{path}", data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                if not 200 <= resp.status < 300:
                    return None      # fails CLOSED — see module docstring
                return json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError):
            return None              # fails CLOSED — see module docstring

    async def reserve(self, *, tenant: str, amount_halalas: int, source: str) -> str | None:
        body: dict[str, Any] = {
            "tenant": tenant, "net": max(0, int(amount_halalas)), "source": source,
            "reason": "whatsapp_assistant.llm_turn"}
        if self._reserve_funds:
            body["funds"] = list(self._reserve_funds)
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        result = await asyncio.to_thread(self._post, self._reserve_path, body)
        if result is None:
            return None
        hold_id = result.get("hold_id")
        return str(hold_id) if hold_id else None

    async def confirm(self, hold_id: str, *, final_net: int | None = None) -> None:
        # Idempotent on wallet-service's own side (confirming an already-confirmed hold is a
        # no-op there, and a RETRY WITH A DIFFERENT final_net still replays the FIRST confirm's
        # result — keyed on hold_id, never on the amount) — a retry after a timeout on OUR side is
        # therefore safe to just re-call, unconditionally, with whatever final_net we have now.
        body: dict[str, Any] = {"hold_id": hold_id}
        if final_net is not None:
            body["final_net"] = max(0, int(final_net))
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        await asyncio.to_thread(self._post, self._confirm_path, body)

    async def release(self, hold_id: str) -> None:
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        await asyncio.to_thread(self._post, self._release_path, {"hold_id": hold_id})


def estimated_hold_halalas(*, estimated_tokens: int, halalas_per_1k_tokens: float,
                           safety_margin_halalas: int) -> int:
    """The reserve ceiling for ONE turn: a generous token estimate priced at the configured
    usage rate — today the ACTUAL per-model rate (core/ai_unit_pricing.py::model_rate_halalas_per_1k,
    the worse of its input/output halves — see core/conversation.py's own `_reserve_llm_hold`),
    never a flat one when a real per-model registry is wired — plus a fixed safety margin on top so
    a misestimate or a mid-flight price wobble can never itself be the thing that pushes a confirm
    past the true available balance. `halalas_per_1k_tokens` is a float (a real per-model rate is
    rarely a whole halala) — `math.ceil` still rounds the token component UP, never down, so the
    margin exists to absorb variance rather than be eaten by rounding working against it."""
    token_cost = math.ceil(
        (max(0, estimated_tokens) / TOKENS_PER_PRICING_UNIT) * max(0.0, halalas_per_1k_tokens))
    return token_cost + max(0, safety_margin_halalas)


def new_reserve_source(conversation_ref: str) -> str:
    """A unique idempotency key per reserve ATTEMPT — wallet-service replays an identical `source`
    into the SAME hold rather than a second one (core/wallet_service.py::reserve's own
    `_replay`), so this must differ per attempt, not be constant per conversation."""
    return f"whatsapp_assistant:{conversation_ref}:{uuid.uuid4().hex[:16]}"


def build(settings: Any) -> Any:
    if not settings.WALLET_SERVICE_URL:
        return NullWalletBalance()
    reserve_funds = tuple(
        f.strip() for f in (settings.WALLET_RESERVE_FUNDS or "").split(",") if f.strip())
    return HttpWalletBalance(
        url=settings.WALLET_SERVICE_URL, reserve_path=settings.WALLET_SERVICE_RESERVE_PATH,
        confirm_path=settings.WALLET_SERVICE_CONFIRM_PATH,
        release_path=settings.WALLET_SERVICE_RELEASE_PATH, token=settings.INTERNAL_SERVICE_TOKEN,
        timeout=settings.PEER_TIMEOUT_SECONDS, reserve_funds=reserve_funds)
