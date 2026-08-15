"""Three levels of setting, and the owner never chooses between them (spec §10.8.1).

THE PROBLEM ON DAY ONE. An establishment with twenty services has a cycle, a lead time and a
follow-up window for each — sixty decisions before a single message goes out. That is an owner who
closes the tab. So everything starts from ONE general setting that already works, and a service
gets its own value only when the owner deliberately changes that service.

THEY ARE NEVER ASKED WHICH LEVEL THEY WANT. There is no mode selector, no "advanced" tab, no
concept to learn. They edit a service; it becomes an override; a sentence appears next to it saying
so and offering the way back. The levels exist and the owner discovers them by working.

INHERIT, NEVER COPY — and this is the decision the whole file turns on.

Copying the general values into each service at creation is the obvious implementation. It is also
the one that fails silently: the owner edits the general setting a month later, twenty services
keep their copied values, nothing changes, and they conclude the feature is broken. Nothing errors,
nothing is logged, and the next thing they do is stop trusting the settings screen.

So a service stores ONLY what it overrides. An absent field means "follow", and following is not a
value — it is the absence of one. That is what makes a general edit reach twenty services at once
while leaving the one the owner customised exactly as they left it.

WHY A GENERAL EDIT MUST NOT ERASE A DELIBERATE CHOICE. It is tempting to make "set general" reset
everything for consistency. But an owner who spent a minute setting the oil change to 60 days and
then adjusts a general default has not asked us to undo that minute — and a system that quietly
undoes deliberate work is one nobody adjusts twice.

EVERY EFFECTIVE VALUE CARRIES ITS SOURCE. Not decoration: the screen cannot say "this one is
customised — tap to go back" unless the API says where the number came from. A resolver that
returned only the number would force the console to re-derive the answer, and the two would
disagree the first time this file changed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SETTINGS = "reminder_settings"

# The fields an owner can set at any level. Deliberately short: every one added here is another
# decision somebody can be asked to make, and the whole point is that they are not asked.
FIELDS = ("interval_days", "lead_days", "follow_up_days", "enabled")

GENERAL = "_general"


@dataclass(frozen=True)
class Resolved:
    """One effective value and where it came from."""
    value: Any
    # "general", "group:<name>", "service", or "default" — the platform's own fallback when the
    # tenant has set nothing at all. Four sources, and the screen renders three of them the same:
    # only "service" produces the "customised" note.
    source: str

    @property
    def is_override(self) -> bool:
        return self.source == "service"


@dataclass
class SettingsTree:
    """A tenant's whole settings picture, resolved once and read many times.

    Built from three rows rather than queried per field: the tick resolves settings for every
    service of every tenant, and a datastore round trip per field would turn one read into sixty.
    """
    tenant: str
    general: dict[str, Any] = field(default_factory=dict)
    # group name -> its settings, and service id -> group name. Two maps rather than a nested
    # structure, because a service moving between groups is then one write instead of two.
    groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    service_group: dict[str, str] = field(default_factory=dict)
    services: dict[str, dict[str, Any]] = field(default_factory=dict)
    # The platform's fallback — what a tenant who has set nothing at all gets. Passed in rather
    # than imported so this file stays pure and testable.
    defaults: dict[str, Any] = field(default_factory=dict)

    def resolve(self, service_id: str, field_name: str) -> Resolved:
        """The effective value for one field of one service, and its source.

        Order: the service's own value, then its group's, then the tenant's general, then the
        platform default. The FIRST level that has the field wins — and "has" means the key is
        present, not that it is truthy: `enabled: False` is a decision, and treating it as absent
        would silently re-enable something the owner switched off.
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

    def resolve_all(self, service_id: str) -> dict[str, Resolved]:
        return {f: self.resolve(service_id, f) for f in FIELDS}

    def effective(self, service_id: str) -> dict[str, Any]:
        """Just the values, for the engine that does not care where they came from."""
        return {f: r.value for f, r in self.resolve_all(service_id).items()}


    def is_customised(self, service_id: str) -> bool:
        """Whether this service has ANY value of its own — what the screen's note depends on."""
        return bool(self.services.get(service_id))


class SettingsStore:
    """Reads and writes the three levels. One row per tenant holds all of it.

    ONE ROW, not three collections. The whole tree is small — a general dict, a handful of groups,
    and the services the owner actually touched — and it is always read as a unit. Splitting it
    would make the tick do three reads per tenant to answer one question.
    """

    def __init__(self, store, *, defaults: dict[str, Any] | None = None) -> None:
        self._s = store
        self._defaults = defaults or {}

    async def load(self, tenant: str) -> SettingsTree:
        row = await self._s.get(SETTINGS, f"{tenant}|settings") or {}
        return SettingsTree(
            tenant=tenant,
            general=dict(row.get("general") or {}),
            groups=dict(row.get("groups") or {}),
            service_group=dict(row.get("service_group") or {}),
            services=dict(row.get("services") or {}),
            defaults=dict(self._defaults))

    async def _save(self, tree: SettingsTree) -> None:
        await self._s.put(SETTINGS, f"{tree.tenant}|settings", {
            "id": f"{tree.tenant}|settings", "tenant": tree.tenant,
            "general": tree.general, "groups": tree.groups,
            "service_group": tree.service_group, "services": tree.services})

    async def set_general(self, tenant: str, values: dict[str, Any]) -> SettingsTree:
        """Change the tenant-wide setting.

        REACHES EVERY FOLLOWER AND NOTHING ELSE. A service the owner customised keeps its value —
        see the module docstring for why undoing their minute of work is worse than a change that
        does not reach everywhere.
        """
        tree = await self.load(tenant)
        tree.general.update(_clean(values))
        await self._save(tree)
        return tree

    async def set_service(self, tenant: str, service_id: str,
                          values: dict[str, Any]) -> SettingsTree:
        """Give one service its own values. This is what "customising" means, and it is the only
        way a service stops following."""
        tree = await self.load(tenant)
        current = dict(tree.services.get(service_id) or {})
        current.update(_clean(values))
        tree.services[service_id] = current
        await self._save(tree)
        return tree

    async def follow_again(self, tenant: str, service_id: str,
                           fields: list[str] | None = None) -> SettingsTree:
        """Drop a service's own values so it follows again — the "tap to go back" the note offers.

        DELETES rather than writing the general value into it. Writing the current general value
        would look identical today and diverge tomorrow: the service would stop following, and the
        NEXT general edit would skip it. The bug would appear a month later, in a different
        session, with nothing connecting it to this button.
        """
        tree = await self.load(tenant)
        own = dict(tree.services.get(service_id) or {})
        if fields is None:
            tree.services.pop(service_id, None)
        else:
            for f in fields:
                own.pop(f, None)
            if own:
                tree.services[service_id] = own
            else:
                tree.services.pop(service_id, None)
        await self._save(tree)
        return tree

    async def set_group(self, tenant: str, group: str, values: dict[str, Any],
                        service_ids: list[str] | None = None) -> SettingsTree:
        """Create or update a group, and optionally put services in it.

        Groups arrive LATE and by suggestion (spec §10.8.1): when the owner has set the same value
        on five services we offer to group them. Nobody is asked to design a taxonomy up front.
        """
        tree = await self.load(tenant)
        current = dict(tree.groups.get(group) or {})
        current.update(_clean(values))
        tree.groups[group] = current
        for sid in service_ids or []:
            tree.service_group[sid] = group
        await self._save(tree)
        return tree

    async def leave_group(self, tenant: str, service_id: str) -> SettingsTree:
        """Take one service out of its group. It goes back to following general.

        THE OPPOSITE OF set_group HAD NO EXISTENCE, and the shape of the tree hid that: putting a
        service in a group is a write to `service_group`, and there is no value that means "not in
        one" — absence does. So the screen could offer «بلا مجموعة» in a dropdown and there was
        nothing behind it. Found by an owner trying to undo his own grouping.

        It does NOT touch the group's settings or its other members: leaving is about this service
        only. And it does not copy the group's values into the service on the way out, for the same
        reason `follow_again` deletes rather than writes — a frozen copy diverges silently.
        """
        tree = await self.load(tenant)
        tree.service_group.pop(service_id, None)
        await self._save(tree)
        return tree

    async def delete_group(self, tenant: str, group: str) -> SettingsTree:
        """Remove a group entirely; everything in it becomes ungrouped.

        MEMBERS ARE RELEASED, NEVER DELETED WITH IT. A group is a way of saying "these share a
        setting", so deleting it is deleting the sharing — not the services, and not any values a
        service holds of its own. Leaving members pointing at a group that no longer exists would
        be worse than either: `settingFor` would resolve through `groups[name]`, find nothing, and
        silently fall back to general — a service quietly changing behaviour with nothing on any
        screen to explain it.
        """
        tree = await self.load(tenant)
        tree.groups.pop(group, None)
        for sid in [s for s, g in tree.service_group.items() if g == group]:
            tree.service_group.pop(sid, None)
        await self._save(tree)
        return tree

    async def suggest_group(self, tenant: str, *, minimum: int = 3) -> dict[str, Any] | None:
        """Is the owner repeating themselves? — the only place a group is ever proposed.

        Returns the field, the value and the services sharing it when enough of them do. Read-only:
        it proposes, and the owner decides. Acting on it automatically would be a system rearranging
        their settings without being asked, which is the fastest way to lose their trust in a
        screen.
        """
        tree = await self.load(tenant)
        counts: dict[tuple[str, Any], list[str]] = {}
        for sid, values in tree.services.items():
            # Only ungrouped services: proposing a group for services already in one is proposing
            # to reorganise, not to simplify.
            if tree.service_group.get(sid):
                continue
            for f, v in values.items():
                if isinstance(v, (dict, list)):
                    continue
                counts.setdefault((f, v), []).append(sid)
        best = max(counts.items(), key=lambda kv: len(kv[1]), default=None)
        if best is None or len(best[1]) < minimum:
            return None
        (field_name, value), ids = best
        return {"field": field_name, "value": value, "services": sorted(ids)}


def _clean(values: dict[str, Any], *, allow: tuple[str, ...] = ()) -> dict[str, Any]:
    """Keep only the fields this system knows about.

    An unknown key would be stored, never read, and would look like a setting that does nothing —
    which is the same shape as DEFAULT_LOCALE sitting unread in eighteen values files. Dropped
    here, where it is one line, rather than discovered later as a support question.
    """
    return {k: v for k, v in (values or {}).items() if k in FIELDS or k in allow}
