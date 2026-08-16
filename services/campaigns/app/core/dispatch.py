"""Firing a campaign — and the rule that this service never sends anything itself.

CAMPAIGNS DOES NOT SEND. It resolves an audience and hands each recipient to `reminders`, which
applies spec §8.4.2: the window, the per-class caps, the marketing cooldown, the engagement tier,
and the customer's own stop. Every one of those already exists there, tested, and a second send
path here would be a second set of rules — and the second one is always the one missing a check
the day somebody adds one to the first.

THE STANDING CAMPAIGN IS WHY THIS MATTERS. A manual send is watched by the owner who pressed it; if
it misbehaves they see it and stop. A standing rule runs unattended, every day, for a year, and
could wake a thousand customers at dawn. Nobody is watching it but the gate.

IDEMPOTENT ON (campaign, run, subject). A retried run must not double-send, and a run interrupted
halfway must resume rather than start over — a campaign that re-sends its first four hundred
recipients because the pod was evicted is worse than one that sends nothing.

BOUNDED PER PASS, AND RESUMABLE. The run records what it reached; the next pass continues from
there. Progress that survives an interruption beats completeness that does not.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.models import Run, as_row


@dataclass
class DispatchResult:
    run: Run
    finished: bool = True


class Dispatcher:
    def __init__(self, *, store, sender, audience_resolver, batch: int = 200,
                 telemetry=None, daily_share: int = 0) -> None:
        self._s = store
        self._sender = sender
        self._resolve = audience_resolver
        self._batch = batch
        self._t = telemetry
        # THE CAMPAIGN'S SHARE OF TODAY'S PROVIDER CEILING — the ceiling minus what the automatic
        # engine reserved (spec §8.4.3). Deliberately a NUMBER rather than a channel: this module
        # must not learn which provider imposes it, and a test enforces that by reading this
        # source. Zero means unknown, and unknown falls back to the pass batch — the provider
        # enforces its own limit regardless, and a campaign refusing to run because we could not
        # read a number would be our outage wearing their ceiling.
        self._daily_share = int(daily_share)

    async def fire(self, campaign: dict[str, Any], *, now: int, daily_share: int = 0,
                   fired_by: str = "system") -> DispatchResult:
        """One pass over one campaign.

        Returns the run — written whether or not anything was sent, because a run that matched
        nobody is information and its absence looks like a broken cron.
        """
        tenant = campaign.get("tenant", "")
        cid = campaign.get("id", "")
        run = Run(tenant=tenant, campaign_id=cid, at=now, fired_by=fired_by)

        reached = await self._already_reached(tenant, cid)
        audience = await self._resolve(campaign, already_reached=reached, now=now)
        run.matched = audience.count
        # Everyone the rule matched and the gate would refuse. Counted into the run so the report
        # explains the difference between "matched" and "sent" instead of leaving a gap.
        run.suppressed += audience.excluded
        if audience.excluded:
            run.reasons["البوابة رفضتها قبل الإرسال"] = audience.excluded

        # SPREAD ACROSS DAYS RATHER THAN FAILING AT THE CEILING. Ten thousand recipients against a
        # share of two thousand is five days whether we plan it or not; the only question is
        # whether the system does it deliberately or the shop discovers it as a list of failures.
        # PER TENANT AND PER DAY, so it arrives with the call rather than with the process. The
        # constructor's value was never passed by anything, and it could not have been right if it
        # had been: the share is the shop's own ceiling minus the engine's reserve minus what has
        # already gone today — three numbers from three services, none of them the same for two
        # shops. The preview computes it exactly this way, and the two now agree instead of the
        # screen promising a spread the sender did not perform.
        per_pass = daily_share or self._daily_share or self._batch

        sent_this_pass = 0
        for candidate in audience.candidates:
            if sent_this_pass >= per_pass:
                # BOUNDED. The run is saved with what it reached and the next pass continues —
                # a campaign that re-sends its first four hundred recipients because the pod was
                # evicted is worse than one that sends nothing.
                await self._save(run)
                return DispatchResult(run=run, finished=False)

            # THE KEY IS (campaign, subject) AND IT IS GENERATED BEFORE THE CALL. A timeout is
            # not evidence that nothing was sent, and the customer must not pay for our uncertainty
            # with a duplicate.
            #
            # AND `run.id` IS NOT IN IT ANY MORE, which was the whole defect. Every pass and every
            # retry opens a NEW run, so a send that timed out — but arrived — was re-sent under a
            # fresh key the moment the campaign was fired again: the customer got the same offer
            # twice, and the shop paid twice against its cap. The key that protects a customer from
            # our uncertainty cannot be derived from the attempt that is uncertain.
            #
            # ONE CAMPAIGN REACHES ONE PERSON ONCE — which is also what `_already_reached` says in
            # the other direction, so the two now agree instead of one quietly undoing the other.
            key = f"cmp:{cid}:{candidate.subject_ref}"
            try:
                outcome = await self._sender.send(
                    tenant=tenant,
                    subject_ref=candidate.subject_ref,
                    template_type=campaign.get("template_type", ""),
                    cls=campaign.get("cls", "marketing"),
                    owner_text=campaign.get("owner_text", ""),
                    idempotency_key=key,
                    # THE SAME END DATE FOR EVERY RECIPIENT OF THIS CAMPAIGN. A spread run reaches
                    # people over several days, and an expiry counted from each person's send would
                    # give the last recipient longer than the first — the shop would be running two
                    # different offers without deciding to.
                    offer_expires_at=int(campaign.get("expires_at") or 0),
                    offer_services=list(campaign.get("scope_service_ids") or []),
                    # THE OFFER'S VALUE, TYPED — see rendering.campaign_slots. Empty until the
                    # screen collects it (#244); a template that needs it then refuses to render
                    # rather than sending «خصم » with a hole where the number belongs.
                    offer_value=str(campaign.get("offer_value") or ""),
                    service_names=list(campaign.get("scope_service_names") or []),
                    # THE CAMPAIGN'S OWN BRANCH. It already narrows the audience; it must also
                    # decide the number the message leaves from, or a branch campaign speaks in the
                    # head office's voice and the reply lands on a team that cannot answer it.
                    branch_id=str(campaign.get("branch_id") or ""))
            except Exception as exc:                                        # noqa: BLE001
                # ONE RECIPIENT'S FAILURE MUST NOT END THE RUN. The alternative is one bad row
                # stopping a campaign for every other customer, indefinitely, and the symptom is
                # "the campaign does not work" rather than "one recipient failed".
                run.failed += 1
                _count(run.reasons, f"تعذّر الإرسال: {str(exc)[:60]}")
                if self._t is not None:
                    self._t.event("campaign_send_failed", tenant=tenant, campaign=cid,
                                  error=str(exc)[:200])
                continue

            if outcome.get("sent"):
                run.sent += 1
                await self._remember(tenant, cid, candidate.subject_ref, now)
            else:
                # THE GATE'S OWN REASON, VERBATIM. Rewriting it here would mean two vocabularies
                # for the same refusal, and the owner reading the report would be told something
                # subtly different from what actually happened.
                run.suppressed += 1
                _count(run.reasons, outcome.get("reason") or "امتنعت بلا سبب مذكور")
            sent_this_pass += 1

        await self._save(run)
        return DispatchResult(run=run, finished=True)

    # ── the dedup ledger ──────────────────────────────────────────────────────────────────────
    # WHO THIS CAMPAIGN HAS ALREADY REACHED, kept per (campaign, subject) rather than as a flag on
    # the customer. A flag would have to be cleared by something, and whatever clears it is the
    # bug — this needs no cleanup and is correct after a restore.
    async def _already_reached(self, tenant: str, campaign_id: str) -> set[str]:
        rows, _ = await self._s.find("campaign_reached",
                                     {"tenant": tenant, "campaign_id": campaign_id},
                                     limit=10000, sort=("at", "asc"))
        return {r.get("subject_ref", "") for r in rows if r.get("subject_ref")}

    async def _remember(self, tenant: str, campaign_id: str, subject: str, now: int) -> None:
        key = f"{tenant}|{campaign_id}|{subject}"
        await self._s.put("campaign_reached", key, {
            "id": key, "tenant": tenant, "campaign_id": campaign_id,
            "subject_ref": subject, "at": now})

    async def _save(self, run: Run) -> None:
        await self._s.put("campaign_runs", run.key, as_row(run))


def _count(reasons: dict[str, int], reason: str) -> None:
    # Truncated so one long peer error cannot make a report unreadable, and counted rather than
    # listed: an owner needs "3 deferred for the daily cap", not three identical lines.
    k = reason[:80]
    reasons[k] = reasons.get(k, 0) + 1
