"""Turning a till's invoice into a visit — and the one field that decides everything.

A POS sends what it sold. Most of those lines are products it has defined: they carry a stable
`product_id` and the same id means the same thing tomorrow. But every till also has a FREE ITEM,
where the cashier types whatever is not on the list — "extra cheese", "special discount", "fix the
thing".

THE BOUNDARY IS THE ID, NOT THE TEXT (spec §16.6.4). We do not guess, we do not cluster strings, we
do not run similarity matching. We ask the partner for a field, and the field decides:

  line WITH a stable product_id   -> a real service. Added to THIS tenant's catalogue, earns a
                                     cycle, and a reminder is built on it.
  line WITHOUT one                -> the catch-all. Recorded, counted in the visit, generating no
                                     service and no reminder — because "extra cheese" is not
                                     something anyone should be reminded about.

WHY NOT CLUSTER THE TEXT? Because it fails in the direction that hurts. Merge two things that are
different and the owner sees one service where they have two. Split one thing that is the same and
they see hundreds of near-duplicates within a week and stop trusting the screen. A field we ask for
in the integration contract has neither failure, and it costs the partner one line of code.

THREE THINGS THAT GO WRONG IN THE FIELD, ALL HANDLED HERE:

  A renamed product.  Same id, new label. The id wins and the label is UPDATED — never forked.
                      Forking would double the catalogue every time a shop tidies its wording.
  A retyped id.       A partner sends 4471 as a number one day and "4471" the next. Normalised to
                      a string, or the same product becomes two services.
  A resent invoice.   Idempotent on THEIR invoice id, not on ours — the till is the only party
                      that knows whether these two calls are the same sale.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# What a free-item line looks like when the partner does send an id for it: one shared id used with
# many different labels. Recognised by the CALLER passing it in, because the value differs per POS
# vendor and hard-coding a list of them is a file nobody updates.
DEFAULT_FREE_ITEM_IDS = frozenset({"0", "-1", "free", "open", "custom", "misc", "other"})

_WS = re.compile(r"\s+")


@dataclass
class Line:
    """One invoice line, normalised."""
    product_id: str
    name: str
    quantity: int = 1
    amount_minor: int = 0

    @property
    def is_defined(self) -> bool:
        return bool(self.product_id)


@dataclass
class InvoiceResult:
    service_ids: list[str] = field(default_factory=list)
    # Labels of the lines that had no id. They ride on the visit as `custom_service` so the owner
    # can read what was actually sold, and a label that keeps recurring is the signal to offer it
    # as a real service.
    free_text: list[str] = field(default_factory=list)
    created_services: list[str] = field(default_factory=list)
    renamed_services: list[str] = field(default_factory=list)
    # HOW MANY OF EACH SERVICE THIS ONE RECEIPT HELD, keyed by OUR service id.
    #
    # It is evidence about the RECEIPT, not about the shop: two coffees on one bill say a group was
    # served, and insights drops that receipt from LEARNING while still counting it everywhere else
    # (§10.6.2). Without it the association engine treats a table of four as one person with
    # extraordinary habits, and «من اشترى س اشترى ص» is learned from parties rather than people.
    quantities: dict[str, int] = field(default_factory=dict)
    # WHAT THE RECEIPT CAME TO, in halalas, summed from the lines (أ-1).
    #
    # The till sends `amount_minor` per line, `parse_lines` reads it into `Line.amount_minor` — and
    # there it stopped. Nothing carried it out of this function, so the visit had no amount, the
    # event had no amount, and loyalty's earn rule computed `(0 // 100) * points_per_riyal = 0`.
    # A 480-riyal invoice earned zero points, and the reason recorded was «no points configured»:
    # no error, in any log, anywhere on the chain.
    total_minor: int = 0


def normalise_id(raw: Any) -> str:
    """A product id as a string, always.

    A partner that sends 4471 as an integer one day and "4471" the next would otherwise produce two
    services for one product — and the owner would see the duplicate long before anyone found the
    type change. Floats are handled because JSON has no integers: 4471.0 must not become "4471.0".
    """
    if raw is None:
        return ""
    if isinstance(raw, bool):          # a bool is an int in Python, and neither is a product id
        return ""
    if isinstance(raw, float) and raw.is_integer():
        raw = int(raw)
    return str(raw).strip()


def normalise_name(raw: str) -> str:
    """Collapse whitespace and trim. Nothing more.

    Deliberately NOT a fuzzy normaliser: this text is displayed to the owner exactly as their till
    holds it, and quietly rewriting it produces a catalogue they do not recognise as theirs.
    """
    return _WS.sub(" ", (raw or "").strip())


def parse_lines(raw_lines: list[dict[str, Any]], *,
                free_item_ids: frozenset[str] = DEFAULT_FREE_ITEM_IDS) -> list[Line]:
    """Normalise what the till sent. Never raises — a malformed line becomes a free-text line.

    Raising here would fail a whole invoice because one line was odd, and the till has already
    taken the customer's money. The visit must be recorded.
    """
    out: list[Line] = []
    for raw in raw_lines or []:
        if not isinstance(raw, dict):
            continue
        pid = normalise_id(raw.get("product_id"))
        # A SHARED free-item id is treated as no id at all. Some tills do send one, and taking it
        # at face value would create a single service called whatever the first cashier typed, then
        # attach every subsequent free item to it — one bogus service accumulating everything.
        if pid.lower() in free_item_ids:
            pid = ""
        name = normalise_name(str(raw.get("name") or raw.get("label") or ""))
        if not pid and not name:
            continue
        # `qty` FIRST, BECAUSE IT IS OUR OWN NAME FOR IT.
        #
        # `TillLineIn.qty` is the field OUR till API declares, and `line.model_dump()` hands this
        # parser a dict keyed by it. Reading only `quantity` meant every line arrived as 1 — so the
        # clearest group-basket signal we have, «two coffees on one bill», never once fired in
        # production. `quantity` stays for the third-party tills that post to the batch endpoint
        # directly, exactly as `label` stands beside `name` two lines up.
        qty = raw.get("qty", raw.get("quantity", 1))
        amount = raw.get("amount_minor", raw.get("amount", 0))
        out.append(Line(product_id=pid, name=name,
                        quantity=int(qty) if isinstance(qty, (int, float)) else 1,
                        amount_minor=int(amount) if isinstance(amount, (int, float)) else 0))
    return out


async def resolve(lines: list[Line], *, tenant: str, service_store,
                  new_id, now: int, auto_create: bool = True,
                  existing: list | None = None) -> InvoiceResult:
    """Map invoice lines onto this tenant's own catalogue, creating what is genuinely new.

    THE CATALOGUE IS PER TENANT AND ALWAYS HAS BEEN. A service created here belongs to this
    establishment alone — a shop's services are its own rows, never a shared reference. That
    is why one shop renaming "بنشر" does not rename it for every other shop, and it is what makes
    auto-creation safe at all.

    `existing` LETS A CALLER SHARE ONE CATALOGUE READ ACROSS SEVERAL INVOICES FOR THE SAME
    TENANT (`record_visits_batch`, up to 50 items a batch, most from the same till) — `None`
    (every other caller) keeps the original one-read-per-call behaviour unchanged. When the
    caller DOES share a list, it is mutated in place: a service created or adopted here is
    appended (or already reflected — a rename/adopt mutates the SAME object the caller's list
    already holds) so the NEXT item for this tenant in the same batch sees it too, exactly as it
    would if each item still paid for its own fresh read.
    """
    res = InvoiceResult()
    owns_list = existing is None
    if existing is None:
        existing = await service_store.list(tenant, active_only=False)
    # Two indexes: by external id (authoritative) and by name (for the shop that used the product
    # manually before it ever integrated — see below).
    by_ext = {s.external_id: s for s in existing if getattr(s, "external_id", "")}
    by_name = {s.name: s for s in existing}

    for line in lines:
        # ── THE TOTAL IS THE INVOICE'S TOTAL, WHATEVER WE COULD MAP (ح-6) ────────────────────
        # This used to be added inside the two branches that FOUND or CREATED a catalogue row, so
        # a line the till sent without a product id — a free-text charge, which is most of what a
        # workshop writes — was dropped from the money as well as from the catalogue.
        #
        # An invoice of «غسيل 100.00» plus «خدمة إضافية 380.00» counted as 100.00, and the
        # customer earned 100 points instead of 480. He paid four hundred and eighty riyals and
        # was rewarded for a hundred, and nothing anywhere said a line had been skipped: the
        # catalogue mapping and the money are different questions, and only the first one had a
        # reason to care whether the line was recognised.
        #
        # `max(0, …)` keeps a negative line — a discount row, a correction — from being counted
        # as a positive charge; whether a negative line should REDUCE the total is a question
        # about the till contract, not something to decide silently here.
        res.total_minor += max(0, line.amount_minor)

        if not line.is_defined:
            if line.name:
                res.free_text.append(line.name)
            continue

        found = by_ext.get(line.product_id)

        # THE SHOP THAT WENT MANUAL FIRST. It has "قص شعر" in its catalogue, typed by the owner
        # months ago, and now its till sends that product with an id. Creating a second service
        # would leave the owner with two identical rows and a visit history split across them.
        # So an exact name match ADOPTS the id instead of forking.
        if found is None and line.name and line.name in by_name:
            found = by_name[line.name]
            found.external_id = line.product_id
            await service_store.save(found)
            by_ext[line.product_id] = found

        if found is not None:
            # A RENAME, not a fork. Same id, new label: the shop tidied its wording, and the
            # service is the same service. Forking here would double the catalogue every time.
            if line.name and found.name != line.name:
                found.name = line.name
                await service_store.save(found)
                res.renamed_services.append(found.id)
                by_name[line.name] = found
            res.service_ids.append(found.id)
            res.quantities[found.id] = res.quantities.get(found.id, 0) + max(1, line.quantity)
            continue

        if not auto_create:
            if line.name:
                res.free_text.append(line.name)
            continue

        # NEW, AND WITH NO CYCLE. We do not know how often this product recurs, and guessing is
        # worse than not knowing: a default of 90 days on a coffee is a reminder that reads as
        # nonsense. The adaptive engine learns the real rhythm from repeat visits (spec §5.2), and
        # until it has, the service exists and simply schedules nothing.
        svc = await service_store.save_new(
            id=new_id("srv"), tenant=tenant, name=line.name or f"منتج {line.product_id}",
            cycle_days=0, external_id=line.product_id, created=now)
        by_ext[line.product_id] = svc
        by_name[svc.name] = svc
        if not owns_list:
            # A CALLER-SHARED LIST GETS THE NEW ROW TOO — otherwise the NEXT item for this same
            # tenant in the batch would rebuild `by_ext`/`by_name` from a list that still does not
            # know this service exists, and create a DUPLICATE for the same `product_id`.
            existing.append(svc)
        res.service_ids.append(svc.id)
        res.created_services.append(svc.id)
        res.quantities[svc.id] = res.quantities.get(svc.id, 0) + max(1, line.quantity)

    return res
