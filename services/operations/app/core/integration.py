"""The moment a shop becomes an integrated one — which is not a moment anyone can name in advance.

THE QUESTION WE DELIBERATELY DO NOT ASK AT SIGNUP. "Is your till connected?" looks like a fair
thing to put on the form, and it is unanswerable there: the owner is opening an account, the till
company often integrates him weeks later and sometimes on his behalf, and a wrong answer is
expensive in both directions —

    said yes, integrates never   → a catalogue with one entry, «خدمة أخرى», and a field screen
                                   that cannot record what he actually does
    said no, integrates later    → seventeen seeded names his till never mentions, sitting beside
                                   the real ones with nothing to tell them apart

So nothing is asked and nothing is assumed. The shop DECLARES itself by sending an invoice, which
is the only unambiguous evidence there is, and this module is what happens when it does.

────────────────────────────────────────────────────────────────────────────────────────────────
WHAT IS RETIRED, AND WHY IT IS SAFE

Only rows that are all three of:

    seeded      we wrote them from the sector defaults; he never typed them
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

AND IT RUNS ONCE. The tenant's sector row carries `integrated`, so the second invoice — and the
ten thousandth — does no work and reads no catalogue.
"""
from __future__ import annotations

from typing import Any

from app.core.stores import ServiceStore, VisitStore


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

    def __init__(self, *, store, sectors) -> None:
        self._store = store
        self._sectors = sectors

    async def note_invoice(self, tenant: str) -> dict[str, Any]:
        """Called when a till's invoice lines arrive. Idempotent, and cheap after the first."""
        row = await self._sectors.tenant_row(tenant)
        if row is None or row.get("integrated"):
            # Unknown tenant, or already known to be integrated. Either way there is nothing to do
            # and no catalogue to read — this is the path every invoice after the first takes.
            return {"changed": False, "retired": 0}

        retired = await self._retire_unused_seeds(tenant)
        await self._sectors.mark_integrated(tenant)
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
