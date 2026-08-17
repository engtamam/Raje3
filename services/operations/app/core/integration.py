"""The moment a shop becomes an integrated one — which is not a moment anyone can name in advance.

THE QUESTION WE DELIBERATELY DO NOT ASK AT SIGNUP. "Is your till connected?" looks like a fair
thing to put on the form, and it is unanswerable there: the owner is opening an account, the till
company often integrates him weeks later and sometimes on his behalf, and a wrong answer is
expensive in both directions —

    said yes, integrates never   → a catalogue with one entry, «خدمة أخرى», and a field screen
                                   that cannot record what he actually does
    said no, integrates later    → a catalogue he typed by hand, sitting beside the names his
                                   till sends, with nothing to tell the duplicates apart

So nothing is asked and nothing is assumed. The shop DECLARES itself by sending an invoice, which
is the only unambiguous evidence there is, and this module is what happens when it does.

────────────────────────────────────────────────────────────────────────────────────────────────
WHAT IS RETIRED, AND WHY IT IS SAFE

Only rows that are all three of:

    seeded      we wrote them; he never typed them
    unused      no visit has ever named them
    unclaimed   the till has never matched them (no external_id)

A row that fails any one of those is his, and is left exactly alone. And note what the three
conditions leave standing: everything he edited into use, everything ever sold, and everything the
till adopted by name — because `invoices.resolve` matches a seeded «غيار الزيت» to the till's
product and stamps its id onto our row rather than forking. That adoption is what makes retiring
the remainder honest: the survivors are the ones nothing in the world refers to.

DEACTIVATED, NEVER DELETED. `active = False` keeps the row, its id and any history attached to it;
a shop that integrates a till by mistake, or whose till sends one bad invoice, loses nothing that
cannot be switched back on from «خدماتي». Deleting would be irreversible on evidence this thin.

AND IT RUNS ONCE. One row per establishment carries `integrated`, so the second invoice — and the
ten thousandth — does no work and reads no catalogue.

THE ROW IS ITS OWN, and it used to be a field on the tenant's sector row. The trade a shop was in
is gone (core/vehicles.py says why), and «is this shop's till connected» is a different fact that
outlived it — so it keeps its own tiny collection rather than being folded into an unrelated one.
NOTHING IS SEEDED ANY MORE, so `_retire_unused_seeds` finds candidates only in establishments that
were created while seeding still happened; for every shop opened since, it is correctly a no-op.
"""
from __future__ import annotations

from typing import Any

from app.core.stores import ServiceStore, VisitStore

#: One row per establishment, carrying the two facts about it that are OURS rather than its own:
#: whether its till has ever sent us an invoice, and whether it is a vendor's test shop.
#:
#: THEY USED TO LIVE ON THE TENANT'S SECTOR ROW, and the trade a shop is in is gone (see
#: core/vehicles.py). Neither of these is about a trade — one is about a till and the other about a
#: sales demo — so they keep a row of their own rather than being folded into something unrelated.
STANDING = "tenant_standing"


async def is_sandbox(store, tenant: str) -> bool:
    """A vendor's test shop: earns nobody commission and counts as nobody's customer.

    ABSENT MEANS «REAL», and unreadable means «real» too — the two mistakes are not equal. Treating
    a test shop as real bills a vendor for a demo, which is a refund; treating a real shop as a test
    quietly stops charging for a paying customer, which nobody notices for months.
    """
    if not tenant:
        return False
    try:
        row = await store.get(STANDING, tenant)
    except Exception:                                                        # noqa: BLE001
        return False
    return bool((row or {}).get("sandbox"))


async def mark_sandbox(store, tenant: str, *, expires_at: int = 0) -> bool:
    """Label a shop as a vendor's test shop, with a date it stops being one.

    A SANDBOX IS A REAL TENANT WITH A LABEL, not a second code path. Every branch that says "if
    this is the test system" is a branch nobody exercises against production, and the integration a
    vendor proves in it is then the integration that fails on their first real shop. So it is the
    same routes, the same validation, the same refusals — and the label exists for exactly two
    things: it earns nobody commission, and it does not count as a customer.

    AN EXPIRY, BECAUSE A TEST SHOP IS NEVER CLEANED UP BY THE PERSON WHO MADE IT. Without a date, a
    demo tenant from a sales call two years ago is still on the cluster holding somebody's phone
    number in a customer row.
    """
    if not tenant:
        return False
    row = dict(await store.get(STANDING, tenant) or {})
    row.update({"tenant": tenant, "sandbox": True})
    if expires_at:
        row["sandbox_until"] = int(expires_at)
    await store.put(STANDING, tenant, row)
    return True


class Integration:
    # HOW FAR BACK WE LOOK FOR "EVER SOLD". A shop that integrates on its first day has a handful
    # of visits; one that integrates after two years has thousands, and reading them all to decide
    # whether to hide a seeded row is not a trade worth making.
    #
    # AND THE CAP FAILS SAFE. Reading the most recent 5000 and missing an older sale would retire a
    # service that WAS used — so the newest visits are read, and anything the till claims by name
    # is protected regardless (invoices.resolve stamps an external_id, which excludes the row from
    # the candidates entirely). A retired row is deactivated, never deleted, and one switch in
    # «خدماتي» brings it back.
    _SCAN_CAP = 5000

    def __init__(self, *, store) -> None:
        self._store = store

    async def is_integrated(self, tenant: str) -> bool:
        """Has this shop's till ever sent us an invoice? Absent means no, which is most shops."""
        if not tenant:
            return False
        try:
            row = await self._store.get(STANDING, tenant)
        except Exception:                                                    # noqa: BLE001
            # UNREADABLE IS «NOT YET», and it costs one wasted pass over a small catalogue rather
            # than a wrong answer: the retire step is idempotent, so repeating it changes nothing.
            return False
        return bool((row or {}).get("integrated"))

    async def note_invoice(self, tenant: str) -> dict[str, Any]:
        """Called when a till's invoice lines arrive. Idempotent, and cheap after the first."""
        if not tenant or await self.is_integrated(tenant):
            # Already known to be integrated: nothing to do and no catalogue to read — the path
            # every invoice after the first takes.
            return {"changed": False, "retired": 0}

        retired = await self._retire_unused_seeds(tenant)
        row = dict(await self._store.get(STANDING, tenant) or {})
        row.update({"tenant": tenant, "integrated": True})
        await self._store.put(STANDING, tenant, row)
        return {"changed": True, "retired": retired}

    async def _retire_unused_seeds(self, tenant: str) -> int:
        services = ServiceStore(self._store)
        candidates = [s for s in await services.list(tenant, active_only=False)
                      # THE CATCH-ALL SURVIVES ALWAYS. It is seeded and it is usually unused, and
                      # it is the row that stops an unknown line from losing a visit — retiring it
                      # would break the very path that just told us this shop is integrated.
                      if s.seeded and not s.catchall and not s.external_id and s.active]
        if not candidates:
            return 0

        used = await self._service_ids_ever_sold(tenant)
        retired = 0
        for svc in candidates:
            if svc.id in used:
                continue
            svc.active = False
            await services.save(svc)
            retired += 1
        return retired

    async def _service_ids_ever_sold(self, tenant: str) -> set[str]:
        """Every service id that appears on any visit this establishment has recorded.

        READ ONCE, not per service. The alternative is a query per candidate, which on a seeded
        catalogue is seventeen scans of the same table to answer one question.

        A shop that has only just integrated has few visits by definition, so this is small — and
        if the read fails, the caller treats it as "everything is used" rather than guessing, which
        is why the exception is not caught here.
        """
        # `_find` rather than a store method, because VisitStore has no "everything" read and
        # should not grow one for this: every other caller of it is scoped to a customer or a
        # window, and an unbounded read is exactly the method somebody reuses on a shop with two
        # years of history. The cap is generous and deliberate — see below.
        rows, _ = await VisitStore(self._store)._find(   # noqa: SLF001
            tenant, limit=self._SCAN_CAP)
        out: set[str] = set()
        for row in rows:
            out.update(row.get("service_ids") or [])
        return out
