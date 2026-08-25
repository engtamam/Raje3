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
        "description": "Check open appointment slots for a service on or after a given date.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "earliest_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["service_id"],
        },
    },
    "propose_booking": {
        "name": "propose_booking",
        "description": "Propose (never confirm) one specific appointment slot to the customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "service_id": {"type": "string"},
                "starts_at_iso": {"type": "string"},
            },
            "required": ["service_id", "starts_at_iso"],
        },
    },
    "get_customer_points_summary": {
        "name": "get_customer_points_summary",
        "description": "Get a PATTERN summary of the customer's loyalty points — never raw PII.",
        "parameters": {"type": "object", "properties": {}},
    },
    "suggest_redeemable_offer": {
        "name": "suggest_redeemable_offer",
        "description": "Suggest a reward the customer's current points balance can already afford.",
        "parameters": {"type": "object", "properties": {}},
    },
}


class GeminiLlm:
    driver = "gemini"

    def __init__(self, *, api_key: str, model: str, timeout: int = 20,
                allowed_tools: frozenset[str] = frozenset()) -> None:
        self._key = api_key
        self._model = model
        self._timeout = timeout
        # Intersected with the module's own known schemas — a tool name in config that this file
        # does not know how to describe to Gemini is simply never declared, not an error, because
        # config drives ALLOWLIST membership, not tool CAPABILITY.
        self._allowed = frozenset(allowed_tools) & frozenset(_TOOL_SCHEMAS)

    async def respond(self, *, system_prompt: str, summary: str,
                      recent_messages: list[dict[str, str]], user_message: str,
                      allowed_tools: frozenset[str]) -> LlmReply:
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
                f"\n\nConversation summary so far: {summary}" if summary else "")}]},
            "contents": contents,
        }
        if tools_for_call:
            payload["tools"] = [{"function_declarations": [
                _TOOL_SCHEMAS[name] for name in sorted(tools_for_call)]}]

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{self._model}:generateContent?key={self._key}")
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
