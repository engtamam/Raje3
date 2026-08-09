"""The association engine — two axes, two lifts, and one verdict (spec §10.6.2).

THIS IS THE PRODUCT'S OWN INTELLECTUAL PROPERTY. The owner sees a sentence — "the oil and the
filter are taken together twice as often as chance explains" — and never a lift value, a formula or
a derivation. Everything in this file is deliberately invisible to him; what leaves it is a verdict
and a plain count. A method explained in full is a method copied in a week.

────────────────────────────────────────────────────────────────────────────────────────────────
THE PROBLEM THIS FILE EXISTS TO SOLVE

One receipt can be three people. A burger, a salad and a kids' meal on one bill is not a
relationship between items — it is a family at a table. Mine associations on that basket and the
engine reports, with complete confidence, a relationship that does not exist. The owner then builds
a bundle on it.

This is not a flaw in our arithmetic. It is a documented limit of this entire class of data:
transaction records attribute a purchase to the account holder and conceal who decided and who
consumed — "household influence" is one of the recognised gaps in loyalty-card data. The receipt
cannot be decomposed into people. Anyone who claims otherwise is guessing.

THE ANSWER IS NOT A CLEVERER TEST ON THE BASKET. It is to measure at a second level where the
contamination cannot exist, and to read the two together.

────────────────────────────────────────────────────────────────────────────────────────────────
THE TWO AXES

  lift_basket    within one receipt        — what the literature calls an INTRA-transaction rule
  lift_customer  across one person's own   — an INTER-transaction rule, over an ordered sequence
                 visits, all-time            of that customer's visits

The second is immune, and the reason is worth stating precisely: a family's single receipt cannot
make two services look related if the same pseudonym never takes both across a year. Someone who
brings friends once comes alone many times, and coincidence does not repeat twelve times.

AND ON THE FIRST AXIS — the customer's own list — the contamination stops mattering for a different
and stronger reason: THE UNIT WE MEASURE IS THE UNIT WE ACT ON. We never claim "this person likes
coffee". We claim "this NUMBER always orders coffee and never dessert", and the message goes to
that same number. Who drank it at home never entered the argument.

────────────────────────────────────────────────────────────────────────────────────────────────
THE VERDICTS

  basket   customer   verdict     what it means and what may be done with it
  high     high       real        a genuine relationship — a bundle, and a prompt at the screen
  HIGH     LOW        group       THE FAMILY RECEIPT. Together on the bill, never in one person
                                  over time. Excluded from everything.
  low      high       temporal    a relationship across TIME — oil today, filter next visit.
                                  A reminder, never a bundle: pricing them together sells the
                                  customer something he did not need today.
  low      low        none        nothing

The `group` row is the answer to the family problem: found arithmetically, per shop, with no sector
and no question to the owner — and without pretending we split the receipt into people.

The `temporal` row is a gain we were not looking for: a relationship no single receipt can show, in
a product whose entire subject is coming back.

────────────────────────────────────────────────────────────────────────────────────────────────
NO SECTOR, ANYWHERE IN THIS FILE

An earlier draft said "restaurants are group-prone by default". That is a rule whose input we do
not have: most establishments reach us through a POS link that reports an invoice and never says
what the shop sells. A rule keyed on something unknowable is not a conservative rule, it is a rule
that silently never fires.

NO APRIORI EITHER. It was built for thousands of items in a supermarket; a catalogue here is ten to
forty services and a basket is two or three. Counting pairs directly is simpler and exact, and
importing machinery that buys nothing is complexity added because it looks serious.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any, Iterable

from app.core.models import Pair

# Above this, a pair occurs more often than chance explains by enough to act on. 1.0 is exactly
# chance; the conventional line for "worth acting on" is 1.5, and it is a CHOICE rather than a
# derivation — said out loud so nobody later reads it as a mathematical constant.
STRONG = 1.5

# Below this a relationship is absent enough to call it absent. Deliberately not 1.5: a pair
# between STRONG and this is genuinely ambiguous, and forcing it into a verdict would manufacture
# certainty we do not have. Such pairs get `none` and are simply not shown.
WEAK = 1.2

# A rule needs the support of several hundred transactions before it means anything; below this we
# say we are still learning rather than publish a number that will change next week.
MIN_BASKETS = 200

# And a pair must appear in at least this many baskets on its own. Without it, two services bought
# together exactly twice in a year produce a spectacular lift out of pure noise.
MIN_PAIR_SUPPORT = 5


def _pair_key(a: str, b: str) -> tuple[str, str]:
    """Order-free. `lift(a,b) == lift(b,a)` by construction, so counting both directions would
    double every number and halve nothing."""
    return (a, b) if a <= b else (b, a)


def lift(both: int, count_a: int, count_b: int, total: int) -> float:
    """How much more often two things occur together than chance explains.

        lift = P(a and b) / (P(a) * P(b))

    THE DIVISION IS THE WHOLE POINT. A popular service co-occurs with everything: if a basic wash
    is in 90% of visits it will look like a companion to every line in the catalogue. Counting
    co-occurrences alone would report exactly that, confidently. Dividing by what chance predicts
    is what removes the illusion.

    Returns 0.0 rather than dividing by zero for a service that never occurs — an absent thing has
    no relationships, and raising here would make one missing row break a whole sweep.
    """
    if total <= 0 or count_a <= 0 or count_b <= 0:
        return 0.0
    p_both = both / total
    p_a = count_a / total
    p_b = count_b / total
    expected = p_a * p_b
    return (p_both / expected) if expected else 0.0


def count_pairs(baskets: Iterable[Iterable[str]]) -> tuple[dict, dict, int]:
    """Count singles and pairs over any collection of item-sets.

    ONE FUNCTION FOR BOTH AXES. A basket here is either one receipt's services or one customer's
    whole history — the arithmetic is identical and only the caller differs. Two implementations
    would be two places to fix a counting bug, and the second is always the one that keeps it.
    """
    singles: dict[str, int] = {}
    pairs: dict[tuple[str, str], int] = {}
    total = 0
    for basket in baskets:
        items = sorted(set(str(i) for i in basket if i))
        if not items:
            # An empty basket is not a basket. Counting it would inflate the denominator and drag
            # every lift in the shop downward — a silent, uniform error, which is the worst kind.
            continue
        total += 1
        for item in items:
            singles[item] = singles.get(item, 0) + 1
        for a, b in combinations(items, 2):
            k = _pair_key(a, b)
            pairs[k] = pairs.get(k, 0) + 1
    return singles, pairs, total


def is_group_basket(services: list[str], quantities: dict[str, int] | None = None,
                    median_size: int = 0) -> bool:
    """Does this ONE receipt look like more than one person? (spec §10.6.2)

    EVIDENCE, NOT A CLASSIFIER. This judges a single receipt and says nothing whatever about the
    shop — no sector is inferred, no flag is set on the establishment. A receipt that looks like a
    group is dropped from LEARNING and still counts in every other indicator: it was a real visit
    and the money was real.

    Two signals, both sector-free:

      a repeated item      two coffees on one bill — one person does not drink two coffees, and
                           this is the clearest evidence there is,
      an outsized basket   nine lines where this shop's median is two.

    The second is deliberately generous (four times the median): a big order is not proof of a
    group, and dropping honest baskets costs us the signal we are trying to find.
    """
    if quantities and any(int(q) > 1 for q in quantities.values()):
        return True
    if median_size and len(set(services)) > max(4, median_size * 4):
        return True
    return False


def classify(lift_basket: float, lift_customer: float) -> str:
    """The 2x2. Reading either number alone is what this function exists to prevent."""
    b_high, c_high = lift_basket >= STRONG, lift_customer >= STRONG
    b_low, c_low = lift_basket < WEAK, lift_customer < WEAK
    if b_high and c_high:
        return "real"
    if b_high and c_low:
        # THE FAMILY RECEIPT. Together on the bill and never in one person over time.
        return "group"
    if b_low and c_high:
        return "temporal"
    return "none"


def build(*, baskets: list[list[str]], sequences: list[list[str]],
          tenant: str, customers_with: dict[str, int] | None = None) -> dict[str, Any]:
    """Both axes, joined. Returns the pairs with their verdicts, or a learning state.

    `baskets`   one entry per VISIT — its services
    `sequences` one entry per CUSTOMER — every service they have ever taken

    THE LEARNING STATE IS RETURNED, NOT RAISED. A shop below the threshold is not in an error
    condition; it is new. The panel renders "أتعلّم من زياراتك" with progress, and the one thing it
    must never render is a blank with no explanation — which is what makes an owner conclude the
    feature is broken and stop looking at it.
    """
    if len(baskets) < MIN_BASKETS:
        return {"learning": True, "have": len(baskets), "need": MIN_BASKETS, "pairs": []}

    b_singles, b_pairs, b_total = count_pairs(baskets)
    c_singles, c_pairs, c_total = count_pairs(sequences)

    out: list[Pair] = []
    # The union, because a `temporal` pair may be strong across customers while barely appearing on
    # any single receipt — and that pair is one of the two this design was built to find.
    for key in set(b_pairs) | set(c_pairs):
        a, b = key
        support = b_pairs.get(key, 0)
        cust_support = c_pairs.get(key, 0)
        if support < MIN_PAIR_SUPPORT and cust_support < MIN_PAIR_SUPPORT:
            # Noise. Two services bought together twice in a year produce a spectacular lift and
            # mean nothing at all.
            continue
        lb = lift(support, b_singles.get(a, 0), b_singles.get(b, 0), b_total)
        lc = lift(cust_support, c_singles.get(a, 0), c_singles.get(b, 0), c_total)
        verdict = classify(lb, lc)
        if verdict == "none":
            continue
        out.append(Pair(tenant=tenant, a=a, b=b, lift_basket=lb, lift_customer=lc,
                        customers=cust_support, verdict=verdict))

    out.sort(key=lambda p: (-max(p.lift_basket, p.lift_customer), p.a, p.b))
    return {"learning": False, "have": len(baskets), "need": MIN_BASKETS, "pairs": out}


def missed_opportunities(pairs: list[Pair], sequences: dict[str, list[str]],
                         *, limit: int = 500) -> list[dict[str, Any]]:
    """Customers who repeatedly take one side of a real relationship and never the other.

    THIS IS THE INVERSE OF A RULE, and it only exists once the rule does. Without one, every
    service a customer has not bought is a "missed opportunity" and the indicator is a re-print of
    the catalogue — which is exactly what it was before the engine, and why it needed the owner to
    tell us what complements what.

    `temporal` pairs count here as much as `real` ones: a customer who takes the oil and never the
    filter is a missed opportunity whether the two belong in one bundle or one is due later.
    """
    actionable = [p for p in pairs if p.verdict in ("real", "temporal")]
    out: list[dict[str, Any]] = []
    for ref, services in sequences.items():
        have = set(services)
        for p in actionable:
            if p.a in have and p.b not in have:
                out.append({"subject_ref": ref, "has": p.a, "missing": p.b,
                            "verdict": p.verdict})
            elif p.b in have and p.a not in have:
                out.append({"subject_ref": ref, "has": p.b, "missing": p.a,
                            "verdict": p.verdict})
        if len(out) >= limit:
            break
    return out[:limit]
