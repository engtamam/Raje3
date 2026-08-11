"""Storage for reminders' entities — and the one place tenant isolation is enforced.

SAME SHAPE AS OPERATIONS, AND FOR THE SAME REASON. A handler that remembers to filter by tenant is
a handler that can forget, and the forgetting is invisible: the endpoint works, the tests pass
against one tenant's data, and the leak is found by a customer. Every read takes the tenant as a
required argument and every write stamps it, so crossing a boundary requires passing the wrong
tenant deliberately — and the tenant comes off a verified token, never off a body.

KEYS ARE PREFIXED BY TENANT: `{tenant}|{natural key}`. The filter is the control; the key layout is
what catches the day the filter is not.

ONE DIFFERENCE FROM OPERATIONS, AND IT MATTERS: these rows are keyed by a NATURAL key, not by a
random id. A second visit for the same customer and service must MOVE the pending reminder rather
than add one. With a random key the collision never happens, the duplicate is created, and the
daily cap turns it into one delivered message and one unexplained suppression — a bug that looks
like a cap problem and is a storage problem.
"""
from __future__ import annotations

from typing import Any

SCHEDULES = "schedules"
RULES = "rules"
SEND_LOG = "send_log"
PREFS = "prefs"
ENGAGEMENT = "engagement"

_PAGE = 100


class _Base:
    collection = ""

    def __init__(self, store) -> None:
        self._s = store

    async def _get(self, key: str) -> dict[str, Any] | None:
        return await self._s.get(self.collection, key) if key else None

    async def _put(self, tenant: str, key: str, row: dict[str, Any]) -> None:
        # The tenant is written into the row as well as the key: `find` filters on the field, and a
        # row whose field disagrees with its key is invisible to every query that matters.
        row["tenant"] = tenant
        await self._s.put(self.collection, key, row)

    async def _find(self, tenant: str, where: dict[str, Any] | None = None, *,
                    limit: int = _PAGE, after: str | None = None,
                    sort: tuple[str, str] = ("created", "desc")) -> tuple[list[dict], str | None]:
        filt: dict[str, Any] = {"tenant": tenant}
        if where:
            filt.update(where)
        return await self._s.find(self.collection, filt, limit=limit, after=after, sort=sort)


class ScheduleStore(_Base):
    collection = SCHEDULES

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._get(key)

    async def upsert(self, tenant: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, key, row)
        return row

    async def pending_for_subject(self, tenant: str, subject_ref: str) -> list[dict[str, Any]]:
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref, "state": "pending"},
                                   limit=200, sort=("due_at", "asc"))
        return rows

    async def due(self, tenant: str, *, now: int, limit: int = _PAGE) -> list[dict[str, Any]]:
        """Pending rows whose time has come, oldest first.

        SCOPED TO ONE TENANT, deliberately, even though the tick sweeps all of them. A query that
        crosses tenants here would be the one place in the service where a bug leaks rather than
        merely misbehaves — so the tick iterates tenants and this stays boring.
        """
        rows, _ = await self._find(tenant, {"state": "pending"}, limit=limit,
                                   sort=("due_at", "asc"))
        return [r for r in rows if int(r.get("due_at", 0)) <= now]

    async def cancel_kind(self, tenant: str, subject_ref: str, service_id: str, kind: str,
                          *, reason: str, now: int) -> int:
        """Cancel pending rows of one kind for one customer and service.

        This is what a new visit calls: asking how last month's service went while the customer is
        standing at the counter is the bug spec 5.6 names, and the fix is a cancel, not a filter at
        send time — a row that survives to the tick will eventually find a moment when nothing
        stops it.
        """
        n = 0
        for r in await self.pending_for_subject(tenant, subject_ref):
            if r.get("service_id") == service_id and r.get("kind") == kind:
                r["state"] = "cancelled"
                r["reason"] = reason
                r["updated"] = now
                # Recomputed, never read off the row. `key` is a property on the dataclass and
                # `asdict` does not serialise properties — trusting a `key` field here would work
                # in a test that hand-built the dict and write to a fresh row in production.
                await self._put(tenant, _sched_key(r), r)
                n += 1
        return n


def _sched_key(row: dict[str, Any]) -> str:
    return f"{row['tenant']}|{row['subject_ref']}|{row['service_id']}|{row['kind']}"


class RuleStore(_Base):
    collection = RULES

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._get(key)

    async def upsert(self, tenant: str, key: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, key, row)
        return row

    async def for_service(self, tenant: str, service_id: str) -> list[dict[str, Any]]:
        rows, _ = await self._find(tenant, {"service_id": service_id}, limit=200,
                                   sort=("updated", "desc"))
        return rows


class SendLogStore(_Base):
    collection = SEND_LOG

    async def append(self, tenant: str, row: dict[str, Any]) -> dict[str, Any]:
        # Append-only, keyed by the random send id. A cap enforced by counting rows must never be
        # relieved by overwriting one.
        await self._put(tenant, f"{tenant}|{row['id']}", row)
        return row

    async def get(self, tenant: str, send_id: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{send_id}")

    async def live_offers(self, tenant: str, subject_ref: str, *,
                          now: int) -> list[dict[str, Any]]:
        """EVERY offer this customer is still holding, soonest to expire first.

        The field screen wants one line and takes the first; the customer's own page wants the lot,
        because a shop that ran two offers this month sent him two and he is holding both. Showing
        him one would be the product deciding which of his own messages counts.

        SORTED BY WHAT RUNS OUT FIRST, which is the order he needs to act in — not by when they
        arrived, which is an order only we care about.
        """
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref, "outcome": "sent"},
                                   limit=200, sort=("at", "desc"))
        # AND NOT ALREADY SPENT. An offer is an entitlement with THREE ways to end: it expires, it
        # is used, or the shop stops sending. Only the first was modelled — so a customer who had
        # already had his free wash kept being shown it, and the worker at the counter had no way
        # to tell the difference between an offer and one he had honoured last week.
        live = [r for r in (rows or [])
                if r.get("offer_text")
                and int(r.get("offer_expires_at") or 0) > now
                and not int(r.get("offer_used_at") or 0)]
        return sorted(live, key=lambda r: int(r.get("offer_expires_at") or 0))

    async def consume_offer(self, tenant: str, subject_ref: str, *, visit_id: str,
                            service_ids: list[str], now: int) -> dict[str, Any] | None:
        """Spend ONE offer on ONE visit — and only when somebody says so (§5.6.2).

        FOUR RULES, AND EACH ONE IS A REAL FAILURE WE WOULD OTHERWISE HAVE.

        1. A TAP, NEVER AN INFERENCE. Nothing here runs from a visit arriving: a customer who came
           for something else and was silently charged an offer he was saving is a customer we took
           something from. Silence never spends.
        2. ONE PER VISIT. A second call for the same visit returns the SAME row rather than
           spending another — a double tap at a counter is one intention.
        3. THE SCOPE DECIDES, NOT THE SENTENCE. `offer_services` empty means the whole shop; a
           scoped offer applies only when the visit carries one of its services. The text persuades
           and the scope applies (§5.6.2), which is exactly why both exist.
        4. SOONEST TO EXPIRE FIRST. Holding two, he spends the one about to run out — the other
           survives, and nobody has to explain why the wrong one went.
        """
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref, "outcome": "sent"},
                                   limit=200, sort=("at", "desc"))
        rows = list(rows or [])

        already = next((r for r in rows if r.get("offer_used_visit") == visit_id and visit_id), None)
        if already is not None:
            return already

        wanted = set(service_ids or [])
        applicable = [
            r for r in rows
            if r.get("offer_text")
            and int(r.get("offer_expires_at") or 0) > now
            and not int(r.get("offer_used_at") or 0)
            and (not (r.get("offer_services") or [])
                 or wanted & set(r.get("offer_services") or []))
        ]
        if not applicable:
            return None

        row = sorted(applicable, key=lambda r: int(r.get("offer_expires_at") or 0))[0]
        row["offer_used_at"] = now
        row["offer_used_visit"] = visit_id
        await self._put(tenant, f"{tenant}|{row['id']}", row)
        return row

    async def active_offer(self, tenant: str, subject_ref: str, *,
                           now: int) -> dict[str, Any] | None:
        """The offer this customer is holding right now, or nothing (§5.6.2).

        THE SOURCE IS THE MESSAGE THAT WENT OUT. Not a field an owner filled in a second time —
        what was not sent is not shown, and what was sent is shown in its own words.

        AND AN EXPIRED OFFER IS NOT RETURNED AT ALL, rather than returned with a flag for the
        screen to interpret. A screen that renders an offer which has run out contradicts the
        operator in front of the customer, which is worse than a screen that says nothing.

        THE NEWEST WINS. Two live offers is not a state this product creates, and if it ever did,
        the one the customer received last is the one he is talking about.
        """
        rows, _ = await self._find(tenant, {"subject_ref": subject_ref, "outcome": "sent"},
                                   limit=200, sort=("at", "desc"))
        for row in rows or []:
            if not row.get("offer_text"):
                continue
            if int(row.get("offer_expires_at") or 0) <= now:
                continue
            return row
        return None

    async def since(self, tenant: str, subject_ref: str, *, since: int,
                    cls: str = "") -> list[dict[str, Any]]:
        """Sends to one customer since a moment — the query every cap in spec 8.4.2 is built on.

        BOUNDED AT 500. A customer with more sends than that in a capped window is already a
        failure elsewhere, and an unbounded read on the send path is how a slow query becomes a
        missed batch (playbook: nothing unbounded).
        """
        where: dict[str, Any] = {"subject_ref": subject_ref}
        if cls:
            where["cls"] = cls
        rows, _ = await self._find(tenant, where, limit=500, sort=("at", "desc"))
        return [r for r in rows if int(r.get("at", 0)) >= since]


class PrefsStore(_Base):
    collection = PREFS

    async def get(self, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{subject_ref}")

    async def put(self, tenant: str, subject_ref: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, f"{tenant}|{subject_ref}", row)
        return row


class EngagementStore(_Base):
    collection = ENGAGEMENT

    async def get(self, tenant: str, subject_ref: str) -> dict[str, Any] | None:
        return await self._get(f"{tenant}|{subject_ref}")

    async def put(self, tenant: str, subject_ref: str, row: dict[str, Any]) -> dict[str, Any]:
        await self._put(tenant, f"{tenant}|{subject_ref}", row)
        return row
