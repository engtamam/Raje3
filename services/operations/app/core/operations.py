"""The field operation itself — recording a visit, and everything that hangs off it.

THE FIVE-SECOND RULE IS THE DESIGN CONSTRAINT, not an aspiration (spec §17.3). An operator records
a visit with a customer standing in front of them, and the screen must be empty and ready for the
next car within that budget. Everything here is arranged around it:

  * the request path does the MINIMUM: find or create the customer, write the visit. Two indexed
    reads and two writes, no joins, no fan-out.
  * indexing into search, the analytics event, and the reminder scheduling all happen AFTER the
    operator has been answered (see api/v1/visits.py). A peer being slow must never be the screen
    being slow.
  * the audit record is the one exception and it runs BEFORE the write, deliberately. A visit the
    log cannot witness must not happen — and recording afterwards would tell an operator "saved"
    about something the record does not hold.

THE DOUBLE TAP. A thumb on a phone in a workshop hits the save button twice. The guard is a
CLIENT-generated idempotency key, one per entry on the screen: the second tap carries the same key
and gets the same visit back. This cannot be done server-side — a server sees two identical
requests and cannot tell a double tap from a customer who genuinely came back an hour later, which
in a tyre shop is an ordinary thing.

The guard is a read-before-write rather than a unique constraint, and that is a deliberate trade:
under a true race two writes can still land. The reconciliation is that the SECOND one is
detectable (same key, two rows) and a sweep can merge them, whereas a database-level lock on the
hot path would cost every save to protect against a case that needs two taps inside the same few
milliseconds.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from app.core import branches as B
from app.core import scheduling as SCHED
from app.core.digits import WESTERN, western
from app.core.models import Asset, Customer, Visit
from app.core.pii import subject_ref
from app.core.stores import (AssetStore, BranchStore, CustomerStore, OperatorStore,
                             PackageStore, PrivacyRequestStore, ProcedureStepStore, ServiceStore,
                             VisitStore, new_id)


class OperationError(Exception):
    """A refusal the caller can act on. The message is shown to an operator, so it says what to do
    rather than what went wrong internally."""


@dataclass
class RecordedVisit:
    visit: Visit
    customer: Customer
    created_customer: bool
    duplicate: bool          # True when the idempotency key had already been used
    # Service ids the catalogue did not recognise, folded into the catch-all. REPORTED rather than
    # swallowed: an integration sending a service that does not exist is a bug worth seeing, even
    # though the visit was rightly kept.
    unknown_services: list[str] = field(default_factory=list)
    # EVERY PLATE THIS CUSTOMER HAS, so the index can be written from one place. A vehicle shop
    # finds people by plate and never by phone — the car arrives, the operator reads the plate off
    # it, and the man behind the wheel may not be the man whose number we hold. Carried on the
    # result rather than looked up again in `Seams`, which owns no stores by design.
    plates: list[str] = field(default_factory=list)
    # THE COUNTER'S OWN CELEBRATION MOMENT — `None` on every ordinary visit (the overwhelming
    # majority), a real `MutualBenefitGrant` only on the rare visit that just made a customer eligible
    # for a NEW partner reward. See the mutual-benefit hook below for why this can never
    # affect whether the visit itself succeeds.
    new_mutual_benefit_grant: Any = None
    # A REFERRAL CODE TYPED IN ON THIS VISIT — `None` when none was offered. `{"ok": True, ...}`
    # on a real grant, `{"ok": False, "message": ...}` when the code was rejected (wrong code,
    # already a customer, etc.) — surfaced to the operator's screen so a bad code is visible
    # rather than silently swallowed, while NEVER affecting whether the visit itself is saved
    # (see the referral hook below, same posture as the mutual-benefit one above it).
    referral_registration: Any = None


def _now() -> int:
    return int(time.time())


# A DEFAULT: how far back a claimed visit time may be before we treat it as a broken clock rather
# than a backlog. A shop migrating a year of history legitimately needs more, and a release is the
# wrong way to give it to them. MAX_BACKDATE_SECONDS overrides it.
_DEFAULT_MAX_BACKDATE_SECONDS = 90 * 24 * 3600


class Operations:
    def __init__(self, *, store, pii_salt: str, cache: Any = None,
                 max_backdate: int = _DEFAULT_MAX_BACKDATE_SECONDS,
                 phone_search_ro: Any = None) -> None:
        # Cross-tenant mutual-benefit eligibility detection — see
        # core/mutual_benefit.py's own module docstring for why THIS ONE call site is the
        # single, sufficient hook for every current and future visit-recording channel. `None`
        # until `with_mutual_benefit_engine` installs it (see that method) — any test/run that never
        # wires one simply has nothing to call, same posture `_choose_offer` takes before
        # `with_offer_chooser` runs.
        self._mutual_benefit_engine: Any = None
        # THE "جماعي" MILESTONE HOOK — campaigns' own shared counter (core/milestone.py), reported
        # to over HTTP since campaigns is a separate service, unlike the in-process mutual-benefit
        # engine above. `None` until `with_milestone_peer` installs it; a caller that never wires
        # one simply has nothing to call, same posture every optional peer here already takes.
        self._milestone_peer: Any = None
        # `core/entitlements.py::EntitlementGateway` — `None` until `with_entitlement_gateway`
        # installs it, same posture as `_mutual_benefit_engine`/`_choose_offer` above.
        self._entitlement_gateway: Any = None
        # `core/referral_redemption.py::ReferralRedemptionEngine` — the SAME engine the till's own
        # `/referral/register` route already calls, wired here too so a walk-in visit (no till
        # involved at all) can register a new customer's referral code at the one moment it is
        # ever going to be typed in. `None` until `with_referral_redemption_engine` installs it,
        # same posture as every other optional peer on this class.
        self._referral_redemption: Any = None
        self._customers = CustomerStore(store)
        self._assets = AssetStore(store)
        self._services = ServiceStore(store)
        self._packages = PackageStore(store)
        self._visits = VisitStore(store)
        self._steps = ProcedureStepStore(store)
        # WHICH PLACES THIS SHOP ACTUALLY HAS — read on the write path so an id nobody recognises
        # cannot invent a branch that then appears in every report (core/branches.py).
        self._branches = BranchStore(store)
        # AND WHO WORKS WHERE. The operator's own row is the authority on his branch — the device
        # only says who is saving (see `_branch_for`).
        self._operators = OperatorStore(store)
        # WHAT HIS CUSTOMERS ASKED HIM FOR, from their own pages. Recorded here rather than acted
        # on, because the establishment is the controller and the right is exercised against it —
        # see core/privacy_requests.py.
        self._privacy = PrivacyRequestStore(store)
        self._salt = pii_salt
        # THE OFFER-APPLY LOCK'S OWN CLAIM STORE — see core/offer_lock.py's module docstring.
        # `None` (no cache wired) is a real, supported state: a local run or a test with no
        # second caller to race against; `apply_offer` below runs unlocked in that case, same
        # posture as loyalty's own SpendLock.
        self._cache = cache
        # HOW WE ASK WHICH OFFER APPLIES. A callable rather than a URL so a test can answer it
        # without a socket, and so this file never learns reminders' route shape.
        self._choose_offer = None
        # How far back a claimed visit time may be before it is a broken clock. A shop migrating a
        # year of its own history needs more, and that must not require a release.
        self._max_backdate = int(max_backdate)
        # THE WEAKER ROLE, ONLY FOR THE ONE ROUTE THAT ASKS FOR IT (see app/config.py's
        # DATASTORE_DSN_PHONE_SEARCH and this class's own customer_by_phone_searched below). `None`
        # is the default, supported state — every other caller of `by_phone` (visit recording,
        # bookings' resolve-or-create) keeps using the normal, single-role path unchanged.
        self._phone_search_ro = phone_search_ro

    async def _branch_for(self, tenant: str, *, operator_id: str, claimed: str) -> str:
        """Where this visit happened — from the PERSON when we know him, from the device otherwise.

        THE HOLE THIS CLOSES. `branch_id` arrives in the request body, off a screen the shop
        controls, so any tablet could file its work under any branch — and a chain whose branches
        are managed separately would be comparing numbers anyone could move. The person saving is
        already established: the field screen verifies his PIN at the moment of saving
        (api/v1/staff.py), and his row says which branch he works at.

        SO THE OPERATOR'S OWN ROW WINS over anything the request claims. It is the only half of
        this pair that an owner sets and an employee cannot.

        AND AN OPERATOR WITH NO BRANCH DOES NOT ERASE ONE. Most shops never assign anybody — the
        branch on a PERSON stays optional by design (§12.2), unlike the one on a till's sale — and
        treating "unassigned" as "nowhere" would empty the branch column of every shop that fills
        it from its register instead.

        A VISIT WITH NO OPERATOR IS UNCHANGED: a till sends no person, and the machine credential
        is minted for a shop rather than a place (api/v1/till.py).
        """
        if operator_id.strip():
            op = await self._operators.get(tenant, operator_id.strip())
            # HIS BRANCH IS TAKEN AS WRITTEN, not re-validated: it was checked when it was assigned
            # (api/v1/staff.py), and a branch closed since then is still where he was working.
            if op is not None and op.branch_id:
                return op.branch_id
        return await self.resolve_branch(tenant, claimed)

    async def known_branches(self, tenant: str) -> set[str]:
        """Every branch id this shop really has — asked ONCE, for a door checking many items.

        `resolve_branch` answers about one id and reads the branch list to do it. A batch of fifty
        sales calling it fifty times is fifty reads of the same short list, so the door that checks
        a batch asks for the set instead. Same source, same answer, one read.

        SAME ANSWER AS `resolve_branch`, BY CONSTRUCTION — it is the set `branches.resolve` checks
        against, not a second opinion assembled here. A door that decided validity for itself would
        be free to accept an id the recorder then drops, which is how a field becomes mandatory and
        ignorable at the same time.
        """
        return await B.known(self._branches, tenant)

    async def resolve_branch(self, tenant: str, branch_id: str) -> str:
        """The branch check, offered to the routes that take one outside the visit path.

        ONE OWNER FOR THE QUESTION. The till's redemption and the visit are two doors into the same
        shop, and a second place that decides what an unrecognised branch means is a second place
        that would drift from this one.
        """
        if not (branch_id or "").strip():
            return ""
        return await B.resolve(self._branches, tenant, branch_id)

    # ── his customers' privacy requests ───────────────────────────────────────────────────────
    async def record_privacy_request(self, tenant: str, subject_ref: str, kind: str):
        return await self._privacy.open_request(tenant, subject_ref, kind)

    async def open_privacy_requests(self, tenant: str):
        return await self._privacy.list_open(tenant)

    async def close_privacy_request(self, tenant: str, request_id: str, by: str) -> bool:
        return await self._privacy.close(tenant, request_id, by)

    def with_offer_chooser(self, chooser) -> "Operations":
        """Install who decides which CAMPAIGN offer a visit applies. Set at wiring, not at import.

        ALSO REBUILDS THE ENTITLEMENT GATEWAY, IF ONE IS ALREADY INSTALLED — a caller (container.py
        at boot, or a test overriding the peer afterward, e.g. `test_till_offer.py`'s own fixtures)
        that calls this a SECOND time, after `with_entitlement_gateway` already ran, must see its
        new chooser actually take effect. Without this, `apply_offer` would keep asking the OLD
        gateway — built with the OLD chooser baked in — and a test replacing `self._choose_offer`
        alone would silently have no effect at all, exactly the regression a real review caught
        here (the gateway, not the bare chooser, is what `apply_offer` reads once one exists)."""
        self._choose_offer = chooser
        if self._entitlement_gateway is not None:
            from app.core.entitlements import EntitlementGateway

            self._entitlement_gateway = EntitlementGateway(
                mutual_benefit_engine=self._mutual_benefit_engine, campaign_chooser=chooser)
        return self

    def with_mutual_benefit_engine(self, engine) -> "Operations":
        """Install the mutual-benefit hook. Set at wiring, not at import — `container.py`
        needs `billing_plans` built before it can construct the engine, and `Operations` itself is
        built earlier than that, same reason `with_offer_chooser` above is a post-construction
        setter rather than a constructor argument that would force a build-order dependency."""
        self._mutual_benefit_engine = engine
        if self._entitlement_gateway is not None:
            # Same rebuild `with_offer_chooser` does, symmetrically — see that method's own
            # docstring for why a gateway already installed must see a LATER change to either of
            # its two sources, not just the one it happened to be built from first.
            from app.core.entitlements import EntitlementGateway

            self._entitlement_gateway = EntitlementGateway(
                mutual_benefit_engine=engine, campaign_chooser=self._choose_offer)
        return self

    def with_milestone_peer(self, peer) -> "Operations":
        """Install the "جماعي" milestone hook — a separate service (campaigns), reached over
        HTTP, unlike the in-process `_mutual_benefit_engine` above. Set at wiring for the same
        reason every other post-construction setter here is."""
        self._milestone_peer = peer
        return self

    def with_entitlement_gateway(self, gateway) -> "Operations":
        """Install `core/entitlements.py::EntitlementGateway` — see that module's own docstring for
        why `apply_offer` below now asks ONE thing instead of calling `self._choose_offer` (the
        reminders-only campaign chooser) directly. `None` until wired, same posture every other
        setter on this class takes (`apply_offer` below refuses rather than guesses when it is)."""
        self._entitlement_gateway = gateway
        return self

    def with_referral_redemption_engine(self, engine) -> "Operations":
        """Install `core/referral_redemption.py::ReferralRedemptionEngine` — the same engine
        `api/v1/till.py::register_referral_code_at_the_counter` already calls. Set at wiring, same
        posture as every other optional peer here (`None` until installed)."""
        self._referral_redemption = engine
        return self

    async def _register_referral_if_new(self, tenant: str, *, created_customer: bool, phone: str,
                                        referral_code: str, invoice_minor: int,
                                        actor: str) -> dict | None:
        """The one place a referral code is ever attempted — shared by every real "a code was
        offered alongside a real transaction" moment this class has (`record_visit`,
        `ensure_customer`), the same engine the till's own `/referral/register` route calls
        directly.

        ALWAYS TRIED WHEN A CODE IS OFFERED, REGARDLESS OF NEW/RETURNING (owner instruction,
        2026-09-27) — who is actually eligible is now the campaign's/affiliate's OWN configured
        choice (`referral_redemption.py::_check_beneficiary_eligibility`: "new" / "max_visits" /
        "open"), not a shortcut decided here. `created_customer` is kept as a parameter only
        because callers still compute and pass it (harmless, unused for gating) — it is no longer
        read below.

        NEVER RAISED, NEVER ALLOWED TO UNDO WHAT ALREADY HAPPENED — a rejected code (wrong,
        self-referral, ineligible under this campaign's/affiliate's own setting) is returned so the
        caller's own screen can show it, but the customer/visit/booking this was attached to has
        already been saved by the time this runs and must never be undone over it. Same posture the
        mutual-benefit hook right above this one already holds."""
        if not (referral_code.strip() and self._referral_redemption is not None):
            return None
        from app.core.referral_redemption import ReferralRedemptionError

        try:
            grant = await self._referral_redemption.register(
                tenant, code=referral_code, beneficiary_phone=phone,
                invoice_minor=invoice_minor, actor=actor)
            return {"ok": True, "new_customer_reward_type": grant.new_customer_reward_type,
                   "new_customer_reward_params": grant.new_customer_reward_params}
        except ReferralRedemptionError as exc:
            return {"ok": False, "message": str(exc)}
        except Exception:                                                     # noqa: BLE001
            return {"ok": False, "message": "تعذّر تسجيل كود الإحالة الآن"}

    async def apply_offer(self, *, tenant: str, visit_id: str,
                          subject_ref: str) -> dict[str, Any] | None:
        """Mark this visit as having applied an offer — the tap that proves it (§5.6.2).

        ONE PER VISIT, and it is enforced here because here is where the visit is. A second tap
        returns the offer already recorded and spends nothing more: a double tap at a counter is
        one intention, not two discounts on one invoice — «خصمان على فاتورة واحدة قرارٌ لم يتخذه
        المالك».

        THE JUDGEMENT IS NOT OURS. Which entitlement applies — a reminders campaign offer, or a
        mutual-benefit grant (see `core/entitlements.py::EntitlementGateway`, the one
        aggregation point this method now consults instead of a single fixed peer) — depends
        on what each source itself knows. We ask, and we record what comes back — including the
        TEXT, copied rather than referenced, because an owner reading this visit next year needs
        what was promised and the source's own log may have been pruned by retention.

        AND NO SOURCE MEANS NO SPEND. A missing or unreadable source refuses rather than guesses;
        the alternative is a discount granted because a URL was blank.
        """
        # BY ID OR BY THE CLIENT'S OWN KEY, because the screen has only the latter. «تسجيل زيارة»
        # queues offline and hands the server an idempotency key; it never learns the id we mint,
        # and it must not have to wait for a round trip to apply an offer with a customer standing
        # there. The key is also the one value identical across every retry — which is precisely
        # what «عرضٌ واحد لكل زيارة» needs to hold.
        #
        # RESOLVED TO THE REAL VISIT ROW BEFORE THE LOCK IS TAKEN — both a caller naming the id
        # directly and one naming its own idempotency key must serialise on the SAME key, or the
        # lock protects only one of the two doors into this method.
        v = await self._visits.get(tenant, visit_id)
        if v is None:
            v = await self._visits.by_idempotency_key(tenant, visit_id)
        if v is None:
            raise OperationError("لا توجد زيارة بهذا المعرّف")

        # SERIALISED FROM HERE ON — see core/offer_lock.py's own module docstring for the exact
        # race this closes: two calls for the SAME visit, both reading `offer_ref == ""` before
        # either has saved, both choosing and stamping — the second write winning in silence.
        from app.core.offer_lock import OfferApplyLock

        async with OfferApplyLock(self._cache, tenant, v.id):
            # RE-READ INSIDE THE LOCK — the row this function read above may already be stale by
            # the time the claim is won (the racer that lost the claim is exactly the one whose
            # copy is now behind); trusting it here would silently skip the very check the lock
            # exists to make safe.
            v = await self._visits.get(tenant, v.id) or v
            if v.offer_ref:
                return {"ref": v.offer_ref, "text": v.offer_text, "used_at": v.offer_used_at,
                       "campaign_id": v.offer_campaign_id}

            from app.core.entitlements import EntitlementGateway, EntitlementPeerUnavailable

            gateway = self._entitlement_gateway
            if gateway is None:
                if self._choose_offer is None:
                    raise OperationError("تعذّر التحقق من العروض الآن")
                # BACKWARD-COMPATIBLE FALLBACK — a caller that wired only `with_offer_chooser`
                # (every existing test, and any peer that has not moved to
                # `with_entitlement_gateway` yet) keeps working unchanged: a gateway built with a
                # campaign chooser and no referral source behaves exactly as the old direct call
                # did, referral simply never outranking anything because there is nothing to.
                gateway = EntitlementGateway(mutual_benefit_engine=self._mutual_benefit_engine,
                                             campaign_chooser=self._choose_offer)

            # THE PHONE, FOR THE REFERRAL SOURCE ONLY — reminders' own campaign chooser has never
            # needed it (identity + scope, by `subject_ref`), and it stays that way; only
            # `EntitlementGateway` reads it, only to ask `MutualBenefitEngine.eligibility`.
            customer = await self._customers.get(tenant, v.customer_id)
            phone = customer.phone if customer is not None else ""

            try:
                chosen = await gateway.choose(tenant=tenant, subject_ref=subject_ref, phone=phone,
                                              service_ids=list(v.service_ids))
            except EntitlementPeerUnavailable as exc:
                # AN UNREADABLE SOURCE REFUSES, IT DOES NOT ANSWER «none» — see
                # `core/entitlements.py`'s own module docstring. Applying nothing costs the
                # customer an entitlement he still holds; telling the worker we could not check
                # lets him try again in a moment. The two are not the same answer and must not
                # share a return value.
                raise OperationError(
                    "تعذّر التحقق من العروض الآن. أعد المحاولة بعد قليل.") from exc
            if chosen is None:
                return None

            # THE ENTITLEMENT'S OWN SIDE EFFECT FIRST, BEFORE THE VISIT IS STAMPED — e.g.
            # `MutualBenefitEngine.redeem()` for a referral-sourced grant. A failure here
            # refuses the whole apply and a retry starts from a clean slate (`choose()` runs
            # again); the REVERSE order (stamp first, finalize after) would let a retry after a
            # finalize failure return the already-stamped offer WITHOUT ever retrying the
            # finalize — a grant the customer was told he spent, that nothing ever actually
            # redeemed. See `EntitlementGateway.finalize`'s own docstring, and `redeem()`'s own
            # note on why it is idempotent by visit id for exactly this retry.
            try:
                await gateway.finalize(chosen, tenant=tenant, visit_id=v.id)
            except Exception as exc:                                        # noqa: BLE001
                raise OperationError(
                    "تعذّر تفعيل العرض الآن. أعد المحاولة بعد قليل.") from exc

            fields = chosen.as_offer_fields()
            v.offer_ref = fields["ref"]
            v.offer_text = fields["text"]
            v.offer_used_at = int(time.time())
            v.offer_campaign_id = fields["campaign_id"]
            await self._visits.save(v)
            return {"ref": v.offer_ref, "text": v.offer_text, "used_at": v.offer_used_at,
                   "campaign_id": v.offer_campaign_id}

    # ── the write path ────────────────────────────────────────────────────────────────────────
    async def record_visit(self, *, tenant: str, phone: str, service_ids: list[str],
                           operator_id: str = "", branch_id: str = "", name: str = "",
                           plate: str = "", meter: int = 0, note: str = "",
                           idempotency_key: str = "", custom_service: str = "",
                           # HOW MANY OF EACH SERVICE — an integrated till knows this and the field
                           # screen does not, so empty is the ordinary case and not a gap. It is
                           # read by exactly one thing: the group-basket test (§10.6.2).
                           quantities: dict[str, int] | None = None,
                           # WHAT THE RECEIPT CAME TO, in halalas. An integrated till passes the
                           # REAL amount paid here; the field screen passes nothing (0), and 0 is
                           # then computed below from the catalogue's own priced services — never
                           # «free», and no longer «unknowable». It is what loyalty's earn rule
                           # multiplies.
                           total_minor: int = 0,
                           occurred_at: int = 0,
                           # Bought with points rather than money (ب-6). Recorded on the visit so
                           # every consumer of it — the event, the feed, the earner — sees the
                           # same fact rather than inferring it from the note.
                           free: bool = False,
                           allow_unknown_services: bool = False,
                           # SET ONLY WHEN THIS VISIT FULFILLED A PACKAGE BOOKING — see
                           # Visit.package_id's own docstring. `service_ids` still carries the
                           # package's real components either way; this is threaded through
                           # unchanged to the seams event so loyalty can look up the package's own
                           # point value instead of summing the components'.
                           package_id: str = "",
                           # A NEW CUSTOMER'S REFERRAL CODE, typed in once, right here — the ONLY
                           # moment a walk-in (no till, no separate registration step) ever has to
                           # offer it. Ignored entirely unless this call actually creates a new
                           # customer (see the referral hook below): an existing customer typing
                           # one in is refused by the engine itself, same rule the till's own
                           # `/referral/register` route already enforces.
                           referral_code: str = "") -> RecordedVisit:
        if not tenant:
            raise OperationError("لا توجد منشأة على الطلب — سجّل الدخول من جديد")
        phone = _normalise_phone(phone)
        if not phone:
            raise OperationError("رقم الجوال مطلوب، ولم نتعرّف على ما أُدخل — تأكّد أنه أرقام فقط")
        if not service_ids:
            raise OperationError("اختر خدمة واحدة على الأقل")
        if any(not str(s).strip() for s in service_ids):
            raise OperationError("إحدى الخدمات المختارة بلا معرّف — أعد اختيارها")

        # The double-tap guard, first, before anything is created. Cheapest possible check: one
        # indexed read. If it hits, nothing else in this method runs — including customer creation,
        # which is what stops a double tap from also producing two customers.
        if idempotency_key:
            existing = await self._visits.by_idempotency_key(tenant, idempotency_key)
            if existing is not None:
                customer = await self._customers.get(tenant, existing.customer_id)
                # THE RETRY FINISHES WHAT THE CRASH INTERRUPTED (ز-6). Reaching here means the
                # visit is written. If the counters have not counted it, the first attempt died
                # between the two writes — and this is the only moment anything looks again. The
                # old code returned the visit and left the customer permanently one behind.
                #
                # Guarded by the visit's own id, so the ordinary case — a double tap, a retried
                # request that already succeeded — reads the stamp and changes nothing.
                if customer is not None and customer.counted_visit_id != existing.id:
                    # LOCKED — a real gap a QA audit found (2026-09-12): two concurrent retries
                    # for the same crashed visit could both observe `counted_visit_id != existing.id`
                    # before either saved, and both increment — an over-count. See
                    # core/customer_counter_lock.py's own module docstring.
                    from app.core.customer_counter_lock import CustomerCounterLock
                    async with CustomerCounterLock(self._cache, tenant, customer.id):
                        customer = await self._customers.get(tenant, existing.customer_id)
                        if customer is not None and customer.counted_visit_id != existing.id:
                            customer.last_visit = max(customer.last_visit, existing.occurred_at)
                            customer.visit_count += 1
                            customer.counted_visit_id = existing.id
                            await self._customers.save(customer)
                return RecordedVisit(visit=existing, customer=customer, created_customer=False,
                                     duplicate=True)

        now = _now()
        customer, created_customer = await self._resolve_customer(tenant, phone, name)

        # UNKNOWN SERVICES ARE ABSORBED, NOT REFUSED — and only on the integration path, where
        # `allow_unknown_services` is set. A till sends a service the owner never added to our
        # catalogue: refusing it would lose the visit, and a lost visit loses the CUSTOMER from
        # the product entirely — no reminder, no points, no metric, permanently. Losing the
        # service NAME is a small cost; losing the visit costs the product its premise.
        #
        # So the unknown ids are folded into the tenant's catch-all and their labels preserved on
        # the visit, where an owner can read them and where a name that keeps appearing is exactly
        # the signal that it should become a real catalogue entry.
        #
        # Never silent: the caller is told which ids were unknown, so an integration bug is
        # visible rather than absorbed into a shrug.
        unknown: list[str] = []
        if allow_unknown_services:
            known = {s.id for s in await self._services.list(tenant, active_only=False)}
            unknown = [sid for sid in service_ids if sid not in known]
            if unknown:
                catch = await self._services.catchall(tenant)
                if catch is None:
                    # A tenant provisioned before the catch-all existed. A clean refusal that names
                    # the fix, rather than a crash or a silently dropped service.
                    raise OperationError(
                        "لا توجد خانة «خدمة أخرى» في قائمة هذا المحل، فلا يمكن تسجيل خدمة "
                        "غير معروفة — راسِلنا لإعادة تهيئة القائمة")
                service_ids = [sid for sid in service_ids if sid in known] or []
                if catch.id not in service_ids:
                    service_ids = service_ids + [catch.id]
                if not custom_service:
                    custom_service = ", ".join(unknown)[:200]

        # THE BRANCH IS CHECKED, AND THE VISIT IS NEVER REFUSED OVER IT. An id this shop does not
        # have is dropped to «غير محدد» rather than written through — see core/branches.py for the
        # trade, which is the same one the unknown-service path above makes.
        branch_id = await self._branch_for(tenant, operator_id=operator_id, claimed=branch_id)

        asset_id = ""
        if plate.strip():
            asset_id = await self._resolve_asset(tenant, customer.id, plate.strip())

        # NO TILL TOLD US THE TOTAL, SO WE COMPUTE IT OURSELVES — from the catalogue's own priced
        # services, retiring the old rule that invoice-value earning needed a till at all (spec
        # §9.3, till-integration gate retired 2026-09-08). `quantities` absent for a service means
        # ONE of it, the same reading `is_group_basket` and the seams event already give that dict
        # everywhere else. A service worth 0 (unpriced, or a legitimate freebie) contributes
        # nothing to the sum — not an error, same as loyalty's own "no points configured" isn't
        # one (earn.py). An integrated till's own total (`total_minor` already positive) is never
        # overridden — it is the real amount paid, which can legitimately differ from the
        # catalogue's list prices (a discount, a tip, a tax line the till itself applies).
        if total_minor <= 0:
            priced = {s.id: s.price_minor for s in await self._services.list(tenant, active_only=False)}
            total_minor = sum(
                priced.get(sid, 0) * max(1, int((quantities or {}).get(sid, 1)))
                for sid in service_ids)

        visit = Visit(id=new_id("vis"), tenant=tenant, customer_id=customer.id,
                      service_ids=list(service_ids), asset_id=asset_id, operator_id=operator_id,
                      branch_id=branch_id, meter=meter, note=note.strip(),
                      custom_service=custom_service.strip()[:200],
                      # ONLY WHAT THIS VISIT ACTUALLY HELD. A count for a service that is not on
                      # the visit would be a fact about nothing, and `is_group_basket` reads the
                      # values alone — one stray entry would mark an honest receipt as a party.
                      total_minor=max(0, int(total_minor or 0)),
                      quantities={k: int(v) for k, v in (quantities or {}).items()
                                  if k in set(service_ids) and int(v) > 0},
                      free=bool(free), package_id=package_id,
                      idempotency_key=idempotency_key, created=now,
                      occurred_at=_sane_occurred_at(occurred_at, now,
                                                                    self._max_backdate))

        # last_visit follows the EVENT time, not the receive time: a batch drained two days late
        # describes a customer who was here two days ago, and the reminder must be scheduled from
        # when they were actually here.
        #
        # It only moves FORWARD. A replayed old visit arriving after a newer one must not drag the
        # customer's last-visit date backwards, which would schedule a reminder that has already
        # passed and mark a returning customer as absent.
        # The counters live on the customer so the recent-customers strip is one read. Updated
        # here rather than derived, because deriving them would put a scan on every keystroke.
        # ── THE VISIT IS WRITTEN FIRST, AND THE COUNTERS SAY WHAT THEY HAVE COUNTED (ز-6) ──────
        # THE OLD ORDER RAISED THE COUNTER FOR A VISIT THAT MIGHT NEVER BE WRITTEN. `save(customer)`
        # came before `save(visit)`, so a failure on the second write left a customer with a visit
        # count of nine and eight visits, and a `last_visit` that scheduled a reminder from a visit
        # nobody could find. No reconciliation existed to notice — the points ledger has one, this
        # does not.
        #
        # AND THE RETRY MADE IT WORSE, NOT BETTER. The duplicate guard reads the idempotency key
        # off the VISIT rows. The visit was never written, so there was no key, so the second
        # attempt was not a retry at all: it raised the counter a SECOND time.
        #
        # So the visit goes first — it is the fact, and everything else is derived from it — and
        # the increment then asks a question it can answer after a crash: «have I already counted
        # this visit?» rather than «is this my first attempt?». A crash between the two leaves the
        # visit recorded and the counter behind, which the retry below completes; a retry after a
        # success finds its own id already stamped and changes nothing.
        await self._visits.save(visit)

        # LOCKED WHEN THE CUSTOMER ALREADY EXISTED — a real gap a QA audit found (2026-09-12):
        # two genuinely distinct visits for the SAME customer (two operators, two branches, near-
        # simultaneously) could both read the same `visit_count`, both increment locally, and the
        # later `save()` silently overwrite the earlier one — an undercount with no reconciliation
        # sweep. See core/customer_counter_lock.py's own module docstring. NOT needed for a
        # customer THIS call just created (`created_customer`): no other caller can reference an
        # id that does not exist anywhere else yet, so there is nothing to race.
        if created_customer:
            moved_forward = visit.occurred_at >= customer.last_visit
            customer.last_visit = max(customer.last_visit, visit.occurred_at)
            customer.visit_count += 1
            customer.counted_visit_id = visit.id
            if moved_forward and visit.branch_id:
                customer.last_branch_id = visit.branch_id
            await self._customers.save(customer)
        else:
            from app.core.customer_counter_lock import CustomerCounterLock
            async with CustomerCounterLock(self._cache, tenant, customer.id):
                # RE-READ INSIDE THE LOCK — `customer` above was fetched before the lock was
                # taken, and may already be stale if another writer finished in between.
                fresh = await self._customers.get(tenant, customer.id)
                customer = fresh if fresh is not None else customer
                # THE BRANCH FOLLOWS THE SAME CLOCK AS `last_visit`, and only when the visit is
                # the newest one. A batch replayed from last month must not tell a campaign that
                # this customer's branch is the one they left — the field means «آخر فرع», so a
                # stale visit may not set it.
                #
                # An empty branch does not overwrite a known one either: a till that sends no
                # branch is saying nothing about where the customer is, not that they are now
                # nowhere.
                moved_forward = visit.occurred_at >= customer.last_visit
                customer.last_visit = max(customer.last_visit, visit.occurred_at)
                customer.visit_count += 1
                customer.counted_visit_id = visit.id
                if moved_forward and visit.branch_id:
                    customer.last_branch_id = visit.branch_id
                await self._customers.save(customer)

        # THE MUTUAL-BENEFIT HOOK — never allowed to affect this visit either way. Any
        # failure here (a bad row, a peer outage) is swallowed at this call site, not inside the
        # engine's own contract, so a bug in a completely different paid app can never cost a shop
        # the one fact this product cannot survive losing: the visit itself. See
        # core/mutual_benefit.py's own module docstring for why this is the single hook every
        # channel needs.
        new_mutual_benefit_grant = None
        if self._mutual_benefit_engine is not None:
            try:
                new_mutual_benefit_grant = await self._mutual_benefit_engine.on_visit_recorded(
                    tenant=tenant, customer_phone=customer.phone, service_ids=list(service_ids),
                    total_minor=int(total_minor or 0), visit_id=visit.id)
            except Exception:                                                  # noqa: BLE001
                pass

        # THE REFERRAL HOOK — see `_register_referral_if_new`'s own docstring.
        referral_registration = await self._register_referral_if_new(
            tenant, created_customer=created_customer, phone=customer.phone,
            referral_code=referral_code, invoice_minor=int(total_minor or 0),
            actor=operator_id or "field")

        # THE "جماعي" MILESTONE HOOK — the SAME single choke point every channel (field screen,
        # integrated till, bookings) already reaches for the mutual-benefit hook above, extended
        # to a second, separate service. Swallowed here too, and ALSO inside the peer itself
        # (`HttpMilestonePeer.on_visit_recorded` never raises) — belt and braces, the same double
        # guard the mutual-benefit block already has, because this is a completely different paid
        # feature and a bug in it must never cost a shop the one fact this product cannot survive
        # losing: the visit itself.
        if self._milestone_peer is not None:
            try:
                await self._milestone_peer.on_visit_recorded(
                    tenant=tenant, subject_ref=customer.subject_ref,
                    service_ids=list(service_ids), package_id=package_id,
                    occurred_at=visit.occurred_at)
            except Exception:                                                  # noqa: BLE001
                pass

        return RecordedVisit(visit=visit, customer=customer,
                             created_customer=created_customer, duplicate=False,
                             new_mutual_benefit_grant=new_mutual_benefit_grant,
                             referral_registration=referral_registration,
                             unknown_services=unknown,
                             # ALL OF THEM, not just this visit's. One number can hold two cars —
                             # «ممكن عندي سيارتين برقمي» — and an index written with only the plate
                             # in front of us would make the other car unfindable until the day it
                             # happens to come in.
                             plates=[a.plate for a
                                     in await self._assets.for_customer(tenant, customer.id)
                                     if a.plate])

    async def _resolve_asset(self, tenant: str, customer_id: str, plate: str) -> str:
        """Find this customer's vehicle by plate, or create it.

        Matched WITHIN the customer, not across the tenant. Two customers may present the same
        plate — a sold car, a company vehicle, a transcription error — and attaching a visit to the
        wrong person's car is worse than holding the plate twice.
        """
        for a in await self._assets.for_customer(tenant, customer_id):
            if a.plate == plate:
                return a.id
        asset = Asset(id=new_id("ast"), tenant=tenant, customer_id=customer_id, plate=plate,
                      created=_now())
        await self._assets.save(asset)
        return asset.id

    # ── the read path ─────────────────────────────────────────────────────────────────────────
    async def recent_customers(self, tenant: str, limit: int = 10) -> list[Customer]:
        return await self._customers.recent(tenant, limit=limit)

    async def ratings(self, tenant: str, *, stars: int | None = None, handled: bool | None = None,
                      branch_id: str = "", limit: int = 50, after: str | None = None
                      ) -> tuple[list[Visit], str | None]:
        """The console's «التقييمات» tab — see VisitStore.ratings' own docstring for the filter
        shape and its one known pagination limitation (handled=True)."""
        return await self._visits.ratings(tenant, stars=stars, handled=handled,
                                          branch_id=branch_id, limit=limit, after=after)

    async def mark_rating_handled(self, tenant: str, visit_id: str, note: str = "") -> Visit:
        """Record that a human read this rating and did something about it — never automatic
        (see Visit.rating_handled_at's own docstring). Refuses a visit that carries no rating at
        all rather than silently "handling" nothing, and a visit from another tenant is simply
        not found (the same tenant-scoped `get` every other route here uses)."""
        v = await self._visits.get(tenant, visit_id)
        if v is None:
            raise OperationError("الزيارة غير موجودة.")
        if not v.rating:
            raise OperationError("هذي الزيارة ما فيها تقييم لتُعالَج.")
        v.rating_handled_at = _now()
        v.rating_handled_note = (note or "").strip()
        await self._visits.save(v)
        return v

    async def staff_performance(self, tenant: str, *, since: int, until: int, branch_id: str = ""
                                ) -> list[dict[str, Any]]:
        """Per-operator comparison for the rating app's own report (a shop owner asking "who is
        earning me my reputation, and who is spending it") — one row per operator who recorded at
        least one visit in `[since, until]`, each carrying `operator_id`, `operator_name`,
        `visits` (handled in this window), `ratings` (how many of those were rated),
        `average_rating` (0.0 when `ratings` is 0 — never a divide-by-zero, never a misleading 5.0
        default). Sorted by `average_rating` descending, ties broken by `visits` descending, so the
        leaderboard reads correctly without the console re-sorting it.

        NO-SHOW RATE IS NOT HERE — it lives in `bookings`, a different service and a different
        aggregate root (`Booking`, not `Visit`); the route that serves this report calls
        `bookings_desk.no_show_summary` separately and merges it in, the same "ask the service that
        owns the fact" split `_branch_for`'s own operator-vs-device split already follows.

        Every operator this tenant has ever had is named, even one retired or with zero visits in
        this window is simply absent from the result (not a zero-row) — same "absence is the
        answer" shape `ratings_summary` uses for an empty week.
        """
        by_operator = await self._visits.staff_performance(
            tenant, since=since, until=until, branch_id=branch_id)
        if not by_operator:
            return []
        operators = await self._operators.list(tenant)
        names = {op.id: op.name for op in operators}
        rows: list[dict[str, Any]] = []
        for op_id, counts in by_operator.items():
            ratings = counts["ratings"]
            rows.append({
                "operator_id": op_id,
                "operator_name": names.get(op_id, ""),
                "visits": counts["visits"],
                "ratings": ratings,
                "average_rating": round(counts["rating_sum"] / ratings, 1) if ratings else 0.0,
            })
        rows.sort(key=lambda r: (r["average_rating"], r["visits"]), reverse=True)
        return rows

    async def customers_by_refs(self, tenant: str, refs: set[str]) -> list[Customer]:
        """The join reminders cannot make: pseudonyms to customers, inside one establishment."""
        return await self._customers.by_refs(tenant, refs)

    async def customers_by_ids(self, tenant: str, ids: set[str]) -> dict[str, Customer]:
        """The ratings list's own enrichment — each rating names the customer who left it, by
        their own `Visit.customer_id`, not a pseudonym. See `CustomerStore.get_many`'s own note on
        why this is direct gets rather than `customers_by_refs`'s full-table drain."""
        return await self._customers.get_many(tenant, ids)

    async def operator_names(self, tenant: str, ids: set[str]) -> dict[str, str]:
        """Same lookup `staff_performance` already makes (`self._operators.list` + a name dict),
        lifted out so the ratings list can name who served each customer too, without listing
        every operator this shop has ever had for a caller that only needs a handful of names."""
        if not ids:
            return {}
        operators = await self._operators.list(tenant)
        return {op.id: op.name for op in operators if op.id in ids}

    async def customer_by_phone(self, tenant: str, phone: str) -> Customer | None:
        return await self._customers.by_phone(tenant, _normalise_phone(phone))

    async def customer_by_phone_searched(self, tenant: str, phone: str) -> Customer | None:
        """The SAME lookup as `customer_by_phone`, for the one caller that deserves the weaker
        role: `GET /customers/by-phone`, the human-driven search screen an insider could abuse
        (see customer.searched_by_phone in auditable_actions.py — the audit half of this same
        defence). Visit recording and every other internal caller keeps calling
        `customer_by_phone` unchanged; this is not a replacement for it.

        TWO STEPS, ON PURPOSE, WHEN THE WEAKER ROLE IS WIRED: first find the matching row's KEY
        under a role that can see nothing but (tenant, phone, key) for customers — never a name,
        never a subject_ref, never any other collection — then fetch the full record through the
        normal, already-trusted store. A single-step query under the weak role could not return
        this route's actual response (the customer's name and subject_ref) at all; splitting it is
        what lets the risky half of the query — matching an arbitrary string against every phone
        number — run under a role with almost nothing to lose if it is ever misused.
        """
        phone = _normalise_phone(phone)
        if self._phone_search_ro is None:
            return await self._customers.by_phone(tenant, phone)
        key = await self._phone_search_ro.find_key_by_phone(tenant, phone)
        if key is None:
            return None
        return await self._customers.get(tenant, key)

    async def customer_success_flags(self, tenant: str, *, created_at: float,
                                     now: float, stall_seconds: int) -> dict[str, bool]:
        """The two real, checkable "this shop may need us to reach out" signals — nothing fuzzier.

        `no_services_after_stall`: signed up more than `stall_seconds` ago and has not added a
        single active service — the earliest possible stall, before there is even a catalogue to
        book against. `has_services_no_visits`: has a real catalogue, but not one visit has ever
        been recorded — the shop set up but never actually started using the product day to day.
        The two are deliberately exclusive in READING (a shop with no services cannot also be read
        as "has services, no visits" — that would double-count the same underlying gap under two
        different labels), though nothing stops both fields from being independently computed.

        ONE tenant at a time, TWO bounded existence reads (`has_any_active`/`has_any`) — never a
        count, never `list()`'s own 200-row page. The caller (the platform-wide scan) runs this
        once per tenant from a list it already holds capped at TENANT_LIST_LIMIT, so the total
        cost is bounded by that cap, not by how many services or visits a shop has accumulated.
        """
        has_services = await self._services.has_any_active(tenant)
        stalled_signup = (not has_services) and (now - created_at) >= stall_seconds
        has_visits = await self._visits.has_any(tenant) if has_services else False
        return {
            "no_services_after_stall": stalled_signup,
            "has_services_no_visits": has_services and not has_visits,
        }

    async def _resolve_customer(self, tenant: str, phone: str, name: str,
                                source: str = "manual") -> tuple[Customer, bool]:
        """Find this phone's customer, or build a new (UNSAVED) one. Returns (customer, created).

        EXTRACTED FROM `record_visit`, WHICH USED TO BE THE ONLY CALLER — and this is the whole
        reason it exists rather than being reimplemented at a second call site. `bookings`' console
        dialog needs "resolve or create a customer for this phone" without a visit attached to it
        (docs/خطة-تنفيذ-الحجوزات.md §6.2: "نفس الفعل الخلفي الذي يستعمله VisitIn, لا إعادة
        تنفيذ"), and duplicating this logic for that path is exactly the kind of copy-and-drift
        this file itself is the one place meant to prevent.

        `source` ONLY EVER APPLIES ON THE BRANCH THAT CREATES A ROW — an existing customer keeps
        whatever channel first brought him in, no matter who resolves him next (see Customer.source's
        own docstring on why this must never move after creation).

        NOT SAVED HERE. The caller decides when: `record_visit` saves once, at the end, together
        with the visit-count update; `ensure_customer` below saves immediately because there is no
        visit to save alongside.
        """
        customer = await self._customers.by_phone(tenant, phone)
        created = customer is None
        if customer is None:
            customer = Customer(
                id=new_id("cus"), tenant=tenant, phone=phone,
                subject_ref=subject_ref(self._salt, tenant, phone),
                name=name.strip(), created=_now(), source=source or "manual")
        elif name.strip() and not customer.name:
            # A name arriving later fills a blank, but never overwrites one already there. The
            # operator typing today does not know what the operator typed last month, and the
            # older value was entered with the customer present just as this one is.
            customer.name = name.strip()
        return customer, created

    async def ensure_customer(self, tenant: str, phone: str, name: str = "",
                              source: str = "manual", referral_code: str = "",
                              actor: str = "") -> tuple[Customer, dict | None]:
        """Resolve or create a customer by phone, with NO visit attached — the booking console's
        one call into this service before it has a `customer_id` to hand `bookings` (§6.2), and
        whatsapp-assistant's own auto-register call (`/internal/operations/customer-id-by-phone`).

        SAVED IMMEDIATELY, unlike `record_visit`'s deferred save: there is no visit-count update to
        batch it with, and a customer resolved-or-created here must exist the moment this returns —
        the caller's very next act is to pass the id to a different SERVICE.

        THIS IS ALSO THE REAL "NEW CUSTOMER" MOMENT FOR A BOOKING — unlike a walk-in visit, a
        booking's own attendance (`bookings`' `attend()` -> `/internal/operations/visits/from-
        customer`) happens against a customer who was already resolved-or-created HERE, days or
        weeks earlier, at booking time. So a referral code offered when the booking was first made
        is registered right here, not at attendance — by then `record_visit`'s own hook would see
        `created_customer=False` and never even try. Returns `(customer, referral_registration)`,
        the second `None` unless a code was actually offered — see
        `_register_referral_if_new`'s own docstring for the shape and the "never undo" posture.
        """
        phone = _normalise_phone(phone)
        if not phone:
            raise OperationError("رقم الجوال مطلوب، ولم نتعرّف على ما أُدخل — تأكّد أنه أرقام فقط")
        customer, created = await self._resolve_customer(tenant, phone, name, source)
        await self._customers.save(customer)
        referral_registration = await self._register_referral_if_new(
            tenant, created_customer=created, phone=customer.phone,
            referral_code=referral_code, invoice_minor=0, actor=actor or source)
        return customer, referral_registration

    async def rename_customer(self, tenant: str, customer_id: str, name: str) -> Customer | None:
        """Give a customer his name — the one edit an owner needs and could not make.

        THE NAME ARRIVES LATE BY DESIGN (§4.3): it is hard to ask a stranger his name while taking
        his key, and after five visits the operator simply knows it. The field never blocks a save,
        so most customers are created without one — and until now there was NO way to add it later.
        The owner recognising a regular on his screen had to sit and watch a row that said «بلا
        اسم» for ever.
        
        THE NAME ONLY. Not the phone: that is the identity every peer resolves him by, and letting
        it be edited turns one customer into two — the pseudonym is derived from it, so his points,
        his offers and his history would all stay behind with the old number. A wrong number is a
        new customer and a merge, not an edit.
        """
        c = await self._customers.get(tenant, customer_id)
        if c is None:
            return None
        # TRIMMED AND BOUNDED HERE, not trusted from the screen: this is also the till's route.
        c.name = (name or "").strip()[:120]
        await self._customers.save(c)
        return c

    async def customer_for_erasure(self, tenant: str, customer_id: str) -> Customer | None:
        """The row an erasure needs — which is the pseudonym, and nothing else about him.

        SEPARATE FROM `customer_record` ON PURPOSE. That one assembles his vehicles and his visits
        for a screen; this one is read immediately before his data is destroyed, and reading his
        history in order to delete it is work whose only product is a copy in a log line.
        """
        return await self._customers.get(tenant, customer_id)

    async def customer_by_plate(self, tenant: str, plate: str) -> Customer | None:
        """Whose car this is — the lookup a vehicle shop actually starts from (§4.3).

        THE PLATE IS THE IDENTITY THERE. The car rolls in, the operator reads the plate off it, and
        the number of the man who owns it is something we already hold — asking him for it again on
        every visit is asking a question we can answer ourselves.

        NOT UNIQUE, AND THAT IS ADMITTED. A plate is transcribed by a person, cars are sold, and
        two rows can carry the same one (see models.py). The most recently seen wins, because that
        is the car actually being worked on; a shop that finds the wrong owner corrects it by
        changing the number, which is one tap on the plate step.
        """
        if not plate.strip():
            return None
        assets = await self._assets.by_plate(tenant, plate.strip())
        if not assets:
            return None
        return await self._customers.get(tenant, assets[0].customer_id)

    async def customer_record(self, tenant: str, customer_id: str) -> dict[str, Any] | None:
        """A customer with their vehicles and recent visits — the screen an operator opens when a
        customer asks "when was I last here?"."""
        customer = await self._customers.get(tenant, customer_id)
        if customer is None:
            return None
        # INACTIVE ONES INCLUDED: a visit for a service the shop has since retired is still a
        # visit for that service, and «زيارة» في مكانها is the defect this closes.
        names = {s.id: s.name for s in await self._services.list(tenant, active_only=False)}
        visits = await self._visits.for_customer(tenant, customer_id)

        # WHICH PROCEDURE STEPS THIS CUSTOMER HAS FLAGGED, ACROSS EVERY VISIT — resolved to real
        # text here rather than sent as bare ids, same as the ratings-list route's own enrichment
        # ([[task-service-procedure-checklists]] phase 5). A retired step still resolves (never
        # deleted, only retired — ProcedureStepStore's own docstring).
        all_ids = {sid for v in visits for sid in v.rating_issue_step_ids}
        steps = await self._steps.get_many(tenant, list(all_ids))

        def _issue_steps(v) -> list[dict[str, Any]]:
            return [{"id": s.id, "text": s.text, "severity": s.severity}
                   for sid in v.rating_issue_step_ids if (s := steps.get(sid)) is not None]

        # THE PATTERN — the whole reason this exists (owner's own instruction, 2026-09-16):
        # "شكيت من نفس الشي أكثر من مرة", not a scoreboard of every flag ever raised. Only a step
        # this customer's OWN visits named MORE THAN ONCE counts as a pattern; a single complaint
        # is just a complaint. Sorted by how many times it repeated, most first.
        counts: dict[str, int] = {}
        for v in visits:
            for sid in set(v.rating_issue_step_ids):  # once per VISIT, never twice for one visit
                counts[sid] = counts.get(sid, 0) + 1
        repeated = sorted(
            ({"id": sid, "text": steps[sid].text, "severity": steps[sid].severity, "count": n}
             for sid, n in counts.items() if n > 1 and sid in steps),
            key=lambda r: r["count"], reverse=True)

        return {
            # THE PSEUDONYM TRAVELS WITH THIS ONE RECORD, and with nothing else.
            #
            # `public()` deliberately omits it: it is the shape the recent-customers strip and the
            # search results use, and a pseudonym in a list of fifty is fifty identifiers on a
            # screen that needed none. Here it is the join key — the console asks reminders which
            # offers this customer is holding, and reminders knows people only by this.
            #
            # It is not a secret from the owner: it is derived per establishment from his own
            # tenant, means nothing anywhere else, and cannot be turned back into a number.
            "customer": {**customer.public(), "subject_ref": customer.subject_ref},
            "assets": [a.public() for a in await self._assets.for_customer(tenant, customer_id)],
            # NAMED, NOT KEYED (ب-3). `public()` carries `service_ids`, and the owner's card
            # reads `services` — so twenty rows all read «زيارة», identically, and the shop's own
            # screen told him less than his customer's page did: the portal feed joins the same
            # names and always has. The join happens once for the whole record rather than per
            # row, which is why it is here and not in `public()`.
            "visits": [{**v.public(), "services": _labels(v, names), "rating_issue_steps": _issue_steps(v)}
                       for v in visits],
            "repeated_issues": repeated,
        }

    async def catalogue(self, tenant: str) -> list[dict[str, Any]]:
        return [s.public() for s in await self._services.list(tenant)]

    async def catalogue_packages(self, tenant: str) -> list[dict[str, Any]]:
        """The field screen's own package list — active AND offerable right now, never a package
        the owner has scheduled for a different day or hour (SCHED.is_offerable, the same test
        `/staff/packages` uses for its own `offerable_now` flag). A package outside its own window
        has no business on a counter screen: it cannot be sold this minute, and showing it invites
        exactly the tap it exists to prevent."""
        now = _now()
        return [p.public() for p in await self._packages.list(tenant) if SCHED.is_offerable(p, now)]

    async def package_by_id(self, tenant: str, package_id: str):
        return await self._packages.get(tenant, package_id)


def _labels(visit, names: dict[str, str]) -> str:
    """What this visit was, in his words — the same phrasing the customer's own page uses.

    Falls back to the catch-all's typed label, then to «زيارة», so a row is never blank: an empty
    line in a history reads as a broken record rather than as an unnamed service.
    """
    got = [names.get(sid, "") for sid in (visit.service_ids or [])]
    got = [x for x in got if x] or [(visit.custom_service or "").strip() or "زيارة"]
    return "، ".join(got[:3])


# A device clock may be wrong by days, and occasionally by years — a tablet that lost its battery
# comes back at the epoch, and one set by hand can land in the future. Both are clamped rather than
# trusted, because either would corrupt a reminder schedule silently.


def _sane_occurred_at(claimed: int, now: int,
                      max_backdate: int = _DEFAULT_MAX_BACKDATE_SECONDS) -> int:
    """Trust the device's clock only within a window we can defend.

    Not validation for its own sake: `occurred_at` is what reminders schedule from. A device set to
    next month would schedule a reminder into next month; one at the epoch would mark every
    customer permanently absent and trigger a win-back to somebody who was here this morning.
    """
    if claimed <= 0:
        return now
    if claimed > now:
        # A future timestamp is always wrong — we received it, so it has happened.
        return now
    if now - claimed > max_backdate:
        return now
    return claimed


def _normalise_phone(phone: str) -> str:
    """One stored form, so the same person is one customer however they were typed.

    A Saudi number arrives as 0501234567, 501234567, +966501234567 or 966501234567 depending on who
    is typing and what their keyboard did. Stored differently, they become four customers with one
    visit each instead of one customer with four — and the whole product is built on recognising
    the returning customer.

    Kept deliberately small and country-shaped rather than a general library: this is a Saudi
    product, and a general phone parser would accept forms that are certainly typos here.
    """
    # FOLD BEFORE FILTERING, AND FILTER ON 0-9 RATHER THAN `isdigit()`. This line used to read
    # `if c.isdigit()`, which is true of ARABIC-INDIC DIGIT FIVE — so an Arabic keyboard's digits
    # their own script, `startswith("966")` matched nothing, `lstrip("0")` stripped nothing, and the
    # number was stored exactly as typed. The same man on two keyboards became two customers, which
    # is the outcome the paragraph above exists to prevent.
    digits = "".join(c for c in western(phone) if c in WESTERN)
    if not digits:
        return ""
    if digits.startswith("00966"):
        digits = digits[5:]
    elif digits.startswith("966"):
        digits = digits[3:]
    digits = digits.lstrip("0")
    # A Saudi mobile is 5XXXXXXXX — nine digits starting with 5. Anything else is stored as typed
    # rather than refused: a landline, a foreign number, a genuine oddity. Refusing it would stop a
    # real visit being recorded to enforce a format nobody promised.
    return f"966{digits}" if len(digits) == 9 and digits.startswith("5") else digits
