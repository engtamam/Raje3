""""الخطوة التالية" — one line of guidance on محلّي, chosen from many, and WHICH one changes.

THE PROBLEM THIS SOLVES. The card used to be four `if`/`elif` branches hand-written straight into
the dashboard route — no table, no priority, nothing to enumerate. A screenshot proved the cost:
one branch (a locked-feature upsell) fired for nearly every brand-new shop regardless of what the
branch above it had just said, because nothing coordinated the two. And the comment above that
chain already recorded one scenario ("weak services") being deleted by hand after it turned out to
duplicate a card that renders elsewhere — exactly the kind of drift a flat if-chain cannot resist.

SO A RULE IS A THING NOW, same shape `reminders/core/reasons.py` already proved for the same
problem (its own docstring: "seven files… each holding a template name as a literal"). Each
`NextStepRule` is `(id, category, priority, check)` — `check` is a small pure function over
`NextStepCtx`, answering "does this apply right now, and if so, what does it say". Adding a new
scenario tomorrow is one entry appended to `RULES`; nothing else in this file, the route, or the
console changes.

TEN CATEGORIES, DELIBERATELY NAMED (see `CATEGORY_*` below) rather than left as a free-text field
— the owner scanning his own history of nudges (a future screen, not built yet) needs to see WHICH
part of his shop each one was about, and a category typed as a string per rule drifts the day
somebody misspells one.

ONE PRIORITY QUEUE, NEVER A LIST ON SCREEN. `pick()` below picks exactly one primary (the highest
-priority match) and at most one secondary from a DIFFERENT category, so the card never repeats
itself across the two lines it renders. A rule that keeps matching without being acted on cools
down after `COOLDOWN_SECONDS` — see `pick()`'s own note — so the same sentence does not sit there
for ever the moment its condition stops being new information and starts being wallpaper.

AND WHAT IS STILL DELIBERATELY ABSENT (§ reasons.py's own convention: state the gap, do not fake
a rule to fill it). Two categories exist below with real content and clear room to grow, and two
sit empty on purpose rather than populated with something invented:

  · **الولاء والمكافآت** — `services/loyalty`'s own report (`core/report.py`: outstanding points,
    expired-unredeemed share, redemptions) is real and detailed, but `services/insights` holds no
    peer call to loyalty today — building one is a real port (adapter + container wiring + tests),
    not a rule. Left for the next pass rather than guessed at from data this service does not have.
  · **الإعداد الناقص** — a service with no duration, a branch never opened — these belong to
    `services/operations`, which this route never calls either, and TodayPulse (Shop.tsx) already
    surfaces the one setup gap insights CAN see (WhatsApp not connected) on its own card. A rule
    here would either duplicate that card or reach for data this service does not hold — both are
    the exact defect this file exists to stop repeating.

  الموظفين carries exactly ONE rule for the same reason: the only staff-shaped fact this service
  currently computes is `coverage["staff_performance"]` — how many visits carry an operator_id at
  all, not a workload or performance number. A real "this employee is idle" rule needs a new
  indicator this file does not invent.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# ── the ten categories, named once ───────────────────────────────────────────────────────────────
CATEGORY_VISITS = "visits"
CATEGORY_MESSAGES = "messages"
CATEGORY_AT_RISK = "at_risk"
CATEGORY_LOYALTY = "loyalty"
CATEGORY_SERVICES = "services"
CATEGORY_STAFF = "staff"
CATEGORY_BRANCHES = "branches"
CATEGORY_PLAN = "plan"
CATEGORY_SETUP = "setup"
CATEGORY_HEALTH = "health"

CATEGORY_LABEL: dict[str, str] = {
    CATEGORY_VISITS: "الزوار", CATEGORY_MESSAGES: "فعالية الرسائل",
    CATEGORY_AT_RISK: "العملاء المعرّضون للخطر", CATEGORY_LOYALTY: "الولاء والمكافآت",
    CATEGORY_SERVICES: "الخدمات", CATEGORY_STAFF: "الموظفين", CATEGORY_BRANCHES: "الفروع",
    CATEGORY_PLAN: "الاشتراك والميزات", CATEGORY_SETUP: "الإعداد الناقص",
    CATEGORY_HEALTH: "الصحة العامة",
}


@dataclass(frozen=True)
class NextStepCtx:
    """Everything a rule may read — assembled ONCE per request from reads the route already makes
    (the entitlement-filtered snapshot `values`, the plan's `audience`/`teaser`), never a fresh
    network call per rule. A rule that needs data not listed here does not exist yet; add the field
    when the read exists, not before."""

    values: dict[str, Any]
    entitlements: set[str]
    audience: dict[str, Any] | None
    teaser: dict[str, Any] | None
    multi_branch: bool
    # `snap["coverage"]["staff_performance"]` (tick.py's `_coverage()`) — attribution completeness,
    # not a workload number (see the module's own note on why الموظفين carries one rule).
    staff_coverage: dict[str, Any]
    # `snap["visits"]` — THE ONE GUARD AGAINST A REAL BUG (Tamam, screenshot: a brand-new shop
    # with zero real activity was told a service was "rarely requested"). `weak_services()` ranks
    # a shop's OWN catalogue and is correct to call every service equally weak when they are all
    # genuinely tied at zero visits over real history — but a shop that has never recorded a
    # single visit has no history to rank AT ALL, and every rule that reasons about "his own
    # distribution" must refuse to fire below a real sample, not just check that its OWN signal
    # happens to be non-empty.
    total_visits: int


@dataclass(frozen=True)
class NextStepResult:
    message: str
    cta_label: str = ""
    cta_link: str = ""
    # SAME VOCABULARY THE REST OF THE CONSOLE'S rj-ui/Badge USES (success/warning/danger/info) —
    # a fourth palette invented here would be one more thing to keep in step with the kit's own.
    tone: str = "info"


@dataclass(frozen=True)
class NextStepRule:
    id: str                                          # stable — cooldown/dismiss are keyed on it
    category: str
    priority: int                                     # higher fires first, ties broken by order
    check: Callable[[NextStepCtx], "NextStepResult | None"]


# ── ① الزوار ──────────────────────────────────────────────────────────────────────────────────
def _visits_zero(ctx: NextStepCtx) -> NextStepResult | None:
    w = ctx.values.get("visits_week") or {}
    if w.get("visits", 0) == 0 and w.get("previous") is not None:
        return NextStepResult(
            "ما سجّلت أي زيارة آخر 7 أيام — سجّل زيارتك القادمة من «تسجيل زيارة» فور دخول عميلك.",
            tone="warning")
    return None


def _visits_dropped(ctx: NextStepCtx) -> NextStepResult | None:
    w = ctx.values.get("visits_week") or {}
    cur, prev = w.get("visits"), w.get("previous")
    if isinstance(cur, int) and isinstance(prev, int) and prev >= 5 and cur <= prev * 0.7:
        drop = round((1 - cur / prev) * 100)
        return NextStepResult(
            f"زوارك نزلوا {drop}٪ عن الأسبوع اللي قبله — راجع «العملاء المعرّضون للخطر» تحت.",
            tone="warning")
    return None


def _visits_rose(ctx: NextStepCtx) -> NextStepResult | None:
    w = ctx.values.get("visits_week") or {}
    cur, prev = w.get("visits"), w.get("previous")
    if isinstance(cur, int) and isinstance(prev, int) and prev >= 5 and cur >= prev * 1.3:
        rise = round((cur / prev - 1) * 100)
        return NextStepResult(
            f"زوارك زادوا {rise}٪ عن المعتاد — فرصة تكافئ العائدين منهم الآن.",
            cta_label="كافئهم", cta_link="/messages?tab=campaigns&launch=reward_loyal",
            tone="success")
    return None


# ── ② فعالية الرسائل ──────────────────────────────────────────────────────────────────────────
def _opt_out_high(ctx: NextStepCtx) -> NextStepResult | None:
    o = ctx.values.get("opt_out_rate") or {}
    if o.get("ready") and float(o.get("rate") or 0) >= 15:
        return NextStepResult(
            f"معدل إلغاء الاشتراك {o.get('rate')} لكل ألف رسالة — راجع نبرة رسائلك قبل ما يرتفع أكثر.",
            tone="warning")
    return None


def _weak_reminder_effect(ctx: NextStepCtx) -> NextStepResult | None:
    # `ready` ALONE ONLY MEANS "THE SEND LOG WAS READABLE" — not that enough was sent for "zero
    # came back" to mean anything. A shop that sent one message and had nobody return from it is
    # not a pattern; MIN_VISITS_FOR_DISTRIBUTION is the same real-history floor `weak_services`
    # needs for the identical reason (§ module note on `total_visits`).
    if ctx.total_visits < MIN_VISITS_FOR_DISTRIBUTION:
        return None
    r = ctx.values.get("returned_after_reminder") or {}
    if r.get("ready") and not r.get("partial") and float(r.get("visits") or 0) == 0 \
            and int(r.get("window_days") or 0) > 0:
        return NextStepResult(
            "رسائلك ما رجّعت ولا عميل آخر 30 يوماً — قياسٌ حقيقي، لا تخمين. راجع محتوى الرسالة.",
            tone="warning")
    return None


def _too_few_sends_to_measure(ctx: NextStepCtx) -> NextStepResult | None:
    o = ctx.values.get("opt_out_rate") or {}
    if o.get("ready") is False and o.get("reason") == "too_few_sends":
        need = int(o.get("need") or 0) - int(o.get("sent") or 0)
        if need > 0:
            return NextStepResult(
                f"لسا ما وصلت لعدد رسائل كافٍ نقيس عليه أثرها — أرسل {need} رسالة أخرى وتظهر لك الأرقام.",
                tone="info")
    return None


# ── ③ العملاء المعرّضون للخطر ──────────────────────────────────────────────────────────────────
def _at_risk_some(ctx: NextStepCtx) -> NextStepResult | None:
    rows = ctx.values.get("at_risk")
    if isinstance(rows, list) and 1 <= len(rows) < 10:
        return NextStepResult(
            f"{len(rows)} عميل تأخروا عن دورتهم المعتادة — راسلهم قبل ما ينسوك.",
            tone="warning")
    return None


def _at_risk_many(ctx: NextStepCtx) -> NextStepResult | None:
    rows = ctx.values.get("at_risk")
    if isinstance(rows, list) and len(rows) >= 10:
        return NextStepResult(
            f"{len(rows)} عميل تأخروا عن دورتهم المعتادة — عدد يستحق حملة استرجاع كاملة، لا رسائل فردية.",
            cta_label="ابدأ حملة", cta_link="/messages?tab=campaigns&launch=win_back",
            tone="warning")
    return None


def _churn_worsening(ctx: NextStepCtx) -> NextStepResult | None:
    t = ctx.values.get("churn_rate_trend") or {}
    cur, prev = t.get("current"), t.get("previous")
    if isinstance(cur, (int, float)) and isinstance(prev, (int, float)) and cur - prev > 0.05:
        return NextStepResult(
            "نسبة العملاء المتوقفين ترتفع مقارنة بالفترة السابقة — الوقت المناسب لحملة تذكير.",
            tone="warning")
    return None


# ── ④ الخدمات ─────────────────────────────────────────────────────────────────────────────────
#: BELOW THIS MANY LIFETIME VISITS, "his own distribution" is not a distribution yet — see the
#: module's own note on `NextStepCtx.total_visits` and the bug this constant closes.
MIN_VISITS_FOR_DISTRIBUTION = 10


def _weak_services_exist(ctx: NextStepCtx) -> NextStepResult | None:
    if ctx.total_visits < MIN_VISITS_FOR_DISTRIBUTION:
        return None
    weak = ctx.values.get("weak_services")
    if isinstance(weak, list) and weak:
        return NextStepResult(
            f"{len(weak)} من خدماتك نادراً ما تُطلب — راجعها: تسعيرها، أو ذكّر بها تحديداً.",
            tone="info")
    return None


def _service_concentration(ctx: NextStepCtx) -> NextStepResult | None:
    if ctx.total_visits < MIN_VISITS_FOR_DISTRIBUTION:
        return None       # 2 visits, one per service, is not "60% of your business"
    pop = ctx.values.get("service_popularity")
    if isinstance(pop, list) and pop:
        top = pop[0]
        share = float(top.get("share") or 0)
        if share >= 0.6 and len(pop) > 1:
            return NextStepResult(
                f"خدمة واحدة تمثّل {round(share * 100)}٪ من زياراتك — منشأة متّكئة على خدمة "
                "واحدة تحتاج خطة بديلة إن تباطأت.",
                tone="info")
    return None


def _no_service_data_yet(ctx: NextStepCtx) -> NextStepResult | None:
    pop = ctx.values.get("service_popularity")
    if isinstance(pop, list) and not pop:
        return NextStepResult(
            "ما فيه بيانات خدمات كافية بعد — سجّل بضع زيارات وتبدأ التوصيات تظهر.",
            tone="info")
    return None


# ── ⑤ الموظفين — قاعدة واحدة، بصراحة (انظر توثيق الملف) ──────────────────────────────────────
def _staff_attribution_incomplete(ctx: NextStepCtx) -> NextStepResult | None:
    cov = ctx.staff_coverage or {}
    total = int(cov.get("total") or 0)
    ratio = float(cov.get("ratio") or 0)
    if total >= 20 and ratio < 0.5:
        return NextStepResult(
            "أغلب زياراتك ما تُنسب لموظف مين سواها — نسبها له من «تسجيل زيارة» ليصير عندك "
            "مقارنة أداء حقيقية بين موظفيك لاحقاً.",
            tone="info")
    return None


# ── ⑥ الفروع — لمحل متعدد الفروع فقط ─────────────────────────────────────────────────────────
def _branch_gap_wide(ctx: NextStepCtx) -> NextStepResult | None:
    if not ctx.multi_branch:
        return None
    rows = ctx.values.get("branch_rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    # EACH SIDE OF THE COMPARISON NEEDS ITS OWN REAL SAMPLE, same floor as `weak_services` and
    # `service_concentration` — a 100%-vs-0% gap from one visit apiece is not a verdict on either
    # branch, it is two coin flips.
    rates = [(r.get("name") or r.get("branch_id") or "", float(r.get("return_rate") or 0))
             for r in rows if int(r.get("visits") or 0) >= MIN_VISITS_FOR_DISTRIBUTION]
    if len(rates) < 2:
        return None
    best = max(rates, key=lambda r: r[1])
    worst = min(rates, key=lambda r: r[1])
    if best[1] - worst[1] >= 0.2:
        return NextStepResult(
            f"فرع «{worst[0]}» نسبة عودة عملائه أقل بوضوح من «{best[0]}» — قارن ما يختلف بينهما.",
            cta_label="قارن الفروع", cta_link="/branches", tone="warning")
    return None


def _branch_quiet(ctx: NextStepCtx) -> NextStepResult | None:
    if not ctx.multi_branch:
        return None
    rows = ctx.values.get("branch_rows")
    if not isinstance(rows, list) or len(rows) < 2:
        return None
    quiet = [r for r in rows if int(r.get("visits") or 0) == 0]
    # AT LEAST ONE BRANCH MUST BE ALIVE, OR "QUIET" IS EVERY BRANCH — a chain that has recorded
    # nothing anywhere yet is a shop that has not started, not one branch singled out as the
    # problem among working peers.
    active = [r for r in rows if int(r.get("visits") or 0) > 0]
    if quiet and active:
        name = quiet[0].get("name") or quiet[0].get("branch_id") or ""
        return NextStepResult(f"فرع «{name}» بلا أي زيارة مسجّلة — تأكد إنه يسجّل زياراته.",
                              tone="warning")
    return None


def _branch_unattributed(ctx: NextStepCtx) -> NextStepResult | None:
    if not ctx.multi_branch:
        return None
    unknown = ctx.values.get("branch_unknown")
    if isinstance(unknown, int) and unknown >= 10:
        return NextStepResult(
            f"{unknown} زيارة بلا فرع محدَّد — نسبها لفرعها ليصير ترتيب الفروع دقيقاً.",
            tone="info")
    return None


# ── ⑦ الاشتراك والميزات ───────────────────────────────────────────────────────────────────────
def _associations_teaser(ctx: NextStepCtx) -> NextStepResult | None:
    if ctx.teaser and ctx.teaser.get("message"):
        return NextStepResult(str(ctx.teaser["message"]), tone="info")
    return None


def _audience_ready(ctx: NextStepCtx) -> NextStepResult | None:
    if ctx.audience and ctx.audience.get("message"):
        return NextStepResult(str(ctx.audience["message"]), tone="info")
    return None


def _bundles_locked(ctx: NextStepCtx) -> NextStepResult | None:
    # THE SPECIFIC 402 THIS SERVICE SEES ON `insights.bundles` LIVES ON THE CONSOLE SIDE
    # (Shop.tsx's own `locked.bundles`, caught from that separate route's own response) — this
    # service has no read of it here, so this rule intentionally stays a stub returning None
    # until bundles' own lock state travels through the dashboard response too. Kept declared
    # (not deleted) so its slot in the category is visible rather than silently missing.
    return None


# ── ⑩ الصحة العامة — الحارسة الأخيرة، تطابق دائماً ────────────────────────────────────────────
def _all_is_well(_: NextStepCtx) -> NextStepResult | None:
    return NextStepResult(
        "وضعك ثابت ولا شي يستحق تنبيهاً الآن — جرّب تكافئ عملاءك الدائمين.",
        cta_label="كافئهم", cta_link="/messages?tab=campaigns&launch=reward_loyal", tone="success")


# HOW LONG A SHOWN-BUT-UNACTED-ON RULE STAYS DOWN-WEIGHTED before it is allowed to lead again —
# a week, so the card changes across a normal work cycle rather than nagging with the same line
# every single day, without discarding a still-true fact the instant he stops looking at it.
COOLDOWN_SECONDS = 7 * 24 * 3600
# HOW MUCH A COOLED RULE IS PENALISED — large enough that any un-cooled match always outranks it,
# small enough that a cooled rule STILL wins when it is the only thing matching at all (the "never
# silent" guarantee `_all_is_well` backstops, but a cooled real issue is more honest than the
# catch-all when nothing else is true).
_COOLDOWN_PENALTY = 1000

RULES: tuple[NextStepRule, ...] = (
    NextStepRule("visits_zero", CATEGORY_VISITS, 90, _visits_zero),
    NextStepRule("visits_dropped", CATEGORY_VISITS, 80, _visits_dropped),
    NextStepRule("visits_rose", CATEGORY_VISITS, 40, _visits_rose),

    NextStepRule("opt_out_high", CATEGORY_MESSAGES, 85, _opt_out_high),
    NextStepRule("weak_reminder_effect", CATEGORY_MESSAGES, 55, _weak_reminder_effect),
    NextStepRule("too_few_sends", CATEGORY_MESSAGES, 20, _too_few_sends_to_measure),

    NextStepRule("at_risk_many", CATEGORY_AT_RISK, 75, _at_risk_many),
    NextStepRule("at_risk_some", CATEGORY_AT_RISK, 60, _at_risk_some),
    NextStepRule("churn_worsening", CATEGORY_AT_RISK, 65, _churn_worsening),

    NextStepRule("weak_services", CATEGORY_SERVICES, 45, _weak_services_exist),
    NextStepRule("service_concentration", CATEGORY_SERVICES, 35, _service_concentration),
    NextStepRule("no_service_data", CATEGORY_SERVICES, 15, _no_service_data_yet),

    NextStepRule("staff_attribution_incomplete", CATEGORY_STAFF, 25,
                _staff_attribution_incomplete),

    NextStepRule("branch_gap_wide", CATEGORY_BRANCHES, 70, _branch_gap_wide),
    NextStepRule("branch_quiet", CATEGORY_BRANCHES, 65, _branch_quiet),
    NextStepRule("branch_unattributed", CATEGORY_BRANCHES, 20, _branch_unattributed),

    NextStepRule("associations_teaser", CATEGORY_PLAN, 30, _associations_teaser),
    NextStepRule("audience_ready", CATEGORY_PLAN, 50, _audience_ready),
    NextStepRule("bundles_locked", CATEGORY_PLAN, 30, _bundles_locked),

    # THE ONLY RULE THAT ALWAYS MATCHES — priority far below every real rule's worst-case cooled
    # score (`priority - _COOLDOWN_PENALTY`), so it never outranks a real, if stale, issue; it
    # only ever leads when NOTHING else matches at all.
    NextStepRule("all_is_well", CATEGORY_HEALTH, -_COOLDOWN_PENALTY * 10, _all_is_well),
)
BY_ID = {r.id: r for r in RULES}


def pick(ctx: NextStepCtx, first_seen: dict[str, int], *, now: int) -> dict[str, Any]:
    """The one card the screen renders, and — when there is a second, different-category match —
    the quiet line under it.

    `first_seen` IS THE ONLY STATE THIS FUNCTION READS, AND IT ANSWERS ONE QUESTION: how long has
    THIS rule been true for THIS tenant. It is never reset while a rule keeps matching (a fresh
    timestamp every render would mean a rule can never cool — see the module's own note on why a
    once-set value is kept rather than refreshed), and a dismiss ("ليس الآن") simply back-dates it
    past `COOLDOWN_SECONDS`, which is the same effect using the same field rather than a second one.
    """
    scored: list[tuple[int, NextStepRule, NextStepResult]] = []
    for rule in RULES:
        try:
            result = rule.check(ctx)
        except Exception:                                             # noqa: BLE001
            result = None                # a broken rule loses its own turn, never the screen
        if result is None:
            continue
        seen_at = first_seen.get(rule.id)
        cooled = seen_at is not None and (now - seen_at) >= COOLDOWN_SECONDS
        score = rule.priority - (_COOLDOWN_PENALTY if cooled else 0)
        scored.append((score, rule, result))

    scored.sort(key=lambda t: -t[0])
    # `_all_is_well` ALWAYS MATCHES, so `scored` is never empty — this is not a fallback branch,
    # it is the guarantee the module docstring names.
    primary_rule, primary_res = scored[0][1], scored[0][2]
    secondary = next(
        ((rule, res) for _, rule, res in scored[1:] if rule.category != primary_rule.category),
        None)

    def _view(rule: NextStepRule, res: NextStepResult) -> dict[str, Any]:
        return {"id": rule.id, "category": rule.category,
                "category_label": CATEGORY_LABEL.get(rule.category, rule.category),
                "message": res.message, "cta_label": res.cta_label, "cta_link": res.cta_link,
                "tone": res.tone}

    return {
        "primary": _view(primary_rule, primary_res),
        "secondary": _view(*secondary) if secondary else None,
    }


def next_first_seen(current: dict[str, int], picked_ids: set[str], *, now: int) -> dict[str, int]:
    """Stamp today's matches that have never been seen before; leave every existing timestamp
    exactly as it was (that stability is the whole cooldown mechanism)."""
    out = dict(current)
    for rid in picked_ids:
        out.setdefault(rid, now)
    return out


def dismiss(current: dict[str, int], rule_id: str, *, now: int) -> dict[str, int]:
    """"ليس الآن" — back-date this one rule past its own cooldown window, immediately, without
    touching any other rule's timer."""
    out = dict(current)
    out[rule_id] = now - COOLDOWN_SECONDS
    return out
