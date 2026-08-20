"""§٦ Lead Sourcing's resumable engine — the properties worth a test:

  * step() advances the cursor by exactly one (point, keyword) unit and persists it
  * a NEW place_id creates a Lead; the SAME place_id again is a duplicate, not a second row
  * a DIFFERENT place_id with the SAME phone merges as a branch, never a second Lead
  * a job with no configured key fails cleanly rather than crashing
  * the cursor rolls from keyword -> point -> city correctly, and the job completes
  * a manager may only assign what HIS OWN search found, to someone on HIS OWN team
"""
from __future__ import annotations

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.lead_sourcing import LeadError, LeadSourcingService
from app.core.models import ACTIVE, AFFILIATES, JOB_COMPLETED, JOB_FAILED, JOB_RUNNING, Affiliate

RIYADH = {"name": "الرياض", "region": "منطقة الرياض", "lat": 24.7136, "lng": 46.6753,
         "w_km": 2, "h_km": 2}


class FakeKeys:
    def __init__(self, key: str = "AIzaFakeKey") -> None:
        self._key = key

    async def resolve(self, affiliate_id: str) -> str:
        return self._key


class FakeOnboarding:
    def __init__(self, teams: dict[str, list[str]]) -> None:
        self._teams = teams   # manager_id -> [promoter_id, ...]

    async def team(self, manager_id: str) -> list[dict]:
        return [{"id": p} for p in self._teams.get(manager_id, [])]


def _place(place_id: str, name: str = "صالون تجريبي") -> dict:
    return {"place_id": place_id, "name": name,
           "geometry": {"location": {"lat": 24.71, "lng": 46.67}}}


class FakePlacesClient:
    """Driven by a scripted response list — one `search()` call consumes the next scripted
    result, `details()` looks up by place_id. Deterministic, no network."""

    def __init__(self, *, api_key: str, timeout: int = 10) -> None:
        self.api_key = api_key

    # Class-level scripting so the test controls what the NEXT constructed instance answers —
    # core/lead_sourcing.py constructs a fresh PlacesClient per call, same as the real one.
    search_results: list[dict] = []
    details_by_id: dict[str, dict] = {}

    def search(self, *, lat, lng, radius_m, keyword, page_token=""):
        if page_token:
            return {"status": "OK", "results": []}
        if FakePlacesClient.search_results:
            return {"status": "OK", "results": [FakePlacesClient.search_results.pop(0)]}
        return {"status": "ZERO_RESULTS", "results": []}

    def details(self, place_id: str) -> dict:
        return FakePlacesClient.details_by_id.get(place_id, {})


async def _seed_manager(store, affiliate_id="mgr-1") -> None:
    row = Affiliate(id=affiliate_id, person_id="p1", phone="+966501234567", name="مدير",
                    role="affiliate_manager", status=ACTIVE)
    await store.put(AFFILIATES, affiliate_id, row.to_dict())


def build(store, *, keys=None, onboarding=None) -> LeadSourcingService:
    return LeadSourcingService(store=store, keys=keys or FakeKeys(),
                               onboarding=onboarding or FakeOnboarding({}))


@pytest.fixture(autouse=True)
def _patch_client(monkeypatch):
    FakePlacesClient.search_results = []
    FakePlacesClient.details_by_id = {}
    monkeypatch.setattr("app.core.lead_sourcing.PlacesClient", FakePlacesClient)
    yield


@pytest.mark.anyio
async def test_start_job_refuses_with_no_keywords():
    store = MemoryDataStore()
    await _seed_manager(store)
    svc = build(store)
    with pytest.raises(LeadError) as exc:
        await svc.start_job("mgr-1", place_type="صالون", keywords=[], radius_km=5,
                            cities=[RIYADH])
    assert exc.value.reason == "no_keywords"


@pytest.mark.anyio
async def test_start_job_refuses_with_a_bad_city():
    store = MemoryDataStore()
    await _seed_manager(store)
    svc = build(store)
    with pytest.raises(LeadError) as exc:
        await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                            cities=[{"name": "ناقصة"}])
    assert exc.value.reason == "bad_city"


@pytest.mark.anyio
async def test_step_with_no_api_key_fails_the_job_cleanly():
    store = MemoryDataStore()
    await _seed_manager(store)
    svc = build(store, keys=FakeKeys(key=""))
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                              cities=[RIYADH])
    out = await svc.step(job["id"])
    assert out["done"] is True
    assert out["status"] == JOB_FAILED


@pytest.mark.anyio
async def test_a_new_place_creates_a_lead_and_advances_the_cursor():
    store = MemoryDataStore()
    await _seed_manager(store)
    FakePlacesClient.search_results = [_place("place-1")]
    FakePlacesClient.details_by_id = {"place-1": {"name": "صالون الرياض",
                                                  "formatted_phone_number": "+966501112222"}}
    svc = build(store)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                              cities=[RIYADH])
    out = await svc.step(job["id"])
    assert out["done"] is False
    assert out["found"] == 1

    leads = await svc.leads_of_manager("mgr-1")
    assert len(leads) == 1
    assert leads[0].place_id == "place-1"
    assert leads[0].phone == "+966501112222"

    updated = await svc.get_job(job["id"])
    assert updated.status == JOB_RUNNING
    assert updated.found_count == 1


@pytest.mark.anyio
async def test_the_same_place_id_again_is_a_duplicate_not_a_second_lead():
    store = MemoryDataStore()
    await _seed_manager(store)
    FakePlacesClient.details_by_id = {"place-1": {"name": "صالون", "formatted_phone_number": "+9665"}}
    svc = build(store)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون", "salon"], radius_km=5,
                              cities=[RIYADH])
    FakePlacesClient.search_results = [_place("place-1")]
    await svc.step(job["id"])                      # first keyword — creates the lead
    FakePlacesClient.search_results = [_place("place-1")]
    out = await svc.step(job["id"])                 # second keyword — same place_id

    assert out["duplicates"] == 1
    assert out["found"] == 0
    leads = await svc.leads_of_manager("mgr-1")
    assert len(leads) == 1


@pytest.mark.anyio
async def test_a_different_place_id_with_the_same_phone_merges_as_a_branch():
    store = MemoryDataStore()
    await _seed_manager(store)
    svc = build(store)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون", "salon"], radius_km=5,
                              cities=[RIYADH])

    FakePlacesClient.details_by_id = {"place-1": {"name": "فرع 1", "formatted_phone_number": "+9665551"}}
    FakePlacesClient.search_results = [_place("place-1", "فرع 1")]
    await svc.step(job["id"])

    FakePlacesClient.details_by_id["place-2"] = {"name": "فرع 2", "formatted_phone_number": "+9665551"}
    FakePlacesClient.search_results = [_place("place-2", "فرع 2")]
    await svc.step(job["id"])

    leads = await svc.leads_of_manager("mgr-1")
    assert len(leads) == 1                          # ONE lead, not two
    assert leads[0].place_id == "place-1"
    assert leads[0].extra_place_ids == ["place-2"]


@pytest.mark.anyio
async def test_cursor_rolls_keyword_then_point_then_city_and_the_job_completes():
    store = MemoryDataStore()
    await _seed_manager(store)
    tiny_city = {"name": "بلدة صغيرة", "region": "ر", "lat": 24.7136, "lng": 46.6753,
                "w_km": 0.001, "h_km": 0.001}   # a single grid point
    svc = build(store)
    job = await svc.start_job("mgr-1", place_type="محل", keywords=["أ", "ب"], radius_km=5,
                              cities=[tiny_city])

    out1 = await svc.step(job["id"])   # point 0, keyword "أ"
    assert out1["done"] is False
    out2 = await svc.step(job["id"])   # point 0, keyword "ب"
    assert out2["done"] is False
    out3 = await svc.step(job["id"])   # point index now out of range -> advance city
    assert out3.get("advanced_city") is True
    out4 = await svc.step(job["id"])   # no more cities -> completed
    assert out4["done"] is True
    assert out4["status"] == JOB_COMPLETED


@pytest.mark.anyio
async def test_stepping_a_completed_job_is_a_clean_no_op():
    store = MemoryDataStore()
    await _seed_manager(store)
    tiny_city = {"name": "بلدة", "region": "ر", "lat": 24.7136, "lng": 46.6753,
                "w_km": 0.001, "h_km": 0.001}
    svc = build(store)
    job = await svc.start_job("mgr-1", place_type="محل", keywords=["أ"], radius_km=5,
                              cities=[tiny_city])
    await svc.step(job["id"])   # the one point
    await svc.step(job["id"])   # advance past the city
    done = await svc.step(job["id"])
    assert done["status"] == JOB_COMPLETED
    again = await svc.step(job["id"])
    assert again == {"done": True, "status": JOB_COMPLETED}


@pytest.mark.anyio
async def test_stepping_an_unknown_job_is_refused_not_a_crash():
    store = MemoryDataStore()
    svc = build(store)
    with pytest.raises(LeadError) as exc:
        await svc.step("no-such-job")
    assert exc.value.reason == "not_found"


# ── assignment — ownership on both ends ─────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_a_manager_assigns_his_own_lead_to_his_own_team_member():
    store = MemoryDataStore()
    await _seed_manager(store)
    onboarding = FakeOnboarding({"mgr-1": ["prm-1"]})
    svc = build(store, onboarding=onboarding)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                              cities=[RIYADH])
    FakePlacesClient.details_by_id = {"place-1": {"name": "صالون", "formatted_phone_number": "+9665"}}
    FakePlacesClient.search_results = [_place("place-1")]
    await svc.step(job["id"])
    lead = (await svc.leads_of_manager("mgr-1"))[0]

    out = await svc.assign(lead.id, manager_id="mgr-1", promoter_id="prm-1")
    assert out.assigned_to == "prm-1"
    assert out.status == "assigned"

    assigned = await svc.leads_assigned_to("prm-1")
    assert len(assigned) == 1


@pytest.mark.anyio
async def test_a_manager_cannot_assign_a_lead_another_managers_search_found():
    store = MemoryDataStore()
    await _seed_manager(store, "mgr-1")
    await _seed_manager(store, "mgr-2")
    onboarding = FakeOnboarding({"mgr-2": ["prm-2"]})
    svc = build(store, onboarding=onboarding)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                              cities=[RIYADH])
    FakePlacesClient.details_by_id = {"place-1": {"name": "صالون", "formatted_phone_number": "+9665"}}
    FakePlacesClient.search_results = [_place("place-1")]
    await svc.step(job["id"])
    lead = (await svc.leads_of_manager("mgr-1"))[0]

    with pytest.raises(LeadError) as exc:
        await svc.assign(lead.id, manager_id="mgr-2", promoter_id="prm-2")
    assert exc.value.reason == "not_yours"


@pytest.mark.anyio
async def test_a_manager_cannot_assign_to_someone_outside_his_team():
    store = MemoryDataStore()
    await _seed_manager(store)
    onboarding = FakeOnboarding({"mgr-1": ["prm-1"]})
    svc = build(store, onboarding=onboarding)
    job = await svc.start_job("mgr-1", place_type="صالون", keywords=["صالون"], radius_km=5,
                              cities=[RIYADH])
    FakePlacesClient.details_by_id = {"place-1": {"name": "صالون", "formatted_phone_number": "+9665"}}
    FakePlacesClient.search_results = [_place("place-1")]
    await svc.step(job["id"])
    lead = (await svc.leads_of_manager("mgr-1"))[0]

    with pytest.raises(LeadError) as exc:
        await svc.assign(lead.id, manager_id="mgr-1", promoter_id="not-on-team")
    assert exc.value.reason == "not_on_your_team"
