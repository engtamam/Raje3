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
from app.core import reasons as T
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


# Serialises `on_visit` per (tenant, visit_id) — added 2026-09-12, a real gap a QA audit found;
# see `on_visit`'s own docstring for the full reasoning. Short: the whole method is pure
# computation and store writes, no peer I/O, so the lock only needs to outlive one such call.
_VISIT_LOCKS = "reminders_visit_locks"
VISIT_LOCK_TTL_SECONDS = 15


class Scheduler:
    """Turns visits into schedules. Holds no state; every dependency is passed in."""

    def __init__(self, *, store, cfg: adaptive.AdaptiveConfig,
                 eng_cfg: engagement.EngagementConfig,
                 default_interval_days: float = 90.0, lead_days: float = 7.0,
                 confirm_delay_seconds: int = 600,
                 booking_confirm_delay_seconds: int = 120) -> None:
        self._store = store
        self._sched = ScheduleStore(store)
        self._rules = RuleStore(store)
        self._eng = EngagementStore(store)
        self._cfg = cfg
        self._eng_cfg = eng_cfg
        self._default = default_interval_days
        self._lead = lead_days
        self._confirm_delay = int(confirm_delay_seconds)
        # Its own, separate delay (docs/خطة-تنفيذ-الحجوزات.md §5) — a booking is confirmed on the
        # spot with the customer standing there; the visit confirmation's ten minutes answers a
        # different question ("has he left") that a booking does not ask.
        self._booking_confirm_delay = int(booking_confirm_delay_seconds)

    async def on_visit(self, event: dict[str, Any], *, now: int,
                       service_config: dict[str, dict[str, Any]] | None = None,
                       confirm_visits: bool = True,
                       rating_eligible: bool = False,
                       message_delay_seconds: int | None = None) -> VisitOutcome:
        """LOCKED PER (tenant, visit_id) — fixed 2026-09-12, a real gap a QA audit found. The
        actual work happens in `_on_visit_locked` below; this wrapper only decides whether a
        concurrent redelivery of the SAME visit gets to run it at all. The dedup check inside
        (`_seen`) used to be a plain read with the matching write (`_remember`) not landing until
        the very end of the method — a genuinely concurrent redelivery (the bus redelivers; this
        module's own docstring already says so) could pass that read on both deliveries before
        either wrote the marker, double-running `_learn`/`_credit` for one real visit.

        NOT LOCKED WHEN `visit_id` IS EMPTY — same as the dedup check it replaces (`if visit_id
        and await self._seen(...)`): an event with no visit_id was never deduplicated either, and
        there is no key to lock on.
        """
        tenant = event.get("tenant") or ""
        visit_id = event.get("visit_id") or ""
        if not tenant or not visit_id:
            return await self._on_visit_locked(
                event, now=now, service_config=service_config, confirm_visits=confirm_visits,
                rating_eligible=rating_eligible, message_delay_seconds=message_delay_seconds)

        lock_key = f"{tenant}|visit:{visit_id}"
        took = await self._store.claim(
            _VISIT_LOCKS, lock_key, {"tenant": tenant, "visit_id": visit_id},
            ttl_seconds=VISIT_LOCK_TTL_SECONDS, now=now)
        if not took:
            # Another delivery of this SAME visit is being processed right now — treated exactly
            # like the existing "already seen" case below, not an error.
            return VisitOutcome(scheduled=[], duplicate=True)
        try:
            return await self._on_visit_locked(
                event, now=now, service_config=service_config, confirm_visits=confirm_visits,
                rating_eligible=rating_eligible, message_delay_seconds=message_delay_seconds)
        finally:
            await self._store.delete(_VISIT_LOCKS, lock_key)

    async def _on_visit_locked(self, event: dict[str, Any], *, now: int,
                               service_config: dict[str, dict[str, Any]] | None = None,
                               confirm_visits: bool = True,
                               rating_eligible: bool = False,
                               message_delay_seconds: int | None = None) -> VisitOutcome:
        """Consume one `operations.visit.recorded`.

        `service_config` maps service_id -> {cycle_days, lead_days, follow_up_days, min_days,
        max_days}. Passed in rather than fetched: it comes from the tenant's own catalogue in
        operations, and a core function that calls a peer is a core function that cannot be tested.

        `confirm_visits` is the shop's own answer to "does a visit get a message on the day?".
        Passed in for the same reason — and it is a TENANT setting, not a per-service one, because
        the confirmation is keyed to the visit and a visit has several services.

        `rating_eligible` — resolved by the caller from TWO peer reads this function must not make
        itself: does this establishment own `feature.rating` (app_entitlement.py), and has it
        turned the rating app on (rating_settings.py). When true, it OVERRIDES `confirm_visits`
        entirely — see the schedule block below for why that is "instead of", never "as well as".

        `message_delay_seconds` — this shop's own configured delay for WHICHEVER message this visit
        gets (rating_settings.delay_minutes, asked of every shop, not only ones with the rating
        app — product decision: one "بعد كم دقيقة" answer for both variants of this slot, no
        longer a platform-wide constant). `None` falls back to the constructor's own default.
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

        # ── cancel what a returning customer has made untrue ───────────────────────────────────
        #
        # THE LADDER RUNGS TOO, AND THEY WERE THE ONES THAT MATTERED (د-9). This cancelled the
        # literal kind `follow_up` and nothing else, while the follow-up LADDER writes its rows as
        # `ladder_1` and `ladder_2`. So the customer came back, and days later read «صار لنا فترة
        # ما شفناك» followed by a discount — standing in the shop he had visited yesterday. The
        # shop paid a win-back discount to somebody who had already won himself back.
        LADDER_KINDS = ("ladder_1", "ladder_2")
        # ONE READ FOR THE WHOLE VISIT, NOT ONE PER (service, kind) PAIR. `cancel_kind` used to
        # call `pending_for_subject` itself — an unfiltered query that returns the SAME rows every
        # time for this customer — so a visit with three services issued nine identical reads for
        # one write path. The rows cannot change between these calls (nothing here awaits a store
        # write to this subject's schedules until a cancel fires), so one read, filtered locally
        # per call, is exactly equivalent.
        pending = await self._sched.pending_for_subject(tenant, subject)
        for sid in services:
            dropped = await self._sched.cancel_kind(
                tenant, subject, sid, "follow_up",
                reason="عاد العميل قبل موعد المتابعة", now=now, pending=pending)
            outcome.cancelled += dropped

            rungs_dropped = 0
            for kind in LADDER_KINDS:
                rungs_dropped += await self._sched.cancel_kind(
                    tenant, subject, sid, kind,
                    reason="عاد العميل قبل رنّة المتابعة", now=now, pending=pending)
            outcome.cancelled += rungs_dropped
            # AND THIS IS WHERE THE MARGIN LOCK IS EARNED — the one place in the system that can
            # see it happen, and nothing was writing it down.
            #
            # `ladder.is_locked` reads `first_rung_returns` off this row and, past the threshold,
            # stops offering a discount to somebody who comes back without one (§5.6.1). It was
            # complete, tested, and fed by a field that NOTHING in production ever incremented —
            # so the lock read 0 for every customer for ever, and the shop paid a discount to the
            # loyal exactly as it did to the lapsed. A rule that cannot be triggered is not a
            # cautious rule; it is an absent one wearing a rule's name.
            #
            # A CANCELLED FOLLOW-UP IS THE PROOF, not an inference: rungs were still pending when
            # he walked in, which means he returned on the first reminder alone. Zero cancelled
            # means either no ladder or one that already ran, and neither earns the lock.
            # AND THE LOCK COUNTS THE RUNG, NOT THE QUESTION (د-10). It used to increment on the
            # `follow_up` cancellation — «كيف كانت الخدمة», a row created on EVERY visit — which
            # measures something else entirely: a shop that enabled the question locked the ladder
            # for anybody who visited twice, so no offer ever reached anyone; a shop that left it
            # off (the default) never locked at all, so the discount went to everybody who came
            # back on their own. Two shops, two opposite wrong answers, from one wrong subject.
            #
            # A CANCELLED RUNG IS THE PROOF: rungs were still pending when he walked in, so he
            # returned on the first reminder alone and did not need a discount to do it.
            if rungs_dropped > 0:
                key = f"{tenant}|{subject}|{sid}"
                row = await self._rules.get(key)
                if row is not None:
                    row["first_rung_returns"] = int(row.get("first_rung_returns") or 0) + 1
                    row["updated"] = now
                    await self._rules.upsert(tenant, key, row)

        # ── the confirmation: the reply to what he just did ────────────────────────────────────
        #
        # THE MESSAGE THE WHOLE LIBRARY OPENS WITH, AND NOTHING CREATED IT. Three tones of
        # `svc_visit_confirmation` shipped in the seed, `gate.py` exempts the type from quiet
        # hours by name — and no line anywhere built a row of it. A visit produced a reminder in
        # ninety days and a follow-up in fifteen, and said nothing at all on the day.
        #
        # KEYED WITHOUT A SERVICE. It confirms the VISIT, not one of the services on it: a visit
        # with an oil change and a tyre rotation is one event and gets one confirmation. Keying it
        # by service would send two, which is the noise this product exists to prevent.
        #
        # AND A SECOND VISIT REPLACES IT rather than adding to it — the schedule's natural key is
        # (tenant, customer, service, kind), so the upsert is the mechanism: a customer who comes
        # back within the ten minutes gets one confirmation, for the later visit.
        # AND THE SHOP MAY SWITCH IT OFF. A barber whose customer walks out two minutes after
        # sitting down does not want a message about it; a workshop that keeps the car three days
        # does. The engine had no opinion to offer here and no switch either — every shop got the
        # confirmation whether it fit or not, and the only escape was cancelling messages one by
        # one in «رسائلي». It is a tenant setting because the confirmation belongs to the visit.
        # ONE DELAY FOR BOTH VARIANTS OF THIS SLOT (product decision, rating-app-feature.md) — a
        # shop's own "بعد كم دقيقة" answer governs whichever message this visit gets, the plain
        # confirmation and the rating request alike. It is no longer a platform-wide constant: the
        # caller resolves it per tenant (rating_settings.py's delay_minutes, asked of EVERY shop,
        # not only ones that own the rating app) and passes it in here, same reasoning
        # `service_config`/`confirm_visits` are passed in rather than fetched. `None` (an untaught
        # caller, or a test written before this existed) falls back to `self._confirm_delay` —
        # the constructor's own default, unchanged, so nothing that never passes this breaks.
        delay = message_delay_seconds if message_delay_seconds is not None else self._confirm_delay

        # THE RATING APP'S OWN MESSAGE, INSTEAD OF THE PLAIN CONFIRMATION — NEVER BOTH. Chosen
        # exclusively by what the CALLER already resolved (does this shop own `feature.rating` AND
        # has it enabled — app_entitlement.py + rating_settings.py, both peer reads a core function
        # must not make itself, same reasoning `service_config`/`confirm_visits` are passed in
        # rather than fetched here). `rating_eligible` overrides `confirm_visits` entirely: a shop
        # that turned the rating app on has made its own decision about this exact slot, superseding
        # the older plain switch rather than stacking with it — one message per visit, always.
        if rating_eligible:
            rating = Schedule(
                tenant=tenant, subject_ref=subject, service_id="", kind="rating_request",
                due_at=occurred + delay, cls="service",
                template_type=T.get("rating_requested").template_type, visit_id=visit_id,
                branch_id=event.get("branch_id") or "")
            await self._sched.upsert(tenant, rating.key, as_row(rating))
            outcome.scheduled.append(rating.key)
        elif confirm_visits:
            confirm = Schedule(
                tenant=tenant, subject_ref=subject, service_id="", kind="visit_confirmation",
                due_at=occurred + delay, cls="service",
                template_type=T.get("visit_recorded").template_type, visit_id=visit_id,
                branch_id=event.get("branch_id") or "")
            await self._sched.upsert(tenant, confirm.key, as_row(confirm))
            outcome.scheduled.append(confirm.key)

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
                due_at=cyclic[lead_sid], cls="service", template_type=T.get("service_due").template_type,
                also_services=others, visit_id=visit_id,
                asset_id=event.get("asset_id") or "",
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
                template_type=T.get("after_visit").template_type, visit_id=visit_id,
                asset_id=event.get("asset_id") or "",
                branch_id=event.get("branch_id") or "")
            await self._sched.upsert(tenant, sch.key, as_row(sch))
            outcome.scheduled.append(sch.key)

        # ── the visit is the strongest engagement signal there is ──────────────────────────────
        await self._credit(tenant, subject, "visit", now=now)
        await self._remember(tenant, visit_id, now)
        return outcome

    async def on_booking(self, event: dict[str, Any], *, now: int) -> VisitOutcome:
        """Consume one `bookings.booking.*` event (docs/خطة-تنفيذ-الحجوزات.md §5).

        SIMPLER THAN `on_visit`, AND DELIBERATELY SO — one message, one kind, no learning, no
        merge across services. `bookings` publishes on every act that changes what the customer
        should be told: `created`/`rescheduled` (re)schedule the confirmation at the booking's
        CURRENT time; `cancelled`/`attended`/`no_show` cancel a still-pending one — a confirmed
        appointment the shop closed some other way does not also need a text about the booking.

        KEYED BY `booking_id`, NOT BY SERVICE. `Schedule.key` is (tenant, subject, asset, service,
        kind); a booking has no natural "service" for that key the way a visit does, and re-using
        an empty one would collide two DIFFERENT bookings for the same customer into one row —
        the second booking's confirmation would silently cancel the first's. `service_id` carries
        `booking_id` here instead, exactly the way `asset_id` was added for vehicles: not because
        it IS a service, but because it is the field the key needs to stay unique per booking.

        NO CATCH-UP PATH, UNLIKE VISITS. A missed booking-confirmation is a smaller harm than a
        missed loyalty-earning visit event (§5's own scope), so this is the event-only fast path;
        a gap here means one confirmation text late or absent, not a silently wrong cycle. If that
        trade-off turns out wrong in practice, the fix is the same shape `ingest.py` already has
        for visits — a catch-up read against `bookings`, not a redesign of this method.
        """
        tenant = event.get("tenant") or ""
        subject = event.get("subject_ref") or ""
        booking_id = event.get("booking_id") or ""
        kind_word = event.get("kind") or ""
        if not tenant or not subject or not booking_id:
            return VisitOutcome(scheduled=[], duplicate=False)

        outcome = VisitOutcome(scheduled=[])

        if kind_word in ("cancelled", "attended", "no_show"):
            dropped = await self._sched.cancel_kind(
                tenant, subject, booking_id, "booking_confirmation",
                reason="أُغلِق الحجز قبل إرسال التأكيد", now=now)
            outcome.cancelled = dropped
            return outcome

        if kind_word not in ("created", "rescheduled"):
            return outcome   # an unrecognised kind refuses to guess rather than schedule blindly

        starts_at = int(event.get("starts_at") or 0)
        if not starts_at:
            return outcome

        from app.core.rendering import arabic_appointment

        sch = Schedule(
            tenant=tenant, subject_ref=subject, service_id=booking_id, kind="booking_confirmation",
            due_at=now + self._booking_confirm_delay, cls="service",
            template_type=T.get("booking_confirmed").template_type,
            appt_time=arabic_appointment(starts_at), booking_id=booking_id,
            branch_id=event.get("branch_id") or "")
        await self._sched.upsert(tenant, sch.key, as_row(sch))
        outcome.scheduled.append(sch.key)
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
        # AN ESTIMATE NOBODY LEARNED FOLLOWS THE CONFIGURED CYCLE, rather than freezing the guess
        # it was born with. A row created while the engine still defaulted to 90 days would
        # otherwise keep 90 for ever for a customer of a shop whose catalogue says 10 — the guess
        # outliving the correction that replaced it. Once there is a real observation the customer's
        # own rhythm owns the number and this stops applying.
        stored = float(row.get("interval_days") or default)
        current = default if int(row.get("observations") or 0) <= 0 else stored
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
