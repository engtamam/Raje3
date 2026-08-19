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
import re
import time
import urllib.error
import urllib.request
from typing import Any

from app.core.models import (
    ACTIVE,
    AFFILIATES,
    APPLICATIONS,
    APPROVED,
    MANAGER,
    PENDING,
    PROMOTER,
    REJECTED,
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


def canonical_phone(raw: str, *, default_cc: str) -> str:
    """Same fold as operations' own — see that module for why one human must never become two
    accounts because of how he typed his number."""
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
                 default_cc: str = "966", pii_salt: str = "") -> None:
        self._store = store
        self._http = http
        self._identity = identity_url.rstrip("/")
        self._tenant = tenant
        self._manager_role = manager_role
        self._promoter_role = promoter_role
        self._cc = default_cc
        self._salt = pii_salt

    def _ref(self, phone: str) -> str:
        """"" when PII_SALT is unset (local/dev) — erasure.py then simply finds nothing rather
        than raising, same fallback shape as the rest of this platform's optional salt."""
        return _subject_ref(self._salt, self._tenant, phone) if self._salt else ""

    # ── applying ─────────────────────────────────────────────────────────────────────────────
    async def apply(self, *, phone: str, name: str, password: str,
                    referral_code: str = "") -> dict[str, Any]:
        canonical = canonical_phone(phone, default_cc=self._cc)
        if not canonical:
            raise OnboardingRefused("أدخل رقم جوال صحيح.")
        if not name.strip():
            raise OnboardingRefused("أدخل اسمك.")

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

        app_row = Application(
            id=new_id(), phone=canonical, name=name.strip(), parent_id=parent_id,
            status=PENDING, created_at=int(time.time()), subject_ref=self._ref(canonical),
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

        secret = await self._store.get(_PENDING_SECRET, application_id)
        password = str((secret or {}).get("password") or "")
        if not password:
            # THE SECRET ROW IS GONE OR WAS NEVER WRITTEN. Minting a membership with no password
            # the applicant knows would hand him an account he cannot sign into — refused rather
            # than half-done, same principle as operations' own hire().
            raise OnboardingRefused("تعذّرت الموافقة — أعد الطلب.", reason="secret_missing")

        role = self._promoter_role if app_row.parent_id else self._manager_role
        status, body = self._http.call(
            f"{self._identity}/internal/tenancy/members", method="POST", internal=True,
            body={"tenant": self._tenant, "identifier": app_row.phone, "roles": [role],
                  "password": password})
        if status not in (200, 201):
            raise OnboardingRefused(_member_error(status, body))

        person_id = str(body.get("person_id") or "")
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
        )
        await self._store.put(AFFILIATES, affiliate.id, affiliate.to_dict())

        app_row.status = APPROVED
        app_row.decided_at = int(time.time())
        app_row.decided_by = decided_by
        await self._store.put(APPLICATIONS, app_row.id, app_row.to_dict())
        # THE PASSWORD IS GONE THE MOMENT IT HAS DONE ITS ONE JOB — minting the membership above.
        # Keeping it a second longer than approval takes is PII with no purpose left to serve.
        await self._store.delete(_PENDING_SECRET, application_id)

        return {"affiliate_id": affiliate.id, "role": role, "already_approved": False}

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
