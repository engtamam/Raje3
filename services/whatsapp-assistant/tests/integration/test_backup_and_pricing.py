"""Integration: /internal/backup/{export,verify,import} and /internal/whatsapp_assistant/price.

These three backup routes and the manifest endpoints that declare them were the exact silent gap
docs/adding-a-new-app.md §3b warns about — real code, wired nowhere a gate or a caller could see.
See app/api/internal.py, app/core/backup.py (a verbatim copy of loyalty's generic seal/export/
import/verify logic — its own exhaustive corruption/idempotency/tenant-isolation coverage lives in
services/loyalty/tests/unit/test_backup.py and is not repeated here) and app/backup_manifest.py.
"""
from __future__ import annotations

import asyncio

from tests.conftest import INTERNAL_TOKEN

TENANT = "backup_shop"


def _headers():
    return {"X-Internal-Token": INTERNAL_TOKEN}


def _seed_a_booking(client):
    from app.core.models import BOOKINGS

    app = client.app
    c = app.state.container

    async def _seed():
        await c.datastore.put(BOOKINGS, "bk_1", {
            "id": "bk_1", "tenant": TENANT, "subject_ref": "s1", "service_id": "svc",
            "starts_at": 0, "duration_minutes": 30, "state": "confirmed"})

    asyncio.run(_seed())


def test_backup_export_without_internal_token_is_refused(client):
    resp = client.post("/internal/backup/export", json={})
    assert resp.status_code == 401


def test_backup_export_without_backup_kek_refuses_rather_than_writing_in_the_clear(client):
    # BACKUP_KEK is unset in the test environment (tests/conftest.py) — export must refuse, not
    # silently produce a plaintext-equivalent archive.
    resp = client.post("/internal/backup/export", json={"tenant": TENANT}, headers=_headers())
    assert resp.status_code == 503


def test_backup_export_verify_import_roundtrip(client, monkeypatch):
    monkeypatch.setenv("BACKUP_KEK", "test-backup-kek")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        _seed_a_booking(client)

        export_resp = client.post("/internal/backup/export", json={"tenant": TENANT},
                                  headers=_headers())
        assert export_resp.status_code == 200
        archive = export_resp.json()
        assert archive["row_counts"]["wa_bookings"] == 1
        # Ciphertext at rest — the archive body must not contain the row's own fields in the clear.
        assert "svc" not in str(archive["sealed"])

        verify_resp = client.post("/internal/backup/verify", json={"archive": archive},
                                  headers=_headers())
        assert verify_resp.status_code == 200
        assert verify_resp.json()["verified"] is True

        import_resp = client.post(
            "/internal/backup/import",
            json={"archive": archive, "overwrite": False, "into_tenant": "restored_shop"},
            headers=_headers())
        assert import_resp.status_code == 200
        body = import_resp.json()
        # `bk_1` restores under the SAME datastore key regardless of into_tenant (the default key
        # template is "{id}"), and the live store already holds a row under that key from
        # `_seed_a_booking` — so this asserts REMAPPED (the row's own tenant field was rewritten)
        # rather than INSERTED, which depends on whether that key happened to be free already.
        assert body["remapped"] == 1
        assert body["inserted"] + body["skipped"] == 1
    finally:
        monkeypatch.delenv("BACKUP_KEK", raising=False)
        get_settings.cache_clear()


def test_backup_import_of_a_tampered_archive_is_refused_not_written(client, monkeypatch):
    monkeypatch.setenv("BACKUP_KEK", "test-backup-kek")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        export_resp = client.post("/internal/backup/export", json={"tenant": TENANT},
                                  headers=_headers())
        archive = export_resp.json()
        archive["checksum"] = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        resp = client.post("/internal/backup/import", json={"archive": archive}, headers=_headers())
        assert resp.status_code == 400
    finally:
        monkeypatch.delenv("BACKUP_KEK", raising=False)
        get_settings.cache_clear()


def test_manifest_advertises_the_backup_and_privacy_routes(client):
    resp = client.get("/internal/manifest", headers=_headers())
    assert resp.status_code == 200
    paths = {e["path"] for e in resp.json()["endpoints"]}
    assert {"/internal/backup/export", "/internal/backup/verify", "/internal/backup/import",
            "/internal/privacy/erase", "/internal/whatsapp_assistant/price"} <= paths


# ── pricing — the smallest honest caller for a module ci/check_dead_core.py flagged as unreached ──
def test_price_without_internal_token_is_refused(client):
    resp = client.post("/internal/whatsapp_assistant/price", json={})
    assert resp.status_code == 401


def test_price_is_zero_when_every_pricing_constant_is_zero(client):
    """Every PRICING_* default is 0 (deploy/services/whatsapp-assistant.values.yaml) — this is
    SHAPE, not a shipped price list, until the business sets real numbers."""
    resp = client.post("/internal/whatsapp_assistant/price",
                       json={"input_tokens": 500, "output_tokens": 200}, headers=_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert body["halalas"] == 0
    assert body["strategy"] == "tier_plus_cap"


def test_price_rejects_negative_token_counts(client):
    """A QA audit found `PriceIn.input_tokens`/`output_tokens` had no `Field(ge=0)` — a negative
    value reaches `pricing.usage_based()` and can produce a negative halalas result with nothing
    clamping it. This route is internal-token-gated, not attacker-reachable directly, but a
    misbehaving internal caller (or a future billing peer's own bug) should never be able to make
    this compute a negative charge — refused at the door, same as any other malformed input."""
    resp = client.post("/internal/whatsapp_assistant/price",
                       json={"input_tokens": -1, "output_tokens": 200}, headers=_headers())
    assert resp.status_code == 422
    resp = client.post("/internal/whatsapp_assistant/price",
                       json={"input_tokens": 200, "output_tokens": -1}, headers=_headers())
    assert resp.status_code == 422


def test_price_rejects_an_unknown_strategy_cleanly_not_with_a_500(client, monkeypatch):
    monkeypatch.setenv("PRICING_STRATEGY", "not_a_real_strategy")
    from app.config import get_settings
    get_settings.cache_clear()
    try:
        resp = client.post("/internal/whatsapp_assistant/price", json={}, headers=_headers())
        assert resp.status_code == 400
    finally:
        monkeypatch.delenv("PRICING_STRATEGY", raising=False)
        get_settings.cache_clear()
