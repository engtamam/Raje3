"""core/oauth_state.py — the signed `state` an OAuth callback verifies with nothing else to go
on (no session, no cookie survives the bounce through the provider's own domain)."""
from __future__ import annotations

from app.core import oauth_state as S

SALT = "s" * 32


def test_a_fresh_state_verifies_and_names_the_right_tenant():
    st = S.issue(SALT, "salla", "tnt_alpha")
    assert S.tenant_for(SALT, "salla", st) == "tnt_alpha"


def test_a_state_for_a_different_purpose_never_verifies():
    """A state minted for one provider must not be replayable against a second one that happens
    to reuse this module."""
    st = S.issue(SALT, "salla", "tnt_alpha")
    assert S.tenant_for(SALT, "zid", st) is None


def test_a_tampered_state_never_verifies():
    st = S.issue(SALT, "salla", "tnt_alpha")
    tampered = st[:-1] + ("0" if st[-1] != "0" else "1")
    assert S.tenant_for(SALT, "salla", tampered) is None


def test_an_expired_state_is_refused():
    st = S.issue(SALT, "salla", "tnt_alpha", now=1_000_000)
    assert S.tenant_for(SALT, "salla", st, now=1_000_000 + S.TTL_SECONDS + 1) is None


def test_a_state_just_inside_its_window_still_verifies():
    st = S.issue(SALT, "salla", "tnt_alpha", now=1_000_000)
    assert S.tenant_for(SALT, "salla", st, now=1_000_000 + S.TTL_SECONDS) == "tnt_alpha"


def test_garbage_input_is_refused_not_raised():
    assert S.tenant_for(SALT, "salla", "") is None
    assert S.tenant_for(SALT, "salla", "not-a-real-state") is None
    assert S.tenant_for(SALT, "salla", "a.b.c.d.e.f") is None
    assert S.tenant_for("", "salla", "whatever") is None


def test_two_states_for_the_same_tenant_are_never_identical():
    """The nonce, not the tenant, makes each mint unique — a replayed OLD state from a browser
    history must not silently equal a fresh one."""
    a = S.issue(SALT, "salla", "tnt_alpha", now=1_000_000)
    b = S.issue(SALT, "salla", "tnt_alpha", now=1_000_000)
    assert a != b


def test_a_state_cannot_be_forged_to_claim_a_different_tenant():
    """The whole security property: an attacker who can see tnt_alpha's real state string cannot
    hand-edit it to claim tnt_victim — the tenant is inside the MAC, not beside it."""
    st = S.issue(SALT, "salla", "tnt_alpha")
    tenant_part, rest = st.split(".", 1)
    import base64
    forged_tenant = base64.urlsafe_b64encode(b"tnt_victim").decode("ascii").rstrip("=")
    forged = f"{forged_tenant}.{rest}"
    assert S.tenant_for(SALT, "salla", forged) is None
