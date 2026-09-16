"""`core/marketplaces/tiktok_assistant.py` — the connection resolver, the persona, and the
category-marker extraction. No network: `HttpAssistantConnections` is exercised through a fake
that records calls, exactly like `test_tiktok_shop_api.py` fakes `TikTokShopClient`.
"""
from __future__ import annotations

import pytest

from app.core.marketplaces.tiktok_assistant import (
    _CONNECTION_NAME,
    build_system_prompt,
    ensure_connection,
    extract_category,
    model_url_and_shape,
)
from app.core.tiktok_categories import KNOWN_SLUGS


class _FakeConnections:
    def __init__(self, existing: list[dict] | None = None) -> None:
        self._rows: dict[str, dict] = {r["id"]: r for r in (existing or [])}
        self.create_calls: list[dict] = []
        self.update_calls: list[tuple[str, dict]] = []

    def list(self, tenant: str) -> list[dict]:
        return [r for r in self._rows.values() if r.get("tenant") == tenant]

    def create(self, **body) -> dict:
        cid = f"conn_{len(self._rows) + 1}"
        row = {"id": cid, **body}
        self._rows[cid] = row
        self.create_calls.append(row)
        return row

    def update(self, cid: str, **body) -> dict:
        self._rows[cid].update(body)
        self.update_calls.append((cid, body))
        return self._rows[cid]


# ── ensure_connection ────────────────────────────────────────────────────────────────────────
def test_a_brand_new_tenant_creates_a_connection_named_tiktok_assistant():
    client = _FakeConnections()
    cid = ensure_connection(client, tenant="tnt_a", url="u", shape="chat", model="m", auth="vertex",
                            credential="c", system_prompt="p", tools=[])
    assert len(client.create_calls) == 1
    assert client.create_calls[0]["name"] == _CONNECTION_NAME
    assert client.create_calls[0]["tenant"] == "tnt_a"
    assert cid == client.create_calls[0]["id"]


def test_the_name_is_never_the_whatsapp_ones():
    """The real collision risk the module docstring names — a copy-pasted literal would have
    made this the SAME name as whatsapp-assistant's own connection."""
    assert _CONNECTION_NAME == "tiktok-assistant"
    assert _CONNECTION_NAME != "whatsapp-assistant"


def test_an_unchanged_connection_is_never_updated():
    existing = [{"id": "c1", "tenant": "tnt_b", "name": _CONNECTION_NAME, "system_prompt": "p",
                "tools": [], "url": "u", "shape": "chat", "model": "m", "auth": "vertex"}]
    client = _FakeConnections(existing)
    cid = ensure_connection(client, tenant="tnt_b", url="u", shape="chat", model="m", auth="vertex",
                            credential="c", system_prompt="p", tools=[])
    assert cid == "c1"
    assert client.update_calls == []


def test_a_changed_system_prompt_updates_only_that_field():
    existing = [{"id": "c1", "tenant": "tnt_c", "name": _CONNECTION_NAME, "system_prompt": "old",
                "tools": [], "url": "u", "shape": "chat", "model": "m", "auth": "vertex"}]
    client = _FakeConnections(existing)
    ensure_connection(client, tenant="tnt_c", url="u", shape="chat", model="m", auth="vertex",
                      credential="c", system_prompt="new", tools=[])
    assert len(client.update_calls) == 1
    changes = {k: v for k, v in client.update_calls[0][1].items() if k != "tenant"}
    assert changes == {"system_prompt": "new"}


def test_a_changed_model_updates_an_already_provisioned_tenant():
    """The exact real bug the whatsapp-side ensure_connection fixed 2026-09-14 (url/shape/model/
    auth were once silently never compared) — this fresh implementation starts from the fixed
    shape, verified here rather than trusted."""
    existing = [{"id": "c1", "tenant": "tnt_d", "name": _CONNECTION_NAME, "system_prompt": "p",
                "tools": [], "url": "old-url", "shape": "chat", "model": "old-model",
                "auth": "vertex"}]
    client = _FakeConnections(existing)
    ensure_connection(client, tenant="tnt_d", url="new-url", shape="chat", model="new-model",
                      auth="vertex", credential="c", system_prompt="p", tools=[])
    assert len(client.update_calls) == 1
    changes = {k: v for k, v in client.update_calls[0][1].items() if k != "tenant"}
    assert changes == {"url": "new-url", "model": "new-model"}


def test_two_tenants_each_get_their_own_row_never_sharing_one():
    client = _FakeConnections()
    ensure_connection(client, tenant="tnt_e1", url="u", shape="chat", model="m", auth="vertex",
                      credential="c", system_prompt="p1", tools=[])
    ensure_connection(client, tenant="tnt_e2", url="u", shape="chat", model="m", auth="vertex",
                      credential="c", system_prompt="p2", tools=[])
    assert len(client.create_calls) == 2
    assert client.create_calls[0]["tenant"] != client.create_calls[1]["tenant"]


def test_a_connection_with_a_different_name_on_the_same_tenant_is_ignored():
    """A shop that also has some OTHER assistant-service connection under a different name (a
    future app, or a stray row) must never be mistaken for this one and silently repurposed."""
    existing = [{"id": "c1", "tenant": "tnt_f", "name": "some-other-app", "system_prompt": "p"}]
    client = _FakeConnections(existing)
    cid = ensure_connection(client, tenant="tnt_f", url="u", shape="chat", model="m", auth="vertex",
                            credential="c", system_prompt="p", tools=[])
    assert cid != "c1"
    assert len(client.create_calls) == 1


# ── build_system_prompt ──────────────────────────────────────────────────────────────────────
def test_the_prompt_names_the_real_shop():
    prompt = build_system_prompt("متجر سارة")
    assert "متجر سارة" in prompt


def test_a_blank_shop_name_falls_back_to_a_generic_label_not_an_empty_gap():
    prompt = build_system_prompt("")
    assert "هذا المحل" in prompt


def test_owner_notes_are_appended_after_every_rule_never_before():
    prompt = build_system_prompt("م", owner_notes="نتعامل بالكاش فقط")
    rules_end = prompt.index("لا تدّعِ أبدًا")
    notes_at = prompt.index("نتعامل بالكاش فقط")
    assert notes_at > rules_end


def test_owner_notes_are_redacted_a_second_time_here():
    prompt = build_system_prompt("م", owner_notes="تواصل معي على 0501234567")
    assert "0501234567" not in prompt
    assert "[phone]" in prompt


def test_the_category_catalogue_is_inside_the_prompt():
    prompt = build_system_prompt("م")
    assert "order_status" in prompt
    assert "[تصنيف:" in prompt


def test_two_calls_for_two_tenants_share_no_substring_beyond_the_fixed_template():
    """Same isolation guarantee whatsapp-assistant's own test_shop_identity.py checks for its
    build_system_prompt — a prompt built for one shop must never leak another's name/notes."""
    a = build_system_prompt("متجر أ", owner_notes="ملاحظة أ")
    b = build_system_prompt("متجر ب", owner_notes="ملاحظة ب")
    assert "متجر أ" not in b
    assert "ملاحظة أ" not in b


# ── extract_category ─────────────────────────────────────────────────────────────────────────
def test_a_well_formed_marker_is_extracted_and_stripped():
    text, cat = extract_category("طلبك بالطريق\n[تصنيف: shipping_delay]")
    assert text == "طلبك بالطريق"
    assert cat == "shipping_delay"


def test_a_reply_with_no_marker_at_all_still_returns_the_full_text():
    text, cat = extract_category("شكراً لتواصلك معنا")
    assert text == "شكراً لتواصلك معنا"
    assert cat == ""


def test_an_empty_reply_does_not_crash():
    text, cat = extract_category("")
    assert text == "" and cat == ""


def test_a_marker_must_be_the_very_last_line_not_mid_text():
    """A customer's own message quoted back, or a coincidental bracket mid-reply, must never be
    mistaken for the machine-only marker."""
    text, cat = extract_category("العميل كتب [تصنيف: fake] بس أنا ما أقصد هذا فعلاً")
    assert cat == ""
    assert "[تصنيف: fake]" in text


def test_a_marker_with_extra_whitespace_still_parses():
    text, cat = extract_category("رد قصير\n[تصنيف:   payment]   ")
    assert cat == "payment"
    assert text == "رد قصير"


def test_a_novel_slug_the_model_invents_still_extracts_cleanly():
    """The 'adaptive taxonomy' design — a slug outside KNOWN_SLUGS is not an error, just not
    (yet) a named category an owner sees on a report."""
    text, cat = extract_category("رد\n[تصنيف: loyalty_card_question]")
    assert cat == "loyalty_card_question"
    assert cat not in KNOWN_SLUGS


def test_every_known_slug_round_trips_through_the_marker_format():
    for slug in KNOWN_SLUGS:
        text, cat = extract_category(f"رد\n[تصنيف: {slug}]")
        assert cat == slug


def test_a_marker_with_uppercase_or_arabic_digits_in_the_slug_does_not_match():
    """The marker regex only accepts a-z and underscore — the model was explicitly instructed to
    produce exactly that shape, and a malformed slug is safer treated as no-marker-at-all than
    guessed at."""
    text, cat = extract_category("رد\n[تصنيف: Order_Status]")
    assert cat == ""


def test_multiple_newlines_before_the_marker_still_match():
    text, cat = extract_category("سطر أول\n\n\n[تصنيف: account]")
    assert cat == "account"


def test_only_the_trailing_marker_is_stripped_an_identical_earlier_string_is_kept():
    text, cat = extract_category("[تصنيف: praise] كان هذا رد سابق\n[تصنيف: praise]")
    assert cat == "praise"
    assert text == "[تصنيف: praise] كان هذا رد سابق"


# ── model_url_and_shape ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("model,expected_shape,expected_path_part", [
    ("gemini-2.5-flash", "generate", "publishers/google"),
    ("claude-3-7-sonnet", "anthropic", "publishers/anthropic"),
    ("gpt-oss-20b", "chat", "endpoints/openapi/chat/completions"),
])
def test_model_prefix_selects_the_right_shape(model, expected_shape, expected_path_part):
    url, shape = model_url_and_shape("me-central2", "proj-1", model)
    assert shape == expected_shape
    assert expected_path_part in url
    assert "proj-1" in url
    assert "me-central2" in url
