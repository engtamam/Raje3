"""The heartbeat: scheduled campaigns fire, standing rules evaluate once a day.

WITHOUT THE CRON THIS SERVICE IS INERT AND LOOKS HEALTHY. Campaigns exist, the API is green, every
probe passes — and nothing ever fires. There is no symptom until an owner asks why the win-back
campaign they set up in March has never sent anything.

THE ONE-A-DAY GUARD IS THE WHOLE FILE. A standing rule means "evaluate this daily". The cron runs
every five minutes. Without a guard that is twelve evaluations an hour — and a win-back campaign
would send to the same customer twelve times before lunch, each send perfectly legal by its own
logic.

The guard is `last_evaluated` ON THE CAMPAIGN, not a flag in a side table. A flag somewhere else is
the flag that gets lost: a restore that misses it, a cleanup that clears it, a migration that
forgets it — and each of those turns a daily rule into an hourly one, quietly, at scale.

AND IT IS A DAY BOUNDARY, NOT AN ELAPSED 24 HOURS. "Once a day" to an owner means once per calendar
day in Riyadh; twenty-four hours from the last run drifts forward every day until a morning
campaign is firing at night.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from app.adapters.datastore.drain import drain
from app.core import milestone

# Saudi Arabia has no daylight saving, so a fixed offset is correct — the same constant as
# reminders' gate, and the same reason it is named rather than inlined.
from app.core.riyadh import RIYADH


@dataclass
class TickResult:
    evaluated: int = 0
    fired: int = 0
    sent: int = 0
    suppressed: int = 0
    skipped: int = 0
    reasons: dict[str, int] = field(default_factory=dict)


def same_day(a: int, b: int) -> bool:
    """Whether two epochs fall on the same Riyadh calendar day.

    A calendar boundary, not an elapsed 24 hours: "once a day" to an owner means once per day, and
    twenty-four hours from the last run drifts forward until a morning campaign fires at night.
    """
    if not a or not b:
        return False
    da, db = datetime.fromtimestamp(a, RIYADH), datetime.fromtimestamp(b, RIYADH)
    return da.date() == db.date()


class Tick:
    def __init__(self, *, store, dispatcher, telemetry=None, licence=None,
                 share_reader=None) -> None:
        self._s = store
        self._d = dispatcher
        self._t = telemetry
        # WHAT THE SHOP BOUGHT — asked once per tenant per pass, not once per campaign.
        #
        # THE STANDING CAMPAIGNS ARE THE HALF NOBODY PRESSES. «رجّع اللي غابوا» and «كافئ
        # المخلصين» run every day by themselves, so a subscription that lapses would otherwise
        # keep sending marketing for ever — the create route is not on that path at all.
        self._licence = licence
        # TODAY'S SHARE FOR ONE SHOP, as a callable rather than as three peer clients: this file
        # must not learn which service holds the ceiling, which holds the reserve, or which counts
        # what has gone. `None` means unknown, and unknown falls back to the pass batch — the
        # provider enforces its own limit regardless, and a campaign refusing to run because we
        # could not read a number would be our outage wearing their ceiling.
        self._share_reader = share_reader

    async def _share_for(self, tenant: str) -> int | None:
        """Today's share, or `None` when it could not be read (ج-3).

        UNKNOWN AND ZERO ARE DIFFERENT ANSWERS, and returning 0 for both is what let a spent
        ceiling read as «nobody told me» one layer down — where the sender then fell back to the
        pass batch. Zero means «send nothing this pass»; `None` means «nobody knows», and the
        sender keeps its own bound rather than silencing a shop over an unreadable peer.
        """
        if not self._share_reader or not tenant:
            return None
        try:
            got = await self._share_reader(tenant)
        except Exception:                                                   # noqa: BLE001
            return None
        return None if got is None else int(got)

    async def run(self, tenant: str, *, now: int) -> TickResult:
        res = TickResult()
        # ONE QUESTION PER TENANT, BEFORE THE READ. A shop without the app has nothing here to do,
        # and asking per campaign would be one billing call per row for an answer that cannot
        # change mid-pass.
        if self._licence is not None and not await self._licence.allowed(tenant):
            # NOT AN ERROR, AND IT SAYS SO. A lapsed subscription is a decision somebody made —
            # the campaigns keep their history and their numbers, and only the sending stops
            # (§16.4.2).
            res.reasons["الحملات ليست في اشتراكك"] = 1
            return res
        # DRAINED, NOT PAGE-ONE-AND-DISCARD — fixed 2026-09-12, a real gap a QA audit found: a
        # tenant with more than the old 200-row page's worth of active campaigns had every campaign
        # past the oldest 200 silently never ticked, forever, with nothing logging the omission.
        # Same fix already made for the tick's own "which tenants have work" read (see
        # api/internal.py::_active_tenants).
        rows = await drain(self._s, "campaigns", {"tenant": tenant, "state": "active"},
                          sort=("created", "asc"))

        # CAMPAIGNS ARE INDEPENDENT, SO THEY RUN CONCURRENTLY — bounded, so a tenant with many
        # active campaigns cannot open unbounded connections to the store/sender at once. Each
        # campaign gets its OWN TickResult rather than mutating the shared one from inside the
        # gather: that keeps the merge a simple, sequential, race-free step after every campaign has
        # finished, instead of trusting concurrent tasks not to interleave badly on a shared dict.
        sem = asyncio.Semaphore(10)

        async def _one_bounded(row: dict[str, Any]) -> TickResult:
            local = TickResult()
            async with sem:
                try:
                    await self._one(row, now=now, res=local)
                except Exception as exc:                                    # noqa: BLE001
                    # One campaign's failure must not stop the others. A tenant with a malformed
                    # campaign would otherwise have every campaign frozen, and the symptom is
                    # "nothing sends" rather than "one campaign is broken".
                    key = f"خطأ في حملة: {str(exc)[:50]}"
                    local.reasons[key] = local.reasons.get(key, 0) + 1
                    if self._t is not None:
                        self._t.event("campaign_tick_failed", tenant=tenant,
                                      campaign=row.get("id", ""), error=str(exc)[:200])
            return local

        for local in await asyncio.gather(*(_one_bounded(row) for row in rows)):
            res.evaluated += local.evaluated
            res.fired += local.fired
            res.sent += local.sent
            res.suppressed += local.suppressed
            res.skipped += local.skipped
            for k, v in local.reasons.items():
                res.reasons[k] = res.reasons.get(k, 0) + v
        return res

    async def _one(self, campaign: dict[str, Any], *, now: int, res: TickResult) -> None:
        trigger = campaign.get("trigger", "manual")

        if trigger == "scheduled":
            fire_at = int(campaign.get("fire_at") or 0)
            if not fire_at or fire_at > now:
                res.skipped += 1
                return
            result = await self._fire(campaign, now=now, res=res)
            # DONE, not re-armed — but only once it IS done. A pass is bounded by the campaign's
            # share of the day's ceiling, so a campaign to eight hundred people reaches two hundred
            # and returns `finished=False`. Closing it there told the owner it had run, and the
            # other six hundred were never contacted by anything: the flag existed, was returned,
            # and nobody read it.
            #
            # Left active, the next tick continues it — and `_already_reached` means nobody is
            # contacted twice.
            if result.finished:
                campaign["state"] = "done"
                await self._save(campaign, now)
            return

        if trigger == "milestone":
            # EVERY TICK, NEVER THROTTLED — unlike `standing`'s once-a-Riyadh-day guard. A shared
            # counter can cross its threshold at any minute, and a shop watching «62/100» wants
            # the reveal the moment it happens, not up to a day late.
            res.evaluated += 1
            result = await self._fire(campaign, now=now, res=res)
            if not result.finished:
                # STILL MID-COHORT (a large reveal against a small per-pass cap) — more to send
                # next pass, same resumable shape a large `scheduled` campaign already has. Never
                # ends the round early over this.
                return
            tenant, cid = campaign.get("tenant", ""), campaign.get("id", "")
            # `finished=True` HERE MEANS "this pass did not hit its per-pass send cap" — true of
            # every ordinary no-op pass while the counter is still climbing, so it is NOT by
            # itself "the round is over" the way it is for a `scheduled` campaign. Only the
            # progress record (fully drained) or the campaign's own deadline (passed, never
            # crossed) actually ends a round. A single-key progress read, not a scan.
            progress = await milestone.read_progress(self._s, tenant, cid)
            fully_drained = progress is not None and progress.fired and result.run.matched == 0
            expires_at = int(campaign.get("expires_at") or 0)
            deadline_passed = (not fully_drained and (progress is None or not progress.fired)
                              and bool(expires_at) and now > expires_at)
            if not fully_drained and not deadline_passed:
                # STILL COUNTING, STILL WITHIN ITS WINDOW — the ordinary, harmless case on every
                # tick until one of the two real endings above actually happens.
                return
            if campaign.get("milestone_recurring"):
                # A FRESH ROUND, BACK TO BACK — the next period starts exactly when this one
                # ended (`expires_at`, not `now`), so a tick that runs a little late never lets
                # gaps or drift creep into a repeating schedule. Same period length
                # (`expires_at - fire_at`) every round; `validate_milestone_recurrence` already
                # refused a recurring campaign with no real period to repeat.
                period = expires_at - int(campaign.get("fire_at") or 0)
                campaign["fire_at"] = expires_at
                campaign["expires_at"] = expires_at + max(period, 1)
                await milestone.reset_progress(self._s, tenant, cid)
                await self._save(campaign, now)
                return
            # ONE-SHOT, AND THIS ROUND IS OVER — either the whole earned cohort has been sent
            # (success), or the deadline passed with the threshold never crossed (the challenge
            # simply did not happen in time). Both are `done`; nothing here distinguishes them
            # further — `progress.fired` on the last-read row already tells the two apart for
            # anyone building a screen around this later.
            campaign["state"] = "done"
            await self._save(campaign, now)
            return

        if trigger == "standing":
            if same_day(int(campaign.get("last_evaluated") or 0), now):
                res.skipped += 1
                return
            res.evaluated += 1
            # STAMPED BEFORE THE SEND, deliberately. If the send crashes halfway the campaign is
            # still marked as evaluated today: a partial run repeated four more times before
            # midnight would send to the same customers again, and re-running tomorrow costs one
            # day while re-running now costs the customer's trust.
            campaign["last_evaluated"] = now
            await self._save(campaign, now)
            await self._fire(campaign, now=now, res=res)
            return

        # ── the manual campaign that was created and never sent ──────────────────────────────
        # This used to be one line — `res.skipped += 1`, with a comment calling it harmless
        # because «the owner presses the button». He did press it. The route writes the campaign
        # row and THEN fires inside the same request, so a pod evicted between those two steps
        # leaves a manual campaign sitting at `active` having reached nobody, and this branch was
        # the only thing that ever looked at it again. It said «skipped» for ever.
        #
        # The owner's screen shows it as فعّالة, so he does not press again; the tick refuses to
        # touch it; nothing anywhere reports it. It is the exact shape of «a row in a state it can
        # never leave», in a campaign he has already been charged the intent of.
        #
        # NEVER RUN IS THE ONLY CASE PICKED UP, and `last_evaluated` is what says so. A manual
        # campaign that HAS run is finished business — re-firing it here would be this defect's
        # mirror image, sending a second copy to everyone who already got one.
        # A FUTURE `fire_at` MEANS THIS CAMPAIGN WAS HANDED TO job-service (2026-09-12) — see
        # api/v1/campaigns.py's own create route and adapters/job_service.py. Rescuing it here too
        # would be a genuine double-fire: job-service's own delayed job will call
        # `/internal/campaigns/jobs/run` the moment it is actually due, and this scan must not
        # race it just because a manual campaign with `last_evaluated == 0` looks "never fired" —
        # for one with a future `fire_at`, that is exactly the point, not a defect.
        fire_at = int(campaign.get("fire_at") or 0)
        if fire_at > now:
            res.skipped += 1
            return

        if int(campaign.get("last_evaluated") or 0) == 0:
            res.evaluated += 1
            campaign["last_evaluated"] = now      # stamped first, for the reason above
            await self._save(campaign, now)
            result = await self._fire(campaign, now=now, res=res)
            if result.finished:
                campaign["state"] = "done"
                await self._save(campaign, now)
            return

        res.skipped += 1

    async def _fire(self, campaign: dict[str, Any], *, now: int, res: TickResult) -> Any:
        """Fire one pass. Returns the real `DispatchResult` — `.finished` is what the `scheduled`
        and manual-rescue callers read; the `milestone` branch also reads `.run.matched`, which a
        bare bool could not have carried.
        """
        # THE SHARE ON THE CRON PATH TOO, read the same way the screen reads it. `_share_for` is
        # the tick's own resolver: a campaign fired by the clock spends from the same ceiling as
        # one fired by a press, and honouring the reserve on only one of the two paths is the same
        # bug with better odds.
        out = await self._d.fire(campaign, now=now, fired_by="system",
                                 daily_share=await self._share_for(campaign.get("tenant", "")))
        res.fired += 1
        res.sent += out.run.sent
        res.suppressed += out.run.suppressed
        for k, v in out.run.reasons.items():
            res.reasons[k] = res.reasons.get(k, 0) + v

        return out

    async def _save(self, campaign: dict[str, Any], now: int) -> None:
        campaign["updated"] = now
        await self._s.put("campaigns", f"{campaign['tenant']}|{campaign['id']}", campaign)
