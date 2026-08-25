"""Domain shapes: inbound messages, conversation state, tool proposals.

Plain dataclasses, mirroring the convention in services/reminders and services/operations
(app/core/models.py in both). Rows are stored as dicts (`as_row`/`**row`) through the generic
DataStore port — no ORM, so a memory driver and a postgres driver hold the identical shape.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

# ── collections (DataStore is a generic {collection: [{...}]} store; see ports/datastore.py) ──
INBOUND_MESSAGES = "wa_inbound_messages"     # wamid-keyed dedup store — see ports/inbound_store.py
CONVERSATIONS = "wa_conversations"
PENDING_PROPOSALS = "wa_pending_proposals"   # a model's tool call, awaiting server-side validation
BOOKINGS = "wa_bookings"
COST_LEDGER = "wa_cost_ledger"               # per-conversation token counts, real cost basis


def as_row(obj: Any) -> dict[str, Any]:
    return asdict(obj)


@dataclass
class InboundMessage:
    """One message as notification-service's bus (or its own idempotent replay) delivered it.

    `wamid` is Meta's own message id — the ONLY thing that makes at-most-once, non-durable bus
    delivery safe to re-process: see ports/inbound_store.py for why this is persisted before
    anything else happens.
    """
    tenant: str
    wamid: str
    from_number: str
    kind: str = "text"          # text | button_reply | list_reply
    text: str = ""
    reply_id: str = ""          # the button/list id, when kind != text
    received_at: int = field(default_factory=lambda: int(time.time()))
    processed: bool = False


@dataclass
class ConversationState:
    """Per-customer-per-tenant state machine (design point 3).

    `subject_ref` is the pseudonym this whole conversation is keyed by — never a phone number.
    """
    tenant: str
    subject_ref: str
    from_number: str = ""            # held ONLY long enough to send a reply; never in the summary
    # idle | awaiting_triage | batching | awaiting_confirmation | closed. `awaiting_triage` is
    # entered on every FRESH session (see `handle_inbound_text`) and free text there never reaches
    # `on_inbound_text`/the LLM — only a `triage:*` list-reply id can leave it (core/conversation.py
    # module docstring, "mandatory first-message triage gate").
    state: str = "idle"
    # How many times this SESSION has actually called the LLM (compose_reply). Reset to 0 whenever
    # a fresh session opens (handle_inbound_text). Config ceiling: CONVERSATION_MAX_AUTO_REPLY_TURNS.
    auto_reply_turns: int = 0
    # How many times compose_reply ran with a proposal STILL sitting unconfirmed on this
    # conversation — the customer typed again instead of pressing a button. Reset on any
    # button_reply (confirm or cancel) that resolves the outstanding proposal. Feeds
    # core/frustration.py's early-escalation signal; see that module.
    unconfirmed_proposal_attempts: int = 0
    # This conversation has already been handed to a human (ticket opened). Set once, never
    # unset — prevents a second ticket for the same session on a re-entrant tick or a stray
    # message arriving after the handoff text was sent but before the session actually closes.
    escalated: bool = False
    # Has THIS session already answered the triage gate? `state` alone cannot carry this: a
    # resolved triage pick sets `state` back to "idle" so `on_inbound_text`'s own idle/closed
    # session-open branch still runs unmodified — but "idle" is ALSO a brand-new conversation's
    # default, and `handle_inbound_text` cannot tell those two "idle"s apart without this flag.
    # Reset to False only when a fresh session actually opens (handle_inbound_text).
    triage_resolved: bool = False
    # RAW WINDOW: the last N messages verbatim (config: CONVERSATION_RAW_WINDOW_MESSAGES). Trimmed
    # into `summary` once it grows past that, so LLM context/cost stay bounded (design point 3c).
    raw_window: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    # Debounce: messages arriving inside CONVERSATION_DEBOUNCE_SECONDS of each other are coalesced
    # into one reply cycle. `batch_deadline` is when the debounce window closes (it slides forward
    # on every new message); `batch_started_at` is fixed at the FIRST message of the batch, so
    # compose_reply can select every message the customer sent in this batch, not only the last.
    batch_deadline: int = 0
    batch_started_at: int = 0
    session_started_at: int = 0
    last_activity_at: int = 0
    # WHEN THIS SESSION LAST CLOSED — intent completion (state -> "idle") or silence timeout
    # (state -> "closed"). Retention (app/core/retention.py) counts CHAT_RETENTION_DAYS from here,
    # never from a per-message timestamp: a long-running back-and-forth must not have its early
    # messages purged mid-conversation just because they are individually old. Reset to 0 the
    # moment a new message reopens the session — a purge clock only ticks while the session is
    # actually closed.
    session_closed_at: int = 0
    # The pending model tool-call this conversation is waiting on a button reply for, if any — see
    # PendingProposal. Never a state-changing action itself; see core/tools.py.
    pending_proposal_id: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    updated: int = field(default_factory=lambda: int(time.time()))


@dataclass
class PendingProposal:
    """A tool call the MODEL proposed and the deterministic backend VALIDATED — before any button
    was ever rendered (design point 5). Only a matching button_reply/list_reply id may execute it.
    """
    id: str
    tenant: str
    subject_ref: str
    conversation_id: str
    tool: str                        # must be in settings.llm_tool_allowlist
    args: dict[str, Any] = field(default_factory=dict)
    # What the deterministic re-validation found TRUE at proposal time — re-checked again, not
    # trusted, at execution time (design point 5: "never the model's own decision").
    validated_snapshot: dict[str, Any] = field(default_factory=dict)
    created_at: int = field(default_factory=lambda: int(time.time()))
    expires_at: int = 0
    consumed: bool = False


@dataclass
class Booking:
    id: str
    tenant: str
    subject_ref: str
    service_id: str
    starts_at: int
    duration_minutes: int
    state: str = "confirmed"         # confirmed | cancelled
    created_at: int = field(default_factory=lambda: int(time.time()))
    idempotency_key: str = ""
