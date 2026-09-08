"""Suggested bundles — we say WHERE the relationship is, and never how much (spec §10.6.2.1).

WE DO NOT PRICE. The cost is his, the labour is his, the competitor across the street is his. A
margin computed from inputs we do not hold is bad advice carrying our name, and the first time it
is wrong it costs more trust than every correct indicator on the dashboard earned.

WHAT WE HOLD IS THE RELATIONSHIP, and that is precisely the thing he cannot extract himself. So
the card names the pair, says how many customers the opportunity covers, and hands him a button.
He decides the price, because he is the only one who can.

THREE RULES THAT KEEP IT HONEST:

  a pair that failed the contamination test never appears, however strong it looked on receipts —
  otherwise the family's bill becomes a bundle,

  the opportunity SIZE is always stated: a strong relationship between two services almost nobody
  buys is arithmetic, not an opportunity,

  a `temporal` pair is offered as a REMINDER, not a bundle. Pricing them together sells the
  customer something he did not need today, and this product's whole argument is that we do not
  do that.

AND THE ARITHMETIC IS NEVER SHOWN. No lift value, no formula, no derivation — one sentence. The
engine is the product's own IP (see core/associations.py), and a method explained in full is a
method copied in a week.
"""
from __future__ import annotations

from typing import Any

from app.core.models import Pair

# Below this the pair is real and the opportunity is not. Deliberately a count of PEOPLE rather
# than a share: "twenty customers" is a thing an owner can picture, and a percentage of a base he
# has not seen is not.
# A DEFAULT. Twenty customers is a picture in a small shop and a rounding error in a large one,
# so the floor below which we say nothing belongs at the boundary. INSIGHTS_MIN_OPPORTUNITY.
DEFAULT_MIN_OPPORTUNITY = 20


def _sentence(p: Pair) -> str:
    """What the owner reads. The number is a multiple, not a lift — 'twice as often as expected'
    is the same fact in a form that needs no explanation and gives nothing away."""
    if p.verdict == "temporal":
        return "يأخذها العملاء في زيارات متتالية، لا في زيارة واحدة."
    times = round(max(p.lift_basket, 1.0), 1)
    if times >= 2:
        return f"يُطلبان معاً {int(times)} أضعاف المتوقّع، ويؤكّده سلوك العملاء عبر زياراتهم."
    return "يُطلبان معاً أكثر من المتوقّع، ويؤكّده سلوك العملاء عبر زياراتهم."


def build(pairs: list[Pair], *, names: dict[str, str] | None = None,
          missing_counts: dict[tuple[str, str], int] | None = None,
          limit: int = 10,
          min_opportunity: int = DEFAULT_MIN_OPPORTUNITY) -> list[dict[str, Any]]:
    """The cards, strongest first.

    `names` maps a service id to what the owner calls it — passed in rather than looked up here,
    because a bundle card showing `svc_9f2a` instead of "قص شعر" is a card nobody presses, and
    the catalogue belongs to `operations`.

    `missing_counts` is how many customers take one side and not the other — the opportunity size.
    """
    names = names or {}
    missing_counts = missing_counts or {}
    out: list[dict[str, Any]] = []

    for p in pairs:
        # THE CONTAMINATION TEST IS ENFORCED HERE, not only where the verdict was assigned. This
        # is the surface that turns a relationship into a price the owner publishes, so it re-reads
        # the verdict rather than trusting that whoever called it filtered first.
        if p.verdict not in ("real", "temporal"):
            continue
        size = missing_counts.get((p.a, p.b)) or missing_counts.get((p.b, p.a)) or p.customers
        if size < min_opportunity:
            continue
        # ONE SIDE ALREADY A PACKAGE (packages feature) — `pkg:<id>` is a synthetic item
        # (core/tick.py's `_visit_items`), never a real service id, and the right action for the
        # owner is different: he does not need a NEW package for something one of his packages
        # already is — he needs to ADD the extra, still-separate service INTO the existing one.
        pkg_side = p.a if p.a.startswith("pkg:") else (p.b if p.b.startswith("pkg:") else "")
        out.append({
            "a": p.a, "b": p.b,
            "a_name": names.get(p.a, p.a), "b_name": names.get(p.b, p.b),
            "why": _sentence(p),
            "customers": size,
            # A temporal pair is NOT a bundle. The action differs, and saying so on the card is
            # what stops an owner pricing two things together that belong a month apart.
            "action": ("extend_package" if pkg_side and p.verdict == "real" else
                      "bundle" if p.verdict == "real" else "reminder"),
            "action_label": (
                "أضفها لهذه الباقة" if pkg_side and p.verdict == "real" else
                "اجعلها باقة — تحدّد سعرها أنت" if p.verdict == "real" else
                "ذكّر بها في الزيارة القادمة"),
            # THE PACKAGE'S OWN id, "" for an ordinary pair — the console reads this to know WHICH
            # package to open the "add a service" form against, rather than parsing it back out of
            # `a`/`b`.
            "package_id": pkg_side[len("pkg:"):] if pkg_side else "",
        })
        if len(out) >= limit:
            break
    return out
