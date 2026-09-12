"""insights-r2-004 (QA audit, 2026-09-12): the /internal/backup/verify and /internal/backup/import
routes called core.backup.verify_restore/import_archive WITHOUT `declaration`, while
/internal/backup/export always passes the BACKUP manifest. core/backup.py itself is consistent —
both paths use the same `_key_templates`/`_row_key` logic once `declaration` is supplied — the gap
was the route layer never supplying it, so any collection that ever declares a composite `key`
template would restore under the wrong key on verify/import while export used the right one.

These tests do not roundtrip real data; they prove the ROUTE HANDLERS pass the same `BACKUP`
manifest export uses into verify_restore/import_archive, which is what closes the gap."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api import internal as I
from app.backup_manifest import BACKUP


def _fake_request():
    container = SimpleNamespace(datastore=SimpleNamespace())
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(container=container)))


def _fake_settings():
    return SimpleNamespace(BACKUP_KEK="k" * 32)


def test_backup_verify_route_passes_the_same_manifest_export_uses():
    with patch.object(I._backup, "verify_restore", new=AsyncMock(
            return_value={"verified": True})) as mocked:
        body = I.BackupVerifyIn(archive={"format": "x", "sealed": "y", "checksum": "z"})
        import asyncio
        asyncio.run(I.backup_verify(_fake_request(), body, _fake_settings()))
    assert mocked.await_args.kwargs.get("declaration") is BACKUP


def test_backup_import_route_passes_the_same_manifest_export_uses():
    with patch.object(I._backup, "import_archive", new=AsyncMock(
            return_value={"inserted": 0})) as mocked:
        body = I.BackupImportIn(archive={"format": "x", "sealed": "y", "checksum": "z"})
        import asyncio
        asyncio.run(I.backup_import(_fake_request(), body, _fake_settings()))
    assert mocked.await_args.kwargs.get("declaration") is BACKUP
