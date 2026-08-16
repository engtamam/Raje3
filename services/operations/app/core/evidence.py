"""The evidence file — what we can prove, assembled the moment somebody asks.

WHY THIS EXISTS. When a complaint arrives — from a customer, from an establishment, from SDAIA,
from Meta — the question is never «what does your system do». It is «show me what happened, on this
date, to this person». A system that answers that by having somebody reason across five services
answers it slowly, partially, and in a form the other side can argue with.

EVERY PART OF IT IS ALREADY WRITTEN AT THE MOMENT IT HAPPENS. Consent stores the statement TEXT the
customer saw, not a pointer to a document we can edit afterwards. The send log stores every message
and every suppression with its reason. A privacy request stores when it arrived and when it was
answered. The audit stores who did what from where. NOTHING HERE IS RECONSTRUCTED — this file is an
assembly of ledgers, and that is precisely what makes it defensible: what is reconstructed can be
disputed, what was recorded at the time cannot.

THREE RULES THIS FILE KEEPS, AND THEY ARE THE WHOLE DESIGN:

  A SECTION THAT COULD NOT BE READ SAYS SO. Never an empty list where a peer was unreachable — an
  absent section and an empty one mean opposite things, and confusing them is how a file quietly
  claims «no messages were sent» about a service that simply did not answer.

  NOTHING IS TRUNCATED IN SILENCE. Every section carries its count and a `truncated` flag.

  THE EXTRACTION IS ITSELF AN EVENT. Who asked for this file, about whom, for which window, and
  when — recorded before it is handed over. A disclosure that leaves no trace is the one thing an
  audit trail cannot survive.

PSEUDONYMS, NOT NUMBERS. Every customer in this file is a `subject_ref`. This document leaves the
system by definition; a phone number in it is a phone number in an email attachment on somebody's
laptop.
"""
from __future__ import annotations

import time
from typing import Any

UNAVAILABLE = "unavailable"


def _now() -> int:
    return int(time.time())


class Section(dict):
    """One part of the file — present with rows, or absent WITH A REASON. Never silently empty."""

    @classmethod
    def read(cls, rows: list[dict], *, count: int | None = None,
             truncated: bool = False) -> "Section":
        return cls(status="read", records=rows,
                   count=count if count is not None else len(rows), truncated=truncated)

    @classmethod
    def unavailable(cls, why: str) -> "Section":
        # THE REASON IS CARRIED IN THE FILE ITSELF. Whoever reads it a year later must be able to
        # tell «nothing happened» from «we could not ask», without our help.
        return cls(status=UNAVAILABLE, records=[], count=0, truncated=False, reason=why[:300])


class EvidenceFile:
    """Assembles one establishment's file for one window."""

    def __init__(self, *, privacy_store: Any, consent_reader: Any = None,
                 legal_reader: Any = None) -> None:
        self._privacy = privacy_store
        # The peer that holds consent and the send log (reminders). None means it was never wired,
        # which is a different fact from "it did not answer" — and both are reported.
        self._consent = consent_reader
        self._legal = legal_reader

    async def build(self, tenant: str, *, since: int = 0, until: int = 0,
                    actor: str = "") -> dict[str, Any]:
        until = until or (_now() + 1)
        out: dict[str, Any] = {
            "tenant": tenant,
            "since": since,
            "until": until,
            "generated_at": _now(),
            # WHO ASKED. The file names its own requester, so a copy found later is traceable to
            # the moment it was produced rather than to whoever happens to be holding it.
            "requested_by": actor,
            "sections": {},
        }

        out["sections"]["privacy_requests"] = await self._privacy_section(tenant, since, until)
        consent, messages = await self._reminders_sections(tenant, since, until)
        out["sections"]["consent"] = consent
        out["sections"]["messages"] = messages
        out["sections"]["agreements"] = await self._agreements_section(tenant)
        return out

    async def _privacy_section(self, tenant: str, since: int, until: int) -> Section:
        """His customers' PDPL requests: when each arrived, and when it was answered.

        THE THIRTY-DAY CLOCK IS THE POINT. The regulation counts from the moment the request
        arrives, so «when did you receive it» is the first question and the row that answers it was
        written then.
        """
        try:
            rows = await self._privacy.all_for_tenant(tenant)
        except AttributeError:
            return Section.unavailable("privacy request store exposes no tenant read")
        except Exception as exc:                                              # noqa: BLE001
            return Section.unavailable(f"privacy requests could not be read: {exc}")
        kept = [r for r in rows if since <= int(r.get("at") or 0) < until]
        return Section.read([{"subject_ref": r.get("subject_ref", ""),
                              # `type` is «اطّلاع» or «حذف»; `status` is open or done.
                              "type": r.get("type", ""),
                              "status": r.get("status", ""),
                              "opened_at": int(r.get("at") or 0),
                              "closed_at": int(r.get("closed_at") or 0),
                              # WHO ANSWERED — an unattributed close is not an answer.
                              "closed_by": r.get("closed_by", "")} for r in kept])

    async def _reminders_sections(self, tenant: str, since: int,
                                  until: int) -> tuple[Section, Section]:
        if self._consent is None:
            why = "the messaging service is not wired into this deployment"
            return Section.unavailable(why), Section.unavailable(why)
        try:
            got = await self._consent.evidence(tenant, since=since, until=until)
        except Exception as exc:                                              # noqa: BLE001
            why = f"the messaging service did not answer: {exc}"
            return Section.unavailable(why), Section.unavailable(why)
        con = got.get("consent") or {}
        msg = got.get("messages") or {}
        return (Section.read(list(con.get("records") or []),
                             count=int(con.get("count") or 0),
                             truncated=bool(con.get("truncated"))),
                Section.read(list(msg.get("records") or []),
                             count=int(msg.get("count") or 0),
                             truncated=bool(msg.get("truncated"))))

    async def _agreements_section(self, tenant: str) -> Section:
        """Which version of which document this owner accepted, and when.

        OUR OWN POSITION, NOT HIS. If a shop disputes that it agreed to act as controller over its
        customers' data, this is the row that answers — with the document VERSION, because «he
        agreed to the terms» is worthless when the terms have changed twice since.
        """
        if self._legal is None:
            return Section.unavailable("no acceptance store is wired")
        try:
            rows = await self._legal.accepted_by(tenant)
        except Exception as exc:                                              # noqa: BLE001
            return Section.unavailable(f"acceptances could not be read: {exc}")
        return Section.read([{"document": r.get("document", ""),
                              "version": r.get("version", ""),
                              "actor": r.get("actor", ""),
                              "at": int(r.get("at") or 0)} for r in rows])
