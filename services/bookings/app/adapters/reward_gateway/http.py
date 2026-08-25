"""The reward `attend()` spends — docs/خطة-تنفيذ-الحجوزات.md's §ADR on "نية استبدال, لا استبدال
فوري". A stdlib urllib client of `operations`' `POST
/internal/operations/bookings/redeem`, same shape as `visit_gateway/http.py`.

NEVER called from `create()` or `set_intended_reward()` — see `RewardGateway`'s own docstring in
core/operations.py for why the spend waits for the appointment to actually happen.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request


class HttpRewardGateway:
    def __init__(self, *, operations_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = operations_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def redeem(self, *, tenant: str, subject_ref: str, reward_id: str,
                     idempotency_key: str, branch_id: str, actor: str) -> dict | None:
        """`None` on ANY failure — unreachable peer, a malformed response. The caller
        (`BookingOperations.attend`) treats that exactly like an explicit `{"ok": false}`: leave
        `intended_reward_id` set, never fail the attendance itself over it."""
        body = json.dumps({
            "tenant": tenant, "subject_ref": subject_ref, "reward_id": reward_id,
            "idempotency_key": idempotency_key, "branch_id": branch_id, "actor": actor,
        }).encode()
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                return json.loads(resp.read() or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return None
