"""insights-r2-005 (QA audit, 2026-09-12): backup_manifest.py declared only four collections while
the service writes seven — insight_next_step_state, runtime_config and insight_platform_summary
were in neither `collections` nor `excluded`, the exact silent hole the manifest's own docstring
says must never exist."""
from __future__ import annotations

from app.backup_manifest import BACKUP
from app.core.models import (
    NEXT_STEP_STATE, PAIRS, PLATFORM_SUMMARY, SEQUENCES, SNAPSHOTS,
)
from app.core.runtime_config import _COLL as RUNTIME_CONFIG


def _declared_names() -> set[str]:
    return ({e["name"] for e in BACKUP["collections"]}
            | {e["name"] for e in BACKUP["excluded"]})


def test_every_collection_the_service_writes_is_declared():
    written = {SEQUENCES, SNAPSHOTS, PAIRS, NEXT_STEP_STATE,
               PLATFORM_SUMMARY, RUNTIME_CONFIG}
    missing = written - _declared_names()
    assert not missing, f"backup_manifest.py declares nothing for: {sorted(missing)}"
