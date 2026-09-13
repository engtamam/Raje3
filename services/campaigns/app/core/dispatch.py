"""Firing a campaign — and the rule that this service never sends anything itself.

CAMPAIGNS DOES NOT SEND. It resolves an audience and hands each recipient to `reminders`, which
applies spec §8.4.2: the window, the per-class caps, the marketing cooldown, the engagement tier,
and the customer's own stop. Every one of those already exists there, tested, and a second send
path here would be a second set of rules — and the second one is always the one missing a check
the day somebody adds one to the first.

THE STANDING CAMPAIGN IS WHY THIS MATTERS. A manual send is watched by the owner who pressed it; if
it misbehaves they see it and stop. A standing rule runs unattended, every day, for a year, and
could wake a thousand customers at dawn. Nobody is watching it but the gate.

IDEMPOTENT ON (campaign, run, subject). A retried run must not double-send, and a run interrupted
halfway must resume rather than start over — a campaign that re-sends its first four hundred
recipients because the pod was evicted is worse than one that sends nothing.

BOUNDED PER PASS, AND RESUMABLE. The run records what it reached; the next pass continues from
there. Progress that survives an interruption beats completeness that does not.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.adapters.datastore.drain import drain
from app.core import shape
from app.core.goal_stats import record_reach
from app.core.spread import plan as plan_spread
from app.core.models import Run, as_row, in_window


@dataclass
class DispatchResult:
    run: Run
    finished: bool = True


class Dispatcher:
    def __init__(self, *, store, sender, audience_resolver, batch: int = 200,
                 telemetry=None, daily_share: int = 0, package_offerable=None,
                 bookings_licence=None, assistant_licence=None, ai_toggle=None,
                 loyalty=None) -> None:
        self._s = store
        self._sender = sender
        self._resolve = audience_resolver
        self._batch = batch
        # THE "points" REWARD'S OWN CREDIT (occasion pilot, 2026-09-13) — OPTIONAL like every other
        # peer here: a deployment with none wired never calls `award()`, which only ever happens
        # for a campaign whose owner chose `reward_type="points"` in the first place.
        self._loyalty = loyalty
        self._t = telemetry
        # OPTIONAL — a deployment with none wired (tests, a driver not yet configured) simply never
        # runs this check; package_offer campaigns are a newer feature than this constructor.
        self._package_offerable = package_offerable
        # WHETHER THIS SHOP OWNS THE APPOINTMENT BOOK — the one input core/shape.py needs to decide
        # whether a win-back opens a booking screen or stays today's plain text. OPTIONAL for the
        # same reason `package_offerable` is: a deployment with none wired (tests, a driver not yet
        # configured) resolves every send to PLAIN, which is the behaviour that existed before this
        # parameter did.
        self._bookings_licence = bookings_licence
        # THE OTHER TWO INPUTS THE SINGLE-ITEM QUICK-REPLY BUTTON NEEDS (core/shape.py, 2026-09-13):
        # has this shop bought the smart AI assistant app at all, and did the owner switch it off
        # himself. Both OPTIONAL for the same "resolves to today's behaviour" reason as
        # `bookings_licence` — see `_card_button_allowed`'s own docstring for what "unwired"
        # degrades to.
        self._assistant_licence = assistant_licence
        self._ai_toggle = ai_toggle
        # THE CAMPAIGN'S SHARE OF TODAY'S PROVIDER CEILING — the ceiling minus what the automatic
        # engine reserved (spec §8.4.3). Deliberately a NUMBER rather than a channel: this module
        # must not learn which provider imposes it, and a test enforces that by reading this
        # source. Zero means unknown, and unknown falls back to the pass batch — the provider
        # enforces its own limit regardless, and a campaign refusing to run because we could not
        # read a number would be our outage wearing their ceiling.
        self._daily_share = int(daily_share)
        # AN IN-PROCESS CACHE OF THE REACHED-LEDGER, KEYED BY (tenant, campaign). The container
        # builds one Dispatcher and reuses it for the life of the pod, so a standing or a
        # multi-pass scheduled campaign used to pay a full drain of its own history on every single
        # fire — a set that only ever grows, re-read from scratch every five minutes for as long as
        # the campaign runs. Once this instance has drained a campaign once, `_remember` keeps the
        # cached set current, so later passes on THIS instance skip the drain entirely.
        #
        # THIS IS A PERFORMANCE CACHE, NOT THE SAFETY NET. A pod restart or a second replica starts
        # with an empty cache and drains fresh — correct, just the slow path again. And even a
        # stale cache (another replica remembered a subject this one does not know about yet) does
        # not risk a double message: the send below is keyed on `(campaign, subject)` alone, so
        # reminders' own idempotency catches a duplicate attempt regardless of what this cache
        # believes. This cache only decides whether someone is OFFERED to the sender again, never
        # whether the customer receives a second message.
        self._reached_cache: dict[str, set[str]] = {}

    async def fire(self, campaign: dict[str, Any], *, now: int, daily_share: int | None = None,
                   fired_by: str = "system") -> DispatchResult:
        """One pass over one campaign.

        Returns the run — written whether or not anything was sent, because a run that matched
        nobody is information and its absence looks like a broken cron.
        """
        tenant = campaign.get("tenant", "")
        cid = campaign.get("id", "")
        run = Run(tenant=tenant, campaign_id=cid, at=now, fired_by=fired_by)

        # THE PACKAGE'S OWN SCHEDULE, RE-ASKED FRESH — never trusted from whenever the campaign was
        # created (§ package_offer, packages feature). A manual campaign is usually fired the same
        # minute it is made, but a scheduled or standing one can sit for weeks; an owner stopping
        # the package, or its own recurring window simply ending, must silence the campaign rather
        # than advertise something that no longer exists. Checked BEFORE resolving the audience —
        # refusing here costs nothing an audience read would have spent for nothing.
        package_id = str(campaign.get("package_id") or "")
        if package_id and self._package_offerable is not None:
            if not await self._package_offerable.offerable(tenant, package_id, now):
                run.reasons["الباقة لم تعد متاحة"] = 0
                await self._save(run, goal=str(campaign.get("goal") or ""))
                return DispatchResult(run=run, finished=True)

        # THE OWNER'S OWN WINDOW (`Campaign.window_*`, offer goals only) — re-checked every pass,
        # never decided once at creation, the same "ask again" discipline the package re-check
        # above already follows. `finished=False`, deliberately unlike the package-gone-away
        # case: the window is not a permanent refusal, only a "not yet, come back next tick" —
        # the campaign stays active and the next 15-minute pass tries again.
        if not in_window(
            start_hour=int(campaign.get("window_start_hour") or 0),
            end_hour=int(campaign.get("window_end_hour") if campaign.get("window_end_hour") is not None else 24),
            weekdays=campaign.get("window_weekdays") or None,
            now=now,
        ):
            run.reasons["خارج نافذة الحملة"] = 0
            await self._save(run, goal=str(campaign.get("goal") or ""))
            return DispatchResult(run=run, finished=False)

        reached = await self._already_reached(tenant, cid)
        audience = await self._resolve(campaign, already_reached=reached, now=now)
        run.matched = audience.count
        # Everyone the rule matched and the gate would refuse. Counted into the run so the report
        # explains the difference between "matched" and "sent" instead of leaving a gap.
        run.suppressed += audience.excluded
        if audience.excluded:
            run.reasons["البوابة رفضتها قبل الإرسال"] = audience.excluded

        # SPREAD ACROSS DAYS RATHER THAN FAILING AT THE CEILING. Ten thousand recipients against a
        # share of two thousand is five days whether we plan it or not; the only question is
        # whether the system does it deliberately or the shop discovers it as a list of failures.
        # PER TENANT AND PER DAY, so it arrives with the call rather than with the process. The
        # constructor's value was never passed by anything, and it could not have been right if it
        # had been: the share is the shop's own ceiling minus the engine's reserve minus what has
        # already gone today — three numbers from three services, none of them the same for two
        # shops. The preview computes it exactly this way, and the two now agree instead of the
        # screen promising a spread the sender did not perform.
        # ZERO IS AN ANSWER, AND `None` IS THE ABSENCE OF ONE (ج-3). `share.py` returns
        # `per_day=0, known=True` when the shop's ceiling is fully spent — a real, correct,
        # deliberate zero — and this line used to read it with `or`, which is falsy for exactly
        # that value. So the preview refused with «لا تتوفر مساحة اليوم» and the sender, told the
        # same thing, fell through to the pass batch and pushed 200 messages past the ceiling.
        # The failures then landed on whichever message went last, which is a customer's
        # confirmation rather than the campaign that caused it.
        if daily_share is not None:
            per_pass = daily_share
        else:
            per_pass = self._daily_share or self._batch

        # THE SPREAD REFUSAL IS ENFORCED HERE, NOT ONLY DRAWN IN THE PREVIEW (ج-4).
        #
        # `spread.plan` decides whether a campaign can reach everyone before its offer expires,
        # and it names the two remedies — shrink the audience, or extend the date — because only
        # the owner can choose between them. The preview called it and showed the sentence. The
        # launch called nothing: ten thousand recipients against a share of five hundred and an
        # offer that ends in five days sent ~2,500 and left 7,500 queued for an offer that had
        # expired, each one a message the shop pays for and a customer who is told about a
        # discount he cannot have.
        #
        # AT FIRE, so both paths are covered: the press and the cron. A refusal from the button
        # alone would be the same defect with better odds.
        if per_pass > 0 and int(campaign.get("expires_at") or 0):
            sp = plan_spread(audience=audience.count, available_per_day=per_pass,
                             expires_at=int(campaign.get("expires_at") or 0), now=now)
            if sp.refused:
                # NOTHING IS SENT, and the run says why in the owner's own words. A partial send
                # would be the outcome the refusal exists to prevent, performed anyway.
                run.reasons[sp.refused] = audience.count
                await self._save(run, goal=str(campaign.get("goal") or ""))
                return DispatchResult(run=run, finished=True)

        # WHAT SHAPE THIS CAMPAIGN'S MESSAGES TAKE — asked ONCE, here, not once per recipient. It
        # is a property of the shop (does it own the appointment book) and of the text (is this one
        # of the three that end in «come back»), and neither changes between two candidates of the
        # same pass. A thousand-recipient run must not become a thousand billing calls.
        opens_booking = await shape.opens_booking_for(
            tenant, str(campaign.get("template_type") or ""), licence=self._bookings_licence)
        # WHETHER THE SINGLE-ITEM QUICK-REPLY BUTTON MAY SHOW AT ALL (2026-09-13) — asked once per
        # pass, same reasoning as `opens_booking` above. Deliberately NOT gated on `template_type
        # in BOOKING_TYPES` the way `opens_booking_for` is: the button is a shop-wide capability
        # question ("can ANYTHING answer a tap"), not "does this particular text end in come back"
        # — a loyalty-activation or announcement send should offer the same button a win-back one
        # does, once the shop can actually act on it.
        card_button = await self._card_button_allowed(tenant)

        sent_this_pass = 0
        for candidate in audience.candidates:
            if sent_this_pass >= per_pass:
                # BOUNDED. The run is saved with what it reached and the next pass continues —
                # a campaign that re-sends its first four hundred recipients because the pod was
                # evicted is worse than one that sends nothing.
                await self._save(run, goal=str(campaign.get("goal") or ""))
                return DispatchResult(run=run, finished=False)

            # THE KEY IS (campaign, subject) AND IT IS GENERATED BEFORE THE CALL. A timeout is
            # not evidence that nothing was sent, and the customer must not pay for our uncertainty
            # with a duplicate.
            #
            # AND `run.id` IS NOT IN IT ANY MORE, which was the whole defect. Every pass and every
            # retry opens a NEW run, so a send that timed out — but arrived — was re-sent under a
            # fresh key the moment the campaign was fired again: the customer got the same offer
            # twice, and the shop paid twice against its cap. The key that protects a customer from
            # our uncertainty cannot be derived from the attempt that is uncertain.
            #
            # ONE CAMPAIGN REACHES ONE PERSON ONCE — which is also what `_already_reached` says in
            # the other direction, so the two now agree instead of one quietly undoing the other.
            key = f"cmp:{cid}:{candidate.subject_ref}"
            reward_type = str(campaign.get("reward_type") or "discount")
            reward_points = int(campaign.get("reward_points") or 0)
            # THE "points" REWARD'S OWN CREDIT — fired ONCE per (campaign, recipient), on the SAME
            # key the send below is idempotent on, so a retried pass never double-credits.
            #
            # BEFORE THE SEND, AND ITS OWN FAILURE MUST NOT CANCEL THE SEND. loyalty's own route
            # docstring says plainly "no send happens here" — that is exactly why this caller is
            # what actually has to fire it, and a lapsed licence or an unreachable peer answering
            # `earned: 0` is loyalty's own true answer, not a reason to withhold a message the
            # audience resolver already counted and the owner already paid for. The message's own
            # composed sentence describes what the campaign INTENDED to give; the ledger there is
            # what actually happened, and the two are allowed to disagree the way any courtesy
            # credit can fail quietly without cancelling the news it rode in on.
            if reward_type == "points" and reward_points > 0 and self._loyalty is not None:
                await self._loyalty.award(
                    tenant=tenant, subject_ref=candidate.subject_ref, points=reward_points,
                    idempotency_key=key, reason=str(campaign.get("goal") or ""), actor="campaigns",
                    branch_id=str(campaign.get("branch_id") or ""))
            # THE SAME KEY AGAIN, AS THIS SEND'S FLOW TOKEN — see core/shape.py on why it is not
            # minted separately. PLAIN (both fields empty) for every send that opens nothing, which
            # reminders' sender omits from the wire body entirely.
            scope_ids = list(campaign.get("scope_service_ids") or [])
            campaign_kind = "package" if campaign.get("goal") == "package_offer" else "service"
            send_shape = shape.for_send(
                opens_booking=opens_booking, idempotency_key=key,
                template_type=str(campaign.get("template_type") or ""),
                card_count=len(scope_ids),
                item_id=scope_ids[0] if len(scope_ids) == 1 else "",
                kind=campaign_kind, card_button_allowed=card_button)
            try:
                outcome = await self._sender.send(
                    tenant=tenant,
                    subject_ref=candidate.subject_ref,
                    template_type=campaign.get("template_type", ""),
                    cls=campaign.get("cls", "marketing"),
                    owner_text=campaign.get("owner_text", ""),
                    idempotency_key=key,
                    # THE SAME END DATE FOR EVERY RECIPIENT OF THIS CAMPAIGN. A spread run reaches
                    # people over several days, and an expiry counted from each person's send would
                    # give the last recipient longer than the first — the shop would be running two
                    # different offers without deciding to.
                    offer_expires_at=int(campaign.get("expires_at") or 0),
                    offer_services=list(campaign.get("scope_service_ids") or []),
                    # THE OFFER'S VALUE, TYPED — see rendering.campaign_slots. Empty until the
                    # screen collects it (#244); a template that needs it then refuses to render
                    # rather than sending «خصم » with a hole where the number belongs.
                    offer_value=str(campaign.get("offer_value") or ""),
                    service_names=list(campaign.get("scope_service_names") or []),
                    # WHICH OF THREE REWARDS THIS CAMPAIGN GIVES — see rendering.campaign_slots'
                    # own "reward" branch for the composed sentence each produces.
                    reward_type=reward_type,
                    reward_points=reward_points,
                    # THE CAMPAIGN'S OWN BRANCH. It already narrows the audience; it must also
                    # decide the number the message leaves from, or a branch campaign speaks in the
                    # head office's voice and the reply lands on a team that cannot answer it.
                    branch_id=str(campaign.get("branch_id") or ""),
                    # THE BOOKING SCREEN UNDER THE OFFER, for a shop that owns the appointment
                    # book. Empty on every other send, and an empty token never reaches the wire.
                    flow_token=send_shape.flow_token,
                    flow_action_data=dict(send_shape.flow_action_data),
                    # THE SINGLE-ITEM QUICK-REPLY BUTTON (2026-09-13) — see core/shape.py's own
                    # docstring on `for_send`. Empty on every send that isn't this exact case; an
                    # empty `button_item_id` never reaches the wire (`HttpSender.send` below).
                    button_item_id=send_shape.button_item_id,
                    button_kind=send_shape.button_kind)
            except Exception as exc:                                        # noqa: BLE001
                # ONE RECIPIENT'S FAILURE MUST NOT END THE RUN. The alternative is one bad row
                # stopping a campaign for every other customer, indefinitely, and the symptom is
                # "the campaign does not work" rather than "one recipient failed".
                run.failed += 1
                _count(run.reasons, f"تعذّر الإرسال: {str(exc)[:60]}")
                if self._t is not None:
                    self._t.event("campaign_send_failed", tenant=tenant, campaign=cid,
                                  error=str(exc)[:200])
                continue

            if outcome.get("sent"):
                run.sent += 1
                await self._remember(tenant, cid, candidate.subject_ref, now)
            else:
                # THE GATE'S OWN REASON, VERBATIM. Rewriting it here would mean two vocabularies
                # for the same refusal, and the owner reading the report would be told something
                # subtly different from what actually happened.
                run.suppressed += 1
                _count(run.reasons, outcome.get("reason") or "امتنعت بلا سبب مذكور")
            sent_this_pass += 1

        await self._save(run, goal=str(campaign.get("goal") or ""))
        return DispatchResult(run=run, finished=True)

    # ── the dedup ledger ──────────────────────────────────────────────────────────────────────
    async def _card_button_allowed(self, tenant: str) -> bool:
        """The single-item quick-reply button (2026-09-13) promises an action — SOMETHING has to be
        alive to receive the tap. That means the shop owns BOTH the appointment book (the same
        entitlement `opens_booking_for` checks) AND a live smart AI assistant app: bought
        (the assistant app's own entitlement) and not switched off by its own owner (`ai_toggle`).

        BOTH OPTIONAL, LIKE `bookings_licence` — a deployment with neither wired resolves this to
        `False` (no button), never `True`: a button this service cannot actually verify is safe
        must not be offered on the strength of an absent check. `bookings_licence` unwired already
        made `opens_booking_for` answer `False` for the same reason.
        """
        if self._bookings_licence is None or self._assistant_licence is None:
            return False
        owns_bookings = await self._bookings_licence.allowed(tenant)
        if not owns_bookings:
            return False
        owns_assistant = await self._assistant_licence.allowed(tenant)
        if not owns_assistant:
            return False
        if self._ai_toggle is None:
            return True
        return await self._ai_toggle.enabled(tenant)

    # WHO THIS CAMPAIGN HAS ALREADY REACHED, kept per (campaign, subject) rather than as a flag on
    # the customer. A flag would have to be cleared by something, and whatever clears it is the
    # bug — this needs no cleanup and is correct after a restore.
    async def _already_reached(self, tenant: str, campaign_id: str) -> set[str]:
        # DRAINED, AND IT USED TO BE `limit=10000, sort=("at","asc")`. Ten thousand rows, OLDEST
        # first, cursor discarded — so the moment a campaign passed ten thousand recipients, the
        # people it had reached MOST RECENTLY fell out of this set. They were sent to again on the
        # next pass, and again on the one after, for the life of the campaign. The run counted
        # them as `sent` like anyone else; nothing in the report could tell them apart.
        #
        # This set decides whether a real person is messaged twice. It is exactly the kind of set
        # that must never be a page.
        #
        # DRAINED ONCE PER INSTANCE, THEN GROWN LOCALLY (see `self._reached_cache` above).
        # `_remember` keeps the cached copy current, so a repeat pass on the same Dispatcher
        # returns the cache instead of re-reading the whole ledger every time.
        cache_key = f"{tenant}|{campaign_id}"
        cached = self._reached_cache.get(cache_key)
        if cached is not None:
            return cached
        rows = await drain(self._s, "campaign_reached",
                           {"tenant": tenant, "campaign_id": campaign_id}, sort=("at", "asc"))
        reached = {r.get("subject_ref", "") for r in rows if r.get("subject_ref")}
        self._reached_cache[cache_key] = reached
        return reached

    async def _remember(self, tenant: str, campaign_id: str, subject: str, now: int) -> None:
        key = f"{tenant}|{campaign_id}|{subject}"
        await self._s.put("campaign_reached", key, {
            "id": key, "tenant": tenant, "campaign_id": campaign_id,
            "subject_ref": subject, "at": now})
        # KEEP THE CACHE IN STEP WITH WHAT WAS JUST WRITTEN, so the next `_already_reached` call on
        # this instance (later in the same pass, or on the next tick) sees this subject without a
        # re-drain. Only touches the cache if a prior call already populated it for this campaign —
        # nothing to keep in step with otherwise.
        cache_key = f"{tenant}|{campaign_id}"
        cached = self._reached_cache.get(cache_key)
        if cached is not None:
            cached.add(subject)

    async def _save(self, run: Run, *, goal: str = "") -> None:
        await self._s.put("campaign_runs", run.key, as_row(run))
        # THE RAIL'S OWN "N وصلهم" — a side counter (app.core.goal_stats), updated at the ONE
        # place every run of every trigger (standing, scheduled, manual) is persisted, so this
        # cannot go stale by missing a firing path a second, independent counter would have to be
        # copied into. `goal` is empty only for a campaign row so old it predates the field
        # entirely — that run's own `sent` is simply never counted under any goal, never guessed.
        if run.sent:
            await record_reach(self._s, run.tenant, goal, run.sent)


def _count(reasons: dict[str, int], reason: str) -> None:
    # Truncated so one long peer error cannot make a report unreadable, and counted rather than
    # listed: an owner needs "3 deferred for the daily cap", not three identical lines.
    k = reason[:80]
    reasons[k] = reasons.get(k, 0) + 1
