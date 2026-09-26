"""The first "جماعي" mechanic — a SHARED counter, fixed at creation, that reveals its whole earned
cohort together the moment it crosses its threshold, rather than matching customers one at a time.

WHY THIS IS A SEPARATE FILE, NOT A BRANCH IN `audience.py`. `audience.py`'s entire contract is one
row, matched independently, against a predicate that only ever reads THAT row's own facts (its own
last visit, its own join date). A milestone campaign's answer to "who does this reach" depends on
EVERY OTHER customer who has also contributed — the opposite shape. Squeezing it into `_MATCHERS`
would mean `audience.resolve()` learning about state that lives nowhere near a customer row; keeping
it here means the individual mechanic's file stays exactly what its own docstring already promises,
and this one is free to have a genuinely different contract.

FIXED THRESHOLD ONLY, DELIBERATELY (v1, 2026-09-27) — no rolling window, no re-arming, no dynamic
target. A milestone campaign counts from the moment it is created until its own threshold is
crossed, fires ONCE, and is done — the same one-shot shape a `scheduled` campaign already has, just
triggered by a count instead of a clock. A shop that wants another round creates a new campaign;
teaching this one to reset itself is a real, separate feature this file does not build by guessing
what "reset" should mean (calendar week? rolling 7 days? manual re-arm?).

THE COUNTER IS LOAD-BEARING, NOT A DISPLAY NUMBER — unlike `goal_stats.py`'s own `uses`/`reach`
(cosmetic; a lock failure there is swallowed on purpose, `dispatch.py::Dispatcher._save`'s own
comment says why). Losing an increment here is losing someone's real contribution toward a promise
made in the shop's name, so `_bump`'s own mutex failure RAISES here exactly like `goal_stats.py`'s
does — the difference is this counter's own caller (a future visit-recorded hook) must retry it,
never swallow the failure.

ONCE FIRED, THE COUNTER FREEZES — `record_contribution` is a no-op past that moment (a contribution
that arrives after the reveal joins nothing; the shop's promise was already kept to a fixed list).
`resolve_milestone` itself is idempotent and resumable exactly the way every other goal's dispatch
already is: it always returns the FULL earned cohort minus whoever `already_reached` already covers
— `Dispatcher.fire()`'s own per-pass/`already_reached` machinery does the rest, unchanged. Nothing
here invents a second "have we sent this" ledger.

THE GATE STILL APPLIES. A customer who opted out of marketing, or is on a stopped class, must not
receive a milestone blast either — `resolve_milestone` calls the SAME `gate_check` peer
`core/audience.py::resolve` already calls, exposed on the container's own `_AudienceFacade`
(`gate_check`), never a second, disagreeing compliance path.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

from app.core.audience import Audience, Candidate

MILESTONE_PROGRESS = "campaign_milestone_progress"

# SEPARATE FROM THE ROW IT GUARDS — same reasoning as `goal_stats.py`'s own `_MUTEX_COLLECTION`:
# the mutex must be claimable/expirable on its own terms, not entangled with the value it protects.
_MUTEX_COLLECTION = "campaign_milestone_progress_mutex"
_MUTEX_TTL_SECONDS = 5.0
# A MUCH DEEPER RETRY BUDGET THAN `goal_stats.py`'s OWN 5×50ms, DELIBERATELY. That counter is
# bumped by at most a couple of concurrent callers in practice; THIS one exists specifically to
# absorb a genuine burst — a real shop's "100 سيارة هذا الأسبوع" milestone can plausibly see dozens
# of visits recorded within the same few seconds.
#
# THE REAL BUG THIS MODULE'S OWN STRESS TEST FOUND: with a FIXED retry delay, every losing caller
# wakes up at the same instant and only ONE of them can win the claim per round — the critical
# section's own length barely matters, because throughput is bounded by "one winner per retry
# interval", not by how fast the work actually is. `goal_stats.py`'s 5×50ms was never really an
# issue there because it only ever contends with one other caller; 50 genuinely concurrent
# contributions need up to 50 WINNING ROUNDS, not 50 attempts total, and the original delay copied
# from `goal_stats.py` raised a false "lock lost" alarm at that scale, not a real one. Shortening
# the delay (so many more rounds fit in the same wall-clock budget) fixes the actual bottleneck;
# widening the delay would not have.
_MUTEX_RETRY_ATTEMPTS = 150
_MUTEX_RETRY_DELAY_SECONDS = 0.01


@dataclass
class MilestoneProgress:
    tenant: str
    campaign_id: str
    threshold: int
    count: int = 0
    # ONE ENTRY PER CONTRIBUTION, NOT PER CUSTOMER — a customer contributing twice (two visits) is
    # counted twice toward the threshold, exactly like the owner's own "100 سيارة" example (a car
    # that comes back twice is two washes, not one). The reveal cohort (`resolve_milestone`) dedupes
    # this list; the counter itself never does.
    contributor_refs: list[str] = field(default_factory=list)
    fired: bool = False
    fired_at: int = 0

    @property
    def key(self) -> str:
        return f"{self.tenant}|{self.campaign_id}"


def _row_to_progress(row: dict[str, Any], *, tenant: str, campaign_id: str) -> MilestoneProgress:
    return MilestoneProgress(
        tenant=tenant, campaign_id=campaign_id,
        threshold=int(row.get("threshold") or 0),
        count=int(row.get("count") or 0),
        contributor_refs=list(row.get("contributor_refs") or []),
        fired=bool(row.get("fired") or False),
        fired_at=int(row.get("fired_at") or 0),
    )


def _progress_row(progress: MilestoneProgress) -> dict[str, Any]:
    return {"tenant": progress.tenant, "campaign_id": progress.campaign_id,
            "threshold": progress.threshold, "count": progress.count,
            "contributor_refs": progress.contributor_refs,
            "fired": progress.fired, "fired_at": progress.fired_at}


async def read_progress(store: Any, tenant: str, campaign_id: str) -> MilestoneProgress | None:
    """The current count/cohort/fired state, or `None` for a campaign never contributed to yet —
    a single-key read, never a scan, same shape `goal_stats.read_goal_stats` already uses."""
    if not tenant or not campaign_id:
        return None
    row = await store.get(MILESTONE_PROGRESS, f"{tenant}|{campaign_id}")
    if not row:
        return None
    return _row_to_progress(row, tenant=tenant, campaign_id=campaign_id)


async def record_contribution(store: Any, *, tenant: str, campaign_id: str, threshold: int,
                              subject_ref: str, now: int | None = None) -> MilestoneProgress:
    """One more event toward this campaign's shared goal — a real visit, a real sale, whatever the
    caller decides counts. `threshold` is passed in rather than re-read from a "campaigns" row
    here, on purpose: this file must not learn that collection's shape, or it would drift the day
    that shape changes for a reason that has nothing to do with counting. The one caller that
    matters (a future visit-recorded hook) reads the campaign once and passes its own
    `Campaign.milestone_threshold` straight through.

    SAFE TO CALL BLINDLY, EVERY TIME, FOR THE LIFE OF THE SHOP — a no-op once fired (see this
    module's own docstring on why the counter freezes), and a no-op for an empty `subject_ref` or
    `campaign_id` too, the same "nothing to count" answer `goal_stats.py`'s own `_bump` gives an
    empty goal: a caller passing nothing must not corrupt a real count with a phantom contribution.

    RAISES IF THE LOCK CANNOT BE CLAIMED — unlike `goal_stats.py`'s own best-effort choice. See
    this module's own docstring on why this counter is load-bearing rather than cosmetic.
    """
    if not subject_ref or not campaign_id or not tenant:
        existing = await read_progress(store, tenant, campaign_id)
        return existing or MilestoneProgress(tenant=tenant, campaign_id=campaign_id,
                                             threshold=threshold)

    when = now if now is not None else int(time.time())
    mutex_key = f"{tenant}|{campaign_id}"
    held = False
    for _ in range(_MUTEX_RETRY_ATTEMPTS):
        held = await store.claim(_MUTEX_COLLECTION, mutex_key, {"held": True},
                                 ttl_seconds=_MUTEX_TTL_SECONDS, now=time.time())
        if held:
            break
        await asyncio.sleep(_MUTEX_RETRY_DELAY_SECONDS)
    if not held:
        raise RuntimeError(f"could not claim milestone-progress lock for {tenant}/{campaign_id}")
    try:
        row = await store.get(MILESTONE_PROGRESS, mutex_key)
        progress = (_row_to_progress(row, tenant=tenant, campaign_id=campaign_id) if row
                   else MilestoneProgress(tenant=tenant, campaign_id=campaign_id,
                                         threshold=threshold))
        if progress.fired:
            # THE COUNTER IS FROZEN. Returned as-is — not an error, not a partial update; the
            # milestone already resolved and this contribution simply arrived too late to count.
            return progress
        progress.count += 1
        progress.contributor_refs.append(subject_ref)
        if progress.count >= progress.threshold > 0:
            progress.fired = True
            progress.fired_at = when
        await store.put(MILESTONE_PROGRESS, mutex_key, _progress_row(progress))
        return progress
    finally:
        await store.delete(_MUTEX_COLLECTION, mutex_key)


def contribution_matches(campaign: dict[str, Any], *, service_id: str = "",
                         package_id: str = "") -> bool:
    """Does THIS real event count toward THIS campaign's shared goal?

    THE SAME SCOPE FIELDS THE "فردي" MECHANIC ALREADY USES — `Campaign.service_id`/
    `scope_service_ids`/`package_id` — reused verbatim rather than inventing a second, parallel
    scoping vocabulary for the "جماعي" mechanic. The campaign's own creator decides, at creation,
    whether the shared goal counts EVERY visit, visits of one or more SPECIFIC SERVICES, or visits
    of a specific PACKAGE — exactly the choice `service_offer`/`package_offer` already offer, just
    read here to gate a contribution instead of an audience match.

    NO SCOPE SET AT ALL (every field empty) MEANS EVERY REAL EVENT COUNTS — the "100 سيارة"
    example the owner's own idea was built around: any visit, of any kind. This is the default a
    campaign gets by simply not touching these fields, the same "untouched means unscoped"
    convention `Campaign.branch_id`'s own docstring already uses.

    PACKAGE TAKES PRIORITY OVER SERVICE IDS IF BOTH SOMEHOW GOT SET — the same "a campaign is
    about one or the other, never both" rule `Campaign.package_id`'s own docstring states for the
    individual mechanic; this function does not invent a third meaning for the combination.
    """
    campaign_package = str(campaign.get("package_id") or "")
    if campaign_package:
        return package_id == campaign_package

    scope_ids = list(campaign.get("scope_service_ids") or [])
    single = str(campaign.get("service_id") or "")
    ids = list(dict.fromkeys(scope_ids + ([single] if single else [])))
    if not ids:
        # NO SCOPE AT ALL — every real event counts, regardless of what (if anything) the caller
        # passed for `service_id`/`package_id`.
        return True
    return bool(service_id) and service_id in ids


def _event_matches(campaign: dict[str, Any], *, service_ids: list[str] | None,
                   package_id: str) -> bool:
    """One real event can carry SEVERAL services at once (a visit's own `service_ids` list) — it
    counts toward a scoped campaign if ANY ONE of them is in scope, the same "ready for even one
    is ready for the campaign" reasoning `audience.resolve`'s own cycle-lock note gives the
    individual mechanic for a multi-service offer."""
    if not service_ids:
        return contribution_matches(campaign, package_id=package_id)
    return any(contribution_matches(campaign, service_id=sid, package_id=package_id)
              for sid in service_ids)


async def contribute_from_event(store: Any, *, tenant: str, subject_ref: str,
                                service_ids: list[str] | None = None, package_id: str = "",
                                now: int | None = None) -> list[MilestoneProgress]:
    """The ONE entry point a peer service calls, once per real event — never once per campaign.
    Fans out to every active `community_milestone` campaign this tenant holds, counting the event
    toward whichever ones it matches (`_event_matches`) and leaving the rest untouched.

    WHY THIS LIVES HERE, NOT IN THE CALLER. The caller (operations' own `record_visit`, the single
    point-of-sale every channel — the field screen, an integrated till, bookings — already goes
    through) must not learn this service's own scoping rules or its "campaigns" collection's
    shape; it reports one plain fact ("this event happened, for this tenant, these services/this
    package") and this file decides what, if anything, it counts toward. The same boundary
    `core/service_due_settings.py`'s own peer client already draws for reminders.

    BOUNDED, LIKE EVERY OTHER SCAN IN THIS SERVICE — `drain()` refuses rather than silently
    truncating a tenant with an unusually large number of active milestone campaigns, the same
    discipline `tick.py`'s own `_active_tenants` already follows.

    FAILURES OF ONE CAMPAIGN'S OWN CONTRIBUTION MUST NOT COST ANOTHER'S — a lock-claim failure on
    one campaign (see `record_contribution`'s own docstring on why THAT raises) must not stop the
    same real event from still being counted toward every other campaign it also matches.
    """
    from app.adapters.datastore.drain import drain

    if not tenant or not subject_ref:
        return []
    rows = await drain(store, "campaigns",
                       {"tenant": tenant, "state": "active", "goal": "community_milestone"},
                       sort=("created", "asc"))
    out: list[MilestoneProgress] = []
    for row in rows:
        if not _event_matches(row, service_ids=service_ids, package_id=package_id):
            continue
        threshold = int(row.get("milestone_threshold") or 0)
        cid = str(row.get("id") or "")
        try:
            progress = await record_contribution(store, tenant=tenant, campaign_id=cid,
                                                 threshold=threshold, subject_ref=subject_ref,
                                                 now=now)
        except RuntimeError:
            # ONE CAMPAIGN'S LOCK CONTENTION MUST NOT COST THE OTHERS — see this function's own
            # docstring. The caller (operations' own visit hook) already swallows ITS OWN
            # failure to reach this endpoint at all; this is the same posture one level in.
            continue
        out.append(progress)
    return out


async def resolve_milestone(campaign: dict[str, Any], *, already_reached, now: int,
                            audience: Any = None, store: Any = None) -> Audience:
    """The "جماعي" mechanic's own resolver — same signature every mechanic in
    `core/mechanics.py::MECHANIC_RESOLVERS` implements, so `Dispatcher.fire()` (core/dispatch.py)
    never has to know this campaign's audience isn't matched the ordinary way.

    ALWAYS THE FULL EARNED COHORT, MINUS WHOEVER IS ALREADY REACHED — never gated on `fired` to
    decide whether to return anything ONLY that check: a pass that crashes partway through sending
    a hundred-person cohort must still see all hundred (minus however many `already_reached`
    already covers) on the next tick, the same "bounded per pass, and resumable" promise every
    other goal's dispatch already keeps. Before the threshold is crossed, this simply returns
    nobody — an ordinary, harmless no-op pass, exactly like a `win_back` tick that matched zero
    customers today.
    """
    out = Audience()
    tenant = campaign.get("tenant", "")
    cid = campaign.get("id", "")
    if store is None:
        return out
    progress = await read_progress(store, tenant, cid)
    if progress is None or not progress.fired:
        return out

    reached = already_reached or set()
    cls = str(campaign.get("cls") or "marketing")
    seen: set[str] = set()
    for subject in progress.contributor_refs:
        if not subject or subject in reached or subject in seen:
            continue
        seen.add(subject)
        if audience is not None and hasattr(audience, "gate_check"):
            if not await audience.gate_check(tenant, subject, cls):
                # MATCHED BUT WOULD BE REFUSED — counted, not hidden, the same "the preview says
                # the honest number" discipline `core/audience.py::resolve` already documents.
                out.excluded += 1
                continue
        out.candidates.append(Candidate(
            subject_ref=subject,
            why=f"من ضمن أول {progress.threshold} ساهموا بالهدف الجماعي"))
    return out
