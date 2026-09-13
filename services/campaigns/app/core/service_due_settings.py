"""«حان وقت الخدمة»'s one settings record per tenant — not a campaign that is ever launched.

EVERY OTHER GOAL IN THIS SERVICE IS A THING AN OWNER PRESSES, or a standing rule this service
itself re-evaluates every day (`win_back`/`reward_loyal`, via `tick.py`/`dispatch.py`). This goal is
neither: reminders' own `scheduling.py` computes the precise per-service cycle at visit time and
schedules the row directly — that computation is NOT changing and NOT moving here. What this
service owns for `service_due` is exactly ONE fact an owner can set once and forget: whether the
reminder still goes out at all. No reward, no audience, no send count, no `expires_at` — a settings
record, not a run.

NO REWARD CHOICE HERE, DELIBERATELY (owner's own call, 2026-09-13): the owner's own instruction was
to keep this exactly the old mechanism — an on/off switch, nothing more. An earlier pass of this
same session built a reward_type/reward_points choice here too; it was reverted before ever
shipping to the console because the owner did not want a manual reward decision on this goal, and
did not want an automatic behaviour-based one either — just the plain reminder, unchanged.

ONE ROW PER TENANT, ENFORCED BY A FIXED ID rather than the usual `_id("cmp")` random one — the same
"tenant|id" key shape every other campaign uses (`Campaign.key`), but the id never varies, so a
second "create" is structurally the same write as the first: there is no second row to accumulate,
no press-dedup trick needed the way `core/press.py` exists for a launched campaign.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.core.models import Campaign

#: The fixed id every tenant's one record lives at — `f"{tenant}|{SETTINGS_ID}"` is the key.
SETTINGS_ID = "service_due_settings"

#: A shop that has never touched this setting keeps getting exactly today's behaviour: the plain
#: reminder, unchanged, forever.
DEFAULTS = {"active": True}


@dataclass(frozen=True)
class ServiceDueSettings:
    active: bool = True

    def as_dict(self) -> dict:
        return {"active": self.active}


def key_for(tenant: str) -> str:
    return f"{tenant}|{SETTINGS_ID}"


async def load(datastore, tenant: str) -> ServiceDueSettings:
    """This tenant's settings, or the untouched defaults — never `None`: a shop that has never
    opened this screen is not a shop with a missing record, it is a shop still on day one."""
    row = await datastore.get("campaigns", key_for(tenant))
    if not row:
        return ServiceDueSettings(**DEFAULTS)
    return ServiceDueSettings(active=bool(row.get("state", "active") != "paused"))


async def save(datastore, tenant: str, *, active: bool) -> Campaign:
    """Upsert the one row — same `Campaign` shape every other campaign is stored as, so nothing
    else reading the `campaigns` collection (backup/export, the platform's own tooling) needs a
    second schema to understand.
    """
    existing = await datastore.get("campaigns", key_for(tenant))
    campaign = Campaign(
        tenant=tenant, goal="service_due", id=SETTINGS_ID,
        template_type="svc_service_reminder", cls="marketing", trigger="standing",
        state="active" if active else "paused")
    row = {k: v for k, v in vars(campaign).items()}
    # A RE-SAVE KEEPS ITS ORIGINAL `created` — a settings edit is not a re-dating of the record.
    # The dataclass default (`field(default_factory=_now)`) already gave a genuine first save the
    # right value; this only overwrites it back when a row already existed.
    if existing and existing.get("created"):
        row["created"] = existing["created"]
    await datastore.put("campaigns", key_for(tenant), row)
    return campaign
