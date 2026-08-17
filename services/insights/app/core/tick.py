"""The daily sweep that makes the dashboard instant (spec §10.6.1).

WITHOUT ITS CRON THIS SERVICE IS INERT AND LOOKS HEALTHY — every probe green, every route
answering, and every dashboard empty. That is playbook trap §4.1, and it is why the schedule is
declared beside the endpoint in the manifest rather than left to whoever deploys.

BOUNDED AND RESUMABLE, like every other tick here. A fixed number of tenants per pass, a watermark,
and a report of what remains. The alternative is a run that grows with the product until it times
out, retries from the beginning, and never finishes again — a failure that arrives months after the
decision that caused it.

ONE TENANT'S FAILURE MUST NOT STOP THE SWEEP. Each is its own try. A shop whose peer call times out
is recorded and the next one runs; the alternative is one bad tenant freezing the dashboards of
everybody who comes after it alphabetically.

AND THE PANEL NEVER SHOWS A BLANK BECAUSE THIS HAS NOT RUN. A tenant with no snapshot yet gets
"أحسب الآن" and the time of the next pass. An empty dashboard reads as broken, and an owner who
concludes that on day one does not come back on day two.
"""
from __future__ import annotations

from typing import Any

from app.core import associations, indicators
from app.core.coverage import group_by
from app.core.models import (PAIRS, SEQUENCES, SNAPSHOTS, CustomerSequence, Snapshot,
                             VisitPage)


class Tick:
    def __init__(self, store: Any, peers: Any, *, batch: int = 50,
                 visit_limit: int = 5000,
                 telemetry: Any = None,
                 thresholds: associations.Thresholds | None = None,
                 reserve_weeks: int = 8, reserve_percentile: float = 0.95,
                 reserve_floor: int = 20, holdout_enabled: bool = False,
                 holdout_share: int = 10) -> None:
        self.store = store
        self.peers = peers
        self.batch = batch
        # THE CAP THE OPERATOR CAN ACTUALLY MOVE. `SNAPSHOT_VISIT_LIMIT` sat in the values file
        # looking like a knob while the real bound was a DEFAULT ARGUMENT on `peers.visits()` —
        # so raising it in a deploy changed nothing at all, and the number an operator read was
        # not the number the run obeyed. One authority, passed from the settings, or none.
        self.visit_limit = visit_limit
        self.telemetry = telemetry
        # WHETHER ANYONE IS ACTUALLY WITHHELD FROM — `reminders` decides it; we only measure. False
        # means the control-group card must refuse rather than compare two groups that both
        # received every message.
        self._holdout_enabled = bool(holdout_enabled)
        self._holdout_share = int(holdout_share)
        # WHERE EVIDENCE BECOMES ADVICE. A workshop's baskets are not a café's, and the lift that
        # means something in one is noise in the other — so the four numbers are settings, and the
        # defaults here are only what an unconfigured deployment gets.
        self.thresholds = thresholds or associations.DEFAULTS
        # The reserve's own three judgements. Defaults live in indicators.engine_reserve; these
        # are what the deployment chose, and a new shop's floor is the one that matters most —
        # it is the fortnight when a dropped confirmation does the most damage.
        self._reserve_weeks = reserve_weeks
        self._reserve_percentile = reserve_percentile
        self._reserve_floor = reserve_floor

    async def run(self, *, now: int, tenants: list[str], since: int = 0) -> dict:
        done: list[str] = []
        failed: list[dict] = []
        for tenant in tenants[: self.batch]:
            try:
                await self.compute(tenant, now=now, since=since)
                done.append(tenant)
            except Exception as exc:                                    # noqa: BLE001
                # Recorded, not raised. See the module docstring: one shop must not freeze the rest.
                failed.append({"tenant": tenant, "error": str(exc)[:200]})
                if self.telemetry:
                    self.telemetry.event("insights_tenant_failed", tenant=tenant,
                                         error=str(exc)[:200])
        return {"computed": len(done), "failed": failed,
                "more": len(tenants) > self.batch, "seen": min(len(tenants), self.batch)}

    async def compute(self, tenant: str, *, now: int, since: int = 0) -> Snapshot:
        """One tenant's dashboard, plus one per branch (spec §10.6.4).

        THE BRANCH SNAPSHOTS ARE COMPUTED HERE, NOT FILTERED AT READ TIME. Filtering a stored
        aggregate is not possible — a return rate over three branches cannot be split back into
        three — so each scope is its own computation over its own visits. The alternative was a
        panel that quietly showed the whole shop's numbers under a branch's name.
        """
        visits = await self.peers.visits(tenant, since=since, limit=self.visit_limit)
        catalogue = await self.peers.catalogue(tenant)
        # THE SEND LOG, ONCE PER TENANT. Read here rather than inside _compute_scope: a branch
        # snapshot would otherwise re-fetch the whole shop's messages for every branch.
        #
        # THE LOG NOW CARRIES A BRANCH and this read still does not use it — deliberately, and
        # worth saying so. `/internal/reminders/effect` answers (customer, when, class) and nothing
        # else, because the two indicators built on it — visits credited to a message, and stops
        # per thousand — are properties of the SHOP. Per-branch effect is a question we can now
        # ask; it needs the peer to carry the field and both indicators to be scoped, and pulling
        # the branch through here without doing that would split the denominator and leave the
        # numerator whole.
        # ASKED FOR, NOT DEMANDED. A peers driver without this method is an older reminders behind
        # a rolling deploy — insights rolls first — and two indicators rendering «not yet» for an
        # hour is the right cost. Crashing the whole snapshot pass over it is not.
        #
        # AND «WE DID NOT READ IT» IS CARRIED, NOT COLLAPSED INTO AN EMPTY LIST (ي-3). `{}` here,
        # and `{"sends": [], "sent_count": 0}` from a failed peer read, are indistinguishable from
        # a shop that genuinely sent nothing — so the two indicators built on this used to publish
        # a confident 0 whenever reminders was slow. `ok` is the peer stating it actually read the
        # log; anything that does not say so is unknown, and unknown is not zero.
        #
        # `truncated` IS THE PEER'S OWN WORD FOR «THIS IS A SLICE» (ي-6). reminders exports it on
        # every answer and it used to be dropped here, so a shop past the send-log cap had both
        # its numbers computed over an unnamed sample and neither of them said so. Both flags
        # travel inside `effect` and are read in `_compute_scope` beside the indicators that use
        # them.
        read = getattr(self.peers, "effect", None)
        effect = await read(tenant, since=now - 90 * 86400) if read else {}
        # THE NAMES, ONCE PER TENANT AND CARRIED INTO THE SNAPSHOT. The branch table is grouped by
        # the id on each visit and this service holds no places of its own, so without this every
        # row rendered «بلا اسم». Resolved at COMPUTE time rather than at read time: a dashboard
        # request must not fan out to another service to print a label.
        # ASKED FOR, NOT DEMANDED — a peers driver without it is an older deploy, and a table of
        # ids is a worse table, not a broken snapshot.
        ask = getattr(self.peers, "branches", None)
        branch_names = {str(b.get("id") or ""): str(b.get("name") or "")
                        for b in (await ask(tenant) if ask else [])}
        snap = await self._compute_scope(tenant, visits, catalogue, now=now, branch_id="",
                                         effect=effect, branch_names=branch_names)

        branches = sorted({str(v.get("branch_id") or "") for v in visits if v.get("branch_id")})
        # ONLY FOR A SHOP WITH MORE THAN ONE. A single-branch establishment gets no branch
        # snapshots and no switch — "filter by your only branch" is a control that does nothing
        # and a question the owner has to think about (spec §10.6.4).
        if len(branches) > 1:
            for b in branches:
                # THE BRANCH INHERITS THE SHOP'S TRUNCATION. Filtering makes a plain list, and a
                # branch computed from a partial history is exactly as partial as the shop it was
                # filtered out of — a flag that survived the whole read and died in a list
                # comprehension would be the same defect wearing a smaller scope.
                scoped = VisitPage(v for v in visits
                                   if str(v.get("branch_id") or "") == b)
                scoped.truncated = bool(getattr(visits, "truncated", False))
                await self._compute_scope(tenant, scoped, catalogue, now=now, branch_id=b,
                                          effect=effect, branch_names=branch_names)
        return snap

    async def _compute_scope(self, tenant: str, visits: list[dict], catalogue: list[dict],
                             *, now: int, branch_id: str,
                             effect: dict[str, Any] | None = None,
                             branch_names: dict[str, str] | None = None) -> Snapshot:
        cycles = {s.get("id", ""): int(s.get("cycle_days") or 0) for s in catalogue}
        names = {s.get("id", ""): s.get("name", "") for s in catalogue}

        eff = effect or {}
        # DID WE ACTUALLY READ THE SEND LOG? The peer sets `ok` only on a read that succeeded; a
        # failure, and a driver with no `effect` method at all, both arrive here without it. That
        # distinction is the whole of ي-3 — see `indicators.returned_after_reminder`.
        have_log = bool(eff.get("ok"))
        partial_log = bool(eff.get("truncated"))

        values: dict[str, Any] = {
            "return_rate": indicators.return_rate(visits),
            # THE SAME NUMBER AS A LINE. Computed beside its own snapshot rather than in a second
            # job: one read of `visits`, one clock, and no chance of the headline figure and the
            # last point of the trend disagreeing — which is exactly the bug an owner screenshots.
            "retention_series": indicators.retention_series(visits, now=now),
            # AND WHAT THE ENGINE DID — measured against the tenth of his customers it leaves
            # alone. Tenant-scoped because the group is: the same person at two shops is not in
            # both holdouts, or a low-hashing customer would be under-served platform-wide.
            "holdout_comparison": indicators.holdout_comparison(
                visits, tenant=tenant, now=now, enabled=self._holdout_enabled,
                share=self._holdout_share),
            # WHAT THE MESSAGES ACTUALLY MOVED, in the only unit we hold: visits. No prices live in
            # this product, so «هل سدّدت الباقة نفسها» stays his arithmetic — we hand him the
            # count and he multiplies by an average bill only he knows.
            "returned_after_reminder": indicators.returned_after_reminder(
                visits, eff.get("sends") or [], now=now,
                have_log=have_log, partial_log=partial_log),
            # AND WHAT THEY COST. Stops per thousand messages: the signal that precedes a blocked
            # number, which loses the channel rather than a message.
            "opt_out_rate": indicators.opt_out_rate(
                int(eff.get("sent_count") or 0), int(eff.get("opt_outs") or 0),
                have_log=have_log, partial_log=partial_log),
            "return_cycle_days": indicators.return_cycle_days(visits),
            # THE WEEK, AND THE WEEK BEFORE IT — what «أسبوعك» is a report about (ي-2). Computed
            # here rather than in the digest so the report and the panel cannot describe two
            # different periods with one word.
            "visits_week": indicators.visits_in_window(visits, now=now),
            "churn_rate": indicators.churn_rate(visits, now=now),
            "active_customers": indicators.active_customers(visits, now=now),
            "new_vs_returning": indicators.new_vs_returning(visits, now=now),
            "service_popularity": indicators.service_popularity(visits),
            "services_per_visit": indicators.services_per_visit(visits),
            "peak_map": indicators.peak_map(visits),
            "expected_flow": indicators.expected_flow(visits, now=now),
            # HOW MUCH OF TODAY'S SENDING CEILING THE ENGINE NEEDS (spec §8.4.3). Computed here
            # because the input — visits by weekday — is already in this snapshot, and computing
            # it anywhere else would mean a second counter of the same thing that drifts from it.
            #
            # The CEILING is not ours to know, so it is not applied here: this says how much the
            # shop's own traffic warrants, and whoever holds the ceiling caps it.
            "engine_reserve": indicators.engine_reserve(
                visits, now=now, weeks=self._reserve_weeks,
                percentile=self._reserve_percentile, floor=self._reserve_floor),
            "cycle_completion": indicators.cycle_completion(visits, cycles=cycles, now=now),
            "at_risk": indicators.at_risk(visits, now=now),
            "weak_services": indicators.weak_services(
                visits, catalogue=[s.get("id", "") for s in catalogue]),
            "service_names": names,
        }

        # ── the engine — THE WHOLE ESTABLISHMENT ONLY ─────────────────────────────────────────
        # Two reasons, and the second is a bug this nearly shipped with.
        #
        # A relationship between two services is a property of the SHOP, not of a branch: the same
        # oil and the same filter go together in Riyadh and in Jeddah, and splitting the evidence
        # three ways only makes each piece too small to pass the learning threshold.
        #
        # And `CustomerSequence` is keyed `{tenant}|{subject_ref}` with no branch in it — so
        # rebuilding it inside a branch scope would OVERWRITE a customer's whole history with the
        # part of it that happened at one branch. The engine would then read a person's Riyadh
        # visits as their entire life. Found by asking what `_rebuild_sequences` does on the
        # second pass.
        engine: dict[str, Any] = {"learning": True, "have": 0, "need": 0, "pairs": []}
        if not branch_id:
            # Sequences are rebuilt rather than incremented, because a corrected or erased visit
            # must DISAPPEAR from them — an incremented set can only grow, and a customer's
            # deleted history would live on in the thing we derived from it.
            sequences = await self._rebuild_sequences(tenant, visits, now=now)
            median = _median_basket(visits)
            baskets = [list(set(v.get("service_ids") or [])) for v in visits
                       if not associations.is_group_basket(
                           list(set(v.get("service_ids") or [])),
                           quantities=v.get("quantities") or {}, median_size=median)]

            # THE HABIT, not the history. See `CustomerSequence.repeated` — a one-off group
            # visit must not vouch for a relationship for ever.
            engine = associations.build(baskets=baskets,
                                        sequences=[s.repeated() for s in sequences],
                                        tenant=tenant, th=self.thresholds)
            values["associations"] = {"learning": engine["learning"],
                                      "have": engine["have"], "need": engine["need"],
                                      "pairs": [p.to_dict() for p in engine["pairs"]]}
            values["missed_opportunities"] = associations.missed_opportunities(
                engine["pairs"], {s.subject_ref: s.services for s in sequences})
            # NOTE: missed opportunities read the FULL history deliberately, unlike the engine.
            # "He has never taken the filter" is a fact about everything he has ever done, and
            # using the habit here would call a one-time purchase a gap.

        # The branch table, with its unspecified row and its ranking rule (spec §10.6.3). Computed
        # on the WHOLE establishment only: a branch's own snapshot comparing branches would be a
        # table of one row, which can never be ranked and says nothing.
        if not branch_id:
            table = group_by(visits, "branch_id")
            # THE ROW THE SCREEN ACTUALLY READS. `group_by` speaks in {key, count} because it also
            # groups operators; the branch table is rendered as a NAMED row with two numbers, and
            # the console read {branch_id, name, visits, customers} against the raw shape — so
            # every row showed «بلا اسم · 0 زيارة» while the guard above it happily passed. The
            # translation belongs here, at the one place that knows this grouping is branches.
            people: dict[str, set[str]] = {}
            for v in visits:
                b = str(v.get("branch_id") or "")
                ref = str(v.get("subject_ref") or "")
                if b and ref:
                    people.setdefault(b, set()).add(ref)
            names = branch_names or {}
            values["branch_rows"] = [
                # A NAME WE DO NOT HOLD STAYS EMPTY, never filled with the id: the screen says
                # «بلا اسم» honestly, and an id printed as a name is a name an owner will search
                # his own shop for.
                {"branch_id": r["key"], "name": names.get(r["key"], ""),
                 "visits": r["count"], "customers": len(people.get(r["key"], ()))}
                for r in table["rows"]]
            values["branch_unknown"] = table["unknown"]
            values["branch_can_rank"] = table["can_rank"]
            # For the switcher (§10.6.4): every branch with a snapshot, in the order of the table.
            values["branch_names"] = {r["key"]: names.get(r["key"], "")
                                      for r in table["rows"]}

        # `getattr`, BECAUSE AN OLDER PEERS DRIVER RETURNS A PLAIN LIST. Absent means «the cap did
        # not bite», which is what a driver that cannot truncate is in fact saying.
        snap = Snapshot(tenant=tenant, values=values, visits=len(visits), computed_at=now,
                        branch_id=branch_id, partial=bool(getattr(visits, "truncated", False)))
        snap.coverage = await self._coverage(visits)
        await self.store.put(SNAPSHOTS, snap.key, snap.to_dict())

        for p in engine.get("pairs") or []:
            await self.store.put(PAIRS, p.id, p.to_dict())
        return snap

    async def _rebuild_sequences(self, tenant: str, visits: list[dict],
                                 *, now: int) -> list[CustomerSequence]:
        by_ref: dict[str, CustomerSequence] = {}
        for v in visits:
            ref = str(v.get("subject_ref") or "")
            if not ref:
                continue
            seq = by_ref.setdefault(ref, CustomerSequence(tenant=tenant, subject_ref=ref))
            here = {str(x) for x in (v.get("service_ids") or []) if x}
            seq.services = sorted(set(seq.services) | here)
            for svc in here:
                # Per VISIT, not per line: a receipt listing the same service twice is one visit
                # to it, and counting lines would let a single big order look like a habit.
                seq.counts[svc] = seq.counts.get(svc, 0) + 1
            seq.visits += 1
            seq.last_visit_at = max(seq.last_visit_at,
                                    int(v.get("occurred_at") or v.get("created_at") or 0))
            seq.updated_at = now
        for seq in by_ref.values():
            await self.store.put(SEQUENCES, seq.key, seq.to_dict())
        return list(by_ref.values())

    async def _coverage(self, visits: list[dict]) -> dict[str, Any]:
        total = len(visits)
        return {
            "branch_comparison": {"total": total,
                                  "known": sum(1 for v in visits if v.get("branch_id")),
                                  "unknown": sum(1 for v in visits if not v.get("branch_id")),
                                  "ratio": round(
                                      sum(1 for v in visits if v.get("branch_id")) / total, 3)
                                  if total else 0.0},
            "staff_performance": {"total": total,
                                  "known": sum(1 for v in visits if v.get("operator_id")),
                                  "unknown": sum(1 for v in visits if not v.get("operator_id")),
                                  "ratio": round(
                                      sum(1 for v in visits if v.get("operator_id")) / total, 3)
                                  if total else 0.0},
        }


def _median_basket(visits: list[dict]) -> int:
    """This shop's ordinary basket size — measured on ONE-PERSON receipts only (ي-7).

    THE THRESHOLD WAS BEING SET BY THE THING IT IS MEANT TO CATCH. `is_group_basket` calls a
    receipt outsized when it runs past four times the median, and the median was taken over EVERY
    receipt — group orders included. So a restaurant whose bills are mostly family tables has a
    median pulled up by those tables, four times it is enormous, and not one of them is filtered:
    the engine then learns «what goes with what» from what a table of six ordered rather than from
    what one person chooses. The filter switched itself off in exactly the shops that need it.

    THE ONE SIGNAL THAT NEEDS NO THRESHOLD BREAKS THE CIRCLE. A repeated line — two coffees on one
    bill — is evidence of more than one person that stands on its own, with no reference to any
    shop-level statistic. Those receipts are removed first, and the median is taken over what is
    left. It is not a perfect separation, and it does not have to be: it only has to stop the
    group receipts from raising the bar that is supposed to exclude them.

    A SHOP WHOSE EVERY RECEIPT REPEATS A LINE FALLS BACK TO ALL OF THEM, rather than to a median
    of nothing — 0 disables the size signal entirely (see `is_group_basket`), which would be this
    same defect reached by the other road.
    """
    singles = [v for v in visits
               if not associations.is_group_basket(
                   list(set(v.get("service_ids") or [])),
                   quantities=v.get("quantities") or {})]
    sizes = sorted(len(set(v.get("service_ids") or [])) for v in (singles or visits))
    if not sizes:
        return 0
    return sizes[len(sizes) // 2]
