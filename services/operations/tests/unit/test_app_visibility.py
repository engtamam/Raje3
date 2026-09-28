"""Per-tenant app-visibility overrides (core/app_visibility.py). No peer, no fake needed — this
module only ever touches its own store rows."""
from __future__ import annotations

import asyncio

import pytest

from app.adapters.datastore.memory import MemoryDataStore
from app.core.app_visibility import AppVisibilityError, AppVisibilityOverrides

TENANT_A = "tnt_alpha"
TENANT_B = "tnt_beta"
KEY = "feature.partner_loyalty"


def run(coro):
    return asyncio.run(coro)


def _overrides() -> AppVisibilityOverrides:
    return AppVisibilityOverrides(store=MemoryDataStore())


# ── set_visible: validation ─────────────────────────────────────────────────────────────────────

def test_set_visible_refuses_an_empty_tenant():
    ov = _overrides()
    with pytest.raises(AppVisibilityError, match="لا يوجد محل"):
        run(ov.set_visible("", KEY, True))


def test_set_visible_refuses_a_malformed_feature_key():
    ov = _overrides()
    for bad in ("", "not_a_feature_key", "feature.", "feature.Partner", "feature.partner-loyalty",
               "'; drop table plans; --", "feature.a b"):
        with pytest.raises(AppVisibilityError, match="مفتاح تطبيق غير صالح"):
            run(ov.set_visible(TENANT_A, bad, True))


def test_set_visible_accepts_a_well_formed_feature_key():
    ov = _overrides()
    row = run(ov.set_visible(TENANT_A, KEY, True))
    assert row == {"tenant": TENANT_A, "feature_key": KEY, "visible": True}


# ── visible_keys_for_tenant: the read the shop's OWN store screen calls ────────────────────────

def test_visible_keys_for_tenant_returns_empty_for_a_tenant_with_no_overrides():
    ov = _overrides()
    assert run(ov.visible_keys_for_tenant(TENANT_A)) == []


def test_visible_keys_for_tenant_returns_empty_for_an_empty_tenant():
    """Never even queries the store for a blank tenant — the caller here is always
    `_tenant(principal)`, which is never blank for a real token, but this must not crash if it
    somehow were."""
    ov = _overrides()
    assert run(ov.visible_keys_for_tenant("")) == []


def test_visible_keys_for_tenant_reflects_a_grant():
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    assert run(ov.visible_keys_for_tenant(TENANT_A)) == [KEY]


def test_visible_keys_for_tenant_never_leaks_across_tenants():
    """THE core security property of this whole module — granting tenant A visibility must never
    make it visible for tenant B too."""
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    assert run(ov.visible_keys_for_tenant(TENANT_B)) == []


def test_visible_keys_for_tenant_excludes_a_revoked_override():
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    run(ov.set_visible(TENANT_A, KEY, False))
    assert run(ov.visible_keys_for_tenant(TENANT_A)) == []


def test_visible_keys_for_tenant_re_grant_after_revoke_works():
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    run(ov.set_visible(TENANT_A, KEY, False))
    run(ov.set_visible(TENANT_A, KEY, True))
    assert run(ov.visible_keys_for_tenant(TENANT_A)) == [KEY]


def test_visible_keys_for_tenant_generic_across_several_apps_for_the_same_tenant():
    """The whole point of the generic (tenant, feature_key) key shape — a second unlisted app
    grants with zero new code, only a new row."""
    ov = _overrides()
    run(ov.set_visible(TENANT_A, "feature.partner_loyalty", True))
    run(ov.set_visible(TENANT_A, "feature.mutual_benefit", True))
    assert run(ov.visible_keys_for_tenant(TENANT_A)) == \
        ["feature.mutual_benefit", "feature.partner_loyalty"]


# ── list_for_tenant: the admin panel's own read (shows visible AND revoked rows) ────────────────

def test_list_for_tenant_is_empty_for_a_blank_tenant():
    ov = _overrides()
    assert run(ov.list_for_tenant("")) == []


def test_list_for_tenant_shows_a_revoked_row_too_unlike_visible_keys_for_tenant():
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    run(ov.set_visible(TENANT_A, KEY, False))
    assert run(ov.list_for_tenant(TENANT_A)) == [{"feature_key": KEY, "visible": False}]


def test_list_for_tenant_never_leaks_another_tenants_rows():
    ov = _overrides()
    run(ov.set_visible(TENANT_A, KEY, True))
    assert run(ov.list_for_tenant(TENANT_B)) == []
