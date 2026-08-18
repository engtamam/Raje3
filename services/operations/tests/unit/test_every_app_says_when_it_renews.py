"""Each app a shop pays for carries ITS OWN renewal date — #347.

WHAT WAS WRONG. `/apps` fetched the tenant's whole subscription list, read the base's
`current_period_end`, and dropped every other row. A shop paying for the base, the campaigns app
and the loyalty app holds THREE subscriptions renewing on three different days — because billing
starts each period at the moment of purchase — and the console showed one date. The other two
charges were discovered on the card statement.

The alignment itself (one billing day for the whole shop, the first cycle prorated) is
billing-service's `subscribe`, which sets `current_period_start=now` unconditionally and never
consults the tenant's existing anchor. `platform/` is read-only to us; the escalation is written
down in the task. THIS file is the half that is ours: whatever billing decides, the owner reads
the real dates rather than one of them.
"""
from app.core import apps as app_catalogue

BASE = {"plan_id": "base", "status": "active", "current_period_end": 1_000.0,
        "limits_snapshot": {"messages.monthly": 500}}
CAMPAIGNS = {"plan_id": "camp", "status": "active", "current_period_end": 2_000.0,
             "limits_snapshot": {"feature.campaigns": True}}


def _app(body, key):
    return next(a for a in body["apps"] if a["key"] == key)


def test_each_owned_app_carries_its_own_date_not_the_base_s():
    renewals = app_catalogue.renewals_by_key([BASE, CAMPAIGNS])
    body = app_catalogue.public({"feature.campaigns"}, True, None, renewals)
    assert _app(body, "feature.campaigns")["renews_at"] == 2_000.0


def test_an_app_the_shop_does_not_hold_has_no_date_rather_than_a_zero():
    renewals = app_catalogue.renewals_by_key([BASE, CAMPAIGNS])
    body = app_catalogue.public({"feature.campaigns"}, True, None, renewals)
    assert _app(body, "feature.loyalty")["renews_at"] is None


def test_an_unanswered_check_reports_no_date_at_all():
    """«لا أعرف» is not «لا يتجدّد» — a billing outage must not print a date it did not read."""
    body = app_catalogue.public(set(), False, None, {"feature.campaigns": {"renews_at": 2_000.0}})
    assert _app(body, "feature.campaigns")["renews_at"] is None


def test_a_capacity_pack_is_not_an_app_and_claims_no_card():
    pack = {"plan_id": "pack", "status": "active", "current_period_end": 3_000.0,
            "limits_snapshot": {"messages.pack": 1000}}
    assert app_catalogue.renewals_by_key([pack]) == {}
