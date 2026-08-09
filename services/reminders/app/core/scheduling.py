"""What a visit means for this service — the only input the product has.

`operations` publishes `operations.visit.recorded` and this consumes it. Nothing else creates a
schedule, which makes this file the whole write path: get it wrong and the service holds a perfect
scheduler with nothing in it.

THREE THINGS HAPPEN, AND THE SECOND AND THIRD ARE THE ONES PEOPLE FORGET:

  1. SCHEDULE the next reminder for each service in the visit — one merged message, not one per
     service (spec 5.8: merge before counting). A visit with three services produces a single
     reminder naming three. Two rows here would become one delivered message and one unexplained
     suppression once the daily cap runs, and the owner would read that as a cap bug.

  2. LEARN from the gap since the last visit for that service (spec 5.2), before overwriting it.
     Learning after the update would compare a timestamp to itself and observe zero.

  3. CANCEL the pending follow-up for the services just performed. Asking how last month's oil
     change went while the customer stands at the counter is the bug spec 5.6 names, and the fix
     is a cancel here rather than a filter at send time — a row that survives to the tick will
     eventually find a moment when nothing stops it.

IDEMPOTENT ON THE VISIT ID. The event bus redelivers; that is not a failure, it is how at-least-once
delivery works. A second delivery must not double-count a visit into the engagement score or
re-learn the same interval — which would halve the customer's estimated cycle on a bus hiccup.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core import adaptive, engagement
from app.core.models import Schedule, SendLog, as_row
from app.core.stores import EngagementStore, RuleStore, ScheduleStore

DAY = 86400

# Follow-up windows by service, in days. Zero means no follow-up, and zero is the DEFAULT: a car
# wash does not deserve a message asking how the wash went (spec 5.6). Held per service on the
# rule, and this is only the fallback for a service nobody configured.
NO_FOLLOW_UP = 0


@dataclass
class VisitOutcome:
    """What consuming one visit changed. Returned rather than logged so the caller can assert on
    it — a scheduler whose effects are only visible in a log is a scheduler nobody can test."""
    scheduled: list[str]
    cancelled: int = 0
    learned: list[str] = None            # service ids whose interval moved
    anomalies: list[str] = None
    duplicate: bool = False

    def __post_init__(self) -> None:
        self.learned = self.learned or []
        self.anomalies = self.anomalies or []


class Scheduler:
    """Turns visits into schedules. Holds no state; every dependency is passed in."""

    def __init__(self, *, store, cfg: adaptive.AdaptiveConfig,
                 eng_cfg: engagement.EngagementConfig,
                 default_interval_days: float = 90.0, lead_days: float = 7.0) -> None:
        self._store = store
        self._sched = ScheduleStore(store)
        self._rules = RuleStore(store)
        self._eng = EngagementStore(store)
        self._cfg = cfg
        self._eng_cfg = eng_cfg
        self._default = default_interval_days
        self._lead = lead_days

    async def on_visit(self, event: dict[str, Any], *, now: int,
                       service_config: dict[str, dict[str, Any]] | None = None) -> VisitOutcome:
        """Consume one `operations.visit.recorded`.

        `service_config` maps service_id -> {cycle_days, lead_days, follow_up_days, min_days,
        max_days}. Passed in rather than fetched: it comes from the tenant's own catalogue in
        operations, and a core function that calls a peer is a core function that cannot be tested.
        """
        tenant = event.get("tenant") or ""
        subject = event.get("subject_ref") or ""
        visit_id = event.get("visit_id") or ""
        services = [s for s in (event.get("service_ids") or []) if s]
        # The device clock, clamped by operations before it reached us. Falling back to `created`
        # rather than to `now` — a visit drained from an offline till happened when it happened,
        # and treating it as happening at drain time would put a week of visits on one day.
        occurred = int(event.get("occurred_at") or event.get("created") or now)
        cfgs = service_config or {}

        if not tenant or not subject or not services:
            return VisitOutcome(scheduled=[], duplicate=False)

        # ── idempotency ────────────────────────────────────────────────────────────────────────
        # The bus redelivers. A second delivery must not add points again or re-learn the same
        # gap — which would halve the customer's estimated cycle on a hiccup.
        if visit_id and await self._seen(tenant, visit_id):
            return VisitOutcome(scheduled=[], duplicate=True)

        outcome = VisitOutcome(scheduled=[])

        # ── learn, per service, BEFORE the timestamp is overwritten ────────────────────────────
        intervals: dict[str, float] = {}
        for sid in services:
            svc = cfgs.get(sid, {})
            interval, learned, anomaly = await self._learn(
                tenant, subject, sid, occurred=occurred, svc=svc)
            intervals[sid] = interval
            if learned:
                outcome.learned.append(sid)
            if anomaly:
                outcome.anomalies.append(sid)

        # ── cancel follow-ups for what was just performed ──────────────────────────────────────
        for sid in services:
            outcome.cancelled += await self._sched.cancel_kind(
                tenant, subject, sid, "follow_up",
                reason="عاد العميل قبل موعد المتابعة", now=now)

        # ── schedule ONE merged reminder ───────────────────────────────────────────────────────
        # The lead service is the one whose reminder falls EARLIEST. Not the first in the list:
        # a visit with an oil change and a tyre rotation must be reminded when the oil is due,
        # or the merged message arrives after the sooner service is already overdue.
        due_by_service = {}
        for sid in services:
            svc = cfgs.get(sid, {})
            if float(svc.get("cycle_days", intervals[sid])) <= 0 and sid not in intervals:
                continue
            due_by_service[sid] = adaptive.next_due_at(
                last_visit_at=occurred, interval_days=intervals[sid],
                lead_days=float(svc.get("lead_days", self._lead)), now=now)

        # A service with no natural cycle (a puncture repair) contributes nothing to schedule, but
        # it must not suppress the reminder for the services that do.
        cyclic = {sid: due for sid, due in due_by_service.items()
                  # A service switched off in the settings tree (spec §10.8.1) contributes no
                  # reminder. Checked HERE rather than at send time: a schedule that exists and is
                  # filtered later is a row the owner sees under "what is coming" for a service
                  # they switched off, and they would reasonably call that a bug.
                  if cfgs.get(sid, {}).get("enabled", True)
                  and float(cfgs.get(sid, {}).get("cycle_days", intervals[sid])) > 0}
        if cyclic:
            lead_sid = min(cyclic, key=lambda s: cyclic[s])
            others = [s for s in cyclic if s != lead_sid]
            sch = Schedule(
                tenant=tenant, subject_ref=subject, service_id=lead_sid, kind="reminder",
                due_at=cyclic[lead_sid], cls="service", template_type="svc_service_reminder",
                also_services=others, visit_id=visit_id,
                branch_id=event.get("branch_id") or "")
            await self._sched.upsert(tenant, sch.key, as_row(sch))
            outcome.scheduled.append(sch.key)

        # ── schedule the follow-ups that are configured ────────────────────────────────────────
        for sid in services:
            if not cfgs.get(sid, {}).get("enabled", True):
                continue
            days = int(cfgs.get(sid, {}).get("follow_up_days", NO_FOLLOW_UP) or NO_FOLLOW_UP)
            if days <= 0:
                continue
            sch = Schedule(
                tenant=tenant, subject_ref=subject, service_id=sid, kind="follow_up",
                due_at=occurred + days * DAY, cls="service",
                template_type="svc_follow_up", visit_id=visit_id,
                branch_id=event.get("branch_id") or "")
            await self._sched.upsert(tenant, sch.key, as_row(sch))
            outcome.scheduled.append(sch.key)

        # ── the visit is the strongest engagement signal there is ──────────────────────────────
        await self._credit(tenant, subject, "visit", now=now)
        await self._remember(tenant, visit_id, now)
        return outcome

    async def _learn(self, tenant: str, subject: str, service_id: str, *,
                     occurred: int, svc: dict[str, Any]) -> tuple[float, bool, bool]:
        key = f"{tenant}|{subject}|{service_id}"
        row = await self._rules.get(key)
        default = float(svc.get("cycle_days") or self._default)
        lo = float(svc.get("min_days") or self._cfg.min_days)
        hi = float(svc.get("max_days") or self._cfg.max_days)

        if row is None:
            row = {"id": f"rul_{tenant}_{service_id}", "tenant": tenant, "subject_ref": subject,
                   "service_id": service_id, "interval_days": default, "observations": 0,
                   "last_visit_at": occurred, "anomalies": 0, "updated": occurred}
            await self._rules.upsert(tenant, key, row)
            return default, False, False

        last = int(row.get("last_visit_at") or 0)
        gap_days = (occurred - last) / DAY if last else 0.0
        current = float(row.get("interval_days") or default)
        obs = int(row.get("observations") or 0)

        new, anomaly = adaptive.observe(current_days=current, observed_days=gap_days,
                                        observations=obs, cfg=self._cfg,
                                        min_days=lo, max_days=hi)
        row["interval_days"] = new
        row["last_visit_at"] = max(last, occurred)
        row["anomalies"] = int(row.get("anomalies") or 0) + (1 if anomaly else 0)
        # An anomaly is NOT an observation. Counting it would let a run of outliers graduate the
        # estimate to "learned" while nothing was actually learned from them.
        row["observations"] = obs + (0 if anomaly or gap_days <= 0 else 1)
        row["updated"] = occurred
        await self._rules.upsert(tenant, key, row)
        return new, new != current, anomaly

    async def _credit(self, tenant: str, subject: str, event: str, *, now: int) -> float:
        row = await self._eng.get(tenant, subject) or {
            "id": f"eng_{subject}", "tenant": tenant, "subject_ref": subject,
            "score": 0.0, "scored_at": now, "updated": now}
        score, at = engagement.add(
            float(row.get("score") or 0.0), scored_at=int(row.get("scored_at") or now),
            points=engagement.points_for(event, self._eng_cfg), now=now, cfg=self._eng_cfg)
        row["score"], row["scored_at"], row["updated"] = score, at, now
        await self._eng.put(tenant, subject, row)
        return score

    # ── the idempotency ledger ────────────────────────────────────────────────────────────────
    # Stored in the send log's collection under a reserved subject, so no new collection appears
    # that the backup manifest does not declare. A collection nobody declares is a collection
    # nobody backs up, and the gate that catches it only runs on collections it knows about.
    async def _seen(self, tenant: str, visit_id: str) -> bool:
        return await self._store.get("send_log", f"{tenant}|visit:{visit_id}") is not None

    async def _remember(self, tenant: str, visit_id: str, now: int) -> None:
        if not visit_id:
            return
        marker = SendLog(tenant=tenant, subject_ref="_visit_marker", cls="service", at=now,
                         outcome="consumed", reason=visit_id)
        row = as_row(marker)
        row["id"] = f"visit:{visit_id}"
        await self._store.put("send_log", f"{tenant}|visit:{visit_id}", row)
