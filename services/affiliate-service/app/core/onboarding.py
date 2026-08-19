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

import json
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.phone import canonical_phone
from app.core.models import (
    ACTIVE,
    AFFILIATES,
    APPLICATIONS,
    APPROVED,
    INVITED,
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


class OnboardingService:
    def __init__(self, *, store, http: Http, identity_url: str, tenant: str,
                 manager_role: str = MANAGER, promoter_role: str = PROMOTER,
                 default_cc: str = "966", pii_salt: str = "",
                 terms_version: str = "v1",
                 tenants_url: str = "", authz_url: str = "") -> None:
        self._store = store
        self._http = http
        self._identity = identity_url.rstrip("/")
        self._tenant = tenant
        self._manager_role = manager_role
        self._promoter_role = promoter_role
        self._cc = default_cc
        self._salt = pii_salt
        self._terms_version = terms_version
        # THE SHARED AFFILIATE TENANT'S OWN PROVISIONING (spec §1/§12) — see _ensure_tenant_ready
        # for the whole reasoning. Optional: empty means "assume it already exists", which keeps
        # a test/local run that never set these working exactly as it did before this existed.
        self._tenants = tenants_url.rstrip("/")
        self._authz = authz_url.rstrip("/")
        self._tenant_ready = False   # per-process cache — see _ensure_tenant_ready's own note

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
        status, _ = self._http.call(
            f"{self._tenants}/internal/tenants/{self._tenant}", method="GET", internal=True)
        if status != 200:
            status, body = self._http.call(
                f"{self._tenants}/internal/tenants", method="POST", internal=True,
                body={"slug": self._tenant, "name": "برنامج المسوّقين بالعمولة"})
            # 409 = another approval won this exact race a moment ago — not a failure.
            if status not in (201, 409):
                raise OnboardingRefused(
                    "تعذّرت الموافقة — تهيئة النظام غير مكتملة.", reason="tenant_provision_failed")

        if self._authz:
            status, _ = self._http.call(
                f"{self._authz}/internal/authz/tenants/{self._tenant}/bootstrap", method="POST",
                internal=True,
                body={"roles": [
                    {"name": self._manager_role, "capabilities": [],
                     "description": "مدير تسويق — بوابة المسوّقين بالعمولة"},
                    {"name": self._promoter_role, "capabilities": [],
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
                    referral_code: str = "", agreed: bool = False) -> dict[str, Any]:
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

        # ONE ATTEMPT AT A TIME PER NUMBER. A second apply while the first is still pending is not
        # a new person — refusing it here is what stops an admin's inbox from filling with
        # duplicates of the same applicant retrying a slow connection.
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

        now = int(time.time())
        app_row = Application(
            id=new_id(), phone=canonical, name=name.strip(), parent_id=parent_id,
            status=PENDING, created_at=now, subject_ref=self._ref(canonical),
            agreed_terms_version=self._terms_version, agreed_at=now,
        )
        # THE PASSWORD IS NOT STORED HERE. Only identity ever holds a credential — this row is a
        # request to be judged, and a plaintext password sitting in a pending-applications table
        # for however long an admin takes to look at it is exactly the kind of "we'll get to it"
        # PII debt this whole platform has spent this session closing everywhere else.
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        # THE ONE EXCEPTION: kept in a SEPARATE, short-lived row so approval can still mint the
        # account with the password the applicant actually chose — never a generated one he was
        # never told, which would just lock him out on his first sign-in.
        await self._store.put(_PENDING_SECRET, app_row.id,
                              {"id": app_row.id, "password": password})
        return {"application_id": app_row.id, "status": PENDING}

    # ── a manager inviting somebody directly ────────────────────────────────────────────────
    async def invite(self, *, inviter_person_id: str, phone: str, name: str) -> dict[str, Any]:
        """A manager names somebody he wants on his team. STILL a row for an admin to decide —
        the admin gate (spec §2) is about the RISK a new marketer account carries, which does
        not shrink because a manager vouches for him first; it only removes the friction of a
        referral code the manager would otherwise have to hand over out-of-band.

        NO PASSWORD IS ASKED HERE, and that is the one real difference from apply(): the manager
        does not know what password the invited person will want, and asking him to invent one on
        somebody else's behalf is exactly the T2 mistake identity-service itself refuses (an
        existing person's credential is never set by an admin). See approve()'s invite branch and
        accept_invite() for how the invited person ends up choosing his own.
        """
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise OnboardingRefused("أدخل رقم جوال صحيح.")
        if not name.strip():
            raise OnboardingRefused("أدخل اسم المدعو.")

        inviter = await self._affiliate_by_person(inviter_person_id)
        if inviter is None or inviter.status != ACTIVE:
            raise OnboardingRefused("حسابك غير مفعّل للدعوة.", reason="not_an_active_affiliate")
        if inviter.role != self._manager_role:
            # PROMOTERS DO NOT INVITE. Spec §1's tree grows from a manager down; a promoter's
            # own referral code (self-apply's `referral_code`) is the mechanism the person he
            # brings in is expected to use — a distinct, lower-trust door on purpose.
            raise OnboardingRefused("دعوة المسوّقين مقصورة على المدير.", reason="managers_only")

        existing = await self._find_application_by_phone(canonical)
        if existing is not None and existing.status == PENDING:
            raise OnboardingRefused(
                "هناك طلب سابق لهذا الرقم قيد المراجعة.", reason="already_pending")
        if await self._affiliate_by_phone(canonical) is not None:
            raise OnboardingRefused("لهذا الرقم حساب مسوّق بالفعل.", reason="already_affiliate")

        app_row = Application(
            id=new_id(), phone=canonical, name=name.strip(), parent_id=inviter.id,
            invited_by=inviter.id, status=PENDING, created_at=int(time.time()),
            subject_ref=self._ref(canonical),
        )
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        # NO `_PENDING_SECRET` ROW — deliberately. Its absence is exactly what approve() reads
        # to tell an invitation from a self-application; writing one here (even empty) would
        # blur that signal for the one check that must never be ambiguous.
        return {"application_id": app_row.id, "status": PENDING}

    # ── who am I ─────────────────────────────────────────────────────────────────────────────
    async def me(self, person_id: str) -> dict[str, Any] | None:
        """What the signed-in affiliate needs to see his OWN referral link — his own `id` IS his
        referral code (spec §1: `?aff=<id>` for a shop, `?ref=<id>` for another marketer applying
        under him), so there is no separate code to mint or keep in step with this row.

        None when `person_id` matches no Affiliate row at all — a token minted for a tenant this
        service does not own, or a race between claiming an invite and this being called. Never
        raises; the route turns None into 404.

        NOT `affiliate.to_dict()` — that carries `invite_token`, which has no business leaving
        this service even blank: a response shape that CAN carry a credential-adjacent field is
        one keystroke away from doing it by accident on some future edit. Named fields only, same
        discipline operator.py's own `list_secrets` already follows for hints vs. values."""
        affiliate = await self._affiliate_by_person(person_id)
        if affiliate is None:
            return None
        return {"id": affiliate.id, "role": affiliate.role, "name": affiliate.name,
               "parent_id": affiliate.parent_id, "status": affiliate.status}

    async def _affiliate_by_person(self, person_id: str) -> Affiliate | None:
        if not person_id:
            return None
        rows, _ = await self._store.find(AFFILIATES, {"person_id": person_id}, limit=1)
        return Affiliate.from_dict(rows[0]) if rows else None

    async def _find_application_by_phone(self, phone: str) -> Application | None:
        rows, _ = await self._store.find(APPLICATIONS, {"phone": phone}, limit=1,
                                         sort=("created_at", "desc"))
        return Application.from_dict(rows[0]) if rows else None

    async def _affiliate_by_phone(self, phone: str) -> Affiliate | None:
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

        role = self._promoter_role if app_row.parent_id else self._manager_role

        if app_row.invited_by:
            # THE MANAGER-INVITE BRANCH — no password anywhere in this process yet. See
            # invite()'s own docstring for why one was never asked for.
            affiliate = await self._mint_invited(app_row, role=role)
        else:
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
        password = str((secret or {}).get("password") or "")
        if not password:
            # THE SECRET ROW IS GONE OR WAS NEVER WRITTEN. Minting a membership with no password
            # the applicant knows would hand him an account he cannot sign into — refused rather
            # than half-done, same principle as operations' own hire().
            raise OnboardingRefused("تعذّرت الموافقة — أعد الطلب.", reason="secret_missing")

        status, body = self._http.call(
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
            st, _ = self._http.call(
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

    async def _mint_invited(self, app_row: Application, *, role: str) -> Affiliate:
        """No password exists anywhere yet. identity mints the membership in its own INVITE mode
        (Settings.IDENTITY_MEMBER_ADD_MODE — the default across this platform) and hands back a
        one-time token; we hold onto it ourselves rather than leaving it only at identity, so our
        OWN accept_invite() can flip this row to ACTIVE the moment it is redeemed rather than the
        console having to ask identity separately whether it was."""
        status, body = self._http.call(
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": self._tenant, "identifier": app_row.phone, "roles": [role]})
        if status not in (200, 201):
            raise OnboardingRefused(_member_error(status, body))

        person_id = str(body.get("person_id") or "")
        await self._ensure_tenant_ready(first_subject=person_id, first_role=role)
        invite = str(body.get("invite_token") or "")
        if not invite:
            # IDENTITY_MEMBER_ADD_MODE=password on this deployment — there is no invite to hand
            # the invited person and no password to give him either, since invite() never asked
            # a manager to invent one on somebody else's behalf. A real configuration mismatch,
            # surfaced rather than silently minting an account nobody can sign into.
            raise OnboardingRefused(
                "الدعوات غير مُفعّلة على هذا الإعداد — تواصل مع الدعم الفني.",
                reason="invite_mode_disabled")

        affiliate = Affiliate(
            id=new_id(), person_id=person_id, phone=app_row.phone, name=app_row.name,
            role=role, parent_id=app_row.parent_id, status=INVITED,
            application_id=app_row.id, created_at=int(time.time()),
            subject_ref=app_row.subject_ref or self._ref(app_row.phone),
            invite_token=invite,
        )
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return affiliate

    # ── the invited person choosing their own password ──────────────────────────────────────
    async def accept_invite(self, *, token: str, password: str, agreed: bool = False) -> dict[str, Any]:
        rows, _ = await self._store.find(AFFILIATES, {"invite_token": token}, limit=1)
        affiliate = Affiliate.from_dict(rows[0]) if rows else None
        if affiliate is None or affiliate.status != INVITED:
            # ONE SENTENCE for "no such token", "already used" and "expired" alike — same
            # enumeration-oracle reasoning as every other refusal in this file: a caller must not
            # be able to tell which of the three is true one request at a time.
            raise OnboardingRefused("الدعوة غير صالحة أو منتهية.", reason="invalid_invite")
        # spec §2 — HIS agreement, not the manager who invited him. Checked before the identity
        # call so a refusal here never burns the one-time claim on a person who has not actually
        # agreed to anything yet.
        if not agreed:
            raise OnboardingRefused("وافق على الشروط وسياسة الخصوصية للمتابعة.", reason="must_agree")

        status, _ = self._http.call(
            f"{self._identity}/api/v1/auth/person/claim", method="POST",
            body={"token": token, "password": password})
        if status != 200:
            raise OnboardingRefused("تعذّر قبول الدعوة. حاول مرة أخرى.", reason="claim_failed")

        affiliate.status = ACTIVE
        affiliate.invite_token = ""     # spent — see the field's own note in models.py
        affiliate.agreed_terms_version = self._terms_version
        affiliate.agreed_at = int(time.time())
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"affiliate_id": affiliate.id}

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

        status, _ = self._http.call(
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

        status, body = self._http.call(
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": self._tenant, "identifier": affiliate.phone, "roles": [affiliate.role]})
        if status not in (200, 201):
            raise OnboardingRefused(_member_error(status, body), reason="grant_failed")

        affiliate.status = ACTIVE
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())
        return {"already_active": False}

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
        status, body = self._http.call(
            f"{self._identity}/api/v1/auth/tenant", method="POST", body=payload)
        if status != 200:
            raise OnboardingRefused("رقم الجوال أو كلمة المرور غير صحيحة.")
        return body


#: A separate collection, deliberately — see apply()'s note on why a chosen password is never
#: written into the same row an admin's dashboard lists and reads from.
_PENDING_SECRET = "affiliate_pending_secret"


def _member_error(status: int, body: dict) -> str:
    detail = str(body.get("detail") or "")
    if detail == "USERNAME_TAKEN" or status == 409:
        return "لهذا الرقم حساب بالفعل."
    if detail == "WEAK_PASSWORD":
        return "كلمة المرور قصيرة."
    return "تعذّرت الموافقة. حاول بعد قليل."
