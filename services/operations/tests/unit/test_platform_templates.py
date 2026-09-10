"""seed_platform_templates — the platform's own templates, made ready without anybody typing
them, never reverting an operator's own edit and never submitting anything to Meta."""
from __future__ import annotations

import asyncio
import json

from app.core.flows import PLATFORM
from app.core.library import NullLibrary
from app.core.platform_templates import load_seed, seed_platform_templates


def run(c):
    return asyncio.run(c)


class _FakeLibrary(NullLibrary):
    def __init__(self, *, existing: set[str] | None = None) -> None:
        super().__init__()
        self._existing = existing
        self.registered_rows: list[dict] = []

    async def list_names(self, tenant: str) -> set[str] | None:
        return self._existing

    async def register(self, tenant: str, template: dict) -> bool:
        self.registered_rows.append({**template, "tenant": tenant})
        return True


SEED = {"templates": [
    {"name": "ai_wallet_low_balance", "language": "ar", "category": "UTILITY",
     "body": "رصيدك أوشك ينتهي: {{1}}", "variables": [1], "examples": ["https://x"]},
    {"name": "subscription_renewal_flow", "language": "ar", "category": "UTILITY",
     "body": "حان موعد التجديد", "variables": [], "examples": [],
     "flow_button": {"flow_name": "subscription_renewal", "text": "جدّد الآن"}},
]}


def _write_seed(tmp_path, data=SEED):
    p = tmp_path / "platform_templates.seed.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


def test_load_seed_reads_the_templates_list():
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        path = _write_seed(pathlib.Path(d))
        rows = load_seed(path)
    assert [r["name"] for r in rows] == ["ai_wallet_low_balance", "subscription_renewal_flow"]


def test_load_seed_with_no_path_is_empty():
    assert load_seed("") == []


def test_load_seed_with_a_missing_file_is_empty_not_a_crash():
    assert load_seed("/no/such/file.json") == []


def test_both_seed_rows_register_when_the_platform_has_neither_yet(tmp_path):
    lib = _FakeLibrary(existing=set())
    out = run(seed_platform_templates(lib, seed_path=_write_seed(tmp_path)))
    assert out == {"registered": 2, "skipped": 0, "failed": 0}
    assert [r["name"] for r in lib.registered_rows] == \
        ["ai_wallet_low_balance", "subscription_renewal_flow"]
    assert all(r["tenant"] == PLATFORM for r in lib.registered_rows)


def test_an_already_registered_name_is_skipped_never_re_registered(tmp_path):
    """THE WHOLE POINT — an operator's own edit (or a re-submission after a Meta rejection) to
    `ai_wallet_low_balance` must never be silently reverted by a later boot re-registering the
    seed's own original content over it."""
    lib = _FakeLibrary(existing={"ai_wallet_low_balance"})
    out = run(seed_platform_templates(lib, seed_path=_write_seed(tmp_path)))
    assert out == {"registered": 1, "skipped": 1, "failed": 0}
    assert [r["name"] for r in lib.registered_rows] == ["subscription_renewal_flow"]


def test_both_already_registered_registers_nothing(tmp_path):
    lib = _FakeLibrary(existing={"ai_wallet_low_balance", "subscription_renewal_flow"})
    out = run(seed_platform_templates(lib, seed_path=_write_seed(tmp_path)))
    assert out == {"registered": 0, "skipped": 2, "failed": 0}
    assert lib.registered_rows == []


def test_a_list_names_that_cannot_answer_registers_nothing_rather_than_guessing(tmp_path):
    """`None` (could not ask) must never be read as "nothing exists yet" — re-registering over
    content this pass never actually looked at is exactly the revert this module exists to avoid.
    """
    lib = _FakeLibrary(existing=None)
    out = run(seed_platform_templates(lib, seed_path=_write_seed(tmp_path)))
    assert out == {"registered": 0, "skipped": 0, "failed": 0}
    assert lib.registered_rows == []


def test_no_seed_file_configured_does_nothing():
    lib = _FakeLibrary(existing=set())
    out = run(seed_platform_templates(lib, seed_path=""))
    assert out == {"registered": 0, "skipped": 0, "failed": 0}
    assert lib.registered_rows == []


def test_a_failed_registration_is_counted_not_raised(tmp_path):
    class _Flaky(_FakeLibrary):
        async def register(self, tenant, template):
            return template["name"] != "subscription_renewal_flow"

    lib = _Flaky(existing=set())
    out = run(seed_platform_templates(lib, seed_path=_write_seed(tmp_path)))
    assert out == {"registered": 1, "skipped": 0, "failed": 1}
