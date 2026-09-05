"""Builds the per-turn `context_block` handed to the LLM alongside the persona (see
app/ports/llm.py's docstring on why this is sent IN FULL rather than trimmed to a hint): the
shop's real priced catalogue and the customer's own real, personal offers — never a generic
suggestion, never an invented number.

A BRAND-NEW, NEVER-SEEN CUSTOMER IS A NORMAL CASE, NOT AN ERROR. A number that reached this shop
straight from a Google Maps listing, with no prior visit or booking, resolves to an empty offers
list here — the same resolve-or-continue shape app/core/inbound_ingest.py already uses for the
subject_ref itself (derive a pseudonym rather than fail). The context block says plainly "new
customer, no history" rather than fabricating a pattern, and the conversation proceeds as a normal
first-visit greeting/booking flow.
"""
from __future__ import annotations

from typing import Any


def _fmt_price(price_minor: int) -> str:
    # Minor units -> a whole-or-decimal riyal string. No currency symbol hardcoded as a business
    # assumption beyond "ر.س", which is fixed shop-facing copy exactly like TRIAGE_PROMPT's
    # register elsewhere in this service, not a config-tunable number.
    riyals = price_minor / 100
    return f"{riyals:g} ر.س"


def _eligible_upsell_packages(packages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Which packages may even be MENTIONED this turn — packages feature's own anti-hallucination
    and anti-discount rules, enforced HERE, structurally, never left to the model to judge:

      1. `active` and genuinely bookable soon — `next_offerable_dates` non-empty (precomputed by
         operations' core/scheduling.py; a package with none is either off/expired/out-of-season
         and simply does not exist for this purpose right now).

      2. `price_minor >= component_price_minor_sum` — THE WHOLE UPSELL RULE. A package priced
         below what the same services would cost bought separately would LOWER what the customer
         was about to pay; this feature exists to raise the average invoice, never to talk a
         customer into spending less. A package failing this check is silently never shown to
         the model at all — there is nothing for it to accidentally suggest.
    """
    out = []
    for p in packages:
        if not p.get("active"):
            continue
        if not (p.get("next_offerable_dates") or []):
            continue
        if int(p.get("price_minor") or 0) < int(p.get("component_price_minor_sum") or 0):
            continue
        out.append(p)
    return out


def build_context_block(*, catalog: list[dict[str, Any]], offers: list[dict[str, Any]],
                        known_customer: bool, packages: list[dict[str, Any]] | None = None) -> str:
    lines: list[str] = []

    if catalog:
        lines.append("خدمات المحل وأسعارها الحالية:")
        for s in catalog:
            name = str(s.get("name") or "")
            price = int(s.get("price_minor") or 0)
            lines.append(f"- {name} (id: {s.get('id')}): {_fmt_price(price)}")
    else:
        lines.append("لا تتوفر قائمة خدمات مسعّرة لهذا المحل حاليًا.")

    if not known_customer:
        # EXPLICIT, not merely absent — a customer with no `offers` list could otherwise be
        # misread by the model as "known, but declined every offer" rather than "never seen
        # before". Saying it plainly removes the ambiguity a silent empty list would leave.
        lines.append("العميل جديد كليًا على هذا المحل — لا تاريخ زيارات ولا نقاط ولا عروض متاحة له.")
    elif offers:
        lines.append("عروض العميل الحقيقية المتاحة له الآن (رصيده الفعلي، لا تُخترع أي نسبة خصم):")
        for o in offers:
            reward = str(o.get("reward_name") or "")
            cost = int(o.get("points_cost") or 0)
            balance = int(o.get("points_balance") or 0)
            expires = str(o.get("expires_at") or "")
            # `id` EXPOSED, same as the catalogue lines above — `propose_booking`'s optional
            # `reward_id` argument needs the model to have seen this exact value somewhere, the
            # same reason a service line shows `(id: ...)` rather than only its price.
            line = f"- {reward} (id: {o.get('reward_id')}): تكلفتها {cost} نقطة (رصيده {balance} نقطة)"
            if expires:
                line += f"، تنتهي صلاحية نقاطه بتاريخ {expires}"
            lines.append(line)
    else:
        lines.append("لا توجد عروض قابلة للاستبدال برصيد العميل الحالي.")

    # ── packages worth mentioning for upselling — see `_eligible_upsell_packages`'s own doctrine.
    # A GENERIC SECTION HEADER, NOT A PERSUASIVE ONE — the persona itself (build_system_prompt)
    # carries the "only if it truly fits, only these, only these dates" instruction; this block's
    # job is only to hand over the real, already-filtered facts.
    names_by_id = {str(s.get("id")): str(s.get("name") or "") for s in catalog}
    eligible = _eligible_upsell_packages(packages or [])
    if eligible:
        lines.append("")
        lines.append("باقات حقيقية قد تناسب العميل (اذكرها فقط إذا كانت أعلى قيمة مما يختاره أصلاً، "
                     "ولا تخترع باقة أو تاريخاً غير الموجودَين هنا):")
        for p in eligible:
            included = "، ".join(names_by_id.get(sid, sid) for sid in p.get("service_ids") or [])
            price = _fmt_price(int(p.get("price_minor") or 0))
            line = f"- {p.get('name')} (id: {p.get('id')}): تشمل {included} — بسعر {price}"
            person_count = int(p.get("person_count") or 1)
            if person_count > 1:
                line += f"، تكفي {person_count} أشخاص"
            dates = p.get("next_offerable_dates") or []
            if dates:
                line += f" — الأيام المتاحة قريبًا: {'، '.join(dates)}"
            lines.append(line)

    return "\n".join(lines)
