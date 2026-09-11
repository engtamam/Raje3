# =============================================================================
# affiliate-service — «بوابة القبول» (spec §2): apply → admin decides → account minted
# -----------------------------------------------------------------------------
# WHY THIS DOES NOT MINT AN ACCOUNT ON REQUEST, unlike operations' own open_shop. A shop owner is
# the one person who could possibly be wrong about his own shop; a marketer applicant is a
# stranger asking for a channel that can message thousands of our customers and a share of real
# money — spec §2 requires a platform admin to look at every one of them before anything is
# usable. So `apply()` writes a ROW, nothing more: no identity account, no tenant membership, no
# capability. The row exists so the decision has something to be made about, and so a duplicate or
# rejected attempt is recorded rather than silently vanishing.
#
# ONE SHARED TENANT (spec §1/§12). identity-service's own `register`/`tenant` concept is generic
# enough to not need a change (confirmed by reading app/core/auth_service.py directly) — every
# marketer becomes a MEMBER of the one tenant named by Settings.AFFILIATE_TENANT, distinguished
# from each other by ROLE (`affiliate_manager` / `affiliate_promoter`) and, inside our own
# `affiliates` table, by `parent_id`. identity never learns the hierarchy; that is ours to keep.
#
# THE PARENT IS RESOLVED AT APPLY TIME, not trusted at approval time — a referral code typed once
# and misread by an admin two weeks later is a real failure; a code that was already validated (or
# already empty, for a manager applicant) removes the chance.
# =============================================================================
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.phone import canonical_phone
from app.core.models import (
    ACTIVE,
    AFFILIATE_SELF,
    AFFILIATES,
    APPLICATIONS,
    APPROVED,
    MANAGER,
    PENDING,
    PROMOTER,
    REJECTED,
    SUSPENDED,
    Affiliate,
    Application,
    new_id,
)
from app.core.pii import subject_ref as _subject_ref


class OnboardingRefused(Exception):
    """A rule of ours, or a refusal identity made, in a sentence meant to be read.

    `reason` mirrors operations/core/signup.py's own SignupRefused — a stable code the console can
    act on (route to a step, or just print the sentence), never matched against the Arabic text.
    """

    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class Http:
    """Same tiny client as operations' core/signup.py — one idiom for internal calls, kept
    identical on purpose rather than reinvented per service."""

    def __init__(self, *, timeout: int = 10, internal_token: str = "") -> None:
        self._timeout = timeout
        self._token = internal_token

    def call(self, url: str, *, method: str, body: dict | None = None,
             internal: bool = False, bearer: str = "") -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if internal:
            headers["X-Internal-Token"] = self._token
        if bearer:
            # THE CALLER'S OWN TOKEN, FORWARDED VERBATIM — used only for a call identity itself
            # gates on `require_user` for the SAME PERSON (change-password): identity re-decodes
            # it and answers for whoever it names, so this is never a way to act as someone else,
            # only a pass-through of a request already inside its own subject's authority.
            headers["Authorization"] = bearer
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


class OnboardingService:
    def __init__(self, *, store, http: Http, identity_url: str, tenant: str,
                 manager_role: str = MANAGER, promoter_role: str = PROMOTER,
                 default_cc: str = "966", pii_salt: str = "",
                 terms_version: str = "v1",
                 tenants_url: str = "", authz_url: str = "",
                 otp_deliverable: bool = False, require_otp: bool = False,
                 phone_search_ro: Any = None, secrets_kek: str = "") -> None:
        self._store = store
        self._http = http
        self._identity = identity_url.rstrip("/")
        self._tenant = tenant
        self._manager_role = manager_role
        self._promoter_role = promoter_role
        self._cc = default_cc
        self._salt = pii_salt
        # SEALS THE ONE PENDING CREDENTIAL apply() EVER WRITES — see _seal_pending_password's own
        # module-level docstring. Same "refuse rather than silently degrade" posture SecretStore
        # itself takes on an empty KEK; enforced lazily, at the one call site that actually needs
        # it (apply()), rather than at construction — a deployment that never touches this feature
        # (a test, a script hitting other routes) must not fail to boot over a KEK it never needed.
        self._kek = secrets_kek
        self._terms_version = terms_version
        # THE PHONE-OWNERSHIP GATE ("لما يجي يسجل... النظام يعرف انه هذا الحساب
        # هو نفس من رقم الجوال ويربط على طول تحت المدير"). Two independent knobs, same shape as
        # operations' own SIGNUP_OTP_DELIVERABLE/SIGNUP_REQUIRE_OTP: `_can_deliver` is whether a
        # code can actually reach a phone (false everywhere today — see notification-service's own
        # console driver), `_require_otp` is whether apply() refuses without one. Both false by
        # default so this whole gate is dormant until real WhatsApp/SMS credentials exist, at which
        # point flipping both on turns it into a hard gate with no further code change.
        self._can_deliver = otp_deliverable
        self._require_otp = require_otp
        # THE SHARED AFFILIATE TENANT'S OWN PROVISIONING (spec §1/§12) — see _ensure_tenant_ready
        # for the whole reasoning. Optional: empty means "assume it already exists", which keeps
        # a test/local run that never set these working exactly as it did before this existed.
        self._tenants = tenants_url.rstrip("/")
        self._authz = authz_url.rstrip("/")
        self._tenant_ready = False   # per-process cache — see _ensure_tenant_ready's own note
        # THE WEAKER ROLE, ONLY FOR `POST /apply`'s two phone lookups — see app/config.py's
        # DATASTORE_DSN_PHONE_SEARCH. `None` (the default) means the fallback below, the exact
        # single-role path this service has always used.
        self._phone_search_ro = phone_search_ro

    # ── the shared affiliate tenant's own provisioning, lazily and idempotently ──────────────
    async def _ensure_tenant_ready(self, *, first_subject: str, first_role: str) -> None:
        """Self-healing, not a script somebody has to remember to run once. Checked at the one
        moment it actually matters — the FIRST time this process is about to mint a membership
        into Settings.AFFILIATE_TENANT — never at boot (a tenant-service/authz hiccup at startup
        must not stop this service from serving every OTHER route) and never by a human-run
        script (exactly the class of gap this session already found twice: a step that has to be
        remembered is a step that gets forgotten).

        `self._tenant_ready` IS ONLY A PER-PROCESS OPTIMISATION, never the correctness guarantee
        — both calls below are themselves idempotent (a 409 on an existing tenant, a bootstrap
        that "corrects drift" per its own docstring), so a cold pod that has forgotten the flag
        still converges safely; the flag only saves a redundant round trip on every later call.
        """
        if self._tenant_ready or not self._tenants:
            return
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve (operations'
        # own module, same idiom copied service to service).
        status, _ = await asyncio.to_thread(
            self._http.call,
            f"{self._tenants}/internal/tenants/{self._tenant}", method="GET", internal=True)
        if status != 200:
            status, body = await asyncio.to_thread(
                self._http.call,
                f"{self._tenants}/internal/tenants", method="POST", internal=True,
                body={"slug": self._tenant, "name": "برنامج المسوّقين بالعمولة"})
            # 409 = another approval won this exact race a moment ago — not a failure.
            if status not in (201, 409):
                raise OnboardingRefused(
                    "تعذّرت الموافقة — تهيئة النظام غير مكتملة.", reason="tenant_provision_failed")

        if self._authz:
            status, _ = await asyncio.to_thread(
                self._http.call,
                f"{self._authz}/internal/authz/tenants/{self._tenant}/bootstrap", method="POST",
                internal=True,
                body={"roles": [
                    # `affiliates.self` — closes the gap this comment used to
                    # flag: neither role ever carried a real capability, so every affiliate
                    # token minted for this tenant held `caps: []` and every self-service route
                    # (once gated by app/api/authz.py::require_capability) would have refused
                    # everyone, including a legitimate marketer reading his own data. Both roles
                    # get the SAME one capability — it answers "is he a real, approved affiliate
                    # at all", never which rows he may touch; ownership checks still decide that.
                    {"name": self._manager_role, "capabilities": [AFFILIATE_SELF],
                     "description": "مدير تسويق — بوابة المسوّقين بالعمولة"},
                    {"name": self._promoter_role, "capabilities": [AFFILIATE_SELF],
                     "description": "مسوّق بالعمولة — بوابة المسوّقين بالعمولة"},
                ], "subject": first_subject, "assign": [first_role]})
            if status not in (200, 201):
                raise OnboardingRefused(
                    "تعذّرت الموافقة — تهيئة النظام غير مكتملة.", reason="role_bootstrap_failed")

        self._tenant_ready = True

    def _ref(self, phone: str) -> str:
        """"" when PII_SALT is unset (local/dev) — erasure.py then simply finds nothing rather
        than raising, same fallback shape as the rest of this platform's optional salt."""
        return _subject_ref(self._salt, self._tenant, phone) if self._salt else ""

    # ── applying ─────────────────────────────────────────────────────────────────────────────
    async def apply(self, *, phone: str, name: str, password: str,
                    referral_code: str = "", agreed: bool = False,
                    cv_url: str = "", code: str = "") -> dict[str, Any]:
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise OnboardingRefused("أدخل رقم جوال صحيح.")
        if not name.strip():
            raise OnboardingRefused("أدخل اسمك.")
        # spec §2: "قبول الشروط إجباري قبل التفعيل". Checked BEFORE the duplicate/referral
        # lookups below — an applicant who never agreed should not learn anything about whether
        # his number is already taken or his referral code is valid; there is nothing for him to
        # act on here besides ticking the box.
        if not agreed:
            raise OnboardingRefused("وافق على الشروط وسياسة الخصوصية للمتابعة.", reason="must_agree")

        # ONE ATTEMPT AT A TIME PER NUMBER, ENFORCED BY A REAL LOCK — fixed 2026-09-12, a real
        # gap a QA audit found: the "no pending application for this phone" check and the write
        # that follows used to be two separate round trips with nothing between them, the exact
        # TOCTOU shape `_PAYOUT_LOCKS`/`_WAFA_LOCKS`/`_EMPLOYMENT_LOCKS` were each added to close
        # elsewhere in this same service. A double-tapped submit button (or a retry over a slow
        # connection — the scenario the dedupe check's own comment above already names) could
        # both pass the check and both write a PENDING row for the same person.
        now0 = int(time.time())
        took = await self._store.claim(
            _APPLY_LOCKS, canonical, {"phone": canonical, "at": now0},
            ttl_seconds=_APPLY_LOCK_TTL_SECONDS, now=now0)
        if not took:
            raise OnboardingRefused(
                "طلبك قيد المعالجة الآن، حاول بعد لحظات.", reason="already_pending")
        try:
            existing = await self._find_application_by_phone(canonical)
            if existing is not None and existing.status == PENDING:
                raise OnboardingRefused(
                    "طلبك السابق ما زال قيد المراجعة.", reason="already_pending")
            if await self._affiliate_by_phone(canonical) is not None:
                raise OnboardingRefused(
                    "لهذا الرقم حساب مسوّق بالفعل — سجّل الدخول.", reason="already_affiliate")

            parent_id = ""
            if referral_code.strip():
                parent = await self._store.get(AFFILIATES, referral_code.strip())
                if parent is None or parent.get("status") != ACTIVE:
                    raise OnboardingRefused("كود الإحالة غير صحيح.", reason="bad_referral")
                parent_id = str(parent["id"])

            # PHONE-OWNERSHIP PROOF, LAST — after every other refusal, so a stranger holding
            # somebody else's number and a wrong code learns nothing beyond "the code was wrong":
            # not whether the number is already taken, not whether the referral code is real. See
            # __init__'s own note on the two flags — a no-op today, a hard gate the moment both
            # are flipped on.
            if self._require_otp:
                # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
                # `_spend_code` stays a plain sync method (correct — it is the offload TARGET, not
                # a coroutine); the offload belongs here, at its one caller.
                await asyncio.to_thread(self._spend_code, canonical, code)

            # CHECKED BEFORE ANYTHING IS WRITTEN — the applicant's password must be sealed, not
            # stored plain (see _seal_pending_password's own docstring), and a missing KEK must
            # refuse the whole application rather than leave an Application row with no matching
            # sealed secret behind it (a half-written apply() that never mints an account either
            # way).
            if not self._kek:
                raise OnboardingRefused(
                    "تعذّرت الموافقة — تهيئة النظام غير مكتملة.", reason="secrets_kek_missing")

            now = int(time.time())
            app_row = Application(
                id=new_id(), phone=canonical, name=name.strip(), parent_id=parent_id,
                status=PENDING, created_at=now, subject_ref=self._ref(canonical),
                agreed_terms_version=self._terms_version, agreed_at=now,
                cv_url=cv_url.strip()[:500],
            )
            # THE PASSWORD IS NOT STORED HERE. Only identity ever holds a credential — this row
            # is a request to be judged, and a plaintext password sitting in a pending-
            # applications table for however long an admin takes to look at it is exactly the
            # kind of "we'll get to it" PII debt this whole platform has spent this session
            # closing everywhere else.
            await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
            # THE ONE EXCEPTION: kept in a SEPARATE, short-lived row so approval can still mint
            # the account with the password the applicant actually chose — never a generated one
            # he was never told, which would just lock him out on his first sign-in. SEALED, not
            # plaintext — see _seal_pending_password's own docstring for why this row needed the
            # same protection every other credential on this platform already gets.
            await self._store.put(
                _PENDING_SECRET, app_row.id,
                {"id": app_row.id, "sealed": _seal_pending_password(self._kek, password)})
            return {"application_id": app_row.id, "status": PENDING}
        finally:
            # RELEASED HERE, NOT LEFT TO THE TTL — same reasoning `request_withdrawal`'s own
            # `finally` gives: the TTL is only a crash safety net, and a legitimate next attempt
            # (after this one is refused) must not wait it out for no reason.
            await self._store.delete(_APPLY_LOCKS, canonical)

    # ── the phone-ownership code itself — same idiom as operations' own send_code/_spend_code ──
    async def request_otp(self, phone: str) -> dict[str, Any]:
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise OnboardingRefused("أدخل رقم جوال صحيح.")
        if not self._can_deliver:
            # ASKED BEFORE THE CALL, not after — requesting a code that cannot arrive burns a
            # minute of the applicant's resend cooldown for nothing. See operations/core/signup.py's
            # own send_code for the identical reasoning.
            raise OnboardingRefused(
                "إرسال رمز التحقق غير مُفعَّل بعد — عُطل لدينا لا في رقمك. تواصل معنا وسنكمل معك.",
                reason="undeliverable")
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, body = await asyncio.to_thread(
            self._http.call,
            f"{self._identity}/api/v1/otp/request", method="POST",
            body={"identifier": canonical, "purpose": "verify"})
        if status == 429:
            raise OnboardingRefused("انتظر قليلاً قبل طلب رمز جديد.", reason="cooldown")
        if status != 200:
            raise OnboardingRefused("تعذّر إرسال الرمز. حاول بعد قليل.")
        if not (body or {}).get("delivered"):
            raise OnboardingRefused("تعذّر إرسال الرمز الآن. حاول بعد قليل.", reason="undelivered")
        return {"sent": True, "expires_in": int((body or {}).get("expires_in") or 0)}

    def _spend_code(self, canonical: str, code: str) -> None:
        """Hand the code to identity, the only party that holds it — same idiom as operations'
        own core/signup.py::_spend_code."""
        status, _ = self._http.call(
            f"{self._identity}/api/v1/otp/verify", method="POST",
            body={"identifier": canonical, "code": code, "purpose": "verify"})
        if status != 200:
            raise OnboardingRefused("الرمز غير صحيح أو انتهت صلاحيته.", reason="bad_code")

    # ── a manager correcting what a person under him submitted, before an admin decides ────────
    async def update_application(self, application_id: str, *, editor_person_id: str,
                                 name: str | None = None, cv_url: str | None = None) -> dict[str, Any]:
        """"امكانية التعديل من المدير... التعديل يكون قبل القبول من الادارة
        وليس بعده." — the manager who referred this applicant may correct his name or attach a
        CV link, but only while there is still a decision to correct it BEFORE. `decided_at`
        being set is what closes the window (models.py's own note on `Application`), not a
        separate flag — the same row an admin is about to look at is the only one this can ever
        be true of.
        """
        row = await self._store.get(APPLICATIONS, application_id)
        if row is None:
            raise OnboardingRefused("الطلب غير موجود.", reason="not_found")
        app_row = Application.from_dict(row)
        if app_row.status != PENDING:
            # NOT "already decided" specifically — see approve()/reject()'s own reasoning:
            # once an admin has acted, correcting the row an admin already judged is not an edit,
            # it is a second, unreviewed decision wearing the first one's approval.
            raise OnboardingRefused("لم يعد بالإمكان تعديل هذا الطلب.", reason="decision_closed")

        editor = await self._affiliate_by_person(editor_person_id)
        if editor is None or editor.id != app_row.parent_id:
            # ONLY THE REFERRING MANAGER, never any other affiliate — the same ownership rule
            # invite() used to check before it was removed: he may touch what came in under his
            # own link, nothing that came in under somebody else's.
            raise OnboardingRefused("هذا الطلب ليس ضمن فريقك.", reason="not_your_referral")

        if name is not None:
            if not name.strip():
                raise OnboardingRefused("أدخل اسماً صحيحاً.")
            app_row.name = name.strip()
        if cv_url is not None:
            app_row.cv_url = cv_url.strip()[:500]
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        return app_row.to_dict()

    # ── who am I ─────────────────────────────────────────────────────────────────────────────
    async def me(self, person_id: str) -> dict[str, Any] | None:
        """What the signed-in affiliate needs to see his OWN referral link — his own `id` IS his
        referral code (spec §1: `?aff=<id>` for a shop, `?ref=<id>` for another marketer applying
        under him), so there is no separate code to mint or keep in step with this row.

        None when `person_id` matches no Affiliate row at all — a token minted for a tenant this
        service does not own. Never raises; the route turns None into 404.

        NOT `affiliate.to_dict()` — named fields only, same discipline operator.py's own
        `list_secrets` already follows for hints vs. values."""
        affiliate = await self._affiliate_by_person(person_id)
        if affiliate is None:
            return None
        return {"id": affiliate.id, "role": affiliate.role, "name": affiliate.name,
               "parent_id": affiliate.parent_id, "status": affiliate.status,
               "sees_platform_revenue": affiliate.sees_platform_revenue}

    async def team(self, manager_affiliate_id: str) -> list[dict[str, Any]]:
        """The promoters a manager brought on — spec §10's own "شفافية الإيراد الفعلي للمدير":
        WHO they are, not what they earned (core/commission.py owns the money side; a manager's
        own dashboard route joins the two, same separation as everywhere else in this service —
        onboarding never reads a Commission and commission.py never reads an Affiliate). Only
        DIRECT children: spec §1's tree is manager→promoter, one level, so there is no deeper
        chain to walk."""
        rows, _ = await self._store.find(
            AFFILIATES, {"parent_id": manager_affiliate_id}, limit=200,
            sort=("created_at", "asc"))
        return [{"id": a["id"], "name": a["name"], "status": a["status"]}
                for a in rows]

    async def _affiliate_by_person(self, person_id: str) -> Affiliate | None:
        if not person_id:
            return None
        rows, _ = await self._store.find(AFFILIATES, {"person_id": person_id}, limit=1)
        return Affiliate.from_dict(rows[0]) if rows else None

    async def _find_application_by_phone(self, phone: str) -> Application | None:
        """`POST /apply`'s dedupe check — reachable with NO capability gate at all (see
        app/config.py's DATASTORE_DSN_PHONE_SEARCH), so this is the one lookup in this service
        that most deserves the weaker role. Two steps when it is wired: find the matching row's
        KEY under a role that can see nothing but (collection, phone, key, created_at) — never a
        name, an address, a payout account, or any other collection — then fetch the full record
        through the normal, already-trusted store."""
        if self._phone_search_ro is not None:
            key = await self._phone_search_ro.find_application_key_by_phone(phone)
            if key is None:
                return None
            row = await self._store.get(APPLICATIONS, key)
            return Application.from_dict(row) if row else None
        rows, _ = await self._store.find(APPLICATIONS, {"phone": phone}, limit=1,
                                         sort=("created_at", "desc"))
        return Application.from_dict(rows[0]) if rows else None

    async def _affiliate_by_phone(self, phone: str) -> Affiliate | None:
        """Same weaker-role split as `_find_application_by_phone` above, for the `affiliates`
        collection — `POST /apply` also checks this one, same unauthenticated route."""
        if self._phone_search_ro is not None:
            key = await self._phone_search_ro.find_affiliate_key_by_phone(phone)
            if key is None:
                return None
            row = await self._store.get(AFFILIATES, key)
            return Affiliate.from_dict(row) if row else None
        rows, _ = await self._store.find(AFFILIATES, {"phone": phone}, limit=1)
        return Affiliate.from_dict(rows[0]) if rows else None

    # ── the admin's queue ────────────────────────────────────────────────────────────────────
    async def list_pending(self) -> list[dict[str, Any]]:
        rows, _ = await self._store.find(APPLICATIONS, {"status": PENDING}, limit=200,
                                         sort=("created_at", "asc"))
        return [Application.from_dict(r).to_dict() for r in rows]

    async def approve(self, application_id: str, *, decided_by: str) -> dict[str, Any]:
        row = await self._store.get(APPLICATIONS, application_id)
        if row is None:
            raise OnboardingRefused("الطلب غير موجود.", reason="not_found")
        app_row = Application.from_dict(row)

        # IDEMPOTENT. An admin's double-click or a retried request must not mint a second
        # identity membership for the same applicant — see the module docstring on why an
        # account here is not a thing to create twice.
        if app_row.status == APPROVED:
            existing = await self._affiliate_by_phone(app_row.phone)
            return {"already_approved": True,
                   "affiliate_id": existing.id if existing else ""}
        if app_row.status == REJECTED:
            raise OnboardingRefused("هذا الطلب مرفوض بالفعل.", reason="already_rejected")

        # RE-ACCEPTANCE, THE SAME SHAPE AS compliance-service's own LegalGate (see
        # platform/services/compliance-service/app/core/legal_gate.py::outstanding): acceptance is
        # pinned to the version in force AT apply() TIME, so a terms bump while this application
        # sat PENDING leaves it stale — the applicant agreed to a document that is no longer the
        # one governing this engagement. Approving it anyway would mint an account whose consent
        # answers a question nobody is asking any more. He must apply again, and re-agree, to the
        # version now in force — the same "no sweep, no flag to flip" property LegalGate gets from
        # a version bump alone.
        if app_row.agreed_terms_version != self._terms_version:
            raise OnboardingRefused(
                "تغيّرت شروط برنامج المسوّقين منذ تقديم الطلب — على المتقدّم إعادة التقديم "
                "والموافقة على النسخة الحالية.", reason="terms_changed")

        role = self._promoter_role if app_row.parent_id else self._manager_role
        affiliate = await self._mint_self_applied(app_row, role=role)

        app_row.status = APPROVED
        app_row.decided_at = int(time.time())
        app_row.decided_by = decided_by
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        # THE PASSWORD IS GONE THE MOMENT IT HAS DONE ITS ONE JOB — minting the membership above.
        # Keeping it a second longer than approval takes is PII with no purpose left to serve.
        await self._store.delete(_PENDING_SECRET, application_id)

        return {"affiliate_id": affiliate.id, "role": role, "already_approved": False,
               "status": affiliate.status}

    async def _mint_self_applied(self, app_row: Application, *, role: str) -> Affiliate:
        """apply()'s own applicant already chose a password (in `_PENDING_SECRET`) — redeem it
        server-side, exactly as before this branch existed. The account is ACTIVE the moment
        approval finishes; there is nobody else who needs to do anything."""
        secret = await self._store.get(_PENDING_SECRET, app_row.id)
        sealed = str((secret or {}).get("sealed") or "")
        password = _open_pending_password(self._kek, sealed) if sealed and self._kek else ""
        if not password:
            # THE SECRET ROW IS GONE OR WAS NEVER WRITTEN. Minting a membership with no password
            # the applicant knows would hand him an account he cannot sign into — refused rather
            # than half-done, same principle as operations' own hire().
            raise OnboardingRefused("تعذّرت الموافقة — أعد الطلب.", reason="secret_missing")

        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, body = await asyncio.to_thread(
            self._http.call,
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": self._tenant, "identifier": app_row.phone, "roles": [role],
                  "password": password})
        if status not in (200, 201):
            raise OnboardingRefused(_member_error(status, body))

        person_id = str(body.get("person_id") or "")
        await self._ensure_tenant_ready(first_subject=person_id, first_role=role)
        invite = str(body.get("invite_token") or "")
        if invite:
            # SAME REDEMPTION AS operations.hire() — an admin approving is vouching for this
            # person exactly as an owner hiring his own staff does; there is no second party to
            # mail a link to.
            st, _ = await asyncio.to_thread(
                self._http.call,
                f"{self._identity}/api/v1/auth/person/claim", method="POST",
                body={"token": invite, "password": password})
            if st != 200:
                raise OnboardingRefused("تعذّرت الموافقة — أعد الطلب.", reason="claim_failed")

        affiliate = Affiliate(
            id=new_id(), person_id=person_id, phone=app_row.phone, name=app_row.name,
            role=role, parent_id=app_row.parent_id, status=ACTIVE,
            application_id=app_row.id, created_at=int(time.time()),
            subject_ref=app_row.subject_ref or self._ref(app_row.phone),
            # HE ALREADY AGREED, AT apply() TIME — copied here so the Affiliate row (the one
            # every later slice reads) carries its own answer to "did this person ever consent"
            # without a join back to a possibly-erased Application row.
            agreed_terms_version=app_row.agreed_terms_version, agreed_at=app_row.agreed_at,
        )
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return affiliate

    async def reject(self, application_id: str, *, decided_by: str, reason: str = "") -> dict:
        row = await self._store.get(APPLICATIONS, application_id)
        if row is None:
            raise OnboardingRefused("الطلب غير موجود.", reason="not_found")
        app_row = Application.from_dict(row)
        if app_row.status == APPROVED:
            raise OnboardingRefused("هذا الطلب مقبول بالفعل.", reason="already_approved")
        if app_row.status == REJECTED:
            return {"already_rejected": True}   # idempotent, same reasoning as approve()

        app_row.status = REJECTED
        app_row.decided_at = int(time.time())
        app_row.decided_by = decided_by
        app_row.reason = reason[:500]
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        # No account was ever minted, so there is nothing at identity to undo — only our own
        # secret row, which never needed to exist past this decision either way.
        await self._store.delete(_PENDING_SECRET, application_id)
        return {"already_rejected": False}

    # ── suspending / reactivating an existing affiliate ──────────────────────────────────────
    async def suspend(self, affiliate_id: str, *, decided_by: str) -> dict[str, Any]:
        """spec §10: «تعليق لا حذف» — the row and every Referral he ever earned stay exactly as
        they are (ReferralRegistry.stamp() already refuses any NEW one for him from this moment
        — see that module). What changes here is that he can no longer SIGN IN: a "suspended"
        marketer who can still open the portal and message customers is not actually suspended,
        whatever the database says.

        IDEMPOTENT. Suspending an already-suspended affiliate is a no-op success, not a second
        decision — same reasoning as approve()/reject() elsewhere in this file."""
        affiliate = await self._affiliate_by_id(affiliate_id)
        if affiliate is None:
            raise OnboardingRefused("المسوّق غير موجود.", reason="not_found")
        if affiliate.status == SUSPENDED:
            return {"already_suspended": True}

        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, _ = await asyncio.to_thread(
            self._http.call,
            f"{self._identity}/internal/tenancy/membership/{self._tenant}::{affiliate.person_id}",
            method="DELETE", internal=True)
        if status not in (200, 204, 404):
            # REFUSED, NOT WARNED — same principle operations' own core/signup.py::revoke states
            # for exactly this call: the caller must not be told somebody was suspended while his
            # login still works.
            raise OnboardingRefused("تعذّر إيقاف الحساب. حاول بعد قليل.", reason="revoke_failed")

        affiliate.status = SUSPENDED
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"already_suspended": False}

    async def reactivate(self, affiliate_id: str, *, decided_by: str) -> dict[str, Any]:
        """The membership is re-granted with NO password and NO caps — identity's own add_member
        refuses to touch an existing person's credential (T2) and simply grants a membership when
        the person already exists, so his old password keeps working exactly as it did before the
        suspension. Idempotent, same shape as suspend()."""
        affiliate = await self._affiliate_by_id(affiliate_id)
        if affiliate is None:
            raise OnboardingRefused("المسوّق غير موجود.", reason="not_found")
        if affiliate.status == ACTIVE:
            return {"already_active": True}

        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, body = await asyncio.to_thread(
            self._http.call,
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": self._tenant, "identifier": affiliate.phone, "roles": [affiliate.role]})
        if status not in (200, 201):
            raise OnboardingRefused(_member_error(status, body), reason="grant_failed")

        affiliate.status = ACTIVE
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"already_active": False}

    async def set_platform_revenue_visibility(self, affiliate_id: str, *, enabled: bool) -> dict[str, Any]:
        """spec §10's optional whole-platform view — admin-only, OFF by
        default (Affiliate.sees_platform_revenue). No identity call here at all: this changes
        what a route READS, not who can sign in or what he can do — the same reasoning
        set_payout_method draws between "what he wants" and "who he is". The moment this flips
        True, /me/team simply starts returning the platform figure — no separate rollout, no
        code path only reachable through an admin UI that does not exist yet."""
        affiliate = await self._affiliate_by_id(affiliate_id)
        if affiliate is None:
            raise OnboardingRefused("المسوّق غير موجود.", reason="not_found")
        if affiliate.sees_platform_revenue == enabled:
            return {"changed": False, "sees_platform_revenue": enabled}
        affiliate.sees_platform_revenue = enabled
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"changed": True, "sees_platform_revenue": enabled}

    async def _affiliate_by_id(self, affiliate_id: str) -> Affiliate | None:
        row = await self._store.get(AFFILIATES, affiliate_id)
        return Affiliate.from_dict(row) if row else None

    # ── getting back in ─────────────────────────────────────────────────────────────────────
    async def sign_in(self, phone: str, password: str, code: str = "") -> dict[str, Any]:
        canonical = canonical_phone(phone, default_cc=self._cc)
        payload: dict[str, Any] = {
            "tenant": self._tenant, "username": canonical, "password": password}
        if code:
            payload["code"] = code
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, body = await asyncio.to_thread(
            self._http.call, f"{self._identity}/api/v1/auth/tenant", method="POST", body=payload)
        if status != 200:
            raise OnboardingRefused("رقم الجوال أو كلمة المرور غير صحيحة.")
        return body

    async def change_password(self, *, bearer: str, old_password: str, new_password: str) -> None:
        """NO PASSWORD IS STORED HERE, STILL — this changes NOTHING in `affiliates`; it forwards
        to identity's own `POST /api/v1/auth/change-password`, the one place a credential is ever
        held (same reasoning `apply()`'s own note gives for `_PENDING_SECRET`). The caller's own
        bearer token IS an identity-issued JWT already — `sign_in` above returns identity's
        response body verbatim, so the access_token the console holds was never re-minted by us —
        which is what lets this be a pure pass-through: identity re-verifies the token and answers
        for the exact person it names, never a person `self` merely claims to be."""
        # OFF THE EVENT LOOP — see core/customer_lookup.py::HttpCustomerLookup.resolve.
        status, body = await asyncio.to_thread(
            self._http.call,
            f"{self._identity}/api/v1/auth/change-password", method="POST",
            body={"old_password": old_password, "new_password": new_password}, bearer=bearer)
        if status != 200:
            # THE STATUS DECIDES FIRST, ALONE — a non-200 with no body (a timeout, a 500 with an
            # empty response) must never be read as "weak password" just because `body.get(...)`
            # defaults to None either way. Only once the peer is known to have actually answered
            # with 400 is its own body worth asking WHY.
            if status == 400:
                if body.get("detail") == "WEAK_PASSWORD":
                    raise OnboardingRefused(
                        "كلمة المرور الجديدة ضعيفة جداً.", reason="weak_password")
            raise OnboardingRefused("كلمة المرور الحالية غير صحيحة.", reason="wrong_password")


#: A separate collection, deliberately — see apply()'s note on why a chosen password is never
#: written into the same row an admin's dashboard lists and reads from.
_PENDING_SECRET = "affiliate_pending_secret"

#: Serialises apply() per-phone — added 2026-09-12, a real gap a QA audit found, same shape as
#: payouts.py's own `_PAYOUT_LOCKS`. The whole locked section is a handful of in-memory reads/
#: writes; this exists only to cover THAT window, never to be a human-facing wait.
_APPLY_LOCKS = "affiliate_apply_locks"
_APPLY_LOCK_TTL_SECONDS = 20

# ── sealing the one credential this collection ever holds ──────────────────────────────────────
#
# FIXED 2026-09-12, a real gap a QA audit found: the applicant's OWN password used to sit in
# `_PENDING_SECRET` unencrypted for the entire pending-approval window — every other credential
# this platform ever handles (SecretStore's operator secrets) is AES-256-GCM sealed under a KEK
# specifically because "storing the credential anyway is the one outcome that must never happen"
# (secret_store.py's own words), and this one row was the exception.
#
# A KEY DERIVED FROM THE SAME `SECRETS_KEK`, A DIFFERENT SALT — deliberately never the identical
# derived key `SecretStore` uses for operator credentials. Two different purposes sharing one KEK
# is fine (that is the whole point of a KEK: many secrets, one root); two different purposes
# sharing the SAME derived key is not, because a bug that ever logged or leaked one derived key
# would then also cover the other.
_PENDING_PASSWORD_SALT = b"affiliate-pending-password-v1"


def _seal_pending_password(kek: str, password: str) -> str:
    """AES-256-GCM, same primitive `secret_store.py` uses — `cryptography`'s AESGCM is a thin,
    constant-time C binding (OpenSSL), the right tool for one-shot authenticated encryption of a
    single short string rather than anything hand-rolled."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = hashlib.scrypt(kek.encode("utf-8"), salt=_PENDING_PASSWORD_SALT, n=2**14, r=8, p=1, dklen=32)
    iv = os.urandom(12)
    return base64.b64encode(iv + AESGCM(key).encrypt(iv, password.encode("utf-8"), None)).decode("ascii")


def _open_pending_password(kek: str, sealed: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = hashlib.scrypt(kek.encode("utf-8"), salt=_PENDING_PASSWORD_SALT, n=2**14, r=8, p=1, dklen=32)
    blob = base64.b64decode(sealed)
    return AESGCM(key).decrypt(blob[:12], blob[12:], None).decode("utf-8")


def _member_error(status: int, body: dict) -> str:
    detail = str(body.get("detail") or "")
    if detail == "USERNAME_TAKEN" or status == 409:
        return "لهذا الرقم حساب بالفعل."
    if detail == "WEAK_PASSWORD":
        return "كلمة المرور قصيرة."
    return "تعذّرت الموافقة. حاول بعد قليل."
