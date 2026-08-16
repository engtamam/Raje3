"""Sectors — DATA IN THE DATASTORE, edited from the platform console at runtime.

THE FILE IS A SEED, NOT THE SOURCE OF TRUTH. An earlier version of this read a JSON file at boot,
and that was wrong for the reason that matters: adding a sector, fixing a service name, or changing
a cycle would have meant a ConfigMap edit and a restart. Sectors are content our own operators
curate — they will change on a Tuesday afternoon because a customer asked — and content that needs
a deploy is content that does not get edited.

So: the sectors live in the datastore, editable through the platform console
(/api/v1/platform/sectors, capability `platform.operations`). The JSON file is applied ONCE, when
the table is empty, so a fresh install is not a blank product.

PLATFORM-SCOPED, NOT TENANT-SCOPED. There is one sector table for the whole product, and it is not
an establishment's to edit — a tyre shop must not be able to rename "بنشر" for everyone else. The
rows carry the reserved tenant `_platform`, which no real tenant can ever hold: a tenant id is
issued by tenant-service and never begins with an underscore.

TWO RULES THAT DECIDE THE CONTENT ITSELF, both learned from what breaks a product on day one:

1. DEFAULTS SHIP FULL, NEVER EMPTY. An establishment that must build its own service list before
   recording a first visit will not record a first visit — the owner signs up, meets a blank grid,
   and closes the tab. Opinionated defaults that are slightly wrong beat nothing that is right.

2. FIELDS ARE PER SECTOR (spec §4.6). The plate renders in vehicle sectors ONLY. A women's salon
   asked for a plate number is a screen built for somebody else, and that one detail tells an owner
   this product was not made for them.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.core.models import Service
from app.core.stores import ServiceStore, new_id

SECTORS = "sectors"
FIELD_SPECS = "sector_fields"

# WHICH SECTOR THIS ESTABLISHMENT IS. One row per tenant, written when its catalogue is seeded.
#
# It did not exist until the field screen needed it, and its absence was a real gap rather than a
# missing convenience: the sector decides which INPUTS render (spec 13.2 - a plate exists in a
# tyre shop and does not exist at all in a salon), yet seeding copied the services and forgot
# which sector they came from. The screen was therefore left to decide for itself, and the only
# way to do that is to write the sector keys into the front-end - a hard-coded list that silently
# stops matching the moment our console adds a fifth sector.
TENANT_SECTOR = "tenant_sector"

# The reserved owner of platform-wide rows. Underscore-prefixed on purpose: tenant ids are issued
# by tenant-service and never take this shape, so no establishment can ever collide with it.
PLATFORM = "_platform"

# What an unnamed catch-all is called when one has to be added. Arabic because every establishment
# reading it is Arabic-speaking, and "خدمة أخرى" is what an owner would have typed themselves.
DEFAULT_CATCHALL = "خدمة أخرى"


# THE SECTOR THAT MEANS "NOT STATED". An establishment provisioned by its till never chooses one
# (§4.2): its catalogue comes from its own invoices and its screen asks only what every trade has.
# A named row rather than an empty string, because `seed_tenant` refuses an unknown sector — and it
# should, since a typo must not quietly produce a shop with no catalogue at all.
UNSPECIFIED = "unspecified"


class SectorError(Exception):
    """A refusal a console user can act on: an unknown sector, a duplicate key, a bad file."""


class SectorCatalogue:
    """Reads and writes the sector table. No caching.

    Deliberately uncached: these are read when a tenant is created and when the signup screen is
    drawn — rare, not hot. A cache here would buy nothing measurable and would cost the thing the
    console is for, which is seeing an edit take effect immediately.
    """

    def __init__(self, store) -> None:
        self._s = store

    # ── reads ─────────────────────────────────────────────────────────────────────────────────
    async def list(self) -> list[dict[str, Any]]:
        rows, _ = await self._s.find(SECTORS, {"tenant": PLATFORM}, limit=200,
                                     sort=("sort", "asc"))
        return rows

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._s.get(SECTORS, f"{PLATFORM}|{key}")

    async def fields(self) -> dict[str, Any]:
        row = await self._s.get(FIELD_SPECS, f"{PLATFORM}|fields")
        return (row or {}).get("specs", {})

    async def fields_for(self, key: str) -> list[dict[str, Any]]:
        """Full descriptors, not names — so the screen never needs its own copy of what a field
        means. A second copy is a second thing to keep in step, and it will not be kept in step."""
        sector = await self.get(key)
        if not sector:
            return []
        specs = await self.fields()
        return [{"name": n, **specs[n]} for n in sector.get("fields", []) if n in specs]

    async def tracks_vehicle(self, key: str) -> bool:
        sector = await self.get(key)
        return bool(sector) and sector.get("asset") == "vehicle"

    # ── writes: the platform console ──────────────────────────────────────────────────────────
    async def upsert(self, sector: dict[str, Any]) -> dict[str, Any]:
        key = (sector.get("key") or "").strip()
        if not key:
            raise SectorError("a sector needs a `key` — without one it can never be selected")
        if key.startswith("_"):
            raise SectorError("a sector key must not start with '_' — that prefix is reserved")
        services = list(sector.get("services", []))

        # A SECTOR WITHOUT A CATCH-ALL IS A SECTOR THAT LOSES VISITS, and the loss is silent.
        #
        # Found on the cluster: the live `tyres` sector had seventeen services and not one of them
        # flagged catchall — the flag was dropped when the sector was edited from the console
        # months after it was seeded. The symptom is not an error. A technician does something the
        # catalogue does not list, or a till sends a free-text line, and there is nowhere to put
        # it: the operator cannot save, and a lost visit is a lost customer with no reminder, no
        # points and no metric, for ever.
        #
        # APPENDED, NOT REFUSED. Refusing would be the tidier rule and the wrong one here: this
        # runs on a console edit, and an operator fixing a service name at 11pm should not have
        # their save rejected over a row they did not know existed. The default is added, named,
        # and visible — they can rename it, and they cannot lose it.
        if services and not any(x.get("catchall") for x in services):
            services.append({"name": DEFAULT_CATCHALL, "cycle_days": 0,
                             "sort": 9999, "catchall": True})

        row = {
            "id": key, "tenant": PLATFORM, "key": key,
            "name": (sector.get("name") or key).strip(),
            "asset": sector.get("asset", "none"),
            "fields": list(sector.get("fields", [])),
            "services": services,
            # THE REWARDS TABLE THE SHOP STARTS WITH (§10.8). Same reasoning as the services: an
            # owner who must invent a loyalty programme before switching one on does not switch one
            # on. It lives on the sector — beside the services it references by NAME, since sector
            # rows are shared and a service id belongs to one establishment.
            #
            # ALLOWED TO BE EMPTY, and one sector deliberately is: a shop whose catalogue arrives
            # from its own till has no service we could name, and a gift we invented would be the
            # only row on the screen he did not choose.
            "rewards": list(sector.get("rewards", [])),
            "sort": int(sector.get("sort", 0)),
            "active": bool(sector.get("active", True)),
            "updated": int(time.time()),
        }
        await self._s.put(SECTORS, f"{PLATFORM}|{key}", row)
        return row

    async def set_field_specs(self, specs: dict[str, Any]) -> dict[str, Any]:
        row = {"id": "fields", "tenant": PLATFORM, "specs": specs, "updated": int(time.time())}
        await self._s.put(FIELD_SPECS, f"{PLATFORM}|fields", row)
        return row

    async def deactivate(self, key: str) -> bool:
        """Deactivate, never delete.

        Establishments already point at this sector. Deleting it would leave them referring to
        something that no longer exists, and the symptom would be a signup screen that works and a
        tenant record that does not resolve.
        """
        row = await self.get(key)
        if row is None:
            return False
        row["active"] = False
        row["updated"] = int(time.time())
        await self._s.put(SECTORS, f"{PLATFORM}|{key}", row)
        return True

    # ── the one-time seed ─────────────────────────────────────────────────────────────────────
    async def seed_from_file(self, path: str) -> int:
        """Apply the shipped defaults — ADDING what is missing, never overwriting what exists.

        NOT «ONLY WHEN THE TABLE IS EMPTY», which is what this used to be, and which is the exact
        shape the TEMPLATE seeder was rewritten to remove. Under that rule the file was read once,
        on the first boot of a fresh deployment, and never again: a sector added to the shipped
        file afterwards — a new trade we decided to serve — reached no existing deployment, ever.
        The seed looked like a source of truth and behaved like a first-run fixture.

        AND STILL NOTHING IS OVERWRITTEN. Re-applying every entry on every boot would silently undo
        an operator's edits, which is the worst kind of bug: the console appears to work, and the
        change is gone tomorrow. So an entry whose key already exists is LEFT ALONE — his edit
        wins over our default, permanently and by design — and only genuinely new keys are written.
        """
        if not path:
            return 0
        p = Path(path)
        if not p.is_file():
            raise SectorError(f"SECTORS_SEED_FILE points at {path!r}, which does not exist — the "
                              f"sector table is empty and every new establishment would get a "
                              f"blank service grid")
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SectorError(f"the sector seed file is not valid JSON: {exc}") from exc

        # THE FIELD SPECS ARE MERGED, NEVER REPLACED — and this line is why the whole-file rewrite
        # above had to be careful. `set_field_specs` is also a panel route: an operator can edit a
        # field's label or options, and this runs on every boot now. Writing the shipped dict
        # wholesale would silently undo his edit on the next restart — the exact bug the old
        # «only when empty» rule was protecting against, reintroduced by the fix for it.
        shipped = {k: v for k, v in data.get("fields", {}).items() if not k.startswith("_")}
        held = await self.fields()
        added = {k: v for k, v in shipped.items() if k not in held}
        if added:
            await self.set_field_specs({**held, **added})
        existing = {str(r.get("key") or "") for r in (await self.list() or [])}
        n = 0
        for entry in data.get("sectors", []):
            if str(entry.get("key") or "") in existing:
                continue        # his, not ours — see the docstring
            await self.upsert(entry)
            n += 1
        return n

    # ── seeding a tenant's catalogue ──────────────────────────────────────────────────────────
    async def seed_tenant(self, *, tenant: str, sector_key: str,
                          integrated: bool = False) -> int:
        """Give a new establishment its catalogue. Returns how many services were created.

        IDEMPOTENT BY NAME. Re-running adds nothing, so a retried provisioning step cannot produce
        a catalogue listing every service twice — a mess the owner cleans by hand, on day one.

        THE COPY IS THE POINT (spec §16.6.4). These rows become the establishment's OWN services,
        editable by it and by nobody else. Without the copy, one tyre shop renaming "بنشر" would
        rename it for every tyre shop on the product — which is why there is no such thing as a
        shared catalogue here, and why auto-creating services from invoices is safe at all.

        `integrated` — the establishment's till will send its catalogue. Seeding names it does not
        use would leave an owner staring at a grid of services their invoices never mention, unable
        to tell which are real. So an integrated shop starts EMPTY except for the catch-all, which
        is not optional: a line with no product id has to land somewhere, and without it the first
        free item would fail the whole invoice.
        """
        sector = await self.get(sector_key)
        if sector is None or not sector.get("active", True):
            keys = [s.get("key") for s in await self.list() if s.get("active", True)]
            raise SectorError(f"unknown or inactive sector {sector_key!r} — one of {keys}")

        svc_store = ServiceStore(self._s)
        existing = {s.name for s in await svc_store.list(tenant, active_only=False)}
        now = int(time.time())
        created = 0
        for entry in sector.get("services", []):
            name = (entry.get("name") or "").strip()
            if not name or name in existing:
                continue
            # An integrated shop takes the catch-all and nothing else — see the docstring.
            if integrated and not entry.get("catchall", False):
                continue
            await svc_store.save(Service(
                id=new_id("srv"), tenant=tenant, name=name,
                cycle_days=int(entry.get("cycle_days", 0)),
                # No price. It varies by city, by shop and by the day — shipping a number ships a
                # wrong one to almost everybody, and a wrong price on a screen is worse than none.
                price_minor=0,
                sort=int(entry.get("sort", 0)),
                catchall=bool(entry.get("catchall", False)), seeded=True, created=now))
            created += 1

        # RECORDED EVEN WHEN NOTHING WAS CREATED. A re-run adds no services (it is idempotent by
        # name) but must still leave the sector written down, or a retried provisioning step ends
        # with a full catalogue and a screen that does not know whether to render a plate.
        # THE SANDBOX FLAG IS PRESERVED ACROSS A RE-SEED. A vendor's test shop that lost its flag
        # would start earning its partner real commission and appear in our revenue as a customer
        # — which is how a demo account becomes a line in a board report.
        prior = await self._s.get(TENANT_SECTOR, tenant) or {}
        await self._s.put(TENANT_SECTOR, tenant,
                          {"id": tenant, "tenant": tenant, "sector": sector_key,
                           "integrated": bool(integrated),
                           "sandbox": bool(prior.get("sandbox", False)),
                           "updated": now})
        return created

    async def rewards_for(self, *, tenant: str, sector_key: str) -> list[dict[str, Any]]:
        """This shop's starting rewards, with every service NAME already resolved to ITS id.

        RESOLVED HERE, NOT IN LOYALTY. The sector row can only name a service — sector rows are
        shared by every shop in the trade, and a service id belongs to exactly one of them. The
        resolution therefore has to happen where the shop's own catalogue is, which is here; asking
        loyalty to do it would mean loyalty reading operations' tables.

        A REWARD WHOSE SERVICE IS MISSING IS DROPPED, not shipped without one. `create` refuses a
        service reward with no service, and rightly: "free wash" that records no visit and restarts
        no cycle is a name and nothing else. An integrated shop seeds no services at all, so this
        is a real case rather than a defensive branch.
        """
        sector = await self.get(sector_key)
        if not sector:
            return []
        by_name = {s.name: s.id for s in await ServiceStore(self._s).list(tenant, active_only=False)}
        out: list[dict[str, Any]] = []
        for entry in sector.get("rewards", []):
            reward = {k: v for k, v in entry.items() if k != "service"}
            if entry.get("type") == "service":
                sid = by_name.get((entry.get("service") or "").strip())
                if not sid:
                    continue
                reward["service_id"] = sid
            out.append(reward)
        return out

    async def tenant_row(self, tenant: str) -> dict[str, Any] | None:
        """This establishment's sector row — sector, integrated, when it was written.

        Returns None for a tenant provisioned before we recorded any of this, which the callers
        treat as "nothing known" rather than as a default. A guess here renders a plate field in a
        salon, or retires a catalogue nobody asked us to touch.
        """
        return await self._s.get(TENANT_SECTOR, tenant)

    async def mark_sandbox(self, tenant: str, *, expires_at: int = 0) -> bool:
        """Mark an establishment as a vendor's test shop, with a date it stops being one.

        A SANDBOX IS A REAL TENANT WITH A LABEL, not a second code path. Every branch that says
        "if this is the test system" is a branch nobody exercises against production, and the
        integration a vendor proves in it is then the integration that fails on their first real
        shop. So it is the same routes, the same validation, the same refusals — and the label
        exists for exactly two things: it earns nobody commission, and it does not count as a
        customer.
        """
        row = await self.tenant_row(tenant)
        if row is None:
            return False
        row["sandbox"] = True
        # AN EXPIRY, BECAUSE A TEST SHOP IS NEVER CLEANED UP BY THE PERSON WHO MADE IT. Without a
        # date, a demo tenant from a sales call two years ago is still on the cluster holding
        # somebody's phone number in a customer row.
        if expires_at:
            row["sandbox_until"] = int(expires_at)
        await self._s.put(TENANT_SECTOR, tenant, row)
        return True

    async def mark_integrated(self, tenant: str) -> bool:
        """Record that this shop's till talks to us. Idempotent; False when there was no row.

        WRITTEN ONCE AND NEVER UNSET. Integration is a fact about the shop, not a state that
        toggles: a till that goes quiet for a week has not become a manual shop, and un-marking it
        would re-seed a catalogue its invoices already built.
        """
        row = await self.tenant_row(tenant)
        if row is None:
            return False
        if row.get("integrated"):
            return True
        await self._s.put(TENANT_SECTOR, tenant,
                          {**row, "integrated": True, "updated": int(time.time())})
        return True

    async def sector_of(self, tenant: str) -> str:
        """Which sector this establishment is, or empty if it was provisioned before we recorded
        it. Empty is answered honestly and never guessed - a guess here renders a plate field in a
        salon, or hides one in a workshop."""
        row = await self._s.get(TENANT_SECTOR, tenant)
        return str((row or {}).get("sector") or "")
