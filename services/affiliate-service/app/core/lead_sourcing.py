# =============================================================================
# affiliate-service — §٦ Lead Sourcing: the resumable search job + dedup + assignment
# -----------------------------------------------------------------------------
# Tamam's own conversion plan for places_scraper_v2.py, followed exactly:
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
    AFFILIATES,
    JOB_COMPLETED,
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    LEAD_ASSIGNED,
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


class LeadError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class LeadSourcingService:
    def __init__(self, *, store, keys, onboarding, default_delay_seconds: float = 0.0) -> None:
        self._s = store
        self._keys = keys              # LeadSourcingKeys — resolve() gives the manager's own key
        self._onboarding = onboarding  # OnboardingService — team() for the assignment ownership check
        self._delay = default_delay_seconds

    # ── starting a search ─────────────────────────────────────────────────────────────────────
    async def start_job(self, affiliate_id: str, *, place_type: str, keywords: list[str],
                        radius_km: float, cities: list[dict[str, Any]],
                        apply_filter: bool = False,
                        filter_indicators: list[str] | None = None) -> dict[str, Any]:
        row = await self._s.get(AFFILIATES, affiliate_id)
        affiliate = Affiliate.from_dict(row) if row else None
        if affiliate is None:
            raise LeadError("المسوّق غير موجود.", reason="not_found")
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
            keywords=list(keywords), radius_km=radius_km, cities=list(cities),
            apply_filter=apply_filter, filter_indicators=list(filter_indicators or []),
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
        found, duplicates = await self._search_one_unit(
            client, lat=lat, lng=lng, radius_km=job.radius_km, keyword=keyword, job=job,
            city=city)
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
                               city: dict[str, Any]) -> tuple[int, int]:
        """One (point, keyword) unit — pagination and auto-split included, same shape as
        places_scraper_v2.py's own `fetch_with_autosplit`, just synchronous-and-bounded rather
        than looping the whole grid."""
        places = self._fetch_all_pages(client, lat, lng, radius_km * 1000, keyword)
        found = duplicates = 0
        if len(places) >= _MAX_PAGE_RESULTS and radius_km > 2.5:
            for olat, olng in split_offsets(radius_km):
                sub = self._fetch_all_pages(client, lat + olat, lng + olng, 2500, keyword)
                f, d = await self._ingest(sub, job=job, city=city)
                found += f
                duplicates += d
        else:
            found, duplicates = await self._ingest(places, job=job, city=city)
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
                      city: dict[str, Any]) -> tuple[int, int]:
        found = duplicates = 0
        for place in places:
            place_id = place.get("place_id", "")
            name = place.get("name", "")
            indicators = job.filter_indicators if job.apply_filter else []
            if not place_id or not matches_indicators(name, indicators):
                continue
            # place_id already known ⇒ skip WITHOUT spending a Details call on it at all.
            if await self._s.get(LEADS, place_id) is not None:
                duplicates += 1
                continue
            found += 1
            await self._save_new_or_merge(place, job=job, city=city)
        return found, duplicates

    async def _save_new_or_merge(self, place: dict, *, job: LeadSearchJob,
                                 city: dict[str, Any]) -> None:
        place_id = place.get("place_id", "")
        api_key = await self._keys.resolve(job.affiliate_id)
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
            place_type=job.place_type, city=city.get("name", ""), region=city.get("region", ""),
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

        lead.assigned_to = promoter_id
        lead.status = LEAD_ASSIGNED
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return lead
