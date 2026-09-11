"""GET /internal/operations/customer-conversion — insights' own lead-conversion read.

Also proves the OTHER half of the wiring: `/internal/operations/customer-id-by-phone`
(whatsapp-assistant's only door onto customer creation) tags every row it creates "whatsapp",
so a customer this route creates shows up under that bucket here.
"""
from __future__ import annotations

INTERNAL = {"X-Internal-Token": "t" * 40}
CONVERSION_PATH = "/internal/operations/customer-conversion"
BY_PHONE_PATH = "/internal/operations/customer-id-by-phone"


def test_no_customers_at_all_answers_an_empty_breakdown(client):
    r = client.get(CONVERSION_PATH, params={"tenant": "tnt_conv_route_1"}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json() == {"tenant": "tnt_conv_route_1", "by_source": {}}


def test_a_customer_created_via_customer_id_by_phone_is_tagged_whatsapp(client):
    tenant = "tnt_conv_route_2"
    created = client.post(BY_PHONE_PATH, json={"tenant": tenant, "phone": "0511112222"},
                          headers=INTERNAL)
    assert created.status_code == 200, created.text
    assert created.json()["customer_id"]

    r = client.get(CONVERSION_PATH, params={"tenant": tenant}, headers=INTERNAL)
    assert r.status_code == 200, r.text
    assert r.json()["by_source"] == {"whatsapp": {"total": 1, "converted": 0}}


def test_no_token_is_refused(client):
    r = client.get(CONVERSION_PATH, params={"tenant": "tnt_conv_route_3"})
    assert r.status_code == 401
