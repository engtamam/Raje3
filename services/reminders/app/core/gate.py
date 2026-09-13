"""May this message go out, right now, to this customer? — spec 8.4.2, in one place.

EVERY RULE IS HERE, AND THAT IS THE DESIGN. A cap checked in the tick, a window checked in the
sender, and an opt-out checked in the template layer is three places that will eventually disagree
— and the disagreement is invisible, because each one is correct on its own. One function, one
answer, and every caller must go through it.

EVERY REFUSAL CARRIES A REASON, VERBATIM AND IN ARABIC. This is not politeness. The only question
support ever gets about this service is "why didn't my customer get the message?", and "not sent"
is unanswerable. The reason string is written into the send log, shown in the owner's screen, and
is the difference between a rule and an outage.

THE ORDER OF CHECKS IS NOT ARBITRARY. Cheapest and most absolute first:

  1. The customer's own stop      — absolute, outranks everything, needs no I/O.
  2. The class is even enabled    — a class with no templates cannot be sent.
  3. Engagement tier              — one read, decides whether we may advertise at all.
  4. The quiet-hours window       — pure arithmetic on the clock, with its exemptions.
  5. The caps                     — the expensive one: it reads the ledger.
  6. The cooldown                 — same read, so it is folded into step 5.

Putting the ledger read first would mean paying for it on every message a customer has already
switched off, which is the population that grows.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from hijridate import Gregorian

from app.core import engagement as E
from app.core import holdout as H

DAY = 86400

# Saudi Arabia has no daylight saving, so a fixed offset is correct and a timezone database is not
# needed. Written as a constant rather than inlined because the day this product crosses a border
# it becomes a per-tenant setting, and a constant is a place to change.
from app.core.riyadh import RIYADH

# Message types that are a REPLY to something the customer just did, and are therefore exempt from
# the quiet-hours window (spec 8.4.2 section 1). Someone who visits at 11pm is not served by a
# confirmation that arrives after eight hours of silence — it stops being a confirmation and
# becomes a message from a shop that is closed.
#
# BY TEMPLATE TYPE, NOT BY CLASS. Reminders and follow-ups are service-class too, and neither is a
# reply to anything: they are ours, sent on our schedule, and they wait for the morning.
WINDOW_EXEMPT_TYPES = frozenset({
    # A READY-FOR-PICKUP USED TO BE HERE TOO. Still a library text with nothing to fire it — it
    # needs a booking system this product has decided not to build yet — and a window exemption
    # for a message that cannot exist is a rule nobody can test.
    #
    # `svc_booking_confirmation` NO LONGER BELONGS ON THAT LIST — a booking system exists now
    # (docs/خطة-تنفيذ-الحجوزات.md), and its confirmation is a reply to an act just taken (booking
    # made), exactly like `svc_visit_confirmation` beside it.
    "svc_visit_confirmation", "svc_booking_confirmation",
    "per_account_notice", "per_points_expiring",
    # A CODE THE SUBJECT IS WAITING ON, and a legal clock that does not stop at night. He asked
    # for his data minutes ago; holding the proof of identity until morning delays a PDPL deadline
    # to spare him a notification he is actively expecting.
    "per_dsar_code",
})

# The priority ladder (spec 8.4.2 section 4). Lower number wins when two messages compete.
PRIORITY = {"warning": 0, "personal": 1, "service": 2, "awareness": 3, "marketing": 4}

# ── the CITC-mandated marketing window, SEPARATE from Limits.window_start/end_hour above ────────
#
# THOSE HOURS (7am-10pm) ARE OUR OWN PRODUCT CHOICE, applied to every non-exempt class. THESE ARE
# A LEGAL FLOOR that applies to marketing/advertising specifically and cannot be configured away —
# found live: the general window let marketing out at 07:00-09:00, two hours the regulation bans
# outright (advertising is banned 22:00-09:00, not 22:00-07:00). Kept as separate constants rather
# than tightening `Limits.window_start_hour` for everyone, because the general window also gates
# service/personal/awareness sends this rule does not reach.
#
# AND DURING RAMADAN THE WINDOW ITSELF CHANGES — not later, not shorter, a DIFFERENT window: banned
# 01:00-12:00 rather than 22:00-09:00. A fixed constant here would be correct eleven months a year
# and silently wrong for the twelfth, so `_is_ramadan` below asks the real Hijri calendar every
# time rather than a hand-maintained date table nobody remembers to update in Sha'ban.
_MARKETING_WINDOW_START_HOUR = 9    # banned 22:00-09:00 the rest of the year
_MARKETING_WINDOW_END_HOUR = 22
_RAMADAN_MARKETING_WINDOW_START_HOUR = 12   # banned 01:00-12:00 during Ramadan
_RAMADAN_MARKETING_WINDOW_END_HOUR = 1      # next day — see the wrap handling in _marketing_window


def _is_ramadan(local_date: date) -> bool:
    """Umm al-Qura Hijri month for `local_date` — the calendar Saudi regulators and banks actually
    use, not the astronomical/tabular calendar some libraries default to (`hijri_converter`'s
    `Gregorian.to_hijri()` IS Umm al-Qura, confirmed against its own docs — not assumed)."""
    return Gregorian(local_date.year, local_date.month, local_date.day).to_hijri().month == 9


def _marketing_window(now: int) -> bool:
    """Is `now` inside the window marketing/advertising messages are legally allowed to send?
    Boolean only — unlike `_window()` below, an out-of-window marketing message is DROPPED, never
    deferred (see evaluate()'s own note on why), so there is no "next open time" to compute."""
    local = datetime.fromtimestamp(now, RIYADH)
    if _is_ramadan(local.date()):
        start, end = _RAMADAN_MARKETING_WINDOW_START_HOUR, _RAMADAN_MARKETING_WINDOW_END_HOUR
    else:
        start, end = _MARKETING_WINDOW_START_HOUR, _MARKETING_WINDOW_END_HOUR
    if end > start:
        return start <= local.hour < end
    # end <= start means the ALLOWED window wraps past midnight (the Ramadan case: allowed from
    # 12:00 through 00:59 the same night) — inside iff at or after start, OR before end.
    return local.hour >= start or local.hour < end


@dataclass(frozen=True)
class Limits:
    """The caps. Platform-owned, overridable per tenant by US with a written reason — never by an
    establishment, because a blocked number lowers the quality rating of every number we hold."""
    window_start_hour: int = 7
    window_end_hour: int = 22
    daily_service_cap: int = 1
    monthly_marketing_cap: int = 4
    monthly_awareness_cap: int = 1
    marketing_cooldown_hours: int = 72
    # Absolute ceiling across every class except personal. Four separate caps can each be satisfied
    # while their sum is five messages in a day — the cap that catches what the others let through.
    daily_total_cap: int = 2

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    # When it could go out instead. Set on a deferral; zero on an outright suppression. The
    # distinction is the whole difference between "wait" and "never", and callers act on it:
    # a deferred schedule moves, a suppressed one is closed with its reason.
    retry_at: int = 0
    tier: str = ""
    details: dict[str, Any] = field(default_factory=dict)


def evaluate(*, cls: str, template_type: str, now: int, limits: Limits,
             prefs_stopped: dict[str, bool], engagement_score: float, engagement_at: int,
             recent_sends: list[dict[str, Any]], eng_cfg: E.EngagementConfig,
             class_enabled: bool = True, marketing_consent: str = "never_asked",
             withdrawal_reachable: bool = True,
             tenant: str = "", subject_ref: str = "",
             holdout_share: int = H.DEFAULT_SHARE, holdout_enabled: bool = False) -> Decision:
    """The one decision. Pure — every input is passed in, nothing is fetched.

    Pure on purpose: this is the function whose behaviour we must be able to reason about at 2am,
    and a function that reads a datastore cannot be tested through its whole space. The caller does
    the I/O; this does the thinking.
    """
    # ── 1. the customer's own stop: absolute ──────────────────────────────────────────────────
    # Outranks the priority ladder, every cap exemption, and every class INCLUDING personal. An
    # earlier draft exempted personal because the customer started that conversation — true when
    # they started it, and not true forever. Someone who switches everything off has said what they
    # want, and keeping a channel open over their objection is not a service to them.
    if prefs_stopped.get(cls, False):
        return Decision(False, f"العميل أوقف الرسائل من نوع «{_ar(cls)}» — إيقافه مطلق ولا يُتجاوَز.")

    # ── 1b. marketing needs an EXPLICIT grant ────────────────────────────────────────────────
    # And this is the one rule here that is not ours to soften. PDPL requires prior consent for
    # direct marketing, and "did not refuse" is not consent — so the absence of a stop, which is
    # enough for every other class, is not enough for this one.
    #
    # THE TWO REFUSALS READ DIFFERENTLY ON PURPOSE. `never_asked` is somebody we have not asked,
    # and asking them is reasonable; `withdrawn` is somebody who said no, and asking again is not.
    # A single "no consent" would have merged them and invited exactly that.
    #
    # Marketing alone. Service, personal, awareness and warning keep the absent-means-allowed rule
    # (§8.4.2), because a shop that cannot confirm a visit to a new customer has no product.
    if cls == "marketing" and marketing_consent != "granted":
        if marketing_consent == "withdrawn":
            return Decision(False, "العميل سحب موافقته على العروض — لا تُرسَل ولا يُعاد سؤاله.")
        return Decision(False, "لا توجد موافقة صريحة على العروض — «لم يرفض» ليست موافقة.")

    # ── 1b-2. AND THERE MUST BE A WAY OUT, OR THERE IS NO WAY IN ────────────────────────────
    # Withdrawal must be as easy as granting — that is the rule consent.py states in its own words,
    # and it is a legal obligation rather than a courtesy. Today the whole of it is one tap at
    # `/p/{ref}/stop`, served by the portal.
    #
    # SO THE PORTAL BEING OFF IS NOT A UI DECISION. The customer page was switched off for the
    # first launch (a product call, and a reasonable one — nothing links to it yet). But switching
    # it off takes the opt-out with it, and marketing without an opt-out is a breach of both the
    # regulation and Meta's own policy for the marketing category.
    #
    # THE REFUSAL IS HERE RATHER THAN IN A RUNBOOK because a rule kept in somebody's memory is a
    # rule that survives exactly as long as that person is in the room. Service, personal,
    # awareness and warning are unaffected: none of them is direct marketing, and none of them
    # requires a one-tap stop. Turn the route back on and this clears itself.
    if cls == "marketing" and not withdrawal_reachable:
        return Decision(False, "رابط الإيقاف غير متاح — لا يخرج تسويقٌ بلا وسيلة إيقاف بنقرة.")

    # ── 1c. the measurement group (proof 2) ──────────────────────────────────────────────────
    # AFTER THE CUSTOMER'S OWN CHOICES, BEFORE EVERYTHING ELSE. Someone who switched the messages
    # off is not evidence about our engine, and asking whether he is in the holdout first would put
    # a research decision above a person's stated wish — the wrong order in every sense.
    #
    # It is checked here rather than in the tick because THIS is the one place every send passes
    # through: a rule enforced upstream is a rule some future caller forgets, and a holdout with a
    # leak is worse than no holdout — it produces a comparison that looks rigorous and is not.
    #
    # DEFAULT OFF IN THE SIGNATURE, ON IN THE PRODUCT. A caller that has not been taught about the
    # holdout must not silently withhold a tenth of a shop's messages; the composition root passes
    # the establishment's real setting.
    if holdout_enabled and H.withholds(cls, template_type) and H.is_holdout(
            tenant, subject_ref, share=holdout_share, enabled=True):
        return Decision(False, H.refusal(holdout_share),
                        details={"holdout": True, "share": holdout_share})

    # ── 2. is the class even sendable ─────────────────────────────────────────────────────────
    # The warning class ships with no templates today (spec 8.4.1). A schedule that reaches here
    # for a class with nothing to send would otherwise fail deep in the sender with a template
    # lookup error — legible here, cryptic there.
    if not class_enabled:
        return Decision(False, f"الصنف «{_ar(cls)}» غير مفعّل على المنصة حالياً — لا قالب تحته.")

    tier = E.tier(engagement_score, scored_at=engagement_at, now=now, cfg=eng_cfg)

    # ── 3. engagement ─────────────────────────────────────────────────────────────────────────
    ok, why = E.allows(cls, tier)
    if not ok:
        return Decision(False, _ar_engagement(cls), tier=tier, details={"en": why})

    # ── 4. the window ─────────────────────────────────────────────────────────────────────────
    if template_type not in WINDOW_EXEMPT_TYPES:
        # MARKETING GETS THE LEGAL WINDOW, NOT THE PRODUCT ONE — see _marketing_window's own
        # header for why these are two different things and why Ramadan changes it.
        if cls == "marketing":
            if not _marketing_window(now):
                # DEFERRED, NOT DROPPED, EXCEPT MARKETING, which is dropped, because a weekend
                # offer arriving on Tuesday is worse than no offer (spec 5.8). That asymmetry is
                # deliberate and is the one place a deferral would do harm.
                return Decision(False, "خارج وقت الإرسال المسموح للرسائل الدعائية، والعرض "
                                       "المؤجَّل يفقد معناه — فيُسقَط ولا يؤجَّل.", tier=tier)
        else:
            inside, next_open = _window(now, limits)
            if not inside:
                return Decision(False, "خارج وقت الإرسال المسموح (7 صباحاً – 10 مساءً) — يؤجَّل.",
                                retry_at=next_open, tier=tier)

    # ── 5 & 6. caps and cooldown, from one read of the ledger ─────────────────────────────────
    day_ago, month_ago = now - DAY, now - 30 * DAY

    # Personal messages are not counted and not deferred: the customer started that exchange, and
    # a points-expiry notice held back by a cap is a notice that arrives after the points expired.
    if cls != "personal":
        sent_today = [s for s in recent_sends
                      if s.get("outcome") == "sent" and int(s.get("at", 0)) >= day_ago
                      and s.get("cls") != "personal"]
        if len(sent_today) >= limits.daily_total_cap:
            return Decision(False,
                            f"بلغ الحد اليومي ({limits.daily_total_cap} رسائل) لهذا العميل.",
                            retry_at=_tomorrow_open(now, limits), tier=tier)

        if cls == "service":
            n = len([s for s in sent_today if s.get("cls") == "service"])
            if n >= limits.daily_service_cap:
                return Decision(False,
                                f"بلغ الحد اليومي للرسائل الخدمية ({limits.daily_service_cap}).",
                                retry_at=_tomorrow_open(now, limits), tier=tier)

        if cls in ("marketing", "awareness"):
            base = (limits.monthly_marketing_cap if cls == "marketing"
                    else limits.monthly_awareness_cap)
            cap = E.monthly_cap(cls, tier, base)
            n = len([s for s in recent_sends
                     if s.get("outcome") == "sent" and s.get("cls") == cls
                     and int(s.get("at", 0)) >= month_ago])
            if n >= cap:
                extra = " (نصف الحد لأن تفاعله منخفض)" if cap != base else ""
                # THE WINDOW IS THIRTY ROLLING DAYS, AND THE SENTENCE USED TO SAY «الشهري».
                # An owner reads «الشهري» as the calendar month: four messages on 2 August, and he
                # expects his 1 September campaign to go out. It does not — the window still holds
                # those four until 1 September plus two days — and what he sees is a product that
                # refuses for no reason he can check against a calendar.
                #
                # AND IT NOW SAYS WHEN, which is the part that turns a refusal into an answer.
                # The oldest send inside the window is the one whose leaving makes room.
                counted = sorted(int(s.get("at", 0)) for s in recent_sends
                                 if s.get("outcome") == "sent" and s.get("cls") == cls
                                 and int(s.get("at", 0)) >= month_ago)
                frees_at = counted[0] + 30 * DAY if counted else 0
                return Decision(
                    False,
                    f"بلغ الحد لرسائل «{_ar(cls)}» ({cap} خلال آخر 30 يوماً){extra}.",
                    retry_at=frees_at or None, tier=tier)

        if cls == "marketing":
            last = max((int(s.get("at", 0)) for s in recent_sends
                        if s.get("outcome") == "sent" and s.get("cls") == "marketing"),
                       default=0)
            cool = limits.marketing_cooldown_hours * 3600
            if last and now - last < cool:
                return Decision(False,
                                f"لم تمضِ {limits.marketing_cooldown_hours} ساعة على آخر رسالة "
                                f"دعائية.", retry_at=last + cool, tier=tier)

    return Decision(True, tier=tier)


def _window(now: int, limits: Limits) -> tuple[bool, int]:
    """Is `now` inside the sending window, and if not, when does it next open?

    Computed in Riyadh local time and returned as a UTC epoch. Doing this arithmetic in UTC would
    put the quiet hours three hours out — the classic timezone bug, and here it means messages at
    4am to real people.
    """
    local = datetime.fromtimestamp(now, RIYADH)
    if limits.window_start_hour <= local.hour < limits.window_end_hour:
        return True, 0
    if local.hour < limits.window_start_hour:
        opens = local.replace(hour=limits.window_start_hour, minute=0, second=0, microsecond=0)
    else:
        opens = (local + timedelta(days=1)).replace(
            hour=limits.window_start_hour, minute=0, second=0, microsecond=0)
    return False, int(opens.timestamp())


def _tomorrow_open(now: int, limits: Limits) -> int:
    local = datetime.fromtimestamp(now, RIYADH)
    opens = (local + timedelta(days=1)).replace(
        hour=limits.window_start_hour, minute=0, second=0, microsecond=0)
    return int(opens.timestamp())


def _ar(cls: str) -> str:
    return {"service": "خدمية", "personal": "شخصية", "awareness": "توعوية",
            "warning": "تحذيرية", "marketing": "دعائية"}.get(cls, cls)


def _ar_engagement(cls: str) -> str:
    return (f"رسائل «{_ar(cls)}» موقوفة مؤقتاً — لم يزر العميل ولم يتفاعل منذ أشهر. "
            f"الرسائل الخدمية مستمرة، وزيارة واحدة تعيد كل شيء فوراً.")


def priority(cls: str) -> int:
    return PRIORITY.get(cls, 99)


def now_epoch() -> int:
    return int(time.time())
