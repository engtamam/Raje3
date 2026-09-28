# =============================================================================
# affiliate-service — §6 Lead Sourcing: the resumable search job + dedup + assignment
# -----------------------------------------------------------------------------
# The conversion plan for places_scraper_v2.py, followed exactly:
#   1. CLI→CSV becomes a background job writing straight to the leads table (no CSV, ever).
#   2. The Google API key is BYOK per manager (core/leads.py), never hardcoded.
#   3. The manager sees progress; he never waits on it.
#
# WHY A CURSOR, NOT A LOOP. places_scraper_v2.py's own cost estimate is 3–5 HOURS for the full
# 10-city run — running that inside one request/response, or even one in-process background
# task tied to a pod's lifetime, means a routine deploy loses hours of progress. `step()`
# processes exactly ONE (city, grid point, keyword) unit and persists the cursor before
# returning — the same "capped, resumable, records where it stopped" shape as
# ReferralRegistry/CommissionEngine's own sweep. A k3s CronJob (like commissions-sweep) calls the
# internal tick route repeatedly; killing the pod mid-run loses at most one unit of work.
#
# DEDUP IS TWO FIELDS, NOT ONE — spec §6 exactly: place_id OR phone. A phone match does not
# discard the new place_id; it is a second branch of the SAME business (Lead.extra_place_ids).
# Global across the WHOLE leads table, never scoped to one manager's own search — two managers
# searching overlapping areas must still find the SAME business once, not twice.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.models import (
    ACTIVE,
    AFFILIATES,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    LEAD_ASSIGNED,
    LEAD_MANUAL_STATUSES,
    LEAD_NOT_INTERESTED,
    LEAD_REGISTERED,
    LEAD_SEARCH_JOBS,
    LEADS,
    Affiliate,
    Lead,
    LeadSearchJob,
    new_id,
)
from app.core.places_client import PlacesClient
from app.core.places_grid import generate_grid, matches_indicators, split_offsets

_MAX_PAGE_RESULTS = 60   # Google's own 3-page × 20 cap — a full point means "there may be more"

# Serialises step() per job — added 2026-09-12, a real gap a QA audit found: the same
# read-then-write cursor race `_REFERRAL_LOCKS`/`_SYNC_LOCKS`/`_PAYOUT_LOCKS` elsewhere in this
# service each exist to close. `step()` is a k3s CronJob's own tick, called repeatedly for a job
# it does not own exclusively — nothing stopped two overlapping tick invocations (a slow tick still
# running when the next scheduled one fires, or two worker pods both ticking the same job) from
# both reading the SAME `job.cursor`, both fetching the SAME (point, keyword) unit twice (a
# duplicate `_search_one_unit`, only wasteful) and then racing the FINAL `put()` — whichever
# finished last would silently overwrite the other's cursor advance, so the loser's own unit of
# work (a found lead, a duplicate count) could be dropped from the persisted cursor entirely.
_STEP_LOCKS = "affiliate_lead_step_locks"
_STEP_LOCK_TTL_SECONDS = 60


class LeadError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


async def owns_lead(store, lead: Lead, affiliate_id: str) -> bool:
    """The ownership check `set_status` originally inlined — extracted once the
    outbound conversion playbook (core/outreach.py) needed the EXACT SAME rule for logging a
    template use or setting its outcome: the lead's own assigned promoter, or that promoter's own
    manager. Never a capability. An unassigned lead belongs to nobody yet — only `assign()` itself
    may act on one, so this returns False rather than falling back to source_manager_id (a
    DIFFERENT ownership rule, still inlined in `assign`/`link_registration` on purpose: they are
    answering "is this MY search result", not "is this MY lead to work")."""
    if affiliate_id == lead.assigned_to:
        return True
    if not lead.assigned_to:
        return False
    assignee_row = await store.get(AFFILIATES, lead.assigned_to)
    assignee = Affiliate.from_dict(assignee_row) if assignee_row else None
    return assignee is not None and assignee.parent_id == affiliate_id


class LeadSourcingService:
    def __init__(self, *, store, keys, onboarding, sectors=None,
                default_delay_seconds: float = 0.0) -> None:
        self._s = store
        self._keys = keys              # LeadSourcingKeys — resolve() gives the manager's own key
        self._onboarding = onboarding  # OnboardingService — team() for the assignment ownership check
        self._sectors = sectors        # SectorService — validates sector_code at request time
        self._delay = default_delay_seconds

    # ── starting a search ─────────────────────────────────────────────────────────────────────
    async def start_job(self, affiliate_id: str, *, place_type: str, sector_code: str,
                        keywords: list[str], radius_km: float, cities: list[dict[str, Any]],
                        apply_filter: bool = False,
                        filter_indicators: list[str] | None = None) -> dict[str, Any]:
        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None:
            raise LeadError("المسوّق غير موجود.", reason="not_found")
        if not sector_code:
            raise LeadError("اختر قطاعًا للبحث.", reason="no_sector")
        if self._sectors is not None:
            sector = await self._sectors.get(sector_code)
            if sector is None or not sector.active:
                raise LeadError("القطاع غير معروف أو غير مفعّل.", reason="unknown_sector")
        if not keywords:
            raise LeadError("أدخل كلمة بحث واحدة على الأقل.", reason="no_keywords")
        if not cities:
            raise LeadError("أدخل مدينة واحدة على الأقل.", reason="no_cities")
        for c in cities:
            if not all(k in c for k in ("name", "lat", "lng", "w_km", "h_km")):
                raise LeadError("بيانات مدينة ناقصة (name/lat/lng/w_km/h_km).",
                                reason="bad_city")

        job = LeadSearchJob(
            id=new_id(), affiliate_id=affiliate_id, place_type=place_type,
            sector_code=sector_code, keywords=list(keywords), radius_km=radius_km,
            cities=list(cities), apply_filter=apply_filter,
            filter_indicators=list(filter_indicators or []),
            status=JOB_QUEUED, created_at=int(time.time()),
        )
        await self._s.put(LEAD_SEARCH_JOBS, job.id, job.to_dict())
        return job.to_dict()

    async def get_job(self, job_id: str) -> LeadSearchJob | None:
        row = await self._s.get(LEAD_SEARCH_JOBS, job_id)
        return LeadSearchJob.from_dict(row) if row else None

    async def jobs_of(self, affiliate_id: str, *, limit: int = 100) -> list[LeadSearchJob]:
        rows, _ = await self._s.find(LEAD_SEARCH_JOBS, {"affiliate_id": affiliate_id},
                                     limit=limit, sort=("created_at", "desc"))
        return [LeadSearchJob.from_dict(r) for r in rows]

    # ── one bounded unit of work — see the module docstring on why this is a cursor, not a loop ─
    async def step(self, job_id: str) -> dict[str, Any]:
        """LOCKED PER JOB, so two overlapping calls for the SAME job (see `_STEP_LOCKS`'s own
        comment) never read-then-write the same cursor concurrently. The loser is not queued
        behind the winner — it simply reports `step_in_progress` and the caller (a CronJob tick,
        already built to run again) picks the job up on its own next pass."""
        now0 = int(time.time())
        took = await self._s.claim(
            _STEP_LOCKS, job_id, {"job_id": job_id, "at": now0},
            ttl_seconds=_STEP_LOCK_TTL_SECONDS, now=now0)
        if not took:
            return {"done": False, "status": JOB_RUNNING, "reason": "step_in_progress"}
        try:
            return await self._step_locked(job_id)
        finally:
            await self._s.delete(_STEP_LOCKS, job_id)

    async def _step_locked(self, job_id: str) -> dict[str, Any]:
        job = await self.get_job(job_id)
        if job is None:
            raise LeadError("المهمة غير موجودة.", reason="not_found")
        if job.status in (JOB_COMPLETED, JOB_FAILED):
            return {"done": True, "status": job.status}

        api_key = await self._keys.resolve(job.affiliate_id)
        if not api_key:
            job.status = JOB_FAILED
            job.error = "لا يوجد مفتاح Google API — أضف مفتاحك أولاً."
            job.finished_at = int(time.time())
            await self._s.put(LEAD_SEARCH_JOBS, job.id, job.to_dict())
            return {"done": True, "status": job.status, "error": job.error}

        if job.status == JOB_QUEUED:
            job.status = JOB_RUNNING
            job.started_at = int(time.time())

        city_i = job.cursor.get("city", 0)
        if city_i >= len(job.cities):
            job.status = JOB_COMPLETED
            job.finished_at = int(time.time())
            await self._s.put(LEAD_SEARCH_JOBS, job.id, job.to_dict())
            return {"done": True, "status": job.status}

        city = job.cities[city_i]
        grid = generate_grid(city["lat"], city["lng"], city["w_km"], city["h_km"],
                             step_km=job.radius_km * 1.5)
        point_i = job.cursor.get("point", 0)
        keyword_i = job.cursor.get("keyword", 0)

        if point_i >= len(grid):
            # This city is done — advance to the next one, no unit of API work this tick.
            job.cursor = {"city": city_i + 1, "point": 0, "keyword": 0}
            await self._s.put(LEAD_SEARCH_JOBS, job.id, job.to_dict())
            return {"done": False, "status": job.status, "advanced_city": True}

        lat, lng = grid[point_i]
        keyword = job.keywords[keyword_i]
        client = PlacesClient(api_key=api_key)
        # `api_key` was just resolved above (a store read + AES-GCM decrypt) and cannot change
        # mid-unit — threaded down through _search_one_unit/_ingest/_save_new_or_merge instead of
        # each of them re-resolving it per lead.
        found, duplicates = await self._search_one_unit(
            client, lat=lat, lng=lng, radius_km=job.radius_km, keyword=keyword, job=job,
            city=city, api_key=api_key)
        job.found_count += found
        job.duplicate_count += duplicates

        # Advance the cursor — next keyword, or next point if keywords are exhausted.
        if keyword_i + 1 < len(job.keywords):
            job.cursor = {"city": city_i, "point": point_i, "keyword": keyword_i + 1}
        else:
            job.cursor = {"city": city_i, "point": point_i + 1, "keyword": 0}
        await self._s.put(LEAD_SEARCH_JOBS, job.id, job.to_dict())
        return {"done": False, "status": job.status, "found": found, "duplicates": duplicates}

    async def _search_one_unit(self, client: PlacesClient, *, lat: float, lng: float,
                               radius_km: float, keyword: str, job: LeadSearchJob,
                               city: dict[str, Any], api_key: str) -> tuple[int, int]:
        """One (point, keyword) unit — pagination and auto-split included, same shape as
        places_scraper_v2.py's own `fetch_with_autosplit`, just synchronous-and-bounded rather
        than looping the whole grid."""
        places = self._fetch_all_pages(client, lat, lng, radius_km * 1000, keyword)
        found = duplicates = 0
        if len(places) >= _MAX_PAGE_RESULTS and radius_km > 2.5:
            for olat, olng in split_offsets(radius_km):
                sub = self._fetch_all_pages(client, lat + olat, lng + olng, 2500, keyword)
                f, d = await self._ingest(sub, job=job, city=city, api_key=api_key)
                found += f
                duplicates += d
        else:
            found, duplicates = await self._ingest(places, job=job, city=city, api_key=api_key)
        return found, duplicates

    def _fetch_all_pages(self, client: PlacesClient, lat: float, lng: float, radius_m: float,
                         keyword: str) -> list[dict]:
        results: list[dict] = []
        page_token = ""
        for _ in range(3):   # Google's own hard cap: 3 pages of 20
            data = client.search(lat=lat, lng=lng, radius_m=int(radius_m), keyword=keyword,
                                 page_token=page_token)
            if not data or data.get("status") not in ("OK", "ZERO_RESULTS"):
                break
            results.extend(data.get("results", []))
            page_token = data.get("next_page_token", "")
            if not page_token:
                break
        return results

    async def _ingest(self, places: list[dict], *, job: LeadSearchJob,
                      city: dict[str, Any], api_key: str) -> tuple[int, int]:
        candidates = []
        for place in places:
            place_id = place.get("place_id", "")
            name = place.get("name", "")
            indicators = job.filter_indicators if job.apply_filter else []
            if place_id and matches_indicators(name, indicators):
                candidates.append(place)

        # ONE batched membership query instead of up to _MAX_PAGE_RESULTS (60) sequential
        # `get(LEADS, place_id)` dedup checks — DataStore.find's `{field: [values]}` form is an
        # indexed IN-query on both adapters (see ports/datastore.py's own note on it). Same
        # dedup rule as before: LEADS is keyed by place_id, so a hit on the `place_id` field is
        # exactly the same "already known" fact a direct key lookup would have found.
        existing_ids: set[str] = set()
        place_ids = [p.get("place_id", "") for p in candidates]
        if place_ids:
            rows, _ = await self._s.find(LEADS, {"place_id": place_ids}, limit=len(place_ids),
                                         sort=("found_at", "desc"))
            existing_ids = {r.get("place_id", "") for r in rows}

        found = duplicates = 0
        seen_in_batch: set[str] = set()
        for place in candidates:
            place_id = place.get("place_id", "")
            # `seen_in_batch` covers the (unlikely but possible) case of the same place_id
            # appearing twice within one page — the sequential version would have caught the
            # second occurrence via a fresh get() after the first was saved; the batched
            # pre-check alone would miss it.
            if place_id in existing_ids or place_id in seen_in_batch:
                duplicates += 1
                continue
            seen_in_batch.add(place_id)
            found += 1
            await self._save_new_or_merge(place, job=job, city=city, api_key=api_key)
        return found, duplicates

    async def _save_new_or_merge(self, place: dict, *, job: LeadSearchJob,
                                 city: dict[str, Any], api_key: str) -> None:
        place_id = place.get("place_id", "")
        client = PlacesClient(api_key=api_key)
        details = client.details(place_id)
        phone = details.get("formatted_phone_number", "")

        if phone:
            rows, _ = await self._s.find(LEADS, {"phone": phone}, limit=1)
            if rows:
                existing = Lead.from_dict(rows[0])
                if place_id not in existing.extra_place_ids and place_id != existing.place_id:
                    existing.extra_place_ids.append(place_id)
                    await self._s.put(LEADS, existing.id, existing.to_dict())
                # Deliberately NO second row keyed by place_id: this collection is listed by
                # source_manager_id (leads_of_manager) and a second stored copy of the SAME
                # business would double-count it there. A place_id already merged in
                # extra_place_ids is caught on a later encounter by the phone check above, not a
                # direct-key lookup — the one-time cost is re-fetching Details for an
                # already-merged branch, never a duplicate Lead.
                return

        wt = details.get("opening_hours", {}).get("weekday_text", [])
        lead = Lead(
            id=place_id, place_id=place_id, phone=phone,
            name=details.get("name") or place.get("name", ""),
            place_type=job.place_type, sector_code=job.sector_code,
            city=city.get("name", ""), region=city.get("region", ""),
            address=details.get("formatted_address") or place.get("vicinity", ""),
            maps_url=details.get("url") or
                    f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            rating=float(details.get("rating") or place.get("rating") or 0.0),
            ratings_count=int(details.get("user_ratings_total") or
                              place.get("user_ratings_total") or 0),
            opening_hours=" | ".join(wt) if wt else "",
            website=details.get("website", ""),
            lat=float(place.get("geometry", {}).get("location", {}).get("lat", 0.0) or 0.0),
            lng=float(place.get("geometry", {}).get("location", {}).get("lng", 0.0) or 0.0),
            source_manager_id=job.affiliate_id, found_at=int(time.time()),
        )
        await self._s.put(LEADS, lead.id, lead.to_dict())

    # ── the manager's own results + assignment (spec §6's own "الإسناد") ────────────────────────
    async def get_lead(self, lead_id: str, *, affiliate_id: str) -> Lead:
        """A single lead's own detail — spec §9's scoping again, one row at a time: visible to
        whoever `GET /me/leads` would already have shown it to, so this is never a second,
        looser rule than the list. A manager sees his own search result (`source_manager_id`)
        whether or not it has been handed out yet; anyone in the assignment chain sees an
        assigned lead via `owns_lead` (the same rule `set_status`/`outreach.py` already use)."""
        row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(row) if row else None
        if lead is None:
            raise LeadError("العميل المحتمل غير موجود.", reason="not_found")
        if lead.source_manager_id == affiliate_id or await owns_lead(self._s, lead, affiliate_id):
            return lead
        raise LeadError("هذا العميل المحتمل ليس ضمن قائمتك.", reason="not_yours")

    async def leads_of_manager(self, affiliate_id: str, *, limit: int = 500) -> list[Lead]:
        rows, _ = await self._s.find(LEADS, {"source_manager_id": affiliate_id}, limit=limit,
                                     sort=("found_at", "desc"))
        return [Lead.from_dict(r) for r in rows]

    async def leads_assigned_to(self, affiliate_id: str, *, limit: int = 500) -> list[Lead]:
        """A promoter's OWN list — spec §9: "كل مسوّق يشوف فقط العملاء المحتملين المُسنَدين له،
        لا القائمة الكاملة"."""
        rows, _ = await self._s.find(LEADS, {"assigned_to": affiliate_id}, limit=limit,
                                     sort=("found_at", "desc"))
        return [Lead.from_dict(r) for r in rows]

    async def stale_leads(self, affiliate_id: str, *, stale_after_seconds: int = 3 * 86400,
                          now: int | None = None, limit: int = 500) -> list[Lead]:
        """A home screen's "بانتظارك الآن" candidate — a lead assigned to him with NO activity
        (no note written, not even a status change) in the last `stale_after_seconds`. Never a
        stored flag: computed fresh every read from `Lead.notes`' own timestamps, the same
        append-only log every other action here already writes to, so nothing new has to be
        kept in sync with lead activity.

        LEAD_REGISTERED and LEAD_NOT_INTERESTED are excluded — both are a closed outcome, not
        something "waiting" on the promoter; a lead sitting in either forever is not stale, it is
        finished."""
        now = now if now is not None else int(time.time())
        leads = await self.leads_assigned_to(affiliate_id, limit=limit)
        out = []
        for lead in leads:
            if lead.status in (LEAD_REGISTERED, LEAD_NOT_INTERESTED):
                continue
            last_activity = max([n.get("at", 0) for n in lead.notes], default=lead.found_at)
            if now - last_activity >= stale_after_seconds:
                out.append(lead)
        return out

    def _note(self, lead: Lead, *, by: str, text: str = "", status_from: str = "",
             status_to: str = "") -> None:
        """APPEND-ONLY ("خانة ملاحظات عشان ما ينسى وش سار") — every status
        change and every reassignment writes its own entry automatically; a free-text note is
        just one more entry in the SAME log, never a second, separate history to keep in sync."""
        lead.notes.append({"at": int(time.time()), "by": by, "text": text,
                           "status_from": status_from, "status_to": status_to})

    async def assign(self, lead_id: str, *, manager_id: str, promoter_id: str) -> Lead:
        lead_row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(lead_row) if lead_row else None
        if lead is None:
            raise LeadError("العميل المحتمل غير موجود.", reason="not_found")
        if lead.source_manager_id != manager_id:
            # Ownership, not RBAC — a manager assigns only what HIS OWN search found, same
            # boundary GET /me/team/wafa-requests already draws.
            raise LeadError("هذا العميل المحتمل ليس ضمن نتائج بحثك.", reason="not_yours")

        members = await self._onboarding.team(manager_id)
        if promoter_id not in {m["id"] for m in members}:
            raise LeadError("هذا المسوّق ليس ضمن فريقك.", reason="not_on_your_team")
        member = next((m for m in members if m["id"] == promoter_id), None)
        if member is None or member.get("status") != ACTIVE:
            raise LeadError("هذا المسوّق موقوف حالياً.", reason="promoter_suspended")

        previous = lead.assigned_to
        self._note(lead, by=manager_id,
                  text=(f"أُعيد الإسناد من {previous} إلى {promoter_id}" if previous
                       else f"أُسنِد إلى {promoter_id}"),
                  status_from=lead.status, status_to=LEAD_ASSIGNED)
        lead.assigned_to = promoter_id
        lead.status = LEAD_ASSIGNED
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return lead

    # ── the follow-up pipeline — spec's own point: a marketer must be able to track it ──────────
    async def set_status(self, lead_id: str, *, affiliate_id: str, new_status: str,
                         text: str = "") -> Lead:
        """Only the assigned promoter, or his OWN manager, may move a lead through the pipeline —
        ownership, never a capability, same shape as everything else in this file.
        LEAD_NEW/LEAD_ASSIGNED/LEAD_REGISTERED are never reachable here (see LEAD_MANUAL_STATUSES'
        own note) — a promoter cannot fake "registered" without actually calling
        link_registration() against a real referral."""
        if new_status not in LEAD_MANUAL_STATUSES:
            raise LeadError("حالة غير معروفة.", reason="bad_status")
        lead_row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(lead_row) if lead_row else None
        if lead is None:
            raise LeadError("العميل المحتمل غير موجود.", reason="not_found")

        if not await owns_lead(self._s, lead, affiliate_id):
            raise LeadError("ما تقدر تعدّل حالة عميل محتمل مو مُسنَد لك أو لأحد بفريقك.",
                            reason="not_yours")

        self._note(lead, by=affiliate_id, text=text, status_from=lead.status,
                  status_to=new_status)
        lead.status = new_status
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return lead

    # ── linking a lead to the real shop it became — spec's own "ربط بسيط", by hand only ────────
    async def link_registration(self, lead_id: str, *, affiliate_id: str, tenant: str,
                                referrals) -> Lead:
        """A shop sometimes signs up with a DIFFERENT phone than the one
        Google has — the automatic place_id/phone dedup can never catch that. A marketer who
        recognises "this lead is the shop I just referred" says so HIMSELF; nothing here
        attempts to guess it from a name or address. `referrals` is the ReferralRegistry — the
        SAME source of truth GET /me/team's ownership checks already use, never a second,
        driftable notion of "his shop"."""
        lead_row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(lead_row) if lead_row else None
        if lead is None:
            raise LeadError("العميل المحتمل غير موجود.", reason="not_found")
        # His own lead — either he found it (manager) or it was assigned to him (promoter).
        if lead.source_manager_id != affiliate_id and lead.assigned_to != affiliate_id:
            raise LeadError("هذا العميل المحتمل ليس ضمن قائمتك.", reason="not_yours")

        referral = await referrals.of_tenant(tenant)
        if referral is None or referral.affiliate_id != affiliate_id:
            # The SAME ownership boundary as the ticket routes: he only links a shop that
            # actually referred THROUGH HIM, never any tenant in the system.
            raise LeadError("هذا المحل ليس ضمن إحالاتك.", reason="not_your_referral")

        self._note(lead, by=affiliate_id, text=f"سُجِّل كمحل حقيقي: {tenant}",
                  status_from=lead.status, status_to=LEAD_REGISTERED)
        lead.converted_tenant = tenant
        lead.status = LEAD_REGISTERED
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return lead

    # ── §6's own point: sector/city analytics for a data-driven dashboard ────────────────────────
    async def sector_stats(self, *, affiliate_id: str = "", limit: int = 5000) -> list[dict[str, Any]]:
        """Counts grouped by (sector_code, city), WITH a full status breakdown per group
        ("تنضاف هذه على الداشبورد الشاملة حقت المدير") — `affiliate_id` scopes to one
        manager's own finds (his team dashboard); blank scans the whole table (the platform-wide
        admin view). A bounded scan over a config-sized collection, same idiom as
        SectorService.list — never the shape of a request-path read."""
        if affiliate_id:
            rows, _ = await self._s.find(LEADS, {"source_manager_id": affiliate_id}, limit=limit)
        else:
            rows = await self._s.scan_all(LEADS, limit)
        counts: dict[tuple[str, str], int] = {}
        by_status: dict[tuple[str, str], dict[str, int]] = {}
        for r in rows:
            key = (r.get("sector_code", ""), r.get("city", ""))
            counts[key] = counts.get(key, 0) + 1
            bucket = by_status.setdefault(key, {})
            st = r.get("status", "")
            bucket[st] = bucket.get(st, 0) + 1
        return [{"sector_code": k[0], "city": k[1], "lead_count": v,
                "by_status": by_status.get(k, {}),
                "registered_count": by_status.get(k, {}).get(LEAD_REGISTERED, 0)}
               for k, v in sorted(counts.items())]
