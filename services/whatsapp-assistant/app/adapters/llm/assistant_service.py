"""AssistantServiceLlm — the LlmPort implementation backed by assistant-service's AI connections
(v0.18.43+), this service's real LLM backend.

ONE ROUND TRIP PER TURN, NEVER A LOOP. assistant-service's own connections support a multi-round
tool-calling loop (send the tool's result back, ask again) — this service has never needed that:
the flow is always "one model call -> either text or a single tool proposal -> render it to the
customer directly". So `messages` is the running transcript plus this turn's message, sent once,
and whatever comes back (text or the first tool call) is the whole answer for this turn.

TOOLS ARE DECLARED ON THE CONNECTION, NOT PER CALL — see core/assistant_connections.py's own
docstring for why (assistant-service's contract has no per-invoke tool list) and why this is an
accepted trade-off rather than a new gap: core/tools.py's `validate_and_render` already re-checks
`allowed_tools` server-side on every proposal, regardless of what the model was offered to see.

ONLY THE FIRST TOOL CALL IS EVER USED when the model returns several in one turn — agreed with the
assistant-service team for exactly this confirm-then-execute shape, matching how this service has
always treated a proposal (one at a time, never a batch the customer did not ask for).

PROJECT/CREDENTIAL RESOLVE LIVE. There is no real GCP project at the time this driver was wired
in — `_resolve_project`/`_resolve_credential` read the operator-set value from SecretStore first,
falling back to the boot-time env value, so an operator can supply both later from «مفاتيح
المزوّدين» with no redeploy, and a rotation is picked up on the very next turn via
`invalidate_key_cache()` (app/api/v1/operator.py's `_invalidate_llm` already calls it generically
for any LLM adapter that defines it).
"""
from __future__ import annotations

from typing import Any

from app.core.assistant_connections import (
    AssistantConnectionsUnavailable,
    HttpAssistantConnections,
    ensure_connection,
)
from app.ports.llm import LlmReply, ToolCall

# The JSON-schema shape for each allowlisted tool — assistant-service's own tool-declaration shape
# ({name, description, parameters}), identical to the underlying model's function-calling API.
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
    "suggest_services_carousel": {
        "name": "suggest_services_carousel",
        "description": (
            "Show the customer a visual, swipeable carousel of a few of the shop's REAL services/"
            "packages that have a real photo — use this ONLY when the customer is browsing or "
            "undecided (e.g. asking 'what do you offer?' or 'what do you have?'), NEVER after "
            "they have already named a specific service, and NEVER on every turn. Read-only: it "
            "never books or changes anything by itself — a customer who wants one still goes "
            "through propose_booking like any other service. May return nothing if too few items "
            "currently have a real photo."),
        "parameters": {"type": "object", "properties": {}},
    },
    "list_packages": {
        "name": "list_packages",
        "description": (
            "Read-only: list the shop's REAL bundled packages available to book soon, with their "
            "real prices — use this when the customer directly asks about packages/bundles/deals "
            "(e.g. 'do you have packages?', 'أبغى عرض/باقة'). Unlike suggest_related_service, this "
            "is not filtered to only-upsells — a genuine discount bundle is exactly the right "
            "answer here. Never invent a package or a price beyond what the result names; booking "
            "one still goes through propose_booking(package_id=...) like any other item."),
        "parameters": {"type": "object", "properties": {}},
    },
    "list_due_services": {
        "name": "list_due_services",
        "description": (
            "Read-only: real services this customer is due for soon, by his OWN learned rhythm — "
            "use this as an INPUT to decide what to suggest, NEVER as a fact to state back to the "
            "customer. You must never say or imply anything like 'you're due', 'it's been a "
            "while', or 'you usually' — build a natural suggestion that simply names the service, "
            "with no stated reason. Booking one still goes through propose_booking like any other "
            "service."),
        "parameters": {"type": "object", "properties": {}},
    },
    "list_lapsed_services": {
        "name": "list_lapsed_services",
        "description": (
            "Read-only: real services this customer used to book but has clearly stopped, by his "
            "OWN learned rhythm — same posture as list_due_services: an input for you to decide "
            "with, never a fact to state. Never say or imply 'you stopped' or reference his past — "
            "just a natural, inviting suggestion naming the service."),
        "parameters": {"type": "object", "properties": {}},
    },
}


class AssistantServiceLlm:
    driver = "assistant_service"

    def __init__(self, *, connections: HttpAssistantConnections, model_location: str, model_name: str,
                model_auth: str, env_project: str = "", env_credential: str = "",
                allowed_tools: frozenset[str] = frozenset(), secret_store: Any = None) -> None:
        self._connections = connections
        self._model_location = model_location
        self._model_name = model_name
        self._model_auth = model_auth
        self._env_project = env_project
        self._env_credential = env_credential
        self._secret_store = secret_store
        self._cached_project: str | None = None
        self._cached_credential: str | None = None
        # config drives ALLOWLIST membership, not tool CAPABILITY — a name this file does not know
        # how to describe is simply never declared.
        self._allowed = frozenset(allowed_tools) & frozenset(_TOOL_SCHEMAS)

    def invalidate_key_cache(self) -> None:
        """Called by app/api/v1/operator.py right after ASSISTANT_MODEL_PROJECT/CREDENTIAL is
        rotated, so the next `respond()` re-reads the store instead of serving the stale value."""
        self._cached_project = None
        self._cached_credential = None

    async def _resolve_project(self) -> str:
        if self._cached_project is not None:
            return self._cached_project
        project = self._env_project
        if self._secret_store is not None:
            project = await self._secret_store.get(tenant="", name="ASSISTANT_MODEL_PROJECT",
                                                    fallback=self._env_project)
        self._cached_project = project
        return project

    async def _resolve_credential(self) -> str:
        if self._cached_credential is not None:
            return self._cached_credential
        credential = self._env_credential
        if self._secret_store is not None:
            credential = await self._secret_store.get(tenant="", name="ASSISTANT_MODEL_CREDENTIAL",
                                                       fallback=self._env_credential)
        self._cached_credential = credential
        return credential

    def _model_url(self, project: str) -> str:
        loc = self._model_location
        return (f"https://{loc}-aiplatform.googleapis.com/v1/projects/{project}"
                f"/locations/{loc}/publishers/google/models/{self._model_name}:generateContent")

    async def respond(self, *, system_prompt: str, summary: str,
                      recent_messages: list[dict[str, str]], user_message: str,
                      allowed_tools: frozenset[str], context_block: str = "",
                      tenant: str = "") -> LlmReply:
        tools_for_call = self._allowed & frozenset(allowed_tools) if allowed_tools else self._allowed
        tool_schemas = [_TOOL_SCHEMAS[name] for name in sorted(tools_for_call)]

        full_prompt = system_prompt + (
            f"\n\nConversation summary so far: {summary}" if summary else "") + (
            f"\n\n{context_block}" if context_block else "")

        project = await self._resolve_project()
        credential = await self._resolve_credential()
        if not project or not credential:
            # NOT AN AssistantConnectionsUnavailable — nothing was even asked for yet. Raised as
            # LlmUnavailable anyway so the caller (core/conversation.py) treats an unconfigured
            # credential the same debounce-and-retry way as a genuine transient failure, rather
            # than a second, untested failure path.
            raise LlmUnavailable(
                "ASSISTANT_MODEL_PROJECT/ASSISTANT_MODEL_CREDENTIAL not yet configured — set them "
                "via /api/v1/assistant/operator/secrets once a real GCP project exists")

        try:
            cid = ensure_connection(
                self._connections, tenant=tenant, url=self._model_url(project), model=self._model_name,
                auth=self._model_auth, credential=credential,
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
            # DEFENCE IN DEPTH: a call outside what THIS turn declared is dropped rather than
            # trusted, even though the connection's own tool list should already make this
            # impossible.
            if name not in tools_for_call:
                return LlmReply(text="", input_tokens=in_tok, output_tokens=out_tok)
            return LlmReply(tool_call=ToolCall(name=name, args=dict(first.get("arguments") or {})),
                            input_tokens=in_tok, output_tokens=out_tok)

        return LlmReply(text=str(result.get("text") or ""), input_tokens=in_tok, output_tokens=out_tok)


class LlmUnavailable(Exception):
    """Transient. The caller (core/conversation.py) retries on the next debounce tick rather than
    dropping the customer's message."""
