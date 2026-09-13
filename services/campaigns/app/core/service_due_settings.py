"""«حان وقت الخدمة»'s one settings record per tenant — not a campaign that is ever launched.

EVERY OTHER GOAL IN THIS SERVICE IS A THING AN OWNER PRESSES, or a standing rule this service
itself re-evaluates every day (`win_back`/`reward_loyal`, via `tick.py`/`dispatch.py`). This goal is
neither: reminders' own `scheduling.py` computes the precise per-service cycle at visit time and
schedules the row directly — that computation is NOT changing and NOT moving here. What this
service owns for `service_due` is exactly three facts an owner can set once and forget: whether the
reminder still goes out at all, and which of two rewards (if any) it hands out. No audience, no
send count, no `expires_at` — a settings record, not a run.

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

#: `service_due`'s OWN reward vocabulary — narrower than `REWARD_TYPES` in models.py.
#: `gift` is deliberately excluded: it requires a specific service in `scope_service_ids`
#: (`validate_reward`'s own rule), and this goal already names one specific service on every send —
#: gifting "the very service this message is about" reads as a strange, circular promise rather
#: than a reward, and this settings record carries no `scope_service_ids` at all to build one from
#: in the first place. Flagged in this session's report as a judgment call rather than guessed
#: silently.
REWARD_TYPES = ("discount", "points")

#: A shop that has never touched this setting keeps getting exactly today's behaviour: the plain
#: reminder, unchanged, forever. `reward_type="discount"` is the same "nothing chosen yet" default
#: every other reward-enabled goal already carries (models.py's own note on `Campaign.reward_type`)
#: — it is NOT "a discount is configured"; this settings record has no amount field for one at all,
#: only `reward_points` (meaningful for `points`). See this session's report for why a reward
#: SENTENCE is not yet composed from this at send time: `svc_service_reminder`'s approved body has
#: four fixed variables and no spare slot for one — adding a fifth needs a new template variant and
#: fresh Meta approval, a separate task.
DEFAULTS = {"active": True, "reward_type": "discount", "reward_points": 0}


def validate(*, reward_type: str, reward_points: int) -> str:
    """One Arabic sentence naming what is wrong with this goal's own reward, or "" when coherent.

    DELIBERATELY NOT `models.validate_reward` — that function requires a non-empty `offer_value`
    for `discount` and a chosen service for `gift`, neither of which this settings record carries
    (and `gift` is not offered here at all — see `REWARD_TYPES` above). Reusing it would either
    refuse this goal's own default (a `discount` with nothing configured, which must always be
    allowed here) or need `validate_reward` itself weakened for every OTHER goal that correctly
    relies on it refusing exactly that.
    """
    if reward_type not in REWARD_TYPES:
        return f"نوع المكافأة غير معروف لهذا الهدف — اختر واحداً من {REWARD_TYPES}"
    if reward_type == "points" and reward_points <= 0:
        return "عدد نقاط الهدية يجب أن يكون أكبر من صفر"
    return ""


@dataclass(frozen=True)
class ServiceDueSettings:
    active: bool = True
    reward_type: str = "discount"
    reward_points: int = 0

    def as_dict(self) -> dict:
        return {"active": self.active, "reward_type": self.reward_type,
                "reward_points": self.reward_points}


def key_for(tenant: str) -> str:
    return f"{tenant}|{SETTINGS_ID}"


async def load(datastore, tenant: str) -> ServiceDueSettings:
    """This tenant's settings, or the untouched defaults — never `None`: a shop that has never
    opened this screen is not a shop with a missing record, it is a shop still on day one."""
    row = await datastore.get("campaigns", key_for(tenant))
    if not row:
        return ServiceDueSettings(**DEFAULTS)
    return ServiceDueSettings(
        active=bool(row.get("state", "active") != "paused"),
        reward_type=str(row.get("reward_type") or DEFAULTS["reward_type"]),
        reward_points=int(row.get("reward_points") or 0))


async def save(datastore, tenant: str, *, active: bool, reward_type: str,
              reward_points: int) -> Campaign:
    """Upsert the one row — same `Campaign` shape every other campaign is stored as, so nothing
    else reading the `campaigns` collection (backup/export, the platform's own tooling) needs a
    second schema to understand.
    """
    existing = await datastore.get("campaigns", key_for(tenant))
    campaign = Campaign(
        tenant=tenant, goal="service_due", id=SETTINGS_ID,
        template_type="svc_service_reminder", cls="marketing", trigger="standing",
        state="active" if active else "paused",
        reward_type=reward_type, reward_points=reward_points)
    row = {k: v for k, v in vars(campaign).items()}
    # A RE-SAVE KEEPS ITS ORIGINAL `created` — a settings edit is not a re-dating of the record.
    # The dataclass default (`field(default_factory=_now)`) already gave a genuine first save the
    # right value; this only overwrites it back when a row already existed.
    if existing and existing.get("created"):
        row["created"] = existing["created"]
    await datastore.put("campaigns", key_for(tenant), row)
    return campaign
