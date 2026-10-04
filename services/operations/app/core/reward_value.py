"""ONE shared way to turn a `{reward_kind, reward_amount, scope_service_ids}` shape into a real
SAR value against a real invoice -- used wherever two differently-sourced discounts must be
compared by what they are actually worth, never by which one happened to be checked first.

Extracted from `core/discount_consultation.py` (which used this privately, for WhatsApp Direct
Ordering) so `core/entitlements.py::EntitlementGateway` (the OLDER manual visit/till flow) can use
the identical math -- one function, never two copies that could quietly drift apart the way the
campaigns free-text bug did.
"""
from __future__ import annotations


def scoped_value(*, kind: str, amount: int, scope_service_ids: list[str] | None,
                 invoice_minor: int, line_minor: dict[str, int]) -> int:
    """How much a `{reward_kind, reward_amount, scope_service_ids}` shape is worth against THIS
    invoice -- same scoping rule everywhere a campaign discount is judged (see
    `services/campaigns/app/core/models.py::Campaign.scope_service_ids`'s own docstring): empty
    scope is the whole invoice, a non-empty one is only the matching services' own subtotal.
    Capped at `invoice_minor`, never negative -- a discount can make an order free, never charge
    the gateway a negative amount."""
    scope = set(scope_service_ids or [])
    base = (sum(v for sid, v in line_minor.items() if sid in scope)
           if scope else invoice_minor)
    if kind == "percent":
        off = base * max(0, amount) // 100
    elif kind == "fixed_halalas":
        off = amount
    else:
        off = 0
    return max(0, min(off, invoice_minor))
