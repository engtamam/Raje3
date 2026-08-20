"""The five traps this service has of its own.

Not the generic ones. These are specific to a service that decides who receives a message under
somebody else's name, and each is silent when it goes wrong.
"""
from __future__ import annotations

import ast
import inspect


def _names(path: str) -> set[str]:
    """Every NAME a module references — imports, attributes, calls, short string literals.

    Read from the AST rather than the text. Three tests in this repo have now failed on a docstring
    that DESCRIBED the rule they were checking; grepping cannot tell a rule from a description of a
    rule.
    """
    tree = ast.parse(open(path, encoding="utf-8").read())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.alias):
            out.add(node.name.rsplit(".", 1)[-1])
            if node.asname:
                out.add(node.asname)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value.count(" ") < 3:
                out.add(node.value)
    return out


# ── TRAP 1: a second send path ─────────────────────────────────────────────────────────────────
def test_this_service_cannot_send_anything_itself():
    """A second send path is a second set of rules, and the second is always the one missing a
    check the day somebody adds one to the first."""
    from app.core import dispatch
    names = _names(dispatch.__file__)
    for forbidden in ("urllib", "httpx", "requests", "whatsapp", "notification_service"):
        assert forbidden not in names, f"dispatch must not reach {forbidden}"


def test_the_only_outbound_send_is_reminders():
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    assert s.SEND_PATH.startswith("/internal/reminders/")


# ── TRAP 2: a preview whose number is not the send's number ────────────────────────────────────
def test_the_preview_does_not_resolve_its_own_audience():
    """One implementation, not two that agree today. A preview promising 47 and delivering 31
    teaches the owner our numbers are decoration."""
    from app.core import preview
    src = inspect.getsource(preview.build)
    assert "resolve(" not in src and "customers" not in src


def test_the_gate_is_applied_inside_the_resolver_not_after_it():
    """Applying it afterwards means the preview counts people the send will refuse."""
    from app.core.audience import resolve
    assert "gate_check" in inspect.signature(resolve).parameters
    assert "excluded" in inspect.getsource(resolve)


# ── TRAP 3: a standing campaign that re-sends to everyone ──────────────────────────────────────
def test_the_dedup_is_a_ledger_and_not_a_flag_on_the_customer():
    """A flag has to be cleared by something, and whatever clears it is the bug. A ledger needs no
    cleanup and is correct after a restore."""
    from app.core.dispatch import Dispatcher
    src = inspect.getsource(Dispatcher)
    assert "campaign_reached" in src
    assert "already_reached" in src


def test_the_reached_ledger_is_in_the_backup_manifest():
    """Restoring without it makes every standing campaign eligible to re-send to everyone it has
    ever reached, on the day of the recovery."""
    from app.backup_manifest import BACKUP
    names = {c["name"] for c in BACKUP["collections"]}
    assert "campaign_reached" in names and "campaign_runs" in names


def test_a_standing_rule_cannot_evaluate_more_than_once_a_day():
    """The cron runs every fifteen minutes. Without the guard a win-back campaign reaches the same
    customer four times an hour, each send legal by its own logic."""
    from app.core.tick import Tick, same_day
    assert "same_day" in inspect.getsource(Tick._one)
    assert "last_evaluated" in inspect.getsource(Tick._one)
    assert same_day(1_800_000_000, 1_800_000_000 + 3600)


# ── TRAP 4: a rule enforced in the core and dropped at the door ────────────────────────────────
def test_every_field_the_core_validates_is_declared_on_the_api_model():
    """operations shipped exactly this: a rule the core refused, a 200 from the route, because
    pydantic dropped the field on the way in. A unit test cannot see it — it calls the core."""
    from app.api.v1.campaigns import CampaignIn
    declared = set(CampaignIn.model_fields)
    for field in ("goal", "owner_text", "fire_at"):
        assert field in declared


def test_the_owners_text_is_bounded_at_the_model_as_well_as_in_the_core():
    from app.api.v1.campaigns import CampaignIn
    f = CampaignIn.model_fields["owner_text"]
    assert any(getattr(m, "max_length", None) for m in f.metadata)


def test_the_class_is_never_something_the_owner_can_send():
    """Every campaign is promotional except awareness, and the class comes from the goal. A model
    that accepted a class would let a marketing message be filed as service."""
    from app.api.v1.campaigns import CampaignIn
    assert "cls" not in CampaignIn.model_fields
    assert "class" not in CampaignIn.model_fields
    assert "template_type" not in CampaignIn.model_fields


# ── TRAP 5: a cron path no route serves, and a peer URL that resolves in one namespace ─────────
def test_the_cron_path_in_the_values_file_is_a_route_this_service_serves():
    """ticket-service sent every notification to a silent 404 for weeks this way."""
    import pathlib
    import re

    from app.config import Settings
    from app.manifest import build_manifest
    values = (pathlib.Path(__file__).resolve().parents[4]
              / "deploy/services/campaigns.values.yaml")
    text = values.read_text(encoding="utf-8")
    cron_paths = re.findall(r"^\s+path:\s*(\S+)", text, re.M)
    assert cron_paths, "the tick is the heartbeat; without it nothing ever fires"
    served = {e["path"] for e in
              build_manifest(Settings(INTERNAL_SERVICE_TOKEN="x" * 40))["endpoints"]}
    for path in cron_paths:
        assert path in served, f"cron drives {path}, which no route serves"


def test_every_peer_path_names_a_route_the_peer_actually_serves():
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    # Verified against operations' and reminders' manifests when written, pinned here so a
    # careless edit fails a test rather than a customer's campaign.
    assert s.CUSTOMERS_PATH.startswith("/internal/operations/")
    # WHICH TEMPLATE THIS SHOP MAY SEND IS REMINDERS', NOT OPERATIONS'. operations owns the words;
    # the tone, Meta's per-account approval and the owner's own re-written text all live in
    # reminders, and asking operations for them is how a preview came to disagree with a send.
    assert s.REMINDERS_SENDABLE_PATH.startswith("/internal/reminders/")
    assert s.ELIGIBILITY_PATH.startswith("/internal/reminders/")
    assert s.TENANT_READ_PATH == "/internal/tenants/{id}"


def test_no_peer_url_assumes_a_namespace_it_was_not_given():
    from app.config import Settings
    s = Settings(INTERNAL_SERVICE_TOKEN="x" * 40)
    for url in (s.OPERATIONS_SERVICE_URL, s.REMINDERS_SERVICE_URL, s.TENANT_SERVICE_URL):
        if url and "://" in url:
            host = url.split("://", 1)[1].split(":")[0].split("/")[0]
            assert "." not in host or host.endswith("svc.cluster.local")


# ── and the promise the whole service rests on ─────────────────────────────────────────────────
def test_a_campaign_can_never_choose_its_own_regulatory_class():
    from app.core.models import GOAL_TEMPLATE
    # PINNED AS A PROPERTY, NOT AS A LIST. It read `== {"marketing", "awareness"}` and broke the
    # day a third class was needed — which is a test asserting the size of the product rather than
    # the promise. The promise is that the class travels with the GOAL and nothing in a request
    # can move it: a shop cannot post a promotional campaign wearing a warning's exemptions.
    allowed = {"marketing", "awareness", "warning"}
    for template_type, cls in GOAL_TEMPLATE.values():
        assert cls in allowed, f"{template_type} carries an unknown regulatory class {cls!r}"
    assert GOAL_TEMPLATE["safety"][1] == "warning"
    assert GOAL_TEMPLATE["announce"][1] == "marketing"


def test_the_boot_guard_refuses_a_service_that_can_reach_nobody():
    """Campaigns created, runs written, every probe green, and every run reaching nobody — for
    ever, with nothing saying why."""
    import pytest

    from app.config import Settings
    s = Settings(ENV="production", INTERNAL_SERVICE_TOKEN="x" * 40, PEERS_DRIVER="null")
    with pytest.raises(ValueError, match="reached nobody|send nothing"):
        s.assert_peers_config_ok()


# ── TRAP 4b: a field the ENGINE reads that no request model carries ────────────────────────────
def test_the_service_the_offer_is_about_can_actually_be_set():
    """THE FEATURE THAT WAS COMPLETE IN THE DEPTH AND SEVERED AT THE DOOR.

    `Campaign.service_id` existed, `audience._too_early` enforced the 70% cycle lock against it,
    and both were tested. But no request model declared it, so nothing could ever set it: every
    "offer on a service" resolved as a shop-wide announcement, the lock never engaged once, and the
    audience count read as proof of targeting that had not happened.

    The previous trap in this file asks whether the DOOR drops a rule the core enforces. This one
    asks the mirror question — whether the door can even express what the core is built to act on.
    """
    from app.api.v1.campaigns import CampaignIn
    assert "service_id" in CampaignIn.model_fields


def test_the_scope_is_a_list_the_screen_can_act_on_not_a_sentence():
    """`owner_text` persuades and cannot be enforced: two operators read "20% off" and cover
    different things on the same afternoon. The scope sits beside the words."""
    from app.api.v1.campaigns import CampaignIn
    assert "scope_service_ids" in CampaignIn.model_fields


def test_an_offer_must_carry_an_end_date():
    """An offer with no end is a price change nobody decided on — and the counter, the customer's
    page and its countdown all have nothing to read."""
    from app.core.models import offers_something
    assert offers_something("service_offer")
    assert offers_something("win_back")
    # A care tip gives nothing away and expires by being read. Demanding a date for it would be a
    # field with no meaning that somebody fills in with a guess.
    assert not offers_something("awareness")


def test_occasion_is_an_offer_goal(): # ح-7
    """`mkt_personal_occasion` — the template `occasion` sends — declares `offer_value` and
    `ends_at` exactly like `win_back` and `reward_loyal` do. A card that says `offers=False` for a
    goal whose template needs both never draws the value or date field in Launch.tsx, so the
    console posts a campaign missing both and `preview.build` refuses it every single time: a whole
    goal, unreachable, with no field on the screen the owner could have filled to fix it."""
    from app.core.goals import cards
    from app.core.models import GOAL_TEMPLATE, offers_something

    assert offers_something("occasion"), \
        "occasion's own template needs amount+date just like win_back and reward_loyal"

    by_goal = {c.goal: c for c in cards(now=0)}
    assert by_goal["occasion"].offers is True, \
        "the card the console reads must carry the same answer"

    # AND THE TEMPLATE ITSELF AGREES — the fill contract in reasons.py for this exact template
    # type, cross-checked so this test fails if the two ever drift apart again.
    template_type = GOAL_TEMPLATE["occasion"][0]
    assert template_type == "mkt_personal_occasion"


# ── the wires the container asks for by name ──────────────────────────────────────────────────
def test_the_peer_builder_answers_every_key_the_container_reads():
    """THE DEFECT THIS CATCHES HAD RUN IN PRODUCTION SINCE THE FEATURE WAS WRITTEN.

    `container.py` reads `peers.get("ceiling")` and `peers.get("engine")`. `build_peers` returned
    neither, `.get` answered None, and both fell back to "unknown" — so `share.known` was False on
    every request, the owner never once saw «this will reach everyone in five days», and the
    engine's reserve was subtracted from nothing. A missing key in a dict is the quietest possible
    wire to cut: nothing raises, nothing logs, and the screen simply renders one sentence less.

    So the keys are asserted against the SOURCE that reads them rather than against a list here —
    a second list would drift from the container the first time somebody adds a peer.
    """
    import re
    from pathlib import Path

    from app.adapters.peers import build_peers

    class S:
        PEERS_DRIVER = "http"
        PEER_TIMEOUT_SECONDS = 8
        INTERNAL_SERVICE_TOKEN = "t" * 40
        OPERATIONS_SERVICE_URL = "http://operations:8000"
        REMINDERS_SERVICE_URL = "http://reminders:8000"
        TENANT_SERVICE_URL = "http://tenant-service:8000"
        INSIGHTS_SERVICE_URL = "http://insights:8000"
        CUSTOMERS_PATH = "/internal/operations/customers"
        OFFERS_REDEEMED_PATH = "/internal/operations/offers-redeemed"
        ELIGIBILITY_PATH = "/internal/reminders/eligibility"
        SEND_PATH = "/internal/reminders/send"
        REMINDERS_ROOM_PATH = "/internal/reminders/room"
        REMINDERS_SENDABLE_PATH = "/internal/reminders/sendable"
        REMINDERS_RHYTHMS_PATH = "/internal/reminders/rhythms"
        INSIGHTS_RESERVE_PATH = "/internal/insights/engine-reserve"
        TENANT_READ_PATH = "/internal/tenants/{id}"
        SEND_WINDOW_START_HOUR = 9
        SEND_WINDOW_END_HOUR = 21
        TEMPLATES_CACHE_TTL_SECONDS = 15

    built = set(build_peers(S()))
    src = Path(__file__).resolve().parents[2].joinpath("app", "container.py").read_text(
        encoding="utf-8")
    wanted = set(re.findall(r'peers\[?\.?get?\(?["\']([a-z_]+)["\']\)?\]?', src))
    wanted &= {"templates", "audience", "sender", "identity", "window", "ceiling", "engine"}
    missing = wanted - built
    assert not missing, f"container reads peers the builder never returns: {sorted(missing)}"


def test_the_ceiling_peer_answers_the_shape_the_share_reads():
    """`share.compute` reads `.limit` off whatever the ceiling peer returns, and `engine_load`
    must answer a mapping with `reserved` and `used`. A peer that answers a different shape fails
    exactly where the previous version failed: silently, into the "unknown" branch."""
    import asyncio

    from app.adapters.peers import HttpRoom

    peer = HttpRoom(reminders_url="http://nowhere.invalid", room_path="/internal/reminders/room",
                    insights_url="http://nowhere.invalid",
                    reserve_path="/internal/insights/engine-reserve", token="t", timeout=1)
    # UNREACHABLE IS THE INTERESTING CASE: it must still answer the shape, with the sentinel that
    # means "unknown" — 0 — rather than raising into a 500 on the composer.
    read = asyncio.run(peer.read("t1"))
    assert read.limit == 0 and isinstance(read.used, int)
    load = asyncio.run(peer.engine_load("t1"))
    assert load == {"reserved": 0, "used": 0}


def test_the_audience_row_carries_the_learned_rhythm():
    """WITHOUT THIS JOIN EVERY WIN-BACK MEASURED EVERYONE AGAINST 90 DAYS.

    operations holds who the customers are; reminders holds the rhythm it learned for each of
    them. `audience._too_early` reads that rhythm off the row and falls back to the window default
    when it is missing — so a missing join does not fail, it flattens: the per-customer cycle the
    product sells becomes one number for the whole shop, and the audience count still looks right.
    """
    import asyncio
    import json
    from unittest.mock import patch

    from app.adapters.peers import HttpAudience

    def fake_post(url, body, token, timeout):
        if url.endswith("/customers"):
            return {"customers": [{"subject_ref": "sub_a", "last_visit": 100, "visit_count": 3},
                                  {"subject_ref": "sub_b", "last_visit": 200, "visit_count": 1}]}
        assert body["service_id"] == "oil", "the service must travel with the rhythm read"
        return {"rhythms": {"sub_a": {"interval_days": 45.0, "last_visit": 90,
                                      "observations": 4}}}

    peer = HttpAudience(operations_url="http://ops", customers_path="/customers",
                        reminders_url="http://rem", eligibility_path="/elig",
                        rhythms_path="/rhythms", token="t", timeout=1)
    with patch("app.adapters.peers._post", fake_post):
        rows = asyncio.run(peer.customers("t1", service_id="oil"))

    by = {r["subject_ref"]: r for r in rows}
    assert by["sub_a"]["interval_days"] == 45.0
    assert by["sub_a"]["services"]["oil"]["last_visit"] == 90
    # AND A CUSTOMER WITH NOTHING LEARNED KEEPS HIS ROW UNCHANGED — no invented cycle, so the
    # rule falls back to the window exactly as it did before this existed.
    assert "interval_days" not in by["sub_b"] and "services" not in by["sub_b"]


def test_an_unreachable_rhythm_read_costs_precision_not_the_campaign():
    """The rhythm is the soft half of the join: losing it narrows nothing and blocks nobody."""
    import asyncio
    from unittest.mock import patch

    from app.adapters.peers import HttpAudience

    def fake_post(url, body, token, timeout):
        if url.endswith("/customers"):
            return {"customers": [{"subject_ref": "sub_a", "last_visit": 100}]}
        raise OSError("reminders is restarting")

    peer = HttpAudience(operations_url="http://ops", customers_path="/customers",
                        reminders_url="http://rem", eligibility_path="/elig",
                        rhythms_path="/rhythms", token="t", timeout=1)
    with patch("app.adapters.peers._post", fake_post):
        rows = asyncio.run(peer.customers("t1", service_id="oil"))
    assert rows == [{"subject_ref": "sub_a", "last_visit": 100}]


def test_the_template_peer_asks_about_THIS_shop_and_caches_per_tenant():
    """The tenant argument was decorative, and three per-shop facts went missing with it.

    The old client fetched the platform library from operations once, cached it PROCESS-WIDE, and
    answered every establishment on the pod from the first row of the matching type — ignoring the
    shop's tone, Meta's per-account approval, and the owner's own re-written text. A goal card read
    «متاح» for a shop whose library was still under review; he launched, and every recipient failed
    at the delivery layer for a reason he could do nothing about.

    THIS FAILS ON THE OLD CLIENT: it asserts two tenants get two answers.
    """
    import asyncio
    import json

    from app.adapters import peers as P

    asked: list[str] = []
    library = {
        "t-quiet": {"templates": {"mkt_winback": {"name": "wb_calm", "tone": "calm"}}},
        "t-loud": {"templates": {"mkt_winback": {"name": "wb_warm", "tone": "warm"},
                                 "mkt_offer": {"name": "of_warm", "tone": "warm"}}},
        # Connected this morning: the whole library is still under review, so NOTHING is sendable.
        "t-new": {"templates": {}, "blocked": {"mkt_winback": "قيد مراجعة واتساب"}},
    }

    def fake_get(url, token, timeout):
        asked.append(url)
        tenant = url.split("tenant=", 1)[1]
        return json.loads(json.dumps(library[tenant]))

    original, P._get = P._get, fake_get
    try:
        c = P.HttpTemplates(url="http://reminders:8000", path="/internal/reminders/sendable",
                            token="t" * 40)
        quiet = asyncio.run(c.pick("t-quiet", "mkt_winback"))
        loud = asyncio.run(c.pick("t-loud", "mkt_winback"))
        assert quiet["name"] == "wb_calm" and loud["name"] == "wb_warm", (
            "one shop's tone was served to another")

        assert asyncio.run(c.enabled_types("t-loud")) == {"mkt_winback", "mkt_offer"}
        # AND THE SHOP STILL UNDER REVIEW GETS THE HONEST ANSWER, so its goal cards lock instead
        # of inviting a launch that cannot deliver a single message.
        assert asyncio.run(c.enabled_types("t-new")) == set()
        assert asyncio.run(c.pick("t-new", "mkt_winback")) is None

        # THE CACHE IS PER TENANT. A process-wide cache of a per-tenant answer is the same defect
        # wearing a performance argument.
        before = len(asked)
        asyncio.run(c.pick("t-quiet", "mkt_winback"))
        assert len(asked) == before, "a second read for a tenant already cached"
        assert sorted({u.split("tenant=", 1)[1] for u in asked}) == ["t-loud", "t-new", "t-quiet"]
    finally:
        P._get = original


def test_the_template_cache_ttl_is_configured_not_a_fixed_five_minutes():
    """Tamam, 2026-08-20: an owner enabled a template in reminders' own screen and the goal card
    still read «غير مفعّل» — `build_peers` never passed `ttl_seconds` through at all, so every
    deployment silently ran `HttpTemplates`' own 300-second class default with no way to shorten
    it short of a code change. `TEMPLATES_CACHE_TTL_SECONDS` closes that: settings decide it now,
    not the class body."""
    from app.adapters.peers import HttpTemplates, build_peers

    class S:
        PEERS_DRIVER = "http"
        PEER_TIMEOUT_SECONDS = 8
        INTERNAL_SERVICE_TOKEN = "t" * 40
        OPERATIONS_SERVICE_URL = "http://operations:8000"
        REMINDERS_SERVICE_URL = "http://reminders:8000"
        TENANT_SERVICE_URL = "http://tenant-service:8000"
        INSIGHTS_SERVICE_URL = "http://insights:8000"
        CUSTOMERS_PATH = "/internal/operations/customers"
        OFFERS_REDEEMED_PATH = "/internal/operations/offers-redeemed"
        ELIGIBILITY_PATH = "/internal/reminders/eligibility"
        SEND_PATH = "/internal/reminders/send"
        REMINDERS_ROOM_PATH = "/internal/reminders/room"
        REMINDERS_SENDABLE_PATH = "/internal/reminders/sendable"
        REMINDERS_RHYTHMS_PATH = "/internal/reminders/rhythms"
        INSIGHTS_RESERVE_PATH = "/internal/insights/engine-reserve"
        TENANT_READ_PATH = "/internal/tenants/{id}"
        SEND_WINDOW_START_HOUR = 9
        SEND_WINDOW_END_HOUR = 21
        TEMPLATES_CACHE_TTL_SECONDS = 42

    templates = build_peers(S())["templates"]
    assert isinstance(templates, HttpTemplates)
    assert templates._ttl == 42                                          # noqa: SLF001


def test_a_stale_template_answer_refreshes_once_the_ttl_elapses():
    """A short TTL is what makes «فعّلتها ومع ذلك باقي نفس الشي» self-heal within seconds instead
    of the old five-minute wait — this is the behaviour that setting actually buys, not just a
    number stored on the object."""
    import asyncio
    import json

    from app.adapters import peers as P

    calls = {"n": 0}
    answer = {"templates": {}}                      # nothing enabled yet

    def fake_get(url, token, timeout):
        calls["n"] += 1
        return json.loads(json.dumps(answer))

    original, P._get = P._get, fake_get
    try:
        clock = {"t": 1000.0}
        c = P.HttpTemplates(url="http://reminders:8000", path="/internal/reminders/sendable",
                            token="t" * 40, ttl_seconds=15)
        import time as _time
        real_time = _time.time
        _time.time = lambda: clock["t"]
        try:
            assert asyncio.run(c.enabled_types("t-1")) == set()
            assert calls["n"] == 1

            # STILL INSIDE THE WINDOW — the cached (stale, in real life) answer, no new call.
            clock["t"] += 10
            assert asyncio.run(c.enabled_types("t-1")) == set()
            assert calls["n"] == 1

            # THE OWNER ENABLED IT IN REMINDERS' OWN SCREEN, out of band — this client cannot
            # know that happened, only that its own window has now elapsed.
            answer["templates"] = {"mkt_winback": {"name": "wb"}}
            clock["t"] += 10          # 20s since the first read — past the 15s TTL
            assert asyncio.run(c.enabled_types("t-1")) == {"mkt_winback"}
            assert calls["n"] == 2
        finally:
            _time.time = real_time
    finally:
        P._get = original


def test_a_branch_campaign_leaves_from_that_branch_s_number():
    """A chain that moved to a number per branch sent every campaign from the central one.

    `tick._sending_identity` reads `branch_id` off the schedule and returns `tenant:branch`. The
    campaign schedule never carried one — so the customer of the Jeddah branch received an offer
    from the Riyadh number and replied to a team that knows nothing about his car. The send log had
    the same hole: «من راسلنا ومن أيّ فرع» could not be answered for one campaign message.
    """
    import asyncio

    from app.adapters.datastore.memory import MemoryDataStore
    from app.core.audience import Audience, Candidate
    from app.core.dispatch import Dispatcher

    sent: list[dict] = []

    class Sender:
        async def send(self, **kw):
            sent.append(kw)
            return {"sent": True}

    async def resolver(campaign, *, already_reached, now):
        return Audience(candidates=[Candidate(subject_ref="sub_abcdefgh")], excluded=0)

    campaign = {"tenant": "t1", "id": "cmp_1", "template_type": "mkt_offer",
                "cls": "marketing", "owner_text": "خصم", "branch_id": "br_jeddah"}

    d = Dispatcher(store=MemoryDataStore(), sender=Sender(), audience_resolver=resolver)
    asyncio.run(d.fire(campaign, now=1_800_000_000))

    assert sent, "the dispatcher sent nothing, so this proves nothing"
    assert sent[0]["branch_id"] == "br_jeddah", (
        "the campaign's branch never reached the send — the message leaves from the central "
        "number and the send log records no branch")
