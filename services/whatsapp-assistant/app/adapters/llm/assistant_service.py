"""AssistantServiceLlm — the LlmPort implementation backed by assistant-service's AI connections
(v0.18.43+), the migration target that replaces GeminiLlm once proven live (see the approved plan,
`stateless-wondering-fox.md`). NOT wired into LLM_DRIVER by default yet — see
app/adapters/llm/__init__.py::build()'s own note on the rollout order.

ONE ROUND TRIP PER TURN, NEVER A LOOP. assistant-service's own connections support a multi-round
tool-calling loop (send the tool's result back, ask again) — this service has never needed that:
today's flow is always "one model call -> either text or a single tool proposal -> render it to the
customer directly", exactly as GeminiLlm already does. So `messages` here is built the same way
GeminiLlm builds `contents`: the running transcript plus this turn's message, sent once, and
whatever comes back (text or the first tool call) is the whole answer for this turn.

TOOLS ARE DECLARED ON THE CONNECTION, NOT PER CALL — see core/assistant_connections.py's own
docstring for why (assistant-service's contract has no per-invoke tool list) and why this is an
accepted trade-off rather than a new gap: core/tools.py's `validate_and_render` already re-checks
`allowed_tools` server-side on every proposal, regardless of what the model was offered to see.

ONLY THE FIRST TOOL CALL IS EVER USED when the model returns several in one turn — agreed with the
assistant-service team for exactly this confirm-then-execute shape, matching how this service has
always treated a proposal (one at a time, never a batch the customer did not ask for).
"""
from __future__ import annotations

from typing import Any

from app.adapters.llm.gemini import _TOOL_SCHEMAS
from app.core.assistant_connections import (
    AssistantConnectionsUnavailable,
    HttpAssistantConnections,
    ensure_connection,
)
from app.ports.llm import LlmReply, ToolCall


class AssistantServiceLlm:
    driver = "assistant_service"

    def __init__(self, *, connections: HttpAssistantConnections, model_url: str, model_name: str,
                model_auth: str, model_credential: str, allowed_tools: frozenset[str] = frozenset(),
                invoke_timeout: int = 20) -> None:
        self._connections = connections
        self._model_url = model_url
        self._model_name = model_name
        self._model_auth = model_auth
        self._model_credential = model_credential
        # Same intersection GeminiLlm applies: config drives ALLOWLIST membership, not tool
        # CAPABILITY — a name this file does not know how to describe is simply never declared.
        self._allowed = frozenset(allowed_tools) & frozenset(_TOOL_SCHEMAS)
        self._invoke_timeout = invoke_timeout

    async def respond(self, *, system_prompt: str, summary: str,
                      recent_messages: list[dict[str, str]], user_message: str,
                      allowed_tools: frozenset[str], context_block: str = "",
                      tenant: str = "") -> LlmReply:
        tools_for_call = self._allowed & frozenset(allowed_tools) if allowed_tools else self._allowed
        tool_schemas = [_TOOL_SCHEMAS[name] for name in sorted(tools_for_call)]

        full_prompt = system_prompt + (
            f"\n\nConversation summary so far: {summary}" if summary else "") + (
            f"\n\n{context_block}" if context_block else "")

        try:
            cid = ensure_connection(
                self._connections, tenant=tenant, url=self._model_url, model=self._model_name,
                auth=self._model_auth, credential=self._model_credential,
                system_prompt=full_prompt, tools=tool_schemas)
        except AssistantConnectionsUnavailable as exc:
            raise LlmUnavailable(f"assistant-service unreachable: {exc}") from exc

        messages: list[dict[str, str]] = []
        for m in recent_messages:
            role = "assistant" if m.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": str(m.get("text", ""))})
        messages.append({"role": "user", "content": user_message})

        try:
            result = self._connections.invoke(cid, tenant=tenant, messages=messages)
        except AssistantConnectionsUnavailable as exc:
            raise LlmUnavailable(f"assistant-service unreachable: {exc}") from exc

        in_tok = int(result.get("tokens_in") or 0)
        out_tok = int(result.get("tokens_out") or 0)

        if result.get("kind") == "tool_call":
            calls = result.get("calls") or []
            if not calls:
                return LlmReply(text="", input_tokens=in_tok, output_tokens=out_tok)
            first = calls[0]
            name = str(first.get("name") or "")
            # SAME ENFORCEMENT GeminiLlm's own respond() applies: a call outside what THIS turn
            # declared is dropped rather than trusted, even though the connection's own tool list
            # should already make this impossible — defence in depth, not a belief it is needed.
            if name not in tools_for_call:
                return LlmReply(text="", input_tokens=in_tok, output_tokens=out_tok)
            return LlmReply(tool_call=ToolCall(name=name, args=dict(first.get("arguments") or {})),
                            input_tokens=in_tok, output_tokens=out_tok)

        return LlmReply(text=str(result.get("text") or ""), input_tokens=in_tok, output_tokens=out_tok)


class LlmUnavailable(Exception):
    """Transient. The caller (core/conversation.py) retries on the next debounce tick rather than
    dropping the customer's message — same contract as app/adapters/llm/gemini.py's own."""
