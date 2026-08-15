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

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

# Saudi Arabia has no daylight saving, so a fixed offset is correct — the same constant as
# reminders' gate, and the same reason it is named rather than inlined.
RIYADH = timezone(timedelta(hours=3))

# How long an awareness campaign locks its audience out of another one. A DEFAULT: it is a
# judgement about how often a shop may educate the same customer, and the right answer differs
# between a workshop and a clinic. DEFAULT_AWARENESS_LOCK_DAYS overrides it.
DAY = 86400

DEFAULT_AWARENESS_LOCK_DAYS = 30


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
                 awareness_lock_days: int = DEFAULT_AWARENESS_LOCK_DAYS) -> None:
        self._s = store
        self._d = dispatcher
        self._t = telemetry
        # WHAT THE SHOP BOUGHT — asked once per tenant per pass, not once per campaign.
        #
        # THE STANDING CAMPAIGNS ARE THE HALF NOBODY PRESSES. «رجّع اللي غابوا» and «كافئ
        # المخلصين» run every day by themselves, so a subscription that lapses would otherwise
        # keep sending marketing for ever — the create route is not on that path at all.
        self._licence = licence
        # How often a shop may educate the same customer. A judgement, and a workshop is not a
        # clinic — so it comes from the deployment rather than from this file.
        self._lock_days = int(awareness_lock_days)

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
        rows, _ = await self._s.find("campaigns", {"tenant": tenant, "state": "active"},
                                     limit=200, sort=("created", "asc"))
        for row in rows:
            try:
                await self._one(row, now=now, res=res)
            except Exception as exc:                                        # noqa: BLE001
                # One campaign's failure must not stop the others. A tenant with a malformed
                # campaign would otherwise have every campaign frozen, and the symptom is "nothing
                # sends" rather than "one campaign is broken".
                res.reasons[f"خطأ في حملة: {str(exc)[:50]}"] = \
                    res.reasons.get(f"خطأ في حملة: {str(exc)[:50]}", 0) + 1
                if self._t is not None:
                    self._t.event("campaign_tick_failed", tenant=tenant,
                                  campaign=row.get("id", ""), error=str(exc)[:200])
        return res

    async def _one(self, campaign: dict[str, Any], *, now: int, res: TickResult) -> None:
        trigger = campaign.get("trigger", "manual")

        if trigger == "scheduled":
            fire_at = int(campaign.get("fire_at") or 0)
            if not fire_at or fire_at > now:
                res.skipped += 1
                return
            await self._fire(campaign, now=now, res=res)
            # DONE, not re-armed. A scheduled campaign that stayed active would fire on every tick
            # after its time passed — the same failure as the standing rule, with no guard at all.
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

        # `manual` fires from the API, never here. Reaching this branch means a manual campaign was
        # left active — harmless, and skipped rather than fired: the owner presses the button.
        res.skipped += 1

    async def _fire(self, campaign: dict[str, Any], *, now: int, res: TickResult) -> None:
        if int(campaign.get("locked_until") or 0) > now:
            # The awareness lock (spec §10.9). Skipped rather than refused: the cron is not the
            # place an owner learns about a lock — the card in their screen is.
            res.skipped += 1
            return
        out = await self._d.fire(campaign, now=now, fired_by="system")
        res.fired += 1
        res.sent += out.run.sent
        res.suppressed += out.run.suppressed
        for k, v in out.run.reasons.items():
            res.reasons[k] = res.reasons.get(k, 0) + v

        if campaign.get("cls") == "awareness" and out.run.sent:
            # LOCKED ONLY IF SOMETHING WENT OUT. Locking after a run that reached nobody would
            # cost the owner a month for a send that never happened.
            campaign["locked_until"] = now + self._lock_days * DAY
            await self._save(campaign, now)

    async def _save(self, campaign: dict[str, Any], now: int) -> None:
        campaign["updated"] = now
        await self._s.put("campaigns", f"{campaign['tenant']}|{campaign['id']}", campaign)
