"""Growth opportunities — ONE orchestrating read that raises the average invoice, built as a
pipeline of small, independently real steps rather than five separate tools handed to the model to
chain on its own.

WHY ONE TOOL, NOT FIVE (the owner's own instruction, 2026-09-16): "المشكلة كيف نخليها خوارزمية
واحنا ما نعرف ايش علاقة المنتجات ببعض... نسوي بينهم ترابط يشتغلون مع بعض ما ننتظر الذكاء الاصطناعي
يشغلهم بحيث يرجع له تقرير كامل". A model asked to call four tools and combine their numbers itself
will occasionally skip one, mis-pair a package with the wrong price, or invent a relationship
between two results that were never validated together. `build_report()` at the bottom is the
whole chain, written once, in code — the model calls it ONCE per turn and reads a finished report;
nothing downstream of this file asks it to add, subtract or compare anything itself.

THE REPORT IS DATA FOR THE MODEL, NEVER TEXT FOR THE CUSTOMER (the owner's own instruction,
2026-09-16, discussed and confirmed explicitly): every line is plain and factual — "Package X costs
12 SAR more and earns 35 more points than booking these separately, closing 35 of the 80 points you
still need for [reward]" — never "you should really get this!". The model is the one who decides
whether this turn even calls for mentioning it, and how, exactly like every other read-only tool in
core/tools.py; this file only ever hands it real, already-verified numbers to choose from.

THE FIVE STEPS, EACH A SEPARATE FUNCTION ON PURPOSE — so a reviewer asking "why did it suggest
this" can point at exactly one function's own output, and so any one step can be tested, disabled,
or replaced without touching the others:

  1. find_structural_candidates  — which packages are even RELEVANT to this turn (contain every
                                   service already selected, or are missing exactly one that this
                                   customer's own recent visits already cover). STRUCTURAL, not
                                   statistical — a package's own component list is a fact, not a
                                   learned pattern, so this step needs no history to be exact.
  2. apply_financial_guard       — drops every candidate that would not actually SAVE the customer
                                   money over booking the same services separately. A package that
                                   fails this must never reach the model at all.
  3. apply_points_strategy       — for what survives, the real points comparison AND how much
                                   closer it gets the customer to their next reward.
  4. statistical_cross_sell      — insights' own association engine (core/associations.py there) —
                                   a DIFFERENT relationship than 1-3: not "this package contains
                                   that service", but "customers who book this also book that",
                                   learned from real visits, never manually tagged.
  5. personal_rhythm             — this customer's own learned per-service timing (due soon /
                                   lapsed) — the SAME data list_due_services/list_lapsed_services
                                   already read in core/tools.py, reused rather than re-fetched.

`build_report()` runs all five and hands `format_report()` whatever came back, in one string.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from typing import Any

# THE SAME BANDS list_due_services/list_lapsed_services ALREADY USE (core/tools.py) — imported,
# never re-typed, so a threshold changed in one place cannot quietly drift from the other reader
# of the exact same rhythm data.
from app.core.tools import _DUE_SOON_RATIO_MIN, _LAPSED_RATIO_MIN

# How far back a service still counts as "recently done" for step 1's "missing exactly one piece"
# check — a customer who did the OTHER two components of a 3-service package eight months ago is
# not "one visit away" from it in any useful sense; one who did them three weeks ago plainly is.
# 45 days, not 30: a customer on a genuinely monthly rhythm for one of the two must not fall just
# outside the window by a few days' scheduling slack.
RECENT_SERVICE_WINDOW_DAYS = 45


@dataclass(frozen=True)
class PackageCandidate:
    """One package this turn might be worth mentioning — built up field by field as it survives
    each pipeline step; a candidate `apply_financial_guard` drops never reaches step 3."""
    package_id: str
    name: str
    price_minor: int
    component_price_minor_sum: int
    service_ids: list[str]
    # "contains_selected" — every service the customer is already discussing is IN this package.
    # "missing_one" — every service but ONE is either already selected or in this customer's own
    # recent visits; `missing_service_id` names the one gap.
    kind: str
    missing_service_id: str = ""
    # Filled in by apply_financial_guard — real savings vs booking the same components separately.
    savings_minor: int = 0
    # Filled in by apply_points_strategy — 0 until that step runs.
    points_for_services: int = 0
    points_for_package: int = 0
    extra_points: int = 0
    to_next_reward_before: int = 0
    to_next_reward_after: int = 0


# ── step 1 — structural: does a real package already fit what's on the table? ──────────────────
def find_structural_candidates(*, selected_ids: list[str], recent_ids: set[str],
                               packages: list[dict[str, Any]]) -> list[PackageCandidate]:
    """`packages` is `package_catalog.list_active(tenant)`'s own real rows — the SAME list
    core/tools.py::list_packages already reads, never a second fetch of a different shape.

    A candidate here is a FACT about the package's own declared components (`service_ids`), never
    a guess: either it contains every service already selected (a straight "you're basically
    already buying this, for less"), or it is missing exactly one service the customer's own
    recent visits already cover (a real "one piece away" — never invented from thin air, since
    `recent_ids` itself only ever comes from that customer's own real rhythm data, step 5 below)."""
    selected = set(selected_ids)
    out: list[PackageCandidate] = []
    for p in packages:
        if not p.get("active"):
            continue
        if not (p.get("next_offerable_dates") or []):
            continue
        pkg_services = set(str(s) for s in (p.get("service_ids") or []))
        if not pkg_services:
            continue

        base = dict(
            package_id=str(p.get("id") or ""), name=str(p.get("name") or ""),
            price_minor=int(p.get("price_minor") or 0),
            component_price_minor_sum=int(p.get("component_price_minor_sum") or 0),
            service_ids=sorted(pkg_services))

        # "COVERED" = SELECTED THIS TURN, PLUS ALREADY DONE RECENTLY — the package's own gap
        # (`missing`) is measured against BOTH, never selected alone. A package that also
        # contains services beyond what's selected is not automatically "contains_selected" just
        # because the selected ones happen to be a subset of it — that reads a real signal into a
        # coincidence; it only counts once nothing real is missing.
        covered = selected | recent_ids
        missing = pkg_services - covered
        if selected and pkg_services & selected and not missing:
            out.append(PackageCandidate(**base, kind="contains_selected"))
        elif len(missing) == 1 and (pkg_services & covered):
            out.append(PackageCandidate(**base, kind="missing_one",
                                        missing_service_id=next(iter(missing))))
    return out


def recent_service_ids(rhythm: list[Any], *, now: int,
                       window_days: int = RECENT_SERVICE_WINDOW_DAYS) -> set[str]:
    """Every service this customer has genuinely done within the last `window_days` — read from
    the SAME rhythm rows list_due_services/list_lapsed_services already fetch (`RhythmEntry`,
    app/ports/rhythm_provider.py), never a second peer call. `is_learned` is deliberately IGNORED
    here (unlike those two tools): this only asks "did a real visit happen recently", not "is his
    INTERVAL for it a reliable estimate yet" — a customer's first-ever visit for a service is still
    a real, recent visit even before the adaptive engine trusts an interval for it."""
    cutoff = now - window_days * 86400
    return {r.service_id for r in rhythm if r.last_visit_at >= cutoff}


# ── step 2 — financial guard: never suggest a package that would not actually save money ───────
def apply_financial_guard(candidates: list[PackageCandidate]) -> list[PackageCandidate]:
    """THE WHOLE RULE, and it is the same one context_builder.py::_eligible_upsell_packages
    already enforces for the generic "mention a package" context — restated here as its own gate
    because this tool's candidates were found a DIFFERENT way (structural fit, not "every active
    package") and must be held to the identical bar: `price_minor` strictly below
    `component_price_minor_sum` means the customer would pay LESS buying the components apart, and
    a package that fails this is dropped here, permanently, before step 3 ever sees it — there is
    no such thing as "mention it anyway but downplay it"."""
    out = []
    for c in candidates:
        savings = c.component_price_minor_sum - c.price_minor
        if savings <= 0:
            continue
        out.append(_replace(c, savings_minor=savings))
    return out


# ── step 3 — points strategy: the real earn comparison, and the reward it closes the gap on ────
async def apply_points_strategy(candidates: list[PackageCandidate], *, points_summary: Any,
                                tenant: str, subject_ref: str) -> list[PackageCandidate]:
    """ONE peer call for ALL surviving candidates together (never one per candidate) — loyalty's
    own `/internal/loyalty/earn-preview` (services/loyalty/app/api/internal.py) takes a batch of
    package ids for exactly this reason. `points_for_package` is the shop owner's OWN explicit
    override for that package — never derived from its price, because loyalty's own EarnTree
    deliberately keeps no such relationship (a package can be priced for margin and pointed for
    loyalty independently) — see that route's own docstring.

    `points_for_services` is priced as ONE ordinary multi-service visit covering every component
    the package itself declares (`EarnTree.points_for`) — the fair "if he booked all of these
    separately, on one visit, the normal way" baseline; never multiplied per booking, which would
    overcount against a package that is also exactly one visit."""
    if not candidates or points_summary is None:
        return candidates
    all_service_ids = sorted({sid for c in candidates for sid in c.service_ids})
    package_ids = [c.package_id for c in candidates]
    try:
        preview = await points_summary.earn_preview(
            tenant=tenant, service_ids=all_service_ids, package_ids=package_ids)
        gap = await points_summary.points_and_gap(tenant=tenant, subject_ref=subject_ref)
    except Exception:                                                        # noqa: BLE001
        # A peer hiccup here must not drop candidates the financial guard already cleared — it
        # only means their points numbers stay at zero, same "absent, never guessed" posture
        # every other optional-peer read in this service already takes.
        return candidates

    by_pkg = preview.get("points_by_package") or {}
    balance = int(gap.get("points") or 0)
    to_next_before = int(gap.get("to_next_reward") or 0)

    # ONE "book these separately" BASELINE, SHARED ACROSS CANDIDATES — `points_for_services` above
    # priced every id from every surviving candidate together as one batch (loyalty's own
    # `EarnTree.points_for` returns a whole-visit total, never a per-service breakdown — see that
    # method's own docstring on why a visit resolved through several levels has no single
    # "source"). This is EXACT for the overwhelmingly common case (one selection matches one or
    # two packages whose components mostly overlap) and a documented, honest UPPER BOUND on the
    # rare turn where several candidates share the batch but do not fully overlap — never an
    # invented per-candidate split loyalty was never asked for.
    points_separate = int(preview.get("points_for_services") or 0)

    out = []
    for c in candidates:
        points_package = int(by_pkg.get(c.package_id) or 0)
        extra = points_package - points_separate
        # CLAMPED ON BOTH ENDS — never below 0 (already there), and never ABOVE the real starting
        # gap: a package earning FEWER points than booking separately (`extra` negative) must
        # simply report no progress, never a gap wider than reality already was before this
        # candidate was ever considered.
        to_next_after = min(to_next_before, max(0, to_next_before - extra)) if to_next_before > 0 else 0
        out.append(_replace(
            c, points_for_services=points_separate, points_for_package=points_package,
            extra_points=extra, to_next_reward_before=to_next_before,
            to_next_reward_after=to_next_after))
    return out


# ── step 4 — statistical cross-sell: insights' own association engine, a DIFFERENT relationship ─
async def statistical_cross_sell(*, tenant: str, service_ids: list[str], related_services: Any,
                                 names_by_id: dict[str, str]) -> list[str]:
    """"Customers who book this also book that" — LEARNED from real co-occurrence across real
    visits (services/insights/app/core/associations.py), never a package's own declared
    components (step 1) and never manually tagged. One real, named service per line, nothing
    invented — the same peer core/tools.py::suggest_related_service already calls, reused here so
    this report and that standalone tool never disagree about what insights actually found."""
    if related_services is None:
        return []
    lines: list[str] = []
    for sid in service_ids:
        try:
            related_ids = await related_services.related_to(tenant, sid)
        except Exception:                                                    # noqa: BLE001
            continue
        for rid in related_ids[:3]:
            if rid.startswith("pkg:"):
                continue   # packages are step 1's own, structural job — never double-counted here
            name = names_by_id.get(rid, rid)
            base_name = names_by_id.get(sid, sid)
            lines.append(f"عملاء يطلبون «{name}» غالباً مع «{base_name}» (ارتباط إحصائي حقيقي).")
    return lines


# ── step 5 — this customer's own timing, reused verbatim from list_due_services/list_lapsed ────
def personal_rhythm(rhythm: list[Any], *, now: int,
                    names_by_id: dict[str, str]) -> dict[str, list[str]]:
    """The identical bands core/tools.py::list_due_services/list_lapsed_services already use
    (`_DUE_SOON_RATIO_MIN`/`_LAPSED_RATIO_MIN`, imported above, never re-typed) — this is the SAME
    computation, just returning both bands together instead of as two separate tool calls, so this
    one report can note "due soon" and "clearly stopped" in the same pass."""
    due: list[str] = []
    lapsed: list[str] = []
    for r in rhythm:
        if not r.is_learned or r.interval_days <= 0 or r.last_visit_at <= 0:
            continue
        ratio = (now - r.last_visit_at) / 86400 / r.interval_days
        name = names_by_id.get(r.service_id, r.service_id)
        if _DUE_SOON_RATIO_MIN <= ratio < _LAPSED_RATIO_MIN:
            due.append(name)
        elif ratio >= _LAPSED_RATIO_MIN:
            lapsed.append(name)
    return {"due": due, "lapsed": lapsed}


# ── assembly — plain, factual, never persuasive; the model decides tone and timing, not this ───
def format_report(*, candidates: list[PackageCandidate], cross_sell: list[str],
                  rhythm: dict[str, list[str]]) -> str:
    """Every line here is a FACT with real numbers, never an instruction to the model on how to
    feel about it — "costs more, earns more, closes the gap by this much" is a sentence a model
    can choose to relay warmly, mention once in passing, or not bring up at all this turn. Nothing
    here says "recommend this" or "the customer should".

    EMPTY SECTIONS ARE OMITTED, NOT PRINTED AS ZEROES — a report that found nothing in one category
    says nothing about that category, exactly like every other read-only tool's own "لا يوجد شيء
    هنا الآن" convention elsewhere in this file — never a header over an empty list."""
    lines: list[str] = []

    if candidates:
        lines.append("باقات تستحق الذكر:")
        for c in candidates:
            riyals_savings = c.savings_minor / 100
            sentence = f"- «{c.name}»: توفير حقيقي {riyals_savings:g} ر.س عن حجز نفس الخدمات منفردة"
            if c.kind == "missing_one":
                sentence += f" (تحتاج فقط إضافة خدمة واحدة إلى ما حجزه سابقاً)"
            if c.extra_points:
                sentence += f"، ويكسب {c.extra_points} نقطة إضافية عن الحجز المنفرد"
                if c.to_next_reward_before > 0 and c.to_next_reward_after < c.to_next_reward_before:
                    closed = c.to_next_reward_before - c.to_next_reward_after
                    sentence += f" (يقرّبه {closed} نقطة من مكافأته القادمة)"
            lines.append(sentence + ".")

    if cross_sell:
        lines.append("ارتباطات إحصائية حقيقية:")
        lines.extend(f"- {line}" for line in cross_sell)

    if rhythm.get("due"):
        lines.append("خدمات مستحقة قريباً لهذا العميل: " + "، ".join(rhythm["due"]) + ".")
    if rhythm.get("lapsed"):
        lines.append("خدمات توقف عنها هذا العميل: " + "، ".join(rhythm["lapsed"]) + ".")

    return "\n".join(lines)


async def build_report(*, tenant: str, subject_ref: str, selected_service_ids: list[str],
                       package_catalog: Any, service_catalog: Any, rhythm_provider: Any,
                       related_services: Any, points_summary: Any, now: int | None = None) -> str:
    """The one entry point core/tools.py's `check_growth_opportunities` tool calls — runs all five
    steps in order and returns ONE finished, read-only report. Every peer is optional and
    None-safe (same posture every other tool in this service already takes): a peer that is not
    wired for this deployment simply contributes nothing to its own section, never an error and
    never a guess standing in for a real read.
    """
    now = now if now is not None else int(time.time())

    packages = await package_catalog.list_active(tenant) if package_catalog else []
    catalog = await service_catalog.list_active(tenant) if service_catalog else []
    names_by_id = {str(s.get("id")): str(s.get("name") or s.get("id")) for s in catalog}
    rhythm = (await rhythm_provider.for_subject(tenant=tenant, subject_ref=subject_ref)
             if rhythm_provider else [])

    recent_ids = recent_service_ids(rhythm, now=now)
    candidates = find_structural_candidates(
        selected_ids=selected_service_ids, recent_ids=recent_ids, packages=packages)
    candidates = apply_financial_guard(candidates)
    candidates = await apply_points_strategy(
        candidates, points_summary=points_summary, tenant=tenant, subject_ref=subject_ref)

    cross_sell = await statistical_cross_sell(
        tenant=tenant, service_ids=selected_service_ids, related_services=related_services,
        names_by_id=names_by_id)

    rhythm_bands = personal_rhythm(rhythm, now=now, names_by_id=names_by_id)

    return format_report(candidates=candidates, cross_sell=cross_sell, rhythm=rhythm_bands)


def _replace(c: PackageCandidate, **changes: Any) -> PackageCandidate:
    """`dataclasses.replace`, spelled out — `PackageCandidate` is frozen (its own fields are set
    once per pipeline step, never mutated in place, so a step earlier in the pipeline can never be
    surprised by a later one changing a value out from under it)."""
    return replace(c, **changes)
