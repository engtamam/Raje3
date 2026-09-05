"""GeminiLlm — Gemini function calling, with a hard tool allowlist enforced on the way IN and OUT.

TWO ENFORCEMENTS OF THE SAME ALLOWLIST, deliberately redundant:

  1. Only the allowlisted tool SCHEMAS are ever declared to Gemini's `tools` parameter — a function
     never declared cannot be the one Gemini calls, by construction of the request.
  2. The RESPONSE is checked again before it leaves this adapter. A model that hallucinates a call
     to something never declared (it happens) is rejected here rather than trusted because "we
     never told it about that tool" — a defence-in-depth habit, not a belief that step 1 is
     insufficient.

`confirm_booking` IS NEVER IN THE SCHEMA, ANYWHERE, PERIOD. Confirmation only ever happens from a
button_reply id match in core/conversation.py — never from anything this adapter returns. That is
not a prompt instruction; it is the simple fact that the function does not exist for the model to
call.

stdlib urllib against the REST endpoint (generateLanguageContent / generateContent v1beta), no SDK
dependency — consistent with the rest of this platform's internal HTTP clients.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from app.ports.llm import LlmReply, ToolCall

# The JSON-schema shape for each allowlisted tool. Declared here, not read from anywhere state-
# changing could reach — this file has no access to a datastore or a booking provider; it can only
# ever PROPOSE, and core/tools.py is what validates and executes.
_TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "check_availability": {
        "name": "check_availability",
        "description": (
            "Check open appointment slots on or after a given date, for a single service OR a "
            "package (never both) — package_id must be an id shown under the context block's "
            "own 'باقات حقيقية قد تناسب العميل' section, never invented."),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "package_id": {"type": "string"},
                "earliest_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
        },
    },
    "propose_booking": {
        "name": "propose_booking",
        "description": (
            "Propose (never confirm) one specific appointment slot to the customer, for a single "
            "service OR a package (never both — package_id only from the context block's own "
            "package list, never invented, and never a date it did not name). If the customer "
            "wants to use one of their own real rewards (shown in the context block, never "
            "invented) WITH this booking, pass its id as reward_id — it is only ever spent when "
            "the shop marks them attended, never on confirm alone, so nothing is risked if they "
            "do not show up."),
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "package_id": {"type": "string"},
                "starts_at_iso": {"type": "string"},
                "reward_id": {"type": "string", "description": (
                    "Optional. Only an id the context block actually showed for this customer.")},
            },
            "required": ["starts_at_iso"],
        },
    },
    "get_customer_points_summary": {
        "name": "get_customer_points_summary",
        "description": "Get a PATTERN summary of the customer's loyalty points — never raw PII.",
        "parameters": {"type": "object", "properties": {}},
    },
    "suggest_redeemable_offer": {
        "name": "suggest_redeemable_offer",
        "description": (
            "Read-only: name a reward the customer's current points balance can already afford. "
            "Never redeems anything by itself — mention it, then use propose_booking's reward_id "
            "if the customer wants it attached to an appointment."),
        "parameters": {"type": "object", "properties": {}},
    },
    "suggest_related_service": {
        "name": "suggest_related_service",
        "description": (
            "Suggest a service genuinely often booked together with one the customer is already "
            "discussing or booking — a helpful reminder, never a state change. Never invent a "
            "discount: only mention a price reduction if the tool result explicitly includes one."),
        "parameters": {
            "type": "object",
            "properties": {"service_id": {"type": "string"}},
            "required": ["service_id"],
        },
    },
    "list_my_bookings": {
        "name": "list_my_bookings",
        "description": (
            "Read-only: list THIS customer's OWN bookings — never another customer's, there is "
            "no argument for that. Always includes current and upcoming appointments regardless "
            "of include_history. Set include_history=true only if the customer explicitly asks "
            "about a PAST appointment; it may be declined (a human-required refusal, not an "
            "error) depending on deployment settings."),
        "parameters": {
            "type": "object",
            "properties": {"include_history": {
                "type": "boolean",
                "description": "True only if the customer is asking about a past appointment."}},
        },
    },
    "propose_cancel_booking": {
        "name": "propose_cancel_booking",
        "description": (
            "Propose (never actually cancel) cancelling one of the customer's OWN upcoming "
            "bookings, identified by the booking_id from list_my_bookings. Never invent a "
            "booking_id."),
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string"},
                "reason": {"type": "string", "description": "Optional, customer's own words."},
            },
            "required": ["booking_id"],
        },
    },
    "propose_reschedule_booking": {
        "name": "propose_reschedule_booking",
        "description": (
            "Propose (never actually reschedule) moving one of the customer's OWN upcoming "
            "bookings to a new time. booking_id must come from list_my_bookings; "
            "new_starts_at_iso should be a real, still-open slot — check with check_availability "
            "first if unsure."),
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {"type": "string"},
                "new_starts_at_iso": {"type": "string"},
            },
            "required": ["booking_id", "new_starts_at_iso"],
        },
    },
}


class GeminiLlm:
    driver = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout: int = 20,
                allowed_tools: frozenset[str] = frozenset(), secret_store: Any = None) -> None:
        # `api_key` is the ENV fallback, not necessarily the key actually used — see
        # `_resolve_key` below. `secret_store` is optional so every existing caller (tests, a boot
        # with no SECRETS_KEK configured) keeps working unchanged.
        self._env_key = api_key
        self._secret_store = secret_store
        self._cached_key: str | None = None
        self._model = model
        self._timeout = timeout
        # Intersected with the module's own known schemas — a tool name in config that this file
        # does not know how to describe to Gemini is simply never declared, not an error, because
        # config drives ALLOWLIST membership, not tool CAPABILITY.
        self._allowed = frozenset(allowed_tools) & frozenset(_TOOL_SCHEMAS)

    def invalidate_key_cache(self) -> None:
        """Called by app/api/v1/operator.py right after a GEMINI_API_KEY rotation, so the next
        `respond()` re-reads the store instead of serving the key this process booted with."""
        self._cached_key = None

    async def _resolve_key(self) -> str:
        """The operator-set credential when one exists, else the env value this process booted
        with. Cached in-process (invalidated on rotation, not on a timer) so a normal turn costs
        no extra datastore round trip — only a rotation ever pays for a fresh read."""
        if self._cached_key is not None:
            return self._cached_key
        key = self._env_key
        if self._secret_store is not None:
            key = await self._secret_store.get(tenant="", name="GEMINI_API_KEY",
                                               fallback=self._env_key)
        self._cached_key = key
        return key

    async def respond(self, *, system_prompt: str, summary: str,
                      recent_messages: list[dict[str, str]], user_message: str,
                      allowed_tools: frozenset[str], context_block: str = "") -> LlmReply:
        # Per-call intersection too: a caller may narrow (never widen) what this specific turn may
        # propose — e.g. a conversation already holding a pending proposal should not be offered
        # `propose_booking` again until the pending one resolves.
        tools_for_call = self._allowed & frozenset(allowed_tools) if allowed_tools else self._allowed

        contents = []
        for m in recent_messages:
            role = "model" if m.get("role") == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": str(m.get("text", ""))}]})
        contents.append({"role": "user", "parts": [{"text": user_message}]})

        payload: dict[str, Any] = {
            "system_instruction": {"parts": [{"text": system_prompt + (
                f"\n\nConversation summary so far: {summary}" if summary else "") + (
                f"\n\n{context_block}" if context_block else "")}]},
            "contents": contents,
        }
        if tools_for_call:
            payload["tools"] = [{"function_declarations": [
                _TOOL_SCHEMAS[name] for name in sorted(tools_for_call)]}]

        key = await self._resolve_key()
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self._model}:generateContent?key={key}")
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                data = json.loads(resp.read() or b"{}")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise LlmUnavailable(f"Gemini unreachable: {exc}") from exc

        usage = data.get("usageMetadata") or {}
        in_tok = int(usage.get("promptTokenCount") or 0)
        out_tok = int(usage.get("candidatesTokenCount") or 0)

        candidates = data.get("candidates") or []
        if not candidates:
            return LlmReply(text="", input_tokens=in_tok, output_tokens=out_tok)
        parts = ((candidates[0].get("content") or {}).get("parts") or [])

        for part in parts:
            call = part.get("functionCall")
            if call:
                name = str(call.get("name") or "")
                # ENFORCEMENT #2: a call outside what THIS turn declared is dropped, never executed
                # and never handed further up as a tool_call — it degrades to no proposal at all.
                if name not in tools_for_call:
                    return LlmReply(text="", input_tokens=in_tok, output_tokens=out_tok)
                return LlmReply(tool_call=ToolCall(name=name, args=dict(call.get("args") or {})),
                                input_tokens=in_tok, output_tokens=out_tok)

        text = "".join(str(p.get("text", "")) for p in parts)
        return LlmReply(text=text, input_tokens=in_tok, output_tokens=out_tok)


class LlmUnavailable(Exception):
    """Transient. The caller (core/conversation.py) retries on the next debounce tick rather than
    dropping the customer's message."""
