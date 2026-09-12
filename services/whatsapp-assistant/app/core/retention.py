"""Chat data retention — bulk purge of closed conversations past CHAT_RETENTION_DAYS.

REFERENCE PATTERN (documentation only — do NOT apply this to any other service now):

This is the first service on this platform that accumulates UNBOUNDED RAW TEXT CONTENT every day
with no natural cap — every customer message and every model reply, kept verbatim in raw_window /
the inbound message store, for as long as a conversation exists. Most other services here hold
structured facts (a schedule, a balance, a preference) that are small and bounded by construction;
this one holds a transcript, and a transcript grows without limit unless something prunes it.

The general shape, if a FUTURE service ever has the same property (unbounded raw content, not a
bounded fact table):

  1. A config-driven TTL (here, CHAT_RETENTION_DAYS), counted from a LOGICAL CLOSE EVENT specific
     to the domain — never from the age of an individual message/row. A long conversation's first
     message is not "old" while the conversation is still open; the clock starts when the thing the
     content belongs to is actually finished (here: session close — intent completion or silence
     timeout, see ConversationState.session_closed_at).
  2. A tick-driven purge, in the same tick/scheduler entrypoint the service already has (never a
     second, unmonitored cron) — see app/api/internal.py's /whatsapp_assistant/tick, which calls
     `run_retention_tick` below immediately after the reply/timeout sweep it already runs.
  3. The purge goes through the Auditor as a CRITICAL action before it deletes anything, exactly
     like every other irreversible bulk-delete on this platform (see app/core/audit.py) — a purge
     nobody can prove happened, for the reason claimed, is a purge indistinguishable from data loss.
  4. Idempotent and bounded, same as every sweep on this platform (services/reminders/app/core/
     tick.py, services/reminders/app/core/erasure.py) — safe to re-run, reports truncation rather
     than silently leaving work undone.

This module is the worked example of that shape for this ONE service. Nothing here is generic or
importable by another service; a future service with this same property should read this file for
the reasoning, not import from it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import CONVERSATIONS

# SCAN CURSOR, PER TENANT — fixed 2026-09-12, a real gap a QA audit found: the candidate scan below
# always re-read the same top `batch * 4` rows (sorted oldest-updated-first) with no cursor. A
# tenant with a backlog of conversations that are OPEN and never get touched again (stuck, never
# closing) sorts ahead of everything else forever — those rows always fill the page, and any
# genuinely closed-and-eligible-for-purge conversation behind them in sort order is never reached,
# so that tenant's purge stalls indefinitely. Paging with a cursor that advances past what this
# call already scanned (same convention as `conversation.py`'s `_sweep_due_cursor` /
# `_sweep_timed_out_cursor`) guarantees the scan eventually walks past the stuck backlog instead of
# sitting on it forever — and keeps this bounded per-call cost from ever growing into an unbounded
# one, which is what would let one tenant's backlog crowd out every other tenant's share of a tick.
_SCAN_CURSORS: dict[str, str | None] = {}


@dataclass
class RetentionResult:
    scanned: int = 0
    purged_conversations: int = 0
    purged_messages: int = 0
    truncated: bool = False
    # Subjects whose messages/conversation could not be fully purged within max_scan — surfaced
    # rather than silently retried forever, same convention as reminders' erasure truncation flag.
    incomplete: list[str] = field(default_factory=list)


async def run_retention_tick(tenant: str, *, now: int, store: Any, inbound_store: Any,
                             auditor: Any, retention_days: int, batch: int = 200,
                             max_scan_per_subject: int = 5000) -> RetentionResult:
    """Purge conversations (and their raw inbound messages) whose SESSION CLOSED more than
    `retention_days` ago.

    Per tenant, bounded by `batch`, imitating services/reminders/app/core/tick.py's shape — one
    tenant's backlog must not starve every other tenant's pass through the same tick.

    IDEMPOTENT. A conversation already purged is simply not found by the next pass's `find` (its
    row is gone) — re-running this costs nothing extra and purges nothing twice.
    """
    res = RetentionResult()
    cutoff = now - (retention_days * 86400)

    # CANDIDATES: closed sessions only (`session_closed_at` is only ever set on the idle/closed
    # transitions in core/conversation.py). An open session — batching, awaiting_confirmation, or
    # one that was reopened by a new inbound message (which resets session_closed_at to 0) — has
    # no close time and can never be a candidate, however old its first message is.
    cursor = _SCAN_CURSORS.get(tenant)
    rows, next_cursor = await store.find(
        CONVERSATIONS, {"tenant": tenant}, limit=max(batch * 4, batch), after=cursor,
        sort=("updated", "asc"))
    # `next_cursor` is None once this page reaches the end of the tenant's rows, which naturally
    # restarts the next tick's pass from the top rather than sitting on a stale cursor forever.
    _SCAN_CURSORS[tenant] = next_cursor
    res.scanned = len(rows)

    candidates = [
        r for r in rows
        if int(r.get("session_closed_at") or 0) > 0
        and int(r.get("session_closed_at") or 0) <= cutoff
    ][:batch]

    for row in candidates:
        subject_ref = str(row.get("subject_ref") or "")
        if not subject_ref:
            continue

        # AUDIT BEFORE DELETE, and CRITICAL: see app/core/audit.py's fail-closed rule. If the audit
        # log this service relies on is unreachable, AuditUnavailable propagates and this row is
        # left untouched — purged on a later pass once the log is back, never purged unwitnessed.
        await auditor.record(
            "whatsapp_assistant.chat_retention_purged", actor="whatsapp-assistant",
            resource=f"conversation:{tenant}|{subject_ref}", tenant=tenant,
            metadata={"subject_ref": subject_ref,
                     "session_closed_at": int(row.get("session_closed_at") or 0),
                     "retention_days": retention_days})

        deleted_msgs, truncated = await inbound_store.purge_for_subject(
            tenant, subject_ref, max_scan=max_scan_per_subject)
        res.purged_messages += deleted_msgs
        if truncated:
            res.truncated = True
            res.incomplete.append(subject_ref)
            # The messages are only PARTIALLY purged — leave the conversation row so the next tick
            # finds this subject again (session_closed_at unchanged) rather than deleting the
            # conversation now and orphaning the leftover messages with no row to find them by.
            continue

        await store.delete(CONVERSATIONS, f"{tenant}|{subject_ref}")
        res.purged_conversations += 1

    return res
