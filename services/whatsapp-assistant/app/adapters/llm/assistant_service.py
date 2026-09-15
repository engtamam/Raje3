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

import asyncio
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
    "check_mobile_visit_hours": {
        "name": "check_mobile_visit_hours",
        "description": (
            "Read-only: the shop's REAL weekly working hours — call this BEFORE request_mobile_"
            "visit whenever the customer wants the shop to come to them, so you offer a time that "
            "will actually be accepted rather than guessing. Never state a working hour you did "
            "not get from this tool."),
        "parameters": {"type": "object", "properties": {}},
    },
    "request_mobile_visit": {
        "name": "request_mobile_visit",
        "description": (
            "Use when the customer wants the shop to come TO them for a service instead of them "
            "visiting the shop (e.g. mobile car wash — «تبي تجيك السيارة تغسل عندك؟» style ask), "
            "for a shop whose services can genuinely travel. service_ids must be real ids from "
            "the shop's own service catalogue shown to you, never invented. starts_at_iso must be "
            "a REAL moment inside the shop's own working hours — call check_mobile_visit_hours "
            "first and only offer/accept a time those hours actually allow; never invent or guess "
            "a time. This does NOT create the request yet: calling this only starts the process — "
            "the customer is then asked to share their location, and the request is only actually "
            "created once they do. Never claim it is booked or confirmed; nothing is confirmed "
            "until the shop itself reviews and accepts it."),
        "parameters": {
            "type": "object",
            "properties": {
                "service_ids": {"type": "array", "items": {"type": "string"}},
                "starts_at_iso": {"type": "string"},
            },
            "required": ["service_ids", "starts_at_iso"],
        },
    },
}


class AssistantServiceLlm:
    driver = "assistant_service"

    def __init__(self, *, connections: HttpAssistantConnections, model_location: str, model_name: str,
                model_auth: str, env_project: str = "", env_credential: str = "",
                allowed_tools: frozenset[str] = frozenset(), secret_store: Any = None,
                runtime_config: Any = None, max_reply_tokens: int = 500) -> None:
        self._connections = connections
        self._model_location = model_location
        # `model_name` STAYS THE DEPLOY-TIME DEFAULT — see `_resolve_model_name` below, which is
        # what `respond()` actually calls. Kept here (not renamed) so a caller that never wires
        # `runtime_config` (every existing test, `NullLlm`-adjacent call sites) sees identical
        # behaviour to before this field existed.
        self._model_name = model_name
        self._model_auth = model_auth
        self._env_project = env_project
        self._env_credential = env_credential
        self._secret_store = secret_store
        # ASSISTANT_MODEL_NAME's live override (app/runtime_policy.py) — read fresh every turn,
        # not cached: a model switch must take effect on the very next reply, and this is one
        # cheap datastore read alongside the project/credential resolution already happening here.
        self._runtime_config = runtime_config
        # DEPLOY-TIME DEFAULT — see `_resolve_max_tokens` below, the twin of `_resolve_model_name`
        # for MAX_REPLY_TOKENS (app/runtime_policy.py). Kept as a plain field for the same reason
        # `model_name` is: any caller that never wires `runtime_config` still behaves exactly as
        # configured.
        self._max_reply_tokens = max_reply_tokens
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

    async def _resolve_model_name(self) -> str:
        if self._runtime_config is None:
            return self._model_name
        return await self._runtime_config.get(
            tenant="", key="ASSISTANT_MODEL_NAME", default=self._model_name)

    async def _resolve_max_tokens(self) -> int:
        if self._runtime_config is None:
            return self._max_reply_tokens
        return int(await self._runtime_config.get(
            tenant="", key="MAX_REPLY_TOKENS", default=self._max_reply_tokens))

    def _model_url_and_shape(self, project: str, model_name: str) -> tuple[str, str]:
        """(url, shape) for assistant-service's own /assistant/connections `shape` field — see that
        service's core/connections.py (v0.18.61+): "generate" | "anthropic" | "chat". All three are
        reached through the SAME GCP project/credential (Vertex AI Model Garden hosts every one of
        them), never a different provider account — only the URL path and wire shape differ per
        publisher. Classified by model-id PREFIX, matching the console's own MODEL_OPTIONS grouping
        (apps/console/src/admin/AdminProviderSecrets.tsx) so the two never drift apart silently.
        """
        loc = self._model_location
        base = f"https://{loc}-aiplatform.googleapis.com/v1/projects/{project}/locations/{loc}"
        if model_name.startswith("claude-"):
            return f"{base}/publishers/anthropic/models/{model_name}:rawPredict", "anthropic"
        if model_name.startswith("gemini-"):
            return f"{base}/publishers/google/models/{model_name}:generateContent", "generate"
        # Every other wired publisher (Zhipu/MiniMax/Alibaba/gpt-oss on Vertex) speaks the
        # OpenAI-compatible endpoint — one project-wide URL, the model id travels in the request
        # BODY instead of the path (assistant-service's http_provider.py's own CHAT shape).
        return f"{base}/endpoints/openapi/chat/completions", "chat"

    async def respond(self, *, system_prompt: str, summary: str,
                      recent_messages: list[dict[str, str]], user_message: str,
                      allowed_tools: frozenset[str], context_block: str = "",
                      tenant: str = "", model_name: str = "") -> LlmReply:
        tools_for_call = self._allowed & frozenset(allowed_tools) if allowed_tools else self._allowed
        tool_schemas = [_TOOL_SCHEMAS[name] for name in sorted(tools_for_call)]

        # STABLE CONTENT FIRST, VOLATILE CONTENT LAST — deliberately, for Vertex AI's own
        # automatic prefix caching (implicit context caching, no configuration needed, active for
        # a shared prefix of >=2048 tokens): a cache hit requires the SAME bytes at the START of
        # the prompt. `context_block` (the shop's service catalogue + offers) barely changes
        # across many different conversations for the SAME shop — a real, large caching win if it
        # sits right after the equally-stable persona instructions. `summary` is the opposite: it
        # is THIS conversation's own running summary, different on nearly every turn — placing it
        # first (the old order) meant no two calls ever shared a matching prefix at all, so a
        # catalogue that was otherwise identical call after call never had a chance to cache.
        full_prompt = system_prompt + (
            f"\n\n{context_block}" if context_block else "") + (
            f"\n\nConversation summary so far: {summary}" if summary else "")

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

        # THE CALLER'S ALREADY-RESOLVED VALUE WINS — see LlmPort.respond's own note on why
        # (core/conversation.py's compose_reply resolves this once, before the wallet reserve, and
        # passes it straight through here so the reserve and the actual call can never disagree
        # about which model this turn is really running). Only re-resolve when nothing was passed,
        # for every caller that has no reserve step of its own to have already resolved it for.
        model_name = model_name or await self._resolve_model_name()
        url, shape = self._model_url_and_shape(project, model_name)
        try:
            # OFF THE EVENT LOOP. `ensure_connection` and everything under `HttpAssistantConnections`
            # are plain (non-async) methods that call `urllib.request.urlopen` synchronously — correct
            # for what THEY are, but calling them un-awaited from here used to mean this coroutine
            # blocked the pod's entire single-worker event loop for the round trip, same class of
            # incident `adapters/token_verifier/jwks.py`'s own docstring documents for a different
            # call site on the sibling service (notification-service) — including this pod's own
            # /healthz/readyz, and every other tenant's message, for as long as assistant-service
            # took to answer.
            cid = await asyncio.to_thread(
                ensure_connection, self._connections, tenant=tenant, url=url, shape=shape,
                model=model_name, auth=self._model_auth, credential=credential,
                system_prompt=full_prompt, tools=tool_schemas)
        except AssistantConnectionsUnavailable as exc:
            raise LlmUnavailable(f"assistant-service unreachable: {exc}") from exc

        messages: list[dict[str, str]] = []
        for m in recent_messages:
            role = "assistant" if m.get("role") == "assistant" else "user"
            messages.append({"role": role, "content": str(m.get("text", ""))})
        messages.append({"role": "user", "content": user_message})

        max_tokens = await self._resolve_max_tokens()
        try:
            # THE LLM CALL ITSELF — the largest single freeze on this path (assistant-service's own
            # generation can take several seconds), now off the event loop for the same reason
            # `ensure_connection` above is. Bounded by `ASSISTANT_SERVICE_TIMEOUT_SECONDS` inside
            # `_call`'s own `urlopen(..., timeout=...)`, same as before — only WHERE it blocks changed.
            result = await asyncio.to_thread(
                self._connections.invoke, cid, tenant=tenant, messages=messages,
                max_tokens=max_tokens)
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
