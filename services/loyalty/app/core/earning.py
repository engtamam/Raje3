"""How many points a visit is worth — three levels that inherit, never copy (spec §9.2).

THIS IS REMINDERS' SETTINGS TREE, ON PURPOSE AND ALMOST LITERALLY. Same three levels, same
resolution order, same "absent means follow", same source on every resolved value. It is ported
from `services/reminders/app/core/settings_tree.py` rather than re-derived, and the sameness is the
feature: an owner who learned the tree once when setting reminder intervals must not learn a second
one to set points. Two screens that behave the same way are one concept; two that behave nearly the
same way are two concepts and a bug report.

INHERIT, NEVER COPY — the decision the file turns on, and the reason is worth repeating here rather
than referring to it. Copying the general number into each service at creation looks identical on
day one and fails silently on day thirty: the owner raises the general figure, twenty services keep
their copies, nothing changes, nothing errors, and they conclude points do not work. So a service
stores ONLY what it overrides. Absence is not a value; it is the act of following.

ONE ENTRY PER VISIT, NOT ONE PER SERVICE. A wash with three services earns one ledger row carrying
the sum. The customer experienced one visit, and a statement that shows three lines for one wash is
a statement he reads as a mistake.

WHICH LEVEL PRODUCED THE NUMBER IS RECORDED. Not decoration: the owner will ask "why 30?", and a
loyalty programme whose numbers the owner cannot explain is one he switches off. That is why
`resolve()` returns a source and why the ledger has a `rule_level` field to put it in.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.models import EARN_MODES, SETTINGS, LoyaltyError

# What can be set at a level. ONE field, deliberately: points per visit for services under this
# level. Every field added here is another decision an owner can be asked to make, and the whole
# design is about not asking.
FIELDS = ("points",)

GENERAL = "_general"


@dataclass(frozen=True)
class Resolved:
    """One effective value and where it came from."""
    value: Any
    # "service", "group:<name>", "general", or "default". The screen renders three of them the
    # same way; only "service" gets the "customised — tap to follow again" note.
    source: str

    @property
    def is_override(self) -> bool:
        return self.source == "service"


@dataclass
class EarnConfig:
    """How this establishment earns — a SWITCH, not two toggles (spec §9.3).

    `mode` is one of EARN_MODES and there is no state in which both apply. A shop granting points
    per service AND per riyal pays twice for one transaction, and the error is invisible on screen:
    it surfaces at month end as an obligation twice the size the owner planned for. Making it
    unrepresentable is cheaper than validating it in the one place somebody remembers to.

    `invoice` mode is available to the INTEGRATED establishment alone. The manual field screen
    records no money at all (spec §10 governing principle), so asking for an amount there would add
    a field to the five-second journey in exchange for a figure the operator would be estimating.
    """
    mode: str = "services"
    # Points per riyal, for `invoice` mode. An integer multiplier over whole riyals — no float
    # ever touches this, and the rounding is stated rather than inherited from a language.
    points_per_riyal: int = 1
    integrated: bool = False        # is this establishment wired to a till? (spec §16.6)

    def validate(self) -> None:
        if self.mode not in EARN_MODES:
            raise LoyaltyError("طريقة الاحتساب إما بالخدمات أو بقيمة الفاتورة")
        if self.mode == "invoice" and not self.integrated:
            # ARABIC, because this reaches the owner's screen. The platform is Arabic-only
            # today (and structured so English can be added later) — an English sentence here is
            # not a smaller bug than no sentence at all, it is the same one.
            raise LoyaltyError(
                "الاحتساب بقيمة الفاتورة يحتاج ربطاً بالكاشير — الشاشة الميدانية لا تسجّل مبالغ")
        if self.points_per_riyal < 0:
            raise LoyaltyError("النقاط لكل ريال لا تكون سالبة")

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "points_per_riyal": self.points_per_riyal,
                "integrated": self.integrated}


@dataclass
class EarnTree:
    """A tenant's whole earning picture, resolved once and read many times."""
    tenant: str
    general: dict[str, Any] = field(default_factory=dict)
    groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    service_group: dict[str, str] = field(default_factory=dict)
    services: dict[str, dict[str, Any]] = field(default_factory=dict)
    # A PACKAGE'S OWN POINTS — NOT A FOURTH INHERITING LEVEL. Unlike a service (which follows a
    # group, then the general figure, then a platform default when it has no override of its own),
    # a package has no group, no general rate, and no default to fall back on: it earns EXACTLY the
    # number stored here, always explicit, the same way its own `price_minor` is (operations'
    # Package model, same doctrine: "the platform never invents this number"). The console prefills
    # this input with the sum of the components' CURRENT resolved points at creation time — a
    # convenience shown once, never a value this tree computes or remembers deriving.
    packages: dict[str, dict[str, Any]] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)
    config: EarnConfig = field(default_factory=EarnConfig)

    def resolve(self, service_id: str, field_name: str = "points") -> Resolved:
        """The effective value for one field of one service, and its source.

        The FIRST level that HAS the field wins — and "has" means the key is present, not that it
        is truthy. `points: 0` is a decision (this service earns nothing), and treating zero as
        absent would silently restore the general value the owner just removed.
        """
        own = self.services.get(service_id) or {}
        if field_name in own:
            return Resolved(own[field_name], "service")

        group = self.service_group.get(service_id, "")
        if group:
            gsettings = self.groups.get(group) or {}
            if field_name in gsettings:
                return Resolved(gsettings[field_name], f"group:{group}")

        if field_name in self.general:
            return Resolved(self.general[field_name], "general")

        return Resolved(self.defaults.get(field_name), "default")

    def points_for(self, service_ids: list[str]) -> tuple[int, str]:
        """The whole visit's points, and the level that decided the largest part of it.

        THE SOURCE REPORTED IS THE ONE THAT CONTRIBUTED MOST. A visit resolved through three
        different levels has no single source, and the owner asking "why 30?" wants the level to
        look at first — not a list of three he has to reconcile. Ties break toward the more
        specific level, because that is the one he edited.
        """
        total = 0
        by_source: dict[str, int] = {}
        for sid in service_ids:
            r = self.resolve(sid)
            v = int(r.value or 0)
            total += v
            by_source[r.source] = by_source.get(r.source, 0) + v
        if not by_source:
            return 0, "default"
        rank = {"service": 3, "general": 1, "default": 0}
        best = max(by_source.items(),
                   key=lambda kv: (kv[1], rank.get(kv[0].split(":")[0], 2)))
        return total, best[0]

    def is_customised(self, service_id: str) -> bool:
        return bool(self.services.get(service_id))

    def points_for_package(self, package_id: str) -> int:
        """A package's own explicit point value — 0 if none was ever set (should not happen in
        practice, since operations/console always writes one at creation; a missing value is
        treated as "earns nothing yet" rather than guessed at, same as an unconfigured service
        earning nothing rather than inheriting a number nobody set for it)."""
        return int((self.packages.get(package_id) or {}).get("points") or 0)


class EarnStore:
    """Reads and writes the three levels plus the mode switch. One row per tenant holds all of it.

    ONE ROW, not several collections: the whole tree is small and always read as a unit, and the
    earn path reads it on every visit event in the product.
    """

    def __init__(self, store, *, defaults: dict[str, Any] | None = None) -> None:
        self._s = store
        self._defaults = defaults or {}

    async def load(self, tenant: str) -> EarnTree:
        row = await self._s.get(SETTINGS, f"{tenant}|earning") or {}
        cfg = dict(row.get("config") or {})
        return EarnTree(
            tenant=tenant,
            general=dict(row.get("general") or {}),
            groups=dict(row.get("groups") or {}),
            service_group=dict(row.get("service_group") or {}),
            services=dict(row.get("services") or {}),
            packages=dict(row.get("packages") or {}),
            defaults=dict(self._defaults),
            config=EarnConfig(mode=cfg.get("mode", "services"),
                              points_per_riyal=int(cfg.get("points_per_riyal") or 1),
                              integrated=bool(cfg.get("integrated"))))

    async def _save(self, tree: EarnTree) -> None:
        await self._s.put(SETTINGS, f"{tree.tenant}|earning", {
            "id": f"{tree.tenant}|earning", "tenant": tree.tenant,
            "general": tree.general, "groups": tree.groups,
            "service_group": tree.service_group, "services": tree.services,
            "packages": tree.packages,
            "config": tree.config.to_dict()})

    async def set_general(self, tenant: str, values: dict[str, Any]) -> EarnTree:
        """Change the tenant-wide number. Reaches every follower and NOTHING else — a service the
        owner customised keeps its value, because undoing his deliberate minute of work is worse
        than a change that does not reach everywhere."""
        tree = await self.load(tenant)
        tree.general.update(_clean(values))
        await self._save(tree)
        return tree

    async def set_group(self, tenant: str, group: str, values: dict[str, Any],
                        service_ids: list[str] | None = None) -> EarnTree:
        tree = await self.load(tenant)
        current = dict(tree.groups.get(group) or {})
        current.update(_clean(values))
        tree.groups[group] = current
        for sid in service_ids or []:
            tree.service_group[sid] = group
        await self._save(tree)
        return tree

    async def set_service(self, tenant: str, service_id: str, values: dict[str, Any]) -> EarnTree:
        tree = await self.load(tenant)
        current = dict(tree.services.get(service_id) or {})
        current.update(_clean(values))
        tree.services[service_id] = current
        await self._save(tree)
        return tree

    async def set_package(self, tenant: str, package_id: str, points: int) -> EarnTree:
        """Set a package's own, always-explicit point value — no inheriting, no "follow again":
        a package has no group and no general rate to fall back to (see EarnTree.packages' own
        docstring), so unlike `set_service` there is nothing here but the number itself."""
        if points < 0:
            raise LoyaltyError("النقاط لا تكون سالبة — الزيارة لا تكلّف العميل شيئاً")
        tree = await self.load(tenant)
        tree.packages[package_id] = {"points": int(points)}
        await self._save(tree)
        return tree

    async def remove_package(self, tenant: str, package_id: str) -> EarnTree:
        """Called when a package is deactivated/deleted from operations, so a stale point value
        does not linger for an id nobody can create a visit against any more."""
        tree = await self.load(tenant)
        tree.packages.pop(package_id, None)
        await self._save(tree)
        return tree

    async def follow_again(self, tenant: str, service_id: str) -> EarnTree:
        """Drop a service's own value so it follows again.

        DELETES rather than writing today's general value into it. Writing it would look identical
        now and diverge later: the service would have stopped following, and the NEXT general edit
        would skip it — a bug appearing a month later with nothing connecting it to this button.
        """
        tree = await self.load(tenant)
        tree.services.pop(service_id, None)
        await self._save(tree)
        return tree

    async def set_config(self, tenant: str, **kw: Any) -> EarnTree:
        """Set the earning MODE. Validated here so an invalid combination cannot be stored at all."""
        tree = await self.load(tenant)
        cfg = tree.config
        if "mode" in kw:
            cfg.mode = str(kw["mode"])
        if "points_per_riyal" in kw:
            cfg.points_per_riyal = int(kw["points_per_riyal"])
        if "integrated" in kw:
            cfg.integrated = bool(kw["integrated"])
        cfg.validate()
        tree.config = cfg
        await self._save(tree)
        return tree


def _clean(values: dict[str, Any]) -> dict[str, Any]:
    """Keep only the fields this system knows about.

    An unknown key would be stored, never read, and look like a setting that does nothing — the
    same shape as a typo'd env key that pydantic silently drops. Rejected here, where it is one
    line, rather than discovered later as a support question nobody can reproduce.
    """
    out: dict[str, Any] = {}
    for k, v in (values or {}).items():
        if k not in FIELDS:
            continue
        if k == "points":
            v = int(v)
            if v < 0:
                raise LoyaltyError("النقاط لا تكون سالبة — الزيارة لا تكلّف العميل شيئاً")
        out[k] = v
    return out
