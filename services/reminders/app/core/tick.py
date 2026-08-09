"""The heartbeat: due schedules become messages, or become suppressions with a reason.

THIS IS WHERE EVERY OTHER FILE MEETS. The gate decides, rendering fills, the sender delivers, and
the ledger remembers. The tick's only job is to do that in an order that survives being
interrupted — because it will be interrupted, by a pod eviction, a rollout, or a peer timing out.

THE ORDER, AND WHY EACH STEP IS WHERE IT IS:

  1. Claim the row.       Marked in-flight BEFORE anything external happens. Two replicas run this
                          cron; without a claim they both send.
  2. Gate it.             Cheap and pure. A refusal here costs no peer call at all.
  3. Render it.           Can fail on bad data, and failing before the send costs nothing.
  4. Send.                The only irreversible step, and it carries an idempotency key we
                          generated and stored, so a retry after a timeout cannot double-send.
  5. Record.              Ledger, then schedule state.

STEP 5 IS AFTER STEP 4 AND THAT IS A REAL RISK, ACCEPTED DELIBERATELY. If we crash between the
send and the ledger write, the message went out and we do not know it. The alternative — record
first — means a peer failure leaves a ledger entry for a message that never existed, which
silently consumes the customer's cap and suppresses a REAL message later. Given a choice between
losing the record of a sent message and inventing the record of an unsent one, we lose the record:
the idempotency key makes the resend harmless, and an invented cap consumption is invisible.

BOUNDED, ALWAYS. A batch limit per tenant per tick. An unbounded sweep is how a slow query becomes
a missed batch becomes a day of reminders that never went out.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core import engagement as E
from app.core import gate as G
from app.core import rendering as R
from app.core.models import SendLog, as_row
from app.adapters.message_sender import Unsendable
from app.core.stores import EngagementStore, PrefsStore, ScheduleStore, SendLogStore


@dataclass
class TickResult:
    sent: int = 0
    suppressed: int = 0
    deferred: int = 0
    failed: int = 0
    scanned: int = 0
    # Suppression reasons, counted. This is the number an operator actually needs: "312 suppressed"
    # is an alarm, "312 suppressed, all outside the window" is a working system doing its job.
    reasons: dict[str, int] = field(default_factory=dict)

    def note(self, reason: str) -> None:
        key = reason[:80]
        self.reasons[key] = self.reasons.get(key, 0) + 1


class Tick:
    def __init__(self, *, store, sender, limits: G.Limits, eng_cfg: E.EngagementConfig,
                 batch: int = 100, telemetry=None) -> None:
        self._store = store
        self._sched = ScheduleStore(store)
        self._log = SendLogStore(store)
        self._prefs = PrefsStore(store)
        self._eng = EngagementStore(store)
        self._sender = sender
        self._limits = limits
        self._eng_cfg = eng_cfg
        self._batch = batch
        self._t = telemetry

    async def run(self, tenant: str, *, now: int, library: list[dict[str, Any]],
                  service_names: dict[str, str], establishment: str,
                  customer_names: dict[str, str] | None = None,
                  tone: str = "brief") -> TickResult:
        """One pass over one tenant's due schedules.

        Per tenant rather than across all of them, so a single establishment with a large backlog
        cannot starve every other one — and so the tenant-scoped query in the store stays the only
        query there is.
        """
        res = TickResult()
        names = customer_names or {}
        due = await self._sched.due(tenant, now=now, limit=self._batch)
        res.scanned = len(due)

        # PRIORITY ORDER (spec 8.4.2 section 4). Two messages competing for one daily slot must
        # resolve the same way every time, and the losing one must be the lower-priority one — not
        # whichever the datastore happened to return first.
        due.sort(key=lambda r: (G.priority(r.get("cls", "service")), int(r.get("due_at", 0))))

        for row in due:
            try:
                await self._one(tenant, row, now=now, res=res, library=library,
                                service_names=service_names, establishment=establishment,
                                customer_name=names.get(row.get("subject_ref", ""), ""),
                                tone=tone)
            except Unsendable as exc:
                # PERMANENT, not transient. There is nobody to send to — erased, or never there.
                # Retrying would ask operations about a forgotten customer on every tick forever,
                # which is both useless and the opposite of what they asked for.
                await self._close(tenant, row, "suppressed", f"لا يوجد مستقبِل: {exc}", now)
                res.suppressed += 1
                res.note("no recipient")
            except Exception as exc:                                        # noqa: BLE001
                # ONE ROW'S FAILURE MUST NOT END THE BATCH. The alternative is one malformed
                # schedule stopping every reminder for that establishment, indefinitely, with the
                # symptom appearing as "the product does not work" rather than as one bad row.
                res.failed += 1
                await self._fail(tenant, row, str(exc)[:200], now)
                if self._t is not None:
                    self._t.event("tick_row_failed", tenant=tenant,
                                  schedule=row.get("id", ""), error=str(exc)[:200])
        return res

    async def send_one(self, tenant: str, row: dict[str, Any], *, now: int,
                       library: list[dict[str, Any]], service_names: dict[str, str],
                       establishment: str, tone: str = "brief") -> dict[str, Any]:
        """Send ONE message that is not on a schedule — the campaigns path.

        THE SAME GATE, THE SAME TEMPLATE SELECTION, THE SAME SANITISER, THE SAME LEDGER. What it
        skips is only the schedule bookkeeping, because a campaign message has no schedule to
        close: it is decided, sent, and recorded, and nothing waits for it.

        A campaign-shaped shortcut around the gate would be a second set of rules, and the second
        one is always the one missing a check the day somebody adds one to the first. So this
        reuses the decision rather than repeating it.

        Returns `{"sent": bool, "reason": str}` — the gate's own sentence, carried verbatim into
        the campaign's run report.
        """
        subject = row.get("subject_ref", "")
        cls = row.get("cls", "marketing")

        prefs = await self._prefs.get(tenant, subject) or {}
        eng = await self._eng.get(tenant, subject) or {}
        recent = await self._log.since(tenant, subject, since=now - 31 * 86400)
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            class_enabled=any(t.get("type") == row.get("template_type") for t in library))

        if not decision.allowed:
            # RECORDED AS A SUPPRESSION, exactly like a reminder's. The ledger is what every cap is
            # counted against, and a refusal that leaves no row is a refusal nobody can explain.
            await self._log.append(tenant, as_row(SendLog(
                tenant=tenant, subject_ref=subject, cls=cls, at=now,
                schedule_id=row.get("id", ""), outcome="suppressed", reason=decision.reason)))
            return {"sent": False, "reason": decision.reason}

        try:
            template = R.choose(template_type=row.get("template_type", ""), tone=tone,
                                library=library)
            owner_text = row.get("owner_text", "")
            rendered = R.render(
                template=template,
                system={"1": "", "2": establishment, "3": owner_text, "4": owner_text},
                catalogue={"3": owner_text, "4": owner_text},
                owner={"3": owner_text, "4": owner_text})
        except R.RenderError as exc:
            return {"sent": False, "reason": str(exc)}

        key = row.get("idempotency_key") or f"cmp_{row.get('id','')}"
        try:
            await self._sender.send(
                tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
                variables=rendered.variables, cls=cls, idempotency_key=key)
        except Unsendable as exc:
            return {"sent": False, "reason": f"لا يوجد مستقبِل: {exc}"}

        await self._log.append(tenant, as_row(SendLog(
            tenant=tenant, subject_ref=subject, cls=cls, at=now,
            schedule_id=row.get("id", ""), template_name=rendered.template_name,
            outcome="sent", idempotency_key=key)))
        return {"sent": True, "reason": ""}

    async def _one(self, tenant: str, row: dict[str, Any], *, now: int, res: TickResult,
                   library: list[dict[str, Any]], service_names: dict[str, str],
                   establishment: str, customer_name: str, tone: str) -> None:
        subject = row.get("subject_ref", "")
        cls = row.get("cls", "service")

        # ── 1. claim ──────────────────────────────────────────────────────────────────────────
        # Two replicas run this cron. Without the claim they both read `pending` and both send.
        claimed = await self._claim(tenant, row, now)
        if not claimed:
            return

        # ── 2. gate ───────────────────────────────────────────────────────────────────────────
        prefs = await self._prefs.get(tenant, subject) or {}
        eng = await self._eng.get(tenant, subject) or {}
        recent = await self._log.since(tenant, subject, since=now - 31 * 86400)
        decision = G.evaluate(
            cls=cls, template_type=row.get("template_type", ""), now=now, limits=self._limits,
            prefs_stopped=prefs.get("stopped") or {},
            engagement_score=float(eng.get("score") or 0.0),
            engagement_at=int(eng.get("scored_at") or 0),
            recent_sends=recent, eng_cfg=self._eng_cfg,
            class_enabled=any(t.get("type") == row.get("template_type") for t in library))

        if not decision.allowed:
            if decision.retry_at:
                # DEFERRED: the row goes back to pending with a new due date. Deliberately not a
                # terminal state — "wait" and "never" are different answers and an owner reading
                # the log must be able to tell them apart.
                row["state"] = "pending"
                row["due_at"] = decision.retry_at
                row["reason"] = decision.reason
                row["updated"] = now
                await self._sched.upsert(tenant, _key(row), row)
                res.deferred += 1
            else:
                await self._close(tenant, row, "suppressed", decision.reason, now)
                await self._log.append(tenant, as_row(SendLog(
                    tenant=tenant, subject_ref=subject, cls=cls, at=now,
                    schedule_id=row.get("id", ""), outcome="suppressed",
                    reason=decision.reason)))
                res.suppressed += 1
            res.note(decision.reason)
            return

        # ── 3. render ─────────────────────────────────────────────────────────────────────────
        template = R.choose(template_type=row.get("template_type", ""), tone=tone, library=library)
        service_text = R.merged_service_text(
            [service_names.get(s, s) for s in
             [row.get("service_id", "")] + list(row.get("also_services") or [])])
        rendered = R.render(
            template=template,
            system={"1": customer_name, "2": establishment, "3": service_text,
                    "4": service_text},
            catalogue={"3": service_text, "4": service_text},
            owner={"3": row.get("owner_text", ""), "4": row.get("owner_text", "")})

        # ── 4. send ───────────────────────────────────────────────────────────────────────────
        # The key is generated and stored BEFORE the call and reused on every retry: a timeout is
        # not evidence that nothing was sent, and the customer must not pay for our uncertainty.
        key = row.get("idempotency_key") or f"rem_{uuid.uuid4().hex}"
        if key != row.get("idempotency_key"):
            row["idempotency_key"] = key
            await self._sched.upsert(tenant, _key(row), row)

        await self._sender.send(
            tenant=tenant, subject_ref=subject, template_name=rendered.template_name,
            variables=rendered.variables, cls=cls, idempotency_key=key)

        # ── 5. record ─────────────────────────────────────────────────────────────────────────
        await self._log.append(tenant, as_row(SendLog(
            tenant=tenant, subject_ref=subject, cls=cls, at=now,
            schedule_id=row.get("id", ""), template_name=rendered.template_name,
            outcome="sent", idempotency_key=key)))
        await self._close(tenant, row, "sent", "", now)
        res.sent += 1

    async def _claim(self, tenant: str, row: dict[str, Any], now: int) -> bool:
        """Move the row out of `pending` before anything external happens.

        Read-then-write rather than a compare-and-set: the DataStore port has no CAS, and adding
        one would be a change to base-services. The window is small and the consequence of losing
        the race is bounded by the idempotency key at the sender — which is the belt this braces.
        """
        fresh = await self._sched.get(_key(row))
        if fresh is None or fresh.get("state") != "pending":
            return False
        fresh["state"] = "sending"
        fresh["updated"] = now
        await self._sched.upsert(tenant, _key(fresh), fresh)
        row.update(fresh)
        return True

    async def _close(self, tenant: str, row: dict[str, Any], state: str, reason: str,
                     now: int) -> None:
        row["state"] = state
        row["reason"] = reason
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)

    async def _fail(self, tenant: str, row: dict[str, Any], error: str, now: int) -> None:
        """A row that threw goes back to pending with a short delay, not to a dead state.

        Most failures here are a peer being briefly unavailable, and a schedule closed as `failed`
        is a reminder that silently never happens. It retries on the next tick; a row that keeps
        failing shows up in the reason counts, which is where an operator will actually see it.
        """
        row["state"] = "pending"
        row["due_at"] = now + 3600
        row["reason"] = f"تعذّر الإرسال، سيُعاد: {error}"
        row["updated"] = now
        await self._sched.upsert(tenant, _key(row), row)


def _key(row: dict[str, Any]) -> str:
    return (f"{row.get('tenant','')}|{row.get('subject_ref','')}|"
            f"{row.get('service_id','')}|{row.get('kind','')}")
