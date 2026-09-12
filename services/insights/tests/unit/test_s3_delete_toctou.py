"""insights-r2-006 (QA audit, 2026-09-12): S3ObjectStore.delete() checked head_object then called
delete_object as two separate round trips with nothing pinning them to the same object — a
concurrent writer replacing the key in between meant delete_object would destroy the NEW object
while this call still reported True for having deleted the one it checked. The fix pins the delete
to the VersionId head_object observed, so a versioned bucket never deletes a write that lands after
the check."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from app.adapters.object_store.s3 import S3ObjectStore
from tests.contracts.util import run


class _FakeClientCtx:
    """Mimics aioboto3's `async with session.client(...)` shape around a fake S3 client."""

    def __init__(self, client):
        self._client = client

    async def __aenter__(self):
        return self._client

    async def __aexit__(self, *exc):
        return False


def _store_with_fake_client(fake_client):
    store = S3ObjectStore("bucket", "http://fake")
    store._client = lambda: _FakeClientCtx(fake_client)
    return store


def test_delete_pins_to_the_version_head_object_observed():
    fake = MagicMock()
    fake.head_object = AsyncMock(return_value={"VersionId": "v123"})
    fake.delete_object = AsyncMock(return_value={})
    store = _store_with_fake_client(fake)

    ok = run(store.delete("some/key"))

    assert ok is True
    fake.delete_object.assert_awaited_once_with(Bucket="bucket", Key="some/key", VersionId="v123")


def test_delete_without_a_version_id_falls_back_to_a_plain_delete():
    # Versioning off: S3 offers no atomic primitive at all, so a plain delete is the best available.
    fake = MagicMock()
    fake.head_object = AsyncMock(return_value={})
    fake.delete_object = AsyncMock(return_value={})
    store = _store_with_fake_client(fake)

    ok = run(store.delete("some/key"))

    assert ok is True
    fake.delete_object.assert_awaited_once_with(Bucket="bucket", Key="some/key")


def test_delete_of_a_missing_object_never_calls_delete_object():
    fake = MagicMock()
    fake.head_object = AsyncMock(side_effect=Exception("404"))
    fake.delete_object = AsyncMock(return_value={})
    store = _store_with_fake_client(fake)

    ok = run(store.delete("missing/key"))

    assert ok is False
    fake.delete_object.assert_not_awaited()
