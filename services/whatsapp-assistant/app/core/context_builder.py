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


def build_context_block(*, catalog: list[dict[str, Any]], offers: list[dict[str, Any]],
                        known_customer: bool) -> str:
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
            line = f"- {reward}: تكلفتها {cost} نقطة (رصيده {balance} نقطة)"
            if expires:
                line += f"، تنتهي صلاحية نقاطه بتاريخ {expires}"
            lines.append(line)
    else:
        lines.append("لا توجد عروض قابلة للاستبدال برصيد العميل الحالي.")

    return "\n".join(lines)
