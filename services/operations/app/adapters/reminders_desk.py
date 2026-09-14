"""What `till.py`'s own `POST /till/rating-request` asks of `reminders`: pull an already-scheduled
rating request forward to "due now", rather than building a second send path with its own gating
here (see reminders' own `expedite_rating_request` docstring for why that would be the mistake).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from starlette.concurrency import run_in_threadpool


class RemindersDesk:
    def __init__(self, *, base_url: str, token: str, timeout: int = 5) -> None:
        self._base = (base_url or "").rstrip("/")
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._base)

    def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any] | None:
        req = urllib.request.Request(
            f"{self._base}{path}", method="POST", data=json.dumps(body).encode(),
            headers={"X-Internal-Token": self._token, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:    # nosec B310
                payload = json.loads(resp.read() or b"{}")
                return {"_status": resp.status, **(payload if isinstance(payload, dict) else {})}
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read() or b"{}")
            except Exception:                                                   # noqa: BLE001
                payload = {}
            return {"_status": exc.code,
                   "ok": False,
                   "reason": (payload.get("detail") if isinstance(payload, dict) else None) or ""}
        except Exception:                                                       # noqa: BLE001
            return None

    async def expedite_rating_request(self, tenant: str, subject_ref: str, *,
                                      asset_id: str = "") -> dict[str, Any] | None:
        """`None` means the peer could not be reached at all (try later); a dict is always a real
        answer from `reminders` — `{"ok": True}` or `{"ok": False, "reason": "..."}`."""
        if not self.configured:
            return None
        return await run_in_threadpool(
            self._post, "/internal/reminders/rating-request/expedite",
            {"tenant": tenant, "subject_ref": subject_ref, "asset_id": asset_id})


def build_reminders_desk(settings) -> RemindersDesk:
    return RemindersDesk(base_url=settings.REMINDERS_SERVICE_URL,
                        token=settings.INTERNAL_SERVICE_TOKEN)
