"""What this service reads, and the one thing it sends.

IT READS AND DOES NOT KEEP. Visits come from `operations` on every sweep and are used to compute
numbers, then dropped. The only rows this service stores are ones it derived (see core/models.py).

THE VISITS READ IS THE CATCH-UP SHAPE, NOT AN EVENT SUBSCRIPTION. `/internal/operations/visits/since`
is bounded, ordered by a watermark that only increases, and safe to call from a cron — which is
exactly what a daily snapshot needs. Subscribing to the visit event instead would give this service
the at-most-once problem for no benefit: nothing here has to be up to the second.

AND THE ONE THING IT SENDS — the weekly digest — goes through reminders' gate like every other
message in this product. There is no notification client here and no channel configuration, on
purpose: a second send path is a second set of rules, and the second one is always the one missing
a check.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http
from app.core.models import VisitPage

#: We could not ask operations who this person is. Not a branch, and not «no restriction».
UNREADABLE = "_unreadable"
#: His own shop stopped him — a decision, not a failure. Told apart because they are different
#: facts, and refused identically.
REVOKED = "_revoked"
#: Compared as a set so a fourth state cannot be added and quietly fall through to «see
#: everything», which is how this family of defect starts every time.
DENIED = frozenset({UNREADABLE, REVOKED})


#: How many pages of 500 one snapshot pass will read. Twenty was the old figure and it bounded the
#: WRONG thing — it stopped the read at the oldest end. It now bounds effort only: the rows kept
#: are always the newest, and a shop bigger than this reports itself partial rather than wrong.
PAGE_BUDGET = 60


# The request itself is built in adapters/internal_http.py — the one place in this service that
# attaches the internal token. `_get` is named here for the first time: the five GETs below each
# hand-rolled the same Request beside a `_post` that already existed, which is precisely how the
# token came to be spelled out at six separate sites in one file.
_post = internal_http.post_json
_get = internal_http.get_json


class NullPeers:
    """Serves whatever a test put in it. Refused in production by the boot guard, where it would
    mean a dashboard that computes confidently from nothing."""
    driver = "null"

    def __init__(self, visits: list[dict] | None = None,
                 catalogue: list[dict] | None = None,
                 entitlements: set[str] | None = None,
                 branches: list[dict] | None = None,
                 operators: list[dict] | None = None,
                 packages: list[dict] | None = None) -> None:
        self._visits = visits or []
        self._catalogue = catalogue or []
        self._branches = branches or []
        self._operators = operators or []
        self._packages = packages or []
        # What a test says this caller may see. Empty is the ordinary case: an owner sees it all.
        self.scope = ""
        # What a test says this tenant bought. Empty = an unsubscribed shop, which is the state
        # every check must be correct about.
        self.entitlements: set[str] = set(entitlements or set())
        # What the three optional digest reads would return. Empty means each of them failed or
        # is not applicable — which is the state the digest must be correct about.
        self.extras: dict[str, Any] = {}
        self.sent: list[dict] = []
        # WHAT THE SEND LOG SAYS, and whether it could be read at all. The default is a read that
        # SUCCEEDED and found nothing — a shop that has sent no messages — because that is the
        # ordinary state of a test fixture. A test for the unreadable case sets `ok` to False, and
        # the two must not be the same object (ي-3).
        self.effect_answer: dict[str, Any] = {"ok": True, "sends": [], "sent_count": 0,
                                              "opt_outs": 0, "truncated": False}

    async def visits(self, tenant: str, *, since: int = 0, limit: int = 5000) -> list[dict]:
        return [v for v in self._visits if not tenant or v.get("tenant") == tenant]

    async def catalogue(self, tenant: str) -> list[dict]:
        return list(self._catalogue)

    async def packages(self, tenant: str) -> list[dict]:
        return list(self._packages)

    async def branches(self, tenant: str) -> list[dict]:
        return list(self._branches)

    async def operators(self, tenant: str) -> list[dict]:
        return list(self._operators)

    async def branch_scope(self, tenant: str, subject: str) -> str:
        return self.scope

    async def tenants(self, *, since: int = 0) -> list[str]:
        return sorted({v.get("tenant", "") for v in self._visits if v.get("tenant")})

    async def send(self, **kw: Any) -> dict[str, Any]:
        self.sent.append(kw)
        return {"sent": True}

    async def entitled(self, tenant: str, key: str) -> bool:
        return key in self.entitlements

    async def digest_extras(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        return dict(self.extras)

    async def effect(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        return dict(self.effect_answer)

    async def consented(self, tenant: str) -> int:
        return int(self.extras.get("consented") or 0)


class HttpPeers:
    driver = "http"

    def __init__(self, *, operations_url: str, visits_path: str, catalogue_path: str,
                 packages_path: str = "/internal/operations/packages",
                 branches_path: str = "/internal/operations/branches",
                 operators_path: str = "/internal/operations/operators",
                 scope_path: str = "/internal/operations/branch-scope",
                 ratings_summary_path: str = "/internal/operations/ratings-summary",
                 tenants_path: str = "/internal/operations/tenants-with-visits",
                 reminders_url: str, send_path: str, consent_count_path: str,
                 ceiling_pressure_path: str = "/internal/reminders/ceiling-pressure",
                 effect_path: str = "/internal/reminders/effect",
                 billing_url: str, entitlement_path: str,
                 usage_path: str, loyalty_url: str, loyalty_report_path: str,
                 tenant_url: str, tenant_read_path: str,
                 token: str, timeout: int = 8) -> None:
        self._visits_url = operations_url.rstrip("/") + visits_path
        self._catalogue_url = operations_url.rstrip("/") + catalogue_path
        self._packages_url = operations_url.rstrip("/") + packages_path
        self._branches_url = operations_url.rstrip("/") + branches_path
        self._operators_url = operations_url.rstrip("/") + operators_path
        self._scope_url = operations_url.rstrip("/") + scope_path
        self._ratings_summary_url = operations_url.rstrip("/") + ratings_summary_path
        self._tenants_url = operations_url.rstrip("/") + tenants_path
        self._send_url = reminders_url.rstrip("/") + send_path
        self._entitlement_url = billing_url.rstrip("/") + entitlement_path
        self._consent_url = reminders_url.rstrip("/") + consent_count_path
        self._usage_url = billing_url.rstrip("/") + usage_path
        self._pressure_url = reminders_url.rstrip("/") + ceiling_pressure_path
        self._reminders_url = reminders_url.rstrip("/")
        self._effect_path = effect_path
        self._loyalty_url = loyalty_url.rstrip("/") + loyalty_report_path
        self._tenant_url = tenant_url.rstrip("/")
        self._tenant_path = tenant_read_path
        self._token = token
        self._timeout = timeout

    async def visits(self, tenant: str, *, since: int = 0, limit: int = 5000) -> list[dict]:
        """Paged to the watermark the peer returns, never to one we compute.

        Deriving the next cursor from the last row is a one-line mistake that either replays
        everything or skips a visit, and the peer already returns the correct value.
        """
        # ── THE NEWEST `limit` VISITS, NEVER THE FIRST (ي-1) ─────────────────────────────────
        #
        # This feed is ordered by `created` ASCENDING — operations sorts it that way so the
        # watermark can advance without skipping a row — and this loop used to stop the moment it
        # held `limit` rows and return `out[:limit]`. On a shop past five thousand visits that is
        # its OLDEST five thousand, some of them years old: `active_customers` counts a 90-day
        # window and answered 0, `expected_flow` answered 0, and `at_risk` named people who
        # stopped coming two years ago. The shops it hurt are the busy ones.
        #
        # So the loop pages to the END of the feed and keeps a rolling tail. The page budget still
        # bounds the work — that is a bound on effort, which is honest — but the rows kept are the
        # ones the windows are about.
        # ONE READ, NEWEST FIRST, AND THE PAGING IS GONE. Walking forward and keeping a rolling
        # tail was the previous repair, and it was still walking the wrong way: `PAGE_BUDGET` × 500
        # is thirty thousand visits, read FROM 2021, and a shop with a hundred and twenty thousand
        # ended its budget in 2022 — so the «tail» it kept was two years stale.
        # `active_customers(90)` answered 0, `visits_week` answered 0, and `at_risk` named people
        # who stopped coming two years ago. The symptoms of ي-1, moved from five thousand rows to
        # thirty thousand and no further.
        #
        # `newest_first` asks operations the question this reader actually has. The route reads
        # descending and says whether more stood behind them; the budget above is no longer spent
        # walking a decade to reach last week.
        out = VisitPage()
        data = _post(self._visits_url,
                     {"tenant": tenant, "since": 0, "limit": limit, "newest_first": True},
                     self._token, self._timeout)
        out.extend(data.get("visits") or [])
        # NOT `more`: that field belongs to the watermark reader. `exhaustive` is the route saying
        # whether anything stood behind the window it returned.
        out.truncated = not data.get("exhaustive", True)
        return out

    async def catalogue(self, tenant: str) -> list[dict]:
        try:
            return (_post(self._catalogue_url, {"tenant": tenant},
                          self._token, self._timeout)).get("services") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # NOT fatal. Without the catalogue we lose service NAMES and cycle completion, and
            # every other indicator still computes. Failing the whole snapshot over a display
            # detail would take the dashboard down to protect a label.
            return []

    async def packages(self, tenant: str) -> list[dict]:
        try:
            return (_post(self._packages_url, {"tenant": tenant},
                          self._token, self._timeout)).get("packages") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # NOT fatal, same posture as `catalogue` above. Without this a package visit is simply
            # not folded into a synthetic item — its components still count as ordinary services,
            # which is the CORRECT degraded behaviour (see tick.py's own note), not a broken one.
            return []

    async def branch_scope(self, tenant: str, subject: str) -> str:
        """Which branch this person may see, asked of the service that staffs the shop.

        FAILS CLOSED, and this is the one read here that must. Everywhere else an unreachable peer
        costs a label or a number; here it decides whether a branch manager is shown the whole
        chain. A scope we could not read is answered as «his own nothing» — the dashboard renders
        the unbranched view, which shows him no other branch's figures — rather than as «no
        restriction», which would hand him everybody's.

        AND A STOPPED EMPLOYEE IS ITS OWN ANSWER. `branch_id` cannot carry it: this line reads that
        field as `str(... or "")`, so any empty answer became "" — and "" is «no restriction», the
        opposite of what a dismissal means. operations therefore says `revoked` in a field of its
        own, and it refuses exactly where an unreadable scope does.
        """
        try:
            out = _post(self._scope_url, {"tenant": tenant, "subject": subject},
                        self._token, self._timeout)
            if out.get("revoked"):
                return REVOKED
            # THE LIST FIRST, THE OLD FIELD AS THE FALLBACK. What a person may see is a set;
            # `branch_id` is that set flattened for the single-branch case every shop had until
            # now, and it is empty for a man who watches several — reading it alone would turn his
            # four branches into "" , which this service reads as «the whole chain».
            branches = [str(b) for b in (out.get("branches") or []) if b]
            if branches:
                return frozenset(branches) if len(branches) > 1 else branches[0]
            return str(out.get("branch_id") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return UNREADABLE

    async def branches(self, tenant: str) -> list[dict]:
        """This shop's places — ONLY so a table can print a name instead of `brn_9f2a`.

        SAME FAILURE POSTURE AS THE CATALOGUE: an unreachable operations costs the branch table
        its names, not the snapshot. Every number in that table is computed from the visits we
        already hold, and taking a dashboard down to protect a label is the wrong trade.
        """
        try:
            return (_post(self._branches_url, {"tenant": tenant},
                          self._token, self._timeout)).get("branches") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return []

    async def operators(self, tenant: str) -> list[dict]:
        """This shop's people — ONLY so the staff table can print a name instead of `opr_9f2a`.

        SAME FAILURE POSTURE AS `branches` ABOVE: an unreachable operations costs the staff
        table its names, not the snapshot — every number in it is computed from the visits we
        already hold.
        """
        try:
            return (_post(self._operators_url, {"tenant": tenant},
                          self._token, self._timeout)).get("operators") or []
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return []

    async def tenants(self, *, since: int = 0) -> list[str]:
        """Every tenant that has visits — the BOOTSTRAP.

        A sweep that can only visit tenants it already knows can never learn about the shop whose
        first event it missed, and the bus is at-most-once. So the tenant list is read from the
        data rather than remembered, with no tenant filter — which is what the peer's own comment
        calls the point of that path rather than a forgotten one.
        """
        # ITS OWN ROUTE NOW, AND IT USED TO BE A SIDE EFFECT OF READING VISITS. Five hundred visit
        # rows came back in KEY order — a visit's key is `tenant|visit_id` — so one establishment
        # sorting first alphabetically with five hundred visits filled the whole page, and this
        # returned a list of ONE tenant. Forty shops on the cluster, thirty-nine of them never
        # visited by the snapshot cron again: each one's dashboard computed once, on the first
        # open, and served unchanged for ever after.
        #
        # The question is «who exists», and its answer is a few hundred strings no matter how many
        # millions of visits stand behind them. Asking it through a page of visits is what let the
        # size of one shop hide every other shop.
        data = _post(self._tenants_url, {}, self._token, self._timeout)
        return sorted(str(x) for x in (data.get("tenants") or []) if x)

    async def send(self, *, tenant: str, subject_ref: str, template_type: str, cls: str,
                   owner_text: str, idempotency_key: str, flow_token: str = "",
                   flow_action_data: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "tenant": tenant, "subject_ref": subject_ref, "template_type": template_type,
            "class": cls, "owner_text": owner_text, "idempotency_key": idempotency_key,
        }
        # THE WEEKLY REPORT'S OWN FLOW BUTTON (rating-app-feature.md phase 6b) — omitted entirely
        # when empty, same "no meaningless field on an ordinary send" rule reminders' own
        # HttpSender.send follows for this exact pair.
        if flow_token:
            body["flow_token"] = flow_token
            if flow_action_data:
                body["flow_action_data"] = dict(flow_action_data)
        try:
            return _post(self._send_url, body, self._token, self._timeout)
        except urllib.error.HTTPError as exc:
            return {"sent": False, "reason": f"رفض الإرسال ({exc.code})"}
        except (urllib.error.URLError, OSError) as exc:
            return {"sent": False, "reason": f"تعذّر الوصول لخدمة التذكيرات: {exc}"}


    async def entitled(self, tenant: str, key: str) -> bool:
        """Does this establishment's SUBSCRIPTION include this feature?

        THE PLAN IS NOT ON THE TOKEN, and reading it from there was the mistake this replaces.
        Two things were wrong with it, and billing-service's own code warns about the first:

          a claim the caller presents is a server-side decision enforced client-side (CWE-602),
          and a token minted before an upgrade keeps saying `smart` for its whole lifetime — so a
          shop that just paid is refused for an hour with no error anywhere to explain it.

        FAILS CLOSED, and that is the harder half. If billing is unreachable we deny: showing a
        paid surface to somebody who has not bought it is a leak we cannot take back, while a
        refusal during an outage is a minute of inconvenience that fixes itself. The refusal says
        WHY, so it is not mistaken for "you did not buy this".
        """
        url = self._entitlement_url + "?" + urllib.parse.urlencode({"tenant": tenant, "key": key})
        try:
            return bool(_get(url, self._token, self._timeout).get("allowed"))
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return False


    async def consented(self, tenant: str) -> int:
        """How many customers allow this shop's offers — a number, never a list.

        Zero on failure rather than raising: the dashboard degrades by not showing the line, which
        is right. Showing a wrong count would be worse than showing none, because the whole point
        of the number is that the owner can trust it — it is his own data, and it is what we ask
        him to upgrade on.
        """
        try:
            return int(_post(self._consent_url, {"tenant": tenant},
                             self._token, self._timeout).get("granted") or 0)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            return 0

    async def effect(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        """What went out and what it cost — from the only service that holds a send log.

        A FAILURE HERE COSTS TWO INDICATORS AND NOTHING ELSE. The snapshot is computed for every
        tenant on a tick; a reminders that is slow or restarting must not take the whole dashboard
        with it, so this answers empty and the two surfaces that need it render their «not yet»
        state rather than a wrong number.

        AND `ok` IS WHAT MAKES THAT SENTENCE TRUE (ي-3). The failure answer used to be
        `{"sends": [], "sent_count": 0, "opt_outs": 0}` — which is character for character what a
        shop that has never sent a message looks like. The caller could not tell them apart, so
        «reminders timed out» was rendered as «0 زيارة عادت بعد رسالة»: our outage printed as his
        engine's result, in the one number that argues for renewal. `ok` is set ONLY on a read that
        returned, and its absence is what every indicator downstream checks.
        """
        try:
            q = urllib.parse.urlencode({"tenant": tenant, "since": since})
            data = _get(self._reminders_url + self._effect_path + "?" + q,
                        self._token, self._timeout)
            # `ok` LAST, so a peer that one day sends its own `ok: false` cannot make a read
            # that plainly succeeded look like a failure. What arrived is what we read.
            return {**data, "ok": True}
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {"ok": False, "sends": [], "sent_count": 0, "opt_outs": 0}

    async def digest_extras(self, tenant: str, *, since: int = 0) -> dict[str, Any]:
        """The FOUR things the weekly report needs and this service does not hold.

        EACH FAILURE COSTS ONE LINE, NEVER THE MESSAGE. A digest that refuses to go out because
        billing was slow is a report the owner does not get for a reason he will never learn —
        and the seven other lines were correct. So every read is its own try, and an absent value
        simply drops its line (see core/digest.py).
        """
        out: dict[str, Any] = {}

        # The shop's own name. A message that opens "أسبوعك في" and stops is the blank-name defect
        # this product already shipped once, so an empty answer drops the name rather than
        # printing a gap.
        try:
            path = self._tenant_path.replace("{id}", urllib.parse.quote(tenant, safe=""))
            data = _get(self._tenant_url + path, self._token, self._timeout)
            branding = data.get("branding") or {}
            out["shop"] = str(data.get("name") or "")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # The message quota — the quietest outage this product has: the engine stops mid-month and
        # nothing tells him until a customer mentions they stopped hearing from him.
        try:
            usage = _get(self._usage_url + "?" + urllib.parse.urlencode({"tenant": tenant}),
                         self._token, self._timeout)
            for row in (usage.get("usage") or usage.get("items") or []):
                if str(row.get("key")) == "messages.monthly":
                    # The COUNT only. The limit is -1 on every plan — we do not sell messages, so
                    # there is no allowance to compare it against (spec §16.7).
                    out["messages_sent"] = int(row.get("current") or 0)
                    break
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # WHAT HIS CEILING COST HIM, from reminders — which is the only service that knows, because
        # it is the one whose sends were stopped. A LINE in a report that is already going out, so
        # it costs no message and no unit; a notice of its own would come out of the same ceiling
        # it is reporting on, at the moment there is none left.
        try:
            rows = _get(self._pressure_url + "?" + urllib.parse.urlencode({"limit": 1000}),
                        self._token, self._timeout).get("establishments") or []
            for row in rows:
                if str(row.get("tenant")) == tenant:
                    out["ceiling_missed"] = int(row.get("missed") or 0)
                    break
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # How many customers currently allow this shop's offers. A COUNT and never a list — the
        # peer's route has no shape that could return who (spec §8.5).
        try:
            out["consented"] = int(_post(self._consent_url, {"tenant": tenant},
                                         self._token, self._timeout).get("granted") or 0)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # Points redeemed this week. AGGREGATES ONLY — the peer's route returns totals and never
        # who, because a report builder has no business receiving a customer list.
        try:
            rep = _post(self._loyalty_url, {"tenant": tenant, "since": since},
                        self._token, self._timeout)
            out["points_redeemed"] = int(rep.get("redeemed_since") or 0)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        # The rating app's own week (rating-app-feature.md phase 6). Absent on any failure — a
        # shop that never bought the rating app gets a count of 0 from the peer itself and this
        # line simply never appears (see core/digest.py's own zero-drops-the-line rule), same as
        # a peer that is genuinely down.
        try:
            rat = _post(self._ratings_summary_url, {"tenant": tenant, "since": since},
                       self._token, self._timeout)
            out["ratings_count"] = int(rat.get("count") or 0)
            out["ratings_average"] = float(rat.get("average") or 0.0)
            out["ratings_unhandled"] = int(rat.get("unhandled") or 0)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            pass

        return out


def build_peers(settings) -> Any:
    if (getattr(settings, "PEERS_DRIVER", "") or "null").lower() == "null":
        return NullPeers()
    return HttpPeers(operations_url=settings.OPERATIONS_SERVICE_URL,
                     visits_path=settings.OPERATIONS_VISITS_SINCE_PATH,
                     catalogue_path=settings.OPERATIONS_CATALOGUE_PATH,
                     packages_path=settings.OPERATIONS_PACKAGES_PATH,
                     branches_path=settings.OPERATIONS_BRANCHES_PATH,
                     operators_path=settings.OPERATIONS_OPERATORS_PATH,
                     scope_path=settings.OPERATIONS_SCOPE_PATH,
                     ratings_summary_path=settings.OPERATIONS_RATINGS_SUMMARY_PATH,
                     reminders_url=settings.REMINDERS_SERVICE_URL,
                     send_path=settings.REMINDERS_SEND_PATH,
                     consent_count_path=settings.REMINDERS_CONSENT_COUNT_PATH,
                     ceiling_pressure_path=settings.REMINDERS_CEILING_PRESSURE_PATH,
                     effect_path=settings.REMINDERS_EFFECT_PATH,
                     billing_url=settings.BILLING_SERVICE_URL,
                     entitlement_path=settings.BILLING_ENTITLEMENT_PATH,
                     usage_path=settings.BILLING_USAGE_PATH,
                     loyalty_url=settings.LOYALTY_SERVICE_URL,
                     loyalty_report_path=settings.LOYALTY_REPORT_PATH,
                     tenant_url=settings.TENANT_SERVICE_URL,
                     tenant_read_path=settings.TENANT_READ_PATH,
                     token=settings.INTERNAL_SERVICE_TOKEN,
                     timeout=settings.PEER_TIMEOUT_SECONDS)
