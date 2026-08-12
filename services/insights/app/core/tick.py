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
from app.core.models import PAIRS, SEQUENCES, SNAPSHOTS, CustomerSequence, Snapshot


class Tick:
    def __init__(self, store: Any, peers: Any, *, batch: int = 50,
                 telemetry: Any = None,
                 thresholds: associations.Thresholds | None = None,
                 reserve_weeks: int = 8, reserve_percentile: float = 0.95,
                 reserve_floor: int = 20) -> None:
        self.store = store
        self.peers = peers
        self.batch = batch
        self.telemetry = telemetry
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
        visits = await self.peers.visits(tenant, since=since)
        catalogue = await self.peers.catalogue(tenant)
        snap = await self._compute_scope(tenant, visits, catalogue, now=now, branch_id="")

        branches = sorted({str(v.get("branch_id") or "") for v in visits if v.get("branch_id")})
        # ONLY FOR A SHOP WITH MORE THAN ONE. A single-branch establishment gets no branch
        # snapshots and no switch — "filter by your only branch" is a control that does nothing
        # and a question the owner has to think about (spec §10.6.4).
        if len(branches) > 1:
            for b in branches:
                scoped = [v for v in visits if str(v.get("branch_id") or "") == b]
                await self._compute_scope(tenant, scoped, catalogue, now=now, branch_id=b)
        return snap

    async def _compute_scope(self, tenant: str, visits: list[dict], catalogue: list[dict],
                             *, now: int, branch_id: str) -> Snapshot:
        cycles = {s.get("id", ""): int(s.get("cycle_days") or 0) for s in catalogue}
        names = {s.get("id", ""): s.get("name", "") for s in catalogue}

        values: dict[str, Any] = {
            "return_rate": indicators.return_rate(visits),
            # THE SAME NUMBER AS A LINE. Computed beside its own snapshot rather than in a second
            # job: one read of `visits`, one clock, and no chance of the headline figure and the
            # last point of the trend disagreeing — which is exactly the bug an owner screenshots.
            "retention_series": indicators.retention_series(visits, now=now),
            "return_cycle_days": indicators.return_cycle_days(visits),
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
            values["branch_rows"] = table["rows"]
            values["branch_unknown"] = table["unknown"]
            values["branch_can_rank"] = table["can_rank"]

        snap = Snapshot(tenant=tenant, values=values, visits=len(visits), computed_at=now,
                        branch_id=branch_id)
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
    sizes = sorted(len(set(v.get("service_ids") or [])) for v in visits)
    if not sizes:
        return 0
    return sizes[len(sizes) // 2]
