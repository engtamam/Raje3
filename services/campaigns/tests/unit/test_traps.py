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
    assert s.TEMPLATES_PATH.startswith("/internal/operations/")
    assert s.CUSTOMERS_PATH.startswith("/internal/operations/")
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
    classes = {c for _, c in GOAL_TEMPLATE.values()}
    assert classes == {"marketing", "awareness"}


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
