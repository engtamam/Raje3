"""Opening a shop, and getting back into it — the two doors, and the four values behind them.

WHY THIS IS OURS AND NOT THE PLATFORM'S. identity-service registers a user INTO a tenant and logs
a user IN to a named tenant. Both take the tenant as an argument, and neither creates one. That is
correct for a platform: deciding that a signup means "a new establishment, with the person who
typed the form as its owner" is a product rule, and a product rule in a shared service stops being
shared.

So the platform keeps every hard part — the password hash, the E.164 folding, the lockout, the
mint — and this file supplies exactly the one thing it cannot know: which tenant.

────────────────────────────────────────────────────────────────────────────────────────────────
THREE VALUES TO OPEN A SHOP, AND NOT ONE MORE

    phone · password · shop name

The commercial register, the address, the VAT number and the branch list are all things we will
eventually want and none of them are things the owner has to hand at the moment he decides to try
this. Every extra field on this form is a person who closes the tab, and every one of them can be
asked later from a screen where it is obvious why.

THERE WERE FOUR, AND THE FOURTH WAS «نوع النشاط». It bought a seeded catalogue and a seeded rewards
table — both guessed from a trade we had never seen, so both wrong on their first day for any shop
that does two things, and correcting a guess is longer than writing the truth once. A shop now opens
empty and its owner writes what he actually sells.

────────────────────────────────────────────────────────────────────────────────────────────────
THE TENANT ID IS OURS TO MINT, NEVER HIS TO NAME

A slug derived from the shop name would be a takeover: two owners typing «بنشر النور» would land
in one tenant, and the second would register an account inside the first one's data. The id is
random and the NAME is what he sees, which costs nothing and closes the hole entirely.

────────────────────────────────────────────────────────────────────────────────────────────────
AND SIGNING IN AGAIN IS ONE FIELD SHORT

`/auth/login` needs a tenant. The owner does not know his tenant id and should never be shown it,
so this file keeps a phone → tenant index written at signup, resolves it, and forwards the login.

THE REFUSAL IS IDENTICAL EITHER WAY. An unknown phone and a wrong password produce the same
sentence and the same status, because a door that answers "no such shop" differently from "wrong
password" is a way to ask us which numbers have accounts — one request at a time, for free.

────────────────────────────────────────────────────────────────────────────────────────────────
THE SAGA, AND WHY THE ORDER IS THIS ORDER

    1. create the tenant        (tenant-service, internal)
    2. seed the owner           (identity, internal — the person AND the membership)
    3. bootstrap his roles      (authz, internal — v0.16.3)
    4. seed his catalogue       (ours, idempotent)

STEP 3 IS THE ONE THAT MAKES THE ACCOUNT USABLE, and it did not exist until the platform built it
for us. Without it every self-serve signup produced a token with `caps: []`: the owner signed up,
signed in, and found an empty application — every response a 2xx, nothing anywhere reporting a
fault. Capabilities come from ROLES, a fresh tenant has none, and creating one required a
capability only that role could grant. A closed cycle, and the platform's internal-tier bootstrap
is the one door through it.

A failure at 2 UNDOES 1. A FAILURE AT 3 UNDOES BOTH — an account that cannot do anything is worse
than no account: he cannot fix it, cannot be told why, and would try again with the same number
and be refused for existing. Better that the attempt leaves nothing behind. Without that, a person retrying a failed signup accumulates empty tenants
nobody owns and nobody will ever look for — the orphan the platform's own provisioner was rebuilt
to prevent. A failure at 3 does NOT undo anything: the account exists and works, and the catalogue
is repairable from a screen. Destroying a usable account because a seeding step timed out would be
the worse trade by a wide margin.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from app.core import claim as CL

PHONE_INDEX = "signup_phone_index"
#: THE SAME FACT, KEYED THE OTHER WAY (و-7). The phone index answers «which shop owns this
#: number»; the acts that must not run on an unproven number — binding the shop's WhatsApp above
#: all — know the TENANT and never the phone. Without this they would have to scan the index, and
#: a check nobody can afford to run is a check nobody runs.
TENANT_PROOF = "signup_tenant_proof"


class SignupRefused(Exception):
    """A rule of ours, or a refusal from a peer, in the sentence the owner reads.

    `reason` IS FOR THE SCREEN, NOT FOR THE PERSON. Most refusals are the end of the road and carry
    nothing; one of them — an unproven number — is a step the console can simply take him to. A
    screen cannot act on a sentence without matching Arabic text, which breaks the day somebody
    improves the wording, so the actionable ones carry a stable code beside it.
    """

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


def canonical_phone(raw: str, *, default_cc: str) -> str:
    """`0501234567`, `+966501234567` and `966501234567` are ONE human.

    Folded here as well as in identity, because this file keeps its own index and an index that
    disagrees with the platform's uniqueness rule is worse than no index: the account would exist
    and the login would say it does not.
    """
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0"):
        digits = default_cc + digits[1:]
    elif not digits.startswith(default_cc):
        digits = default_cc + digits
    return "+" + digits


@dataclass(frozen=True)
class NewShop:
    phone: str
    password: str
    shop_name: str
    # WHO BROUGHT IT, and empty means we did. Stamped at creation so attribution exists before the
    # first invoice, and written ONCE — a key arriving later is recorded and changes nothing, or a
    # till company that replaced another's software six months on would inherit its commission
    # (core/partners.py).
    #
    # A RAW KEY, ONLY WHEN THIS FIELD IS SET DIRECTLY BY A CALLER THAT HOLDS ONE. `claim()` never
    # sets it — it passes `partner_id` below, already resolved (ك-5).
    partner_key: str = ""
    # THE RESOLVED ID, for a claim that already looked its key up at invite time. Takes priority
    # over `partner_key` in `open_shop` when both could apply, since a caller that resolved the key
    # already spent the round trip a raw key would repeat.
    partner_id: str = ""
    # The till sends this shop's catalogue, so its services arrive from its own invoices (§4.2).
    integrated: bool = False
    # WHO BROUGHT IT, the affiliate portal's own attribution — an affiliate id read from the
    # console's own `?aff=` link parameter, never a partner_key/partner_id (see this class'
    # own note on those two fields: this is a SEPARATE relationship, stamped at a separate
    # service). Empty means no affiliate link was used; that is not an error, most shops sign up
    # with no link at all.
    affiliate_ref: str = ""


class Http:
    """One tiny client, because three calls do not earn a dependency.

    urllib rather than httpx to match connect.py: this service already reaches its peers this way
    and a second HTTP idiom in the same codebase is a second set of timeout and error behaviour to
    keep in step.
    """

    def __init__(self, *, timeout: int = 10, internal_token: str = "") -> None:
        self._timeout = timeout
        self._token = internal_token

    def call(self, url: str, *, method: str, body: dict | None = None,
             internal: bool = False) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if internal:
            headers["X-Internal-Token"] = self._token
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else {})
        except urllib.error.HTTPError as exc:
            try:
                parsed = json.loads(exc.read() or b"{}")
            except Exception:                                                 # noqa: BLE001
                parsed = {}
            return exc.code, parsed if isinstance(parsed, dict) else {}
        except Exception as exc:                                              # noqa: BLE001
            return 0, {"detail": str(exc)[:200]}


class SignupService:
    def __init__(self, *, store, http: Http, identity_url: str, tenants_url: str,
                 authz_url: str = "", loyalty_url: str = "", compliance_url: str = "",
                 affiliate_url: str = "", ticket_url: str = "",
                 affiliate_ticket_scope_types: str = "",
                 data_map: list[str] | None = None,
                 roles: list[dict[str, Any]] | None = None,
                 partners=None,
                 owner_role: str = "owner",
                 default_cc: str = "966", otp_deliverable: bool = False,
                 require_otp: bool = True, telemetry=None) -> None:
        self._store = store
        self._http = http
        self._identity = identity_url.rstrip("/")
        self._tenants = tenants_url.rstrip("/")
        self._authz = authz_url.rstrip("/")
        # Optional on purpose: a deployment without loyalty seeds a catalogue and no rewards, which
        # is a shop missing a table rather than a signup that fails.
        self._loyalty = loyalty_url.rstrip("/")
        # Optional too: a shop signing up with no `?aff=` link never calls this at all, and a
        # deployment with no affiliate portal simply never sets it.
        self._affiliate = affiliate_url.rstrip("/")
        # spec §13's consent grant — same optional trade as `_affiliate` just above. A shop with
        # no affiliate_ref, or a deployment with no ticket-service/no affiliate portal, never
        # calls this at all.
        self._tickets = ticket_url.rstrip("/")
        self._affiliate_ticket_scope_types = [
            t.strip() for t in affiliate_ticket_scope_types.split(",") if t.strip()]
        # WHERE THIS SHOP'S DATA WILL LIVE, declared as configuration rather than written here.
        # Every entry is "service:category", and the set is a property of what we have deployed —
        # a service added next month must not need a release of this file.
        self._compliance = compliance_url.rstrip("/")
        self._data_map = list(data_map or [])
        self._roles = list(roles or [])
        self._partners = partners
        # AN INCOMPLETE DATA MAP HAS TO BE AUDIBLE SOMEWHERE. See `_register_data_map`: it was
        # returned as a string in a response body nobody reads, and the consequence is a PDPL
        # erasure that reports COMPLETED while a whole service's copy is never touched.
        self._telemetry = telemetry
        self._claims = CL.Claims(store)
        self._owner_role = owner_role
        self._cc = default_cc
        self._can_deliver = otp_deliverable
        self._require_otp = require_otp

    # ── the index ────────────────────────────────────────────────────────────────────────────
    async def tenant_of_phone(self, phone: str) -> str:
        row = await self._store.get(PHONE_INDEX, canonical_phone(phone, default_cc=self._cc))
        return str((row or {}).get("tenant") or "")

    async def _remember(self, phone: str, tenant: str) -> None:
        key = canonical_phone(phone, default_cc=self._cc)
        # `verified` STARTS FALSE, and the row is the only place that fact lives. identity issues
        # and consumes the code but records nothing about it — see `prove` for why that had to be
        # closed here rather than left to the client.
        await self._store.put(PHONE_INDEX, key,
                              {"id": key, "tenant": tenant, "verified": False})
        await self._store.put(TENANT_PROOF, tenant,
                              {"id": tenant, "phone": key, "verified": False})

    async def _row(self, phone: str) -> dict[str, Any] | None:
        return await self._store.get(PHONE_INDEX, canonical_phone(phone, default_cc=self._cc))

    # ── opening a shop ───────────────────────────────────────────────────────────────────────
    async def open_shop(self, shop: NewShop) -> dict[str, Any]:
        phone = canonical_phone(shop.phone, default_cc=self._cc)
        if not phone:
            raise SignupRefused("أدخل رقم جوال صحيح.")
        if not (shop.shop_name or "").strip():
            raise SignupRefused("أدخل اسم المحل.")
        held = await self._row(phone)
        if held:
            # THE ONE PLACE THIS IS SAFE TO SAY. Signup already reveals that a number is taken by
            # refusing to create a second account for it — the platform's uniqueness does that
            # whatever we answer — so a clear sentence here costs nothing and saves a person from
            # trying four passwords on a door they already have a key to.
            #
            # BUT «سجّل الدخول» IS ONLY TRUE IF SOMEBODY PROVED THIS NUMBER (و-7). Nothing stands
            # between typing a number and an account being created on it — the proof is deferred
            # to sign-in — so a stranger can open a shop on a number he does not hold. Everything
            # after that lands on the person who does: he is refused here, told to sign in with a
            # password he never chose, and has no way through. The account is useless to whoever
            # made it (the same unproven number blocks HIS sign-in) — so the whole thing is a lock
            # on somebody else's door with the key thrown away.
            #
            # Told apart, and each state gets its own true sentence. The full fix is that a number
            # is not reserved until it is proven, and that waits on being able to send a code at
            # all (SIGNUP_OTP_DELIVERABLE, task #167).
            if held.get("verified"):
                raise SignupRefused("لهذا الرقم حساب بالفعل — سجّل الدخول.")
            raise SignupRefused(
                "هذا الرقم مُسجَّل في طلبٍ لم يكتمل تأكيده. تواصل معنا لنُكمله معك.",
                reason="unverified_hold")

        slug = "t-" + uuid.uuid4().hex[:16]

        status, body = self._http.call(
            f"{self._tenants}/internal/tenants", method="POST", internal=True,
            body={"slug": slug, "name": shop.shop_name.strip()})
        if status != 201:
            # 409 IS NOT SUCCESS HERE, and that differs from the platform's provisioner. There a
            # repeated slug means "already ours" because the slug was derived deterministically;
            # ours is random, so a collision is a fault rather than a retry.
            raise SignupRefused(_why(status, body, "تعذّر إنشاء المحل. حاول بعد قليل."))
        # THE ID THE REGISTRY MINTED, not the slug we asked for. They are normally the same string;
        # when they are not, every later call keyed on the slug would address a tenant that does
        # not exist, and the account would be created inside nothing.
        tenant = str(body.get("id") or slug)

        # SEED-OWNER, NOT REGISTER — and the difference is the whole reason a signup produces a
        # usable account rather than an empty one.
        #
        # `/auth/register` creates a USER row, and a user row's capabilities are whatever sits in
        # the row itself: the single-tenant mint copies them straight into the token and asks authz
        # nothing. So a role assigned in authz has no way to reach the token, and a live signup
        # showed exactly that — authz answering a role's twenty-two capabilities when asked, and
        # the minted token carrying none.
        #
        # `/internal/tenancy/seed-owner` creates the PERSON and the MEMBERSHIP that hold the role,
        # and the membership mint DERIVES capabilities from it at every issue. It is the platform's
        # own chicken-and-egg breaker: a fresh tenant has nobody holding `members:write`, so no
        # user-tier route can add its first admin, and this internal-tier door does — while
        # refusing to overwrite an owner on a tenant that already has one.
        status, body = self._http.call(
            f"{self._identity}/internal/tenancy/seed-owner", method="POST", internal=True,
            body={"tenant": tenant, "identifier": phone, "roles": [self._owner_role],
                  "password": shop.password,
                  # REFUSE RATHER THAN REPLACE. The tenant was created moments ago so it is empty,
                  # and if it somehow is not, a second owner is a takeover and not a retry.
                  "only_if_empty": True})
        if status not in (200, 201):
            # UNDO STEP 1. See the module note: an orphan tenant is invisible and permanent.
            self._http.call(f"{self._tenants}/internal/tenants/{tenant}",
                            method="DELETE", internal=True)
            raise SignupRefused(_register_error(status, body))

        # ── 3. the roles, and the owner made an owner ────────────────────────────────────────
        # THE PERSON'S ID, which is what a membership token's `sub` will be. seed-owner returns
        # `person_id` alongside an undo reference shaped `tenant::person_id`.
        person_id = str(body.get("person_id") or "")
        if not await self._bootstrap_roles(tenant, subject=person_id):
            # BOTH UNDONE — AND FOR A LONG TIME ONLY ONE WAS. This comment said «both» and the code
            # deleted the tenant alone, so the person and the membership seed-owner had just
            # created lived on with no tenant behind them. His number was then spoken for at
            # identity and unknown to us: signing up again answers «هذا الرقم مسجّل», signing in
            # answers «الرقم أو كلمة المرور غير صحيحة», and nothing anywhere can be repaired from a
            # screen. The number is reserved against him for ever, by a failure that was ours.
            #
            # ORDER: the membership first, because it is the half that makes the number look taken.
            # Neither undo may raise — we are already on the failure path, and a rollback that
            # throws replaces a clear refusal with a 500.
            try:
                await self.revoke(tenant, person_id)
            except Exception:                                                 # noqa: BLE001
                pass
            self._http.call(f"{self._tenants}/internal/tenants/{tenant}",
                            method="DELETE", internal=True)
            raise SignupRefused("تعذّر إنشاء الحساب. حاول بعد قليل.")

        await self._remember(phone, tenant)

        # NOTHING IS SEEDED INTO HIS CATALOGUE. It used to be filled from the trade he picked, and
        # that guess was wrong from day one for every shop that did two things — so «خدماتي» opens
        # empty and invites him to write what he sells, which is one screen of work and is TRUE.
        seeded = 0

        # AND HIS MAIN BRANCH, named after the shop he just typed. Same trade as the catalogue:
        # never undone, because a shop with no branch row works — every branch field is optional
        # (§12.2) — and the row is repairable. What it prevents is a first month of visits with no
        # place on them, which no later purchase can reconstruct.
        await self._seed_main_branch(tenant, shop_name=shop.shop_name)

        # HIS DATA MAP, AND PDPL IS THE REASON IT IS HERE AND NOT LATER.
        #
        # `DsarService.dispatch` refuses with NO_DATA_TARGETS_REGISTERED on an empty map, so until
        # this runs NO export and NO erasure can complete for this shop — his customers hold a
        # right we could not exercise. The refusal is honest rather than a false "done", which is
        # why the gap was survivable; it was never acceptable.
        #
        # AT SIGNUP, because it is the moment the map is certainly whole: the tenant exists, every
        # service that will hold his data is known, and nothing has had a chance to remove one.
        #
        # THE OWNER DOES HOLD `compliance.manage`, and that is deliberate — the erasure button
        # travels on his token so the act is his and we cannot erase a customer of a shop that
        # did not ask (core/erase_customer.py). The same capability grants DELETE on data
        # targets, so the map he narrows is his own; `reassert_data_map` restores it before any
        # fan-out, and `ci/check_an_erasure_reasserts_the_map.py` keeps the two together.
        #
        # NOT UNDONE ON FAILURE, and reported instead. A shop whose map is incomplete works and is
        # repairable from our panel; deleting a working account over one unreachable peer is the
        # worse trade — the same call the catalogue and the rewards table make above.
        map_error = await self._register_data_map(tenant)

        # THE STAMP, AND A BAD KEY DOES NOT COST HIM HIS SHOP. Attribution is our commercial
        # bookkeeping; failing a signup over a mistyped partner key would punish the owner for a
        # mistake made by his till company. Reported here for an operator to act on — never in the
        # response, which is HIS answer, not ours: he did not type the key, cannot fix it, and «unknown
        # partner key» is an English sentence about a company he has never heard of.
        #
        # THIS USED TO RETURN THE STRING TO THE ROUTE, and the route spread it straight into the
        # owner's signup answer (ك-4) — with no audit row and no telemetry, so the one party who
        # could actually repair the stamp never learned it needed repairing. It follows
        # `_register_data_map`'s own pattern below exactly.
        stamp_error = ""
        if self._partners is not None:
            try:
                if shop.partner_id:
                    await self._partners.stamp_by_partner_id(tenant, partner_id=shop.partner_id)
                else:
                    await self._partners.stamp(tenant, key=shop.partner_key)
            except Exception as exc:                                          # noqa: BLE001
                stamp_error = str(exc)[:200]
                if self._telemetry is not None:
                    try:
                        self._telemetry.event("partner_stamp_failed", tenant=tenant,
                                              reason=stamp_error)
                    except Exception:                                          # noqa: BLE001
                        pass    # a telemetry failure must not fail a signup

        # THE AFFILIATE STAMP — same trade as the partner stamp two paragraphs up, for the same
        # reason: an owner who followed a marketer's link did not type an affiliate id, cannot fix
        # a stale or mistyped one, and must not lose his shop over our own attribution bookkeeping.
        # `affiliate-service` decides everything about whether the id is real and still active
        # (core/referrals.py) — this call only hands over the raw fact, once, best-effort.
        affiliate_error = ""
        if self._affiliate and shop.affiliate_ref:
            status, body = self._http.call(
                f"{self._affiliate}/internal/referrals/stamp", method="POST", internal=True,
                body={"tenant": tenant, "affiliate_id": shop.affiliate_ref,
                      "shop_name": shop.shop_name,
                      # spec §2's anti-self-referral check needs this to compare against; see
                      # affiliate-service's own core/referrals.py::stamp for the actual rule.
                      "shop_owner_phone": phone})
            if status not in (200, 201):
                affiliate_error = str((body or {}).get("detail") or f"status {status}")[:200]
                if self._telemetry is not None:
                    try:
                        self._telemetry.event("affiliate_stamp_failed", tenant=tenant,
                                              reason=affiliate_error)
                    except Exception:                                          # noqa: BLE001
                        pass    # a telemetry failure must not fail a signup
            elif self._tickets:
                # spec §13: THE SHOP'S OWN CONSENT, given at the moment it signs up through a
                # marketer's link — not asked for separately later. `granted_by=phone` is the
                # shop owner's own number, the same fact `shop_owner_phone` above already
                # asserts; ticket-service stores it only as a per-tenant pseudonym (its own
                # core/share.py). Best-effort, same "our own attribution bookkeeping must never
                # cost an owner his shop" reasoning as the stamp call itself two lines up — a
                # ticket-service hiccup here is a missing convenience, never a failed signup.
                scope = ({"type": self._affiliate_ticket_scope_types}
                        if self._affiliate_ticket_scope_types else {})
                s2, b2 = self._http.call(
                    f"{self._tickets}/internal/tickets/shares", method="POST", internal=True,
                    body={"tenant": tenant, "grantee": shop.affiliate_ref,
                         "granted_by": phone, "scope": scope})
                if s2 not in (200, 201) and self._telemetry is not None:
                    try:
                        self._telemetry.event(
                            "affiliate_ticket_share_failed", tenant=tenant,
                            reason=str((b2 or {}).get("detail") or f"status {s2}")[:200])
                    except Exception:                                          # noqa: BLE001
                        pass    # a telemetry failure must not fail a signup

        return {"tenant": tenant, "phone": phone, "services": seeded,
                "stamp_error": stamp_error, "data_map_error": map_error,
                "affiliate_stamp_error": affiliate_error}

    async def reassert_data_map(self, tenant: str) -> str:
        """Re-register this tenant's data map, and say what could not be registered.

        CALLED BEFORE AN ERASURE, because the map is the only thing that decides how far one
        reaches. Signup writes it once; nothing has ever re-read it since, and the shop's own owner
        holds `compliance.manage` — which he needs, since the erasure travels on his token — and
        that capability also grants DELETE on those targets. A map narrowed at any point between
        signup and today makes every erasure afterwards close COMPLETED over less than everything.

        The registration is idempotent, so this restores rather than duplicates. Returns "" when
        the map is whole — the caller refuses on anything else.
        """
        return await self._register_data_map(tenant)

    async def _register_data_map(self, tenant: str) -> str:
        """Tell compliance which services hold this tenant's data. Never raises.

        IDEMPOTENT BY THE STORE'S OWN RULE, so a retried signup is harmless. Each target is sent
        separately: one unknown name must not cost the other twenty-two, and the reply names which
        one it was — a service in our list that compliance cannot reach is a deployment drifting
        from its configuration, which is worth seeing rather than swallowing.
        """
        if not self._compliance or not self._data_map:
            return ""
        failed: list[str] = []
        for entry in self._data_map:
            service, _, category = entry.partition(":")
            if not service or not category:
                failed.append(entry)
                continue
            status, _body = self._http.call(
                f"{self._compliance}/internal/compliance/data-targets", method="POST",
                internal=True,
                body={"tenant": tenant, "service": service.strip(),
                      "category": category.strip()})
            if status >= 300:
                failed.append(f"{entry}={status}")

        # SAID OUT LOUD, because the alternative is the quietest compliance failure we have.
        #
        # This used to return a string into the signup response and stop there — no audit row, no
        # telemetry, no screen. A shop registered while compliance was briefly unreachable for ONE
        # entry keeps a data map missing that service for ever. Every later erasure then fans out
        # to the registered targets only, all of them acknowledge, and `derive_completion` closes
        # the request as COMPLETED — while the customer's records in the missing service are never
        # touched. The customer is told his data is gone. It is not.
        #
        # A REPAIR IS POSSIBLE AND CHEAP; noticing was the missing half.
        if failed and self._telemetry is not None:
            try:
                self._telemetry.event("data_map_incomplete", tenant=tenant,
                                      missing=", ".join(failed)[:200], count=len(failed))
            except Exception:                                               # noqa: BLE001
                pass        # a telemetry failure must not fail a signup
        return ", ".join(failed)[:400]

    # ── hiring somebody into a shop that already exists ──────────────────────────────────────
    async def hire(self, tenant: str, *, phone: str, password: str, role: str) -> dict[str, Any]:
        """Give an employee his own login into an establishment that already has an owner.

        WHY THIS EXISTS AT ALL, AND WHY IT COULD NOT UNTIL TODAY. A shop had exactly one account:
        `seed-owner` refuses a second owner on a staffed tenant, so it is the first-account
        primitive and unusable for the second. The only other door was to hand the owner
        `members:write` and let his browser call identity — which is a privilege-escalation
        surface (a membership may carry direct capabilities, and those are unioned into the minted
        token) and puts a platform-shaped API in front of a shop owner. So we did neither, and the
        product had no employees: the four-digit PIN is attribution, never authentication, and
        everything built on "who is looking at this screen" had nobody to be.

        base-services v0.16.8 answered it: an internal-tier add-member, ROLES ONLY, with no `caps`
        parameter at all. Capabilities stay derived from roles, and no shop owner ever holds a
        capability over identity.

        THE ROLE IS CHECKED AGAINST OUR OWN LIST, never taken as typed. `owner` is refused: there
        is exactly one, it is created by the signup saga, and transferring it is its own act with
        its own confirmation — not a value in a dropdown. `partner` is refused for the same reason
        it is absent from the screen: a till company is not staff.

        AND THE PHONE INDEX IS WRITTEN HERE, or he could never sign in. Our door resolves the
        tenant from the number (see the module note); identity would hold a perfectly good
        membership that our own sign-in refuses for a number it does not know.
        """
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise SignupRefused("أدخل رقم جوال صحيح.")
        allowed = {r.get("name", "") for r in self._roles} - {self._owner_role, "partner"}
        if role not in allowed:
            raise SignupRefused("هذا الدور غير متاح.")
        existing = await self.tenant_of_phone(canonical)
        if existing and existing != tenant:
            # HE WORKS SOMEWHERE ELSE. identity can hold two memberships for one person; our index
            # holds one tenant per number, so a second shop would silently take over his sign-in
            # and lock him out of the first. Refused plainly rather than half-done.
            raise SignupRefused("هذا الرقم مسجّل في منشأة أخرى.")

        status, body = self._http.call(
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": tenant, "identifier": canonical, "roles": [role],
                  "password": password})
        if status not in (200, 201):
            raise SignupRefused(_register_error(status, body))

        # ── THE INVITE IS REDEEMED HERE, OR HE CAN NEVER SIGN IN ─────────────────────────────
        #
        # THE DEFECT THIS CLOSES, FOUND ON THE CLUSTER AND NOT BY ANY TEST. `POST
        # /internal/tenancy/members` answers 201 with a person_id — and a membership whose status
        # is **pending**, plus an `invite_token`. A pending membership cannot mint: `/auth/tenant`
        # answers 401 to a perfectly correct password. So every employee an owner hired was
        # reported as hired, appeared in «فريقي», carried a role and a branch — and could not open
        # the app. Nothing failed anywhere; the account simply was not finished.
        #
        # WE REDEEM IT ON HIS BEHALF, and that is the same decision as the verified flag below: an
        # authenticated owner is adding his own employee and typed the password he is about to
        # hand him. The invite exists for the OTHER shape — a link mailed to a stranger — which
        # this product does not have and cannot deliver (no email, and the number is not proven
        # yet).
        #
        # AND A FAILURE HERE IS A REFUSAL, never a warning. Half a hire is worse than none: the
        # seat is counted, the row is in the list, and the man cannot work.
        invite = str(body.get("invite_token") or "")
        if invite:
            st, cl = self._http.call(
                f"{self._identity}/api/v1/auth/person/claim", method="POST",
                body={"token": invite, "password": password})
            if st != 200:
                raise SignupRefused("تعذّر إكمال حساب الموظف. حاول بعد قليل.")

        # VERIFIED BY THE OWNER, NOT BY A CODE. Self-serve signup proves the number because nobody
        # vouches for it; here an authenticated owner is adding his own employee, and the person
        # who will hand him the password is the person who typed it. Leaving it unverified would
        # build another locked door: our sign-in refuses an unproven number, and no code can be
        # delivered yet.
        await self._store.put(PHONE_INDEX, canonical,
                              {"id": canonical, "tenant": tenant, "verified": True})
        return {"person_id": str(body.get("person_id") or ""), "phone": canonical, "role": role}

    async def revoke(self, tenant: str, person_id: str) -> bool:
        """Undo `hire`: take the membership away, so the token stops being mintable.

        THE HALF THAT WAS MISSING, AND IT IS THE HALF THAT MATTERS. `hire` creates two things —
        the membership at identity and the operator row here — and it says so in its own note.
        Stopping somebody only ever wrote the row. The membership lived on, so a man let go on
        Thursday signed in on Thursday evening with the same password, and the shop's screen showed
        him stopped while identity happily minted him a token.

        AND HE DID NOT MERELY KEEP WHAT HE HAD. His operator row is what NARROWS him to his branch
        (api/scope.py); an inactive row matched nothing, an unmatched person was read as
        unnarrowed, and unnarrowed means the whole establishment. Being dismissed WIDENED what he
        could read, from one branch to every branch. That path is closed twice now — here, so the
        token cannot be minted at all, and there, so a stopped row can never widen again.

        IDEMPOTENT, and a missing membership is success: this is also the compensation an
        interrupted dismissal re-attempts.
        """
        if not tenant or not person_id:
            return False
        status, _ = self._http.call(
            f"{self._identity}/internal/tenancy/membership/{tenant}::{person_id}",
            method="DELETE", internal=True)
        if status not in (200, 204, 404):
            # REFUSED, NOT WARNED. The caller must not tell an owner that somebody was stopped
            # while his login still works — that is the exact sentence this whole defect was.
            raise SignupRefused("تعذّر إيقاف دخول الموظف. حاول بعد قليل.")
        return status in (200, 204)

    async def _seed_main_branch(self, tenant: str, *, shop_name: str) -> None:
        """His first place, keyed on a fixed id so a retry cannot leave two. Never raises.

        IMPORTED HERE RATHER THAN AT THE TOP: `stores` imports the models this module never
        touches, and the saga must not gain a boot-time dependency for one row.
        """
        try:
            from app.core.branches import ensure_main
            from app.core.stores import BranchStore
            await ensure_main(BranchStore(self._store), tenant=tenant, name=shop_name)
        except Exception:                                                     # noqa: BLE001
            pass

    async def _bootstrap_roles(self, tenant: str, *, subject: str) -> bool:
        """Create this establishment's roles and make the registrant its owner.

        THE SUBJECT IS THE USER ID IDENTITY JUST MINTED, not the phone: authz resolves capabilities
        for the token's `sub`, and a token's subject is that id. Assigning the role to a phone
        number would create a row nothing ever looks up — and the symptom would be identical to
        having no role at all, which is the bug this whole step exists to fix.
        """
        if not (self._authz and self._roles and subject):
            return False
        status, _ = self._http.call(
            f"{self._authz}/internal/authz/tenants/{tenant}/bootstrap",
            method="POST", internal=True,
            body={
                # EVERY ROLE, not just the owner's. A manager invited next week needs a role to be
                # invited INTO, and creating it then would mean a second code path that runs under
                # a different actor with different powers.
                "roles": [{"name": r.get("name", ""),
                           "capabilities": list(r.get("capabilities") or []),
                           "description": r.get("description", "")}
                          for r in self._roles if r.get("name")],
                "subject": subject,
                "assign": [self._owner_role],
            })
        return status in (200, 201)

    # ── the shop that arrives through its till ───────────────────────────────────────────────
    async def invite_partner_shop(self, *, phone: str, shop_name: str,
                                  partner_key: str) -> dict[str, Any]:
        """Record an invitation and message the owner. Creates NOTHING — see core/claim.py."""
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise SignupRefused("رقم جوال غير صالح.")
        if await self.tenant_of_phone(canonical):
            # SAID PLAINLY, because this route is internal-tier: the caller is a till company we
            # contracted with, and it needs to know it enrolled a shop that is already ours rather
            # than wait for a claim that never comes.
            raise SignupRefused("لهذا الرقم حساب بالفعل.")

        # RESOLVED HERE, NOT AT CLAIM TIME (ك-5). Two things follow from doing it now: the till
        # company that typoed its key learns immediately, at the one moment it can still fix the
        # call, instead of the failure surfacing days later on the OWNER's claim with nobody able to
        # act on it (see `open_shop`'s own note on `stamp_error`) — and the raw key never has to be
        # stored anywhere for the week the invitation stays open. Only the resolved id does.
        partner_id = ""
        if partner_key and self._partners is not None:
            partner = await self._partners.resolve(partner_key)
            if partner is None:
                raise SignupRefused("مفتاح شريكٍ غير معروف.", reason="UNKNOWN_PARTNER_KEY")
            if not partner.get("active", True):
                raise SignupRefused("مفتاح هذا الشريك غير مُفعَّل.", reason="PARTNER_INACTIVE")
            partner_id = str(partner.get("id") or "")

        now = int(time.time())
        await self._claims.invite(phone=canonical, shop_name=shop_name,
                                  partner_id=partner_id, now=now)
        # THE CODE IS THE PROOF, and it is identity's to issue and consume — we hold none of it.
        # A failure to send is REPORTED rather than raised: the invitation is recorded and he can
        # ask for a code from the claim screen, so losing the message must not lose the shop.
        try:
            await self.send_code(canonical)
            delivered = True
        except SignupRefused:
            delivered = False
        return {"invited": True, "delivered": delivered}

    async def claim(self, phone: str, code: str, password: str) -> dict[str, Any]:
        """He proves the number and chooses his password; the ordinary saga runs from there."""
        canonical = canonical_phone(phone, default_cc=self._cc)
        # TRANSLATED, NOT PROPAGATED. `claim.py` raises its own error so it can stay free of this
        # module (they would import each other otherwise) — and an error type the route does not
        # catch escapes as a 500, which is a blank wall where the owner needed one sentence. The
        # unit test caught exactly that.
        try:
            inv = CL.check(await self._claims.get(canonical), now=int(time.time()))
        except CL.ClaimError as exc:
            raise SignupRefused(str(exc)) from exc

        # THE NUMBER IS PROVEN FIRST, ALWAYS. Without it the invitation is a shop anybody who
        # learned the number could open — and the message that carries the code is the only thing
        # tying this claim to the person the till company enrolled.
        #
        # `_spend_code` RATHER THAN `prove`, because `prove` writes its verdict onto the phone
        # index — and there is no index row yet: the shop does not exist. The verdict is written
        # below, once there is something to write it on.
        self._spend_code(canonical, code)

        out = await self.open_shop(NewShop(
            phone=canonical, password=password, shop_name=inv.shop_name,
            # FROM THE INVITATION, NEVER FROM THE REQUEST. A body that could name its own partner
            # key would be a body that could redirect somebody else's commission. ALREADY
            # RESOLVED, not a raw key (ك-5) — `invite_partner_shop` did that at invite time.
            partner_id=inv.partner_id, integrated=True))

        # HE PROVED IT A MOMENT AGO, so the row created by the saga says so. Without this he would
        # open his shop and be refused at the very next sign-in for a number he just confirmed.
        row = await self._row(canonical)
        if row is not None:
            await self._store.put(PHONE_INDEX, canonical, {**row, "verified": True})
            await self._mark_proven(str(row.get("tenant") or ""), canonical)

        # SINGLE USE, AND CONSUMED ONLY AFTER THE SHOP EXISTS. Consuming it first would burn the
        # invitation on a signup that then failed, and the owner would need the till company to
        # issue another one for a mistake that was ours.
        await self._claims.consume(canonical)
        return out

    # ── proving the number ───────────────────────────────────────────────────────────────────
    async def prove(self, phone: str, code: str) -> dict[str, Any]:
        """Spend the code at identity, and RECORD that it was spent.

        THE CLIENT USED TO CALL IDENTITY DIRECTLY, and the hole was only visible by walking away
        from a half-finished signup: identity verifies a code and stores no verdict, our sign-in
        never asked, so an owner who skipped the OTP screen and came back through the front door
        was let straight in. The step was a screen, not a rule.

        So the exchange runs HERE, in the one place that already keys a row on this number. A
        verification identity accepted and we failed to record is the same as none at all — the
        next sign-in refuses and he proves it again, which is the safe direction.
        """
        row = await self._row(phone)
        if row is None:
            # Same refusal as a bad code. Otherwise this is a free oracle for which numbers have
            # accounts, one request at a time.
            raise SignupRefused("الرمز غير صحيح أو انتهت صلاحيته.")

        canonical = canonical_phone(phone, default_cc=self._cc)
        self._spend_code(canonical, code)
        await self._store.put(PHONE_INDEX, canonical, {**row, "verified": True})
        await self._mark_proven(str(row.get("tenant") or ""), canonical)
        return {"verified": True}

    async def _mark_proven(self, tenant: str, canonical: str) -> None:
        """Both indexes move together, or the second one is decoration."""
        if tenant:
            await self._store.put(TENANT_PROOF, tenant,
                                  {"id": tenant, "phone": canonical, "verified": True})

    async def phone_proven(self, tenant: str) -> bool:
        """Did anybody ever prove the number this shop was opened on? (و-7)

        A SHOP CREATED THROUGH A DOOR THAT PREDATES THIS INDEX HAS NO ROW, and the answer for it is
        yes. Reading a missing row as «not proven» would lock every shop that existed before this
        was written out of connecting WhatsApp, which is a fault we would have invented; the rule
        exists to stop a stranger opening a shop on somebody else's number and binding it, and a
        row absent for that reason is a row this saga never wrote.
        """
        if not tenant:
            return False
        row = await self._store.get(TENANT_PROOF, tenant)
        if row is None:
            return True
        return bool(row.get("verified"))

    def _spend_code(self, canonical: str, code: str) -> None:
        """Hand the code to identity, which is the only party that holds it.

        SHARED BY THE TWO DOORS. `prove` is for a number we already have a row for; the partner
        claim is for one we do not — the shop does not exist yet, that is what the claim is for.
        Duplicating the exchange would mean two places that decide what a bad code means, and the
        second one would drift.
        """
        status, _ = self._http.call(
            f"{self._identity}/api/v1/otp/verify", method="POST",
            body={"identifier": canonical, "code": code, "purpose": "verify"})
        if status != 200:
            raise SignupRefused("الرمز غير صحيح أو انتهت صلاحيته.")

    async def send_code(self, phone: str) -> dict[str, Any]:
        """Ask identity for a code — and REPORT WHETHER IT WAS ACTUALLY DELIVERED.

        THE LIE THIS REMOVES. identity answers `{"requested": true, "delivered": <bool>}` and
        issues the code either way, correctly: a provider hiccup must not cost an account. But we
        were returning "sent" on the strength of `requested` alone, so a person stared at a code
        screen waiting for a message that no part of the system had even attempted to send. He
        checks his phone, waits, retries, and concludes his number is wrong.

        And it was not a hiccup — with WHATSAPP_CHAIN on the console driver, NOTHING is delivered,
        ever. A screen that says "we sent you a code" while the sender is a log line is the worst
        failure shape there is: everything reports success and the person is the only one who
        knows it did not work.

        SO A FAILURE TO DELIVER IS A REFUSAL, and it says whose fault it is. He cannot fix it, he
        should not try, and he should not be left holding a form he thinks is his to complete.
        """
        if not self._can_deliver:
            # ASKED BEFORE THE CALL, not after. Requesting a code we know cannot arrive burns a
            # minute of the person's resend cooldown and leaves a live code nobody can spend.
            raise SignupRefused(
                "إرسال رمز التحقق غير مُفعَّل بعد — عُطل لدينا لا في رقمك. تواصل معنا وسنكمل معك.",
                reason="undeliverable")
        status, body = self._http.call(
            f"{self._identity}/api/v1/otp/request", method="POST",
            body={"identifier": canonical_phone(phone, default_cc=self._cc), "purpose": "verify"})
        if status == 429:
            raise SignupRefused("انتظر قليلاً قبل طلب رمز جديد.", reason="cooldown")
        if status != 200:
            raise SignupRefused("تعذّر إرسال الرمز. حاول بعد قليل.")
        if not (body or {}).get("delivered"):
            # THE PROVIDER TRIED AND FAILED — a different fact from the one above, and still ours.
            # Kept even though the console driver never reports it: the moment Meta is wired in,
            # this is the branch that catches a real outage.
            raise SignupRefused(
                "تعذّر إرسال الرمز الآن. حاول بعد قليل.",
                reason="undelivered")
        return {"sent": True, "expires_in": int((body or {}).get("expires_in") or 0)}

    # ── getting back in ──────────────────────────────────────────────────────────────────────
    async def sign_in(self, phone: str, password: str, code: str = "") -> dict[str, Any]:
        """Resolve the shop from the number, then let identity decide everything else."""
        tenant = await self.tenant_of_phone(phone)
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not tenant:
            # THE SAME REFUSAL AS A WRONG PASSWORD. See the module note — anything else is an
            # enumeration oracle for every mobile number in the country.
            raise SignupRefused("رقم الجوال أو كلمة المرور غير صحيحة.")

        # THE RULE, AND IT IS CHECKED BEFORE THE PASSWORD IS EVEN SENT. An unproven number is not
        # an identity: it is the login field AND the channel every reminder goes out on, so a shop
        # built on a number nobody answers is a shop whose whole product is silent.
        #
        # AND IT IS A SETTING, because the rule is only worth anything while a code can actually
        # arrive. With sending not yet wired to Meta, enforcing it is not a protection — it is a
        # locked door with no key, and the person on the wrong side of it did nothing wrong. The
        # verdict is still recorded either way; what the switch changes is whether it BLOCKS.
        #
        # AFTER the row lookup and with the SAME sentence shape as a bad password would produce for
        # an unknown number — a caller may not learn from this which numbers exist.
        row = await self._row(phone)
        if self._require_otp and row is not None and not row.get("verified"):
            # NOT AN ERROR — A STEP. The console reads `unverified` and takes him to the code
            # screen instead of printing a sentence he cannot act on. Telling someone what is
            # wrong while withholding the one door that fixes it is the worst of both.
            raise SignupRefused("أكّد رقم جوالك أولاً.", reason="unverified")

        # /auth/tenant, NOT /auth/login. Both take a phone and a password; only this one mints
        # from the MEMBERSHIP, which is what resolves the role into capabilities. The other builds
        # the token from a user row that our signup no longer creates.
        #
        # AND THE TENANT IT MINTS FOR IS READ OFF THE MEMBERSHIP, never off what we send — what we
        # send is a request to be let in, not an assertion of where we already are. So our index
        # being wrong cannot let anyone into a shop that is not theirs.
        payload: dict[str, Any] = {"tenant": tenant, "username": canonical, "password": password}
        if code:
            payload["code"] = code
        status, body = self._http.call(
            f"{self._identity}/api/v1/auth/tenant", method="POST", body=payload)
        if status != 200:
            # ONE SENTENCE FOR EVERY 401, AND A BRANCH WAS TRIED HERE AND REMOVED.
            #
            # Accounts created before signup moved from `/auth/register` to the membership path
            # cannot mint at all — a user row with no person behind it — and telling those people
            # so would be kinder than blaming a password that is perfectly correct.
            #
            # But identity answers 401 to a stale account and to a wrong password alike, so the
            # only way to tell them apart here is "do we know this number" — and that is exactly
            # the enumeration oracle every refusal in this file is shaped to avoid. A kinder
            # message for the numbers we hold is an answer to "does this number have an account",
            # one request at a time, for free. The unit test caught it.
            raise SignupRefused(_login_error(status, body))
        return {**body, "tenant": tenant}


def _why(status: int, body: dict, fallback: str) -> str:
    detail = body.get("detail") or body.get("message") or ""
    return f"{fallback} ({detail or status})" if detail or status else fallback


def _register_error(status: int, body: dict) -> str:
    detail = str(body.get("detail") or "")
    if detail == "USERNAME_TAKEN" or status == 409:
        return "لهذا الرقم حساب بالفعل — سجّل الدخول."
    if detail == "WEAK_PASSWORD":
        return "كلمة المرور قصيرة."
    if detail == "INVALID_IDENTIFIER":
        return "أدخل رقم جوال صحيح."
    if detail == "REGISTRATION_DISABLED":
        return "التسجيل الذاتي متوقف حالياً."
    return "تعذّر إنشاء الحساب. حاول بعد قليل."


def _login_error(status: int, body: dict) -> str:
    detail = str(body.get("detail") or "")
    if detail == "MFA_REQUIRED":
        return "أدخل رمز التحقق."
    if detail == "CAPS_UNAVAILABLE" or status == 503:
        # NOT "wrong password". The credentials were fine and the capability authority is down;
        # sending this owner to reset a password that works would waste his afternoon.
        return "الخدمة غير متاحة الآن. حاول بعد قليل."
    return "رقم الجوال أو كلمة المرور غير صحيحة."
