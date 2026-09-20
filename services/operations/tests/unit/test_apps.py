"""What the shop bought — and the difference between «لم تشترِ» and «لم نستطع السؤال».

THE DEFECT THIS CLOSES. No screen could answer "does this shop own this app". The console draws a
lock from a CAPABILITY, which is about the person's role, and an owner holds every capability on
every plan — so the lock never appeared for the one person who would have paid to remove it.

THE ONE THING THESE TESTS GUARD ABOVE ALL: a billing outage must never be reported as ownership,
in either direction. Collapsing "could not ask" into False paints «لم تشترِ» across every app of
every paying shop at once; collapsing it into True is a display that lies the other way.
"""
from __future__ import annotations

import asyncio
import json
import urllib.error
from unittest.mock import patch

from app.core.apps import (APPS, CANNOT_ASK, CONTACTS_FEATURES, HttpApps, KEYS, NullApps,
                           RATING_FEATURES, VISIT_FEATURES, build_apps, public)


def run(c):
    return asyncio.run(c)


class _Resp:
    def __init__(self, payload):
        self._p = json.dumps(payload).encode()

    def read(self):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def client():
    return HttpApps(billing_url="http://billing",
                    check_path="/internal/billing/entitlements/check", token="t")


def _answer(owned=(), fail_for=(), fail_all=False):
    """billing that says yes to `owned`, and is unreachable for `fail_for`."""
    def _urlopen(req, timeout=0):
        if fail_all:
            raise urllib.error.URLError("down")
        key = req.full_url.split("key=")[-1]
        if key in fail_for:
            raise urllib.error.URLError("down")
        return _Resp({"allowed": key in owned})
    return _urlopen


# ── the catalogue itself ───────────────────────────────────────────────────────────────────────
def test_every_app_carries_what_it_does_in_arabic():
    """A store that lists `feature.roles.custom` is a glossary, not a page somebody buys from."""
    for app in APPS:
        assert app["name"] and app["what"] and app["screen"]
        assert app["key"].startswith("feature.")


def test_the_keys_are_unique():
    assert len(set(KEYS)) == len(KEYS)


# ── real features, not services (2026-09-11 CTO decision) ───────────────────────────────────────
def test_visit_contacts_and_rating_apps_carry_their_features_verbatim():
    by_key = {a["key"]: a for a in APPS}
    assert by_key["feature.visit"]["features"] == list(VISIT_FEATURES)
    assert by_key["feature.contacts"]["features"] == list(CONTACTS_FEATURES)
    assert by_key["feature.rating"]["features"] == list(RATING_FEATURES)


def test_every_feature_has_a_stable_unique_id_and_a_short_plain_sentence():
    for feature_list in (VISIT_FEATURES, CONTACTS_FEATURES, RATING_FEATURES):
        ids = [f["id"] for f in feature_list]
        assert len(ids) == len(set(ids)), "two features in the same app share one id"
        for f in feature_list:
            assert f["title"].strip() and f["detail"].strip()
            # SHORT, ON PURPOSE — a title reading like a paragraph is a mechanism description
            # wearing a marketing font, not a value line.
            assert len(f["title"]) <= 40, f"{f['id']}'s title reads like a sentence"


def test_rating_features_answer_the_owners_own_framing():
    """The owner's own words (2026-09-11): «يفهم عميله اللي مكمّل ليه مكمّل، واللي ما يكمل ليه
    قرر المغادرة». Pinned so the lead feature can never regress to a plain "collects a star
    rating" description."""
    ids = {f["id"] for f in RATING_FEATURES}
    assert "rating.understands_why_they_leave" in ids
    assert "rating.catches_unhappy_before_they_leave" in ids


def test_the_shared_reminders_feature_names_its_real_owner_and_matches_bookings():
    """`reminders.learns_each_customer` is not this service's own code (see the module docstring)
    — pinned so it can never silently drift into an unattributed visit-registration claim, and so
    it stays byte-identical to bookings-service's own copy of the same entry."""
    shared = next(f for f in VISIT_FEATURES if f["id"] == "reminders.learns_each_customer")
    assert shared["owned_by"] == "reminders"
    assert shared["shared_with"] == ["bookings"]
    assert shared["title"] == "يعيد إليك عميلك دون أي جهد منك"


# ── asking ─────────────────────────────────────────────────────────────────────────────────────
def test_it_reports_exactly_what_billing_said_yes_to():
    with patch("urllib.request.urlopen", _answer(owned={"feature.campaigns"})):
        held, checked = run(client().held("t1"))
    assert held == {"feature.campaigns"}
    assert checked is True


def test_a_shop_that_bought_nothing_is_answered_not_failed():
    """Empty AND checked — that pair is what lets the store draw buy buttons instead of an error."""
    with patch("urllib.request.urlopen", _answer(owned=set())):
        assert run(client().held("t1")) == (set(), True)


def test_every_key_on_the_price_list_is_asked_about():
    seen = []

    def _urlopen(req, timeout=0):
        seen.append(req.full_url.split("key=")[-1])
        return _Resp({"allowed": False})

    with patch("urllib.request.urlopen", _urlopen):
        run(client().held("t1"))
    assert sorted(seen) == sorted(KEYS)


def test_it_asks_about_the_caller_s_own_establishment():
    seen = []

    def _urlopen(req, timeout=0):
        seen.append(req.full_url)
        return _Resp({"allowed": False})

    with patch("urllib.request.urlopen", _urlopen):
        run(client().held("shop_9"))
    assert all("tenant=shop_9" in u for u in seen)


def test_an_empty_tenant_never_reaches_billing_and_is_not_a_failure():
    """No establishment on the token is not a shop. Answered as owning nothing, with `checked`
    true: nothing failed, so there is nothing to offer a retry for."""
    called = {"n": 0}

    def _urlopen(req, timeout=0):
        called["n"] += 1
        return _Resp({"allowed": True})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().held("")) == (set(), True)
    assert called["n"] == 0


# ── the outage, which is the whole reason `checked` exists ─────────────────────────────────────
def test_an_unreachable_billing_is_reported_as_itself_never_as_not_bought():
    with patch("urllib.request.urlopen", _answer(fail_all=True)):
        held, checked = run(client().held("t1"))
    assert held == set()
    assert checked is False


def test_one_failed_key_makes_the_whole_answer_unchecked():
    """A partial answer rendered as whole is the worst of the three: four apps right and one
    silently locked, with nothing on the screen saying which."""
    with patch("urllib.request.urlopen",
               _answer(owned=set(KEYS), fail_for={"feature.loyalty"})):
        held, checked = run(client().held("t1"))
    assert checked is False


def test_a_malformed_answer_is_read_as_not_owned_not_as_a_failure():
    """`{}` has no `allowed`. It IS an answer — billing replied — so it must not raise the retry
    banner over apps the shop genuinely does not have."""
    def _urlopen(req, timeout=0):
        return _Resp({})

    with patch("urllib.request.urlopen", _urlopen):
        assert run(client().held("t1")) == (set(), True)


# ── the shape the console renders ──────────────────────────────────────────────────────────────
def test_the_payload_claims_ownership_only_when_it_was_answered():
    body = public({"feature.loyalty"}, True)
    owned = {a["key"]: a["owned"] for a in body["apps"]}
    assert owned["feature.loyalty"] is True
    assert owned["feature.campaigns"] is False
    assert body["keys"] == ["feature.loyalty"]
    assert body["message"] == ""


def test_on_a_failed_check_every_app_is_unknown_rather_than_unowned():
    """None, not False — three states in the payload because there are three in the world. The
    screen draws «تعذّر التحقق» and a retry, never a lock over something he pays for."""
    body = public(set(), False)
    assert all(a["owned"] is None for a in body["apps"])
    assert body["keys"] == []
    assert body["message"] == CANNOT_ASK


# ── how it is built ────────────────────────────────────────────────────────────────────────────
def test_without_billing_configured_it_is_the_null_reader_and_the_boot_guard_refuses_it():
    class S:
        BILLING_SERVICE_URL = ""
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"

    assert build_apps(S()).driver == "null"


def test_configured_billing_gives_the_http_reader():
    class S:
        BILLING_SERVICE_URL = "http://billing-service:8000"
        BILLING_CHECK_PATH = "/internal/billing/entitlements/check"
        INTERNAL_SERVICE_TOKEN = "t"
        PEER_TIMEOUT_SECONDS = 8

    assert build_apps(S()).driver == "http"


def test_the_null_reader_can_be_asked_for_the_outage_too():
    """Tests need both failures, and «owns nothing» must not be the only one they can express."""
    null = NullApps({"feature.api"})
    assert run(null.held("t1")) == ({"feature.api"}, True)
    null.reachable = False
    assert run(null.held("t1")) == (set(), False)


# ── `feature.api`: the programmatic link, and the third answer that decides the till ───────────
#
# THE DEFECT. `feature.api` was on the price list from the first day and checked by NOTHING — any
# shop on any plan could point a till at us and stream visits in. The guard reported green because
# `Plans.tsx` names the key as a LABEL, and a mention counted as enforcement.
def _api_client():
    from app.core.licence import HttpApiLicence

    return HttpApiLicence(billing_url="http://billing",
                          check_path="/internal/billing/entitlements/check", token="t")


def test_a_shop_that_bought_the_link_may_write_from_its_till():
    from app.core.licence import refuses_machine_writes

    with patch("urllib.request.urlopen", _answer(owned={"feature.api"})):
        assert run(refuses_machine_writes(_api_client(), "t1")) is False


def test_a_shop_that_never_bought_it_is_refused():
    from app.core.licence import refuses_machine_writes

    with patch("urllib.request.urlopen", _answer(owned=set())):
        assert run(refuses_machine_writes(_api_client(), "t1")) is True


def test_an_unreachable_billing_lets_the_sale_through():
    """THE ONE DELIBERATE DIFFERENCE FROM CAMPAIGNS, which fails closed. The till is the shop's
    counter: a fleet-wide billing hiccup that refused every till would stop every shop in the
    country from recording its day, for a reason none of them caused and none can fix. A campaign
    delayed an hour is nothing; a lost day of visits is the product's own record."""
    from app.core.licence import refuses_machine_writes

    with patch("urllib.request.urlopen", _answer(fail_all=True)):
        assert run(refuses_machine_writes(_api_client(), "t1")) is False


def test_with_no_licence_wired_nothing_is_refused():
    """Local runs and tests. Production is refused by the boot guard, not by a silent default."""
    from app.core.licence import refuses_machine_writes

    assert run(refuses_machine_writes(None, "t1")) is False


def test_the_refusal_names_the_key_and_the_way_out():
    """The reader is an integration's log, so it is English. STALE ASSERTION FIXED 2026-09-16:
    this used to check for an Arabic "go buy it on the plans page" pointer, back when `feature.api`
    was merely unenforced-but-sellable. It is now closed by an explicit product decision
    (`API_LINK_ENABLED` defaults False, see `core/licence.py`'s own module docstring) — nobody can
    buy the key at all, so a sentence pointing to «الباقات» would be actively misleading. The
    refusal still names the key, which is all an integrator's log needs."""
    from app.core.licence import NOT_INCLUDED

    assert "feature.api" in NOT_INCLUDED


# ── orphaned_dependents — the self-heal check, not a sweep ──────────────────────────────────────
def test_a_dependent_app_with_neither_prerequisite_held_is_named():
    from app.core.apps import orphaned_dependents

    rows = [
        {"id": "sub_loyalty", "status": "active", "cancel_at_period_end": False,
         "limits_snapshot": {"feature.loyalty": {"kind": "boolean", "limit": 1},
                             "plan.requires_any": {"kind": "list",
                                                   "list": ["feature.visit", "feature.bookings"]}}},
    ]
    assert orphaned_dependents(rows, held=set()) == ["sub_loyalty"]


def test_holding_either_prerequisite_clears_it():
    from app.core.apps import orphaned_dependents

    rows = [
        {"id": "sub_loyalty", "status": "active", "cancel_at_period_end": False,
         "limits_snapshot": {"plan.requires_any": {"kind": "list",
                                                   "list": ["feature.visit", "feature.bookings"]}}},
    ]
    assert orphaned_dependents(rows, held={"feature.visit"}) == []
    assert orphaned_dependents(rows, held={"feature.bookings"}) == []


def test_a_row_with_no_requires_any_is_never_named():
    from app.core.apps import orphaned_dependents

    rows = [{"id": "sub_campaigns", "status": "active", "cancel_at_period_end": False,
            "limits_snapshot": {"feature.campaigns": {"kind": "boolean", "limit": 1}}}]
    assert orphaned_dependents(rows, held=set()) == []


def test_an_already_pending_cancellation_is_not_re_cancelled():
    """Idempotent across repeated reads — no point re-cancelling a cancellation already in
    flight, before billing's own sweep has finished the schedule."""
    from app.core.apps import orphaned_dependents

    rows = [
        {"id": "sub_loyalty", "status": "active", "cancel_at_period_end": True,
         "limits_snapshot": {"plan.requires_any": {"kind": "list", "list": ["feature.visit"]}}},
    ]
    assert orphaned_dependents(rows, held=set()) == []


def test_an_already_canceled_row_is_never_named():
    from app.core.apps import orphaned_dependents

    rows = [
        {"id": "sub_loyalty", "status": "canceled", "cancel_at_period_end": False,
         "limits_snapshot": {"plan.requires_any": {"kind": "list", "list": ["feature.visit"]}}},
    ]
    assert orphaned_dependents(rows, held=set()) == []


# ── requires_whatsapp_connection: apps that ARE a WhatsApp message, not a feature riding one ────
def test_exactly_the_three_declared_apps_require_a_connection():
    from app.core.apps import REQUIRES_WHATSAPP_KEYS

    assert REQUIRES_WHATSAPP_KEYS == frozenset(
        {"feature.whatsapp", "feature.rating", "feature.campaigns"})


def test_a_plan_granting_one_of_the_three_requires_connection():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection({"feature.campaigns"}) is True
    assert requires_whatsapp_connection({"feature.rating"}) is True
    assert requires_whatsapp_connection({"feature.whatsapp"}) is True


def test_every_other_app_does_not_require_connection():
    from app.core.apps import requires_whatsapp_connection

    for key in ("feature.loyalty", "feature.insights.engine", "feature.bookings",
                "feature.visit", "feature.contacts", "feature.coupons",
                "feature.mobile_requests"):
        assert requires_whatsapp_connection({key}) is False, key


def test_a_mixed_set_with_at_least_one_qualifying_key_requires_connection():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection({"feature.loyalty", "feature.rating"}) is True


def test_an_empty_set_does_not_require_connection():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection(set()) is False


def test_every_requiring_key_is_a_real_declared_app():
    """A key in REQUIRES_WHATSAPP_KEYS that is not in KEYS would silently gate nothing — this
    proves the set only ever names rows that actually exist in the catalogue."""
    from app.core.apps import KEYS, REQUIRES_WHATSAPP_KEYS

    assert REQUIRES_WHATSAPP_KEYS <= set(KEYS)


def test_a_non_feature_key_never_qualifies():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection({"plan.standalone", "plan.requires_any"}) is False


def test_requires_whatsapp_connection_accepts_a_plain_set_or_a_frozenset():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection(set(["feature.rating"])) is True
    assert requires_whatsapp_connection(frozenset(["feature.rating"])) is True


def test_all_three_together_still_just_requires_connection_once():
    from app.core.apps import requires_whatsapp_connection

    assert requires_whatsapp_connection(
        {"feature.whatsapp", "feature.rating", "feature.campaigns"}) is True
