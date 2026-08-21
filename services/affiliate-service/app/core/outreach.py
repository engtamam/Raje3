# =============================================================================
# affiliate-service — the outbound conversion playbook (2026-08-22)
# -----------------------------------------------------------------------------
# A FINER axis than Lead.status. Every lead already carries a coarse triage state
# (new/assigned/contacted/interested/...); this is the sales-specific funnel a promoter actually
# walks to turn a discovered business into a paying subscriber — gatekeeper, hook, zero-friction
# offer, staged follow-up, fast-value onboarding, paid conversion, plus a cold-revival leg and a
# post-conversion referral leg. Both axes live on the same Lead row; neither replaces the other.
#
# STAGES AND TEMPLATES ARE MANAGED DATA, NEVER HARDCODED. OutreachStage is a taxonomy exactly like
# Sector (core/sectors.py) — a manager defines it, it is never deleted (only deactivated), and
# nothing in this file assumes any particular stage exists. The eight-stage playbook is SEED DATA
# a manager can edit or replace entirely.
#
# TEMPLATES ARE SHARED ACROSS THE WHOLE PROGRAM, NOT PER-MANAGER. A script one manager finds
# converts becomes every other manager's tool the same day — silo-ing it per manager would keep a
# working idea locked in one team for no reason. Read+use is open to any affiliate; create/edit is
# manager-only, enforced at the API layer the same way affiliate_self.py already gates other
# manager-only actions (`affiliate["role"] != get_settings().AFFILIATE_MANAGER_ROLE`).
#
# OUTCOME IS NEVER INFERRED. Whether a shop owner replied, advanced, or went quiet is a fact only
# the promoter who read the reply can assert — computing it from elapsed time or from what message
# went out next would fabricate a fact nobody actually knows. `TemplateUse.outcome` starts PENDING
# and is changed by a human call, always (`set_outcome`), same discipline as `Lead.converted_tenant`
# never being auto-matched.
# =============================================================================
from __future__ import annotations

import time
from typing import Any

from app.core.lead_sourcing import owns_lead
from app.core.models import (
    LEADS,
    MESSAGE_TEMPLATES,
    OUTCOME_PENDING,
    OUTREACH_STAGES,
    TEMPLATE_OUTCOMES,
    TEMPLATE_USES,
    Lead,
    MessageTemplate,
    OutreachStage,
    TemplateUse,
    new_id,
)


class OutreachError(Exception):
    def __init__(self, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.reason = reason


class OutreachStageService:
    """Same shape as SectorService exactly — a managed, never-deleted taxonomy."""

    def __init__(self, *, store) -> None:
        self._s = store

    async def create(self, *, code: str, name: str, order: int = 0) -> OutreachStage:
        code = code.strip()
        name = name.strip()
        if not code or not name:
            raise OutreachError("أدخل رمز واسم المرحلة.", reason="missing_fields")
        existing = await self._s.get(OUTREACH_STAGES, code)
        if existing is not None:
            stage = OutreachStage.from_dict(existing)
            stage.name = name
            stage.order = order
            stage.active = True
        else:
            stage = OutreachStage(code=code, name=name, order=order, active=True,
                                  created_at=int(time.time()))
        await self._s.put(OUTREACH_STAGES, stage.code, stage.to_dict())
        return stage

    async def deactivate(self, code: str) -> bool:
        row = await self._s.get(OUTREACH_STAGES, code)
        if row is None:
            return False
        stage = OutreachStage.from_dict(row)
        if not stage.active:
            return False   # idempotent — already off
        stage.active = False
        await self._s.put(OUTREACH_STAGES, stage.code, stage.to_dict())
        return True

    async def get(self, code: str) -> OutreachStage | None:
        row = await self._s.get(OUTREACH_STAGES, code)
        return OutreachStage.from_dict(row) if row else None

    async def list(self, *, active_only: bool = True, limit: int = 200) -> list[OutreachStage]:
        if active_only:
            rows, _ = await self._s.find(OUTREACH_STAGES, {"active": True}, limit=limit)
        else:
            rows = await self._s.scan_all(OUTREACH_STAGES, limit)
        return sorted((OutreachStage.from_dict(r) for r in rows), key=lambda s: (s.order, s.code))


class TemplateService:
    """The copy-paste library. Manager-writable, everyone-readable — see this module's own
    docstring for why it is shared rather than siloed per manager."""

    def __init__(self, *, store) -> None:
        self._s = store

    async def create(self, *, stage_code: str, kind: str, title: str, body: str = "",
                     media_url: str = "", objection_type: str = "",
                     created_by: str = "") -> MessageTemplate:
        stage_code = stage_code.strip()
        title = title.strip()
        if not stage_code or not title:
            raise OutreachError("أدخل المرحلة وعنوان القالب.", reason="missing_fields")
        now = int(time.time())
        tpl = MessageTemplate(id=new_id(), stage_code=stage_code, kind=kind.strip(),
                              title=title, body=body, media_url=media_url,
                              objection_type=objection_type.strip(), active=True,
                              created_by=created_by, created_at=now, updated_at=now)
        await self._s.put(MESSAGE_TEMPLATES, tpl.id, tpl.to_dict())
        return tpl

    async def update(self, template_id: str, **fields: Any) -> MessageTemplate:
        row = await self._s.get(MESSAGE_TEMPLATES, template_id)
        if row is None:
            raise OutreachError("القالب غير موجود.", reason="not_found")
        tpl = MessageTemplate.from_dict(row)
        for name in ("stage_code", "kind", "title", "body", "media_url", "objection_type"):
            if name in fields and fields[name] is not None:
                setattr(tpl, name, str(fields[name]))
        tpl.updated_at = int(time.time())
        await self._s.put(MESSAGE_TEMPLATES, tpl.id, tpl.to_dict())
        return tpl

    async def deactivate(self, template_id: str) -> bool:
        row = await self._s.get(MESSAGE_TEMPLATES, template_id)
        if row is None:
            return False
        tpl = MessageTemplate.from_dict(row)
        if not tpl.active:
            return False   # idempotent
        tpl.active = False
        tpl.updated_at = int(time.time())
        await self._s.put(MESSAGE_TEMPLATES, tpl.id, tpl.to_dict())
        return True

    async def get(self, template_id: str) -> MessageTemplate | None:
        row = await self._s.get(MESSAGE_TEMPLATES, template_id)
        return MessageTemplate.from_dict(row) if row else None

    async def list(self, *, stage_code: str = "", active_only: bool = True,
                   limit: int = 500) -> list[MessageTemplate]:
        query: dict[str, Any] = {}
        if active_only:
            query["active"] = True
        if stage_code:
            query["stage_code"] = stage_code
        if query:
            rows, _ = await self._s.find(MESSAGE_TEMPLATES, query, limit=limit)
        else:
            rows = await self._s.scan_all(MESSAGE_TEMPLATES, limit)
        return sorted((MessageTemplate.from_dict(r) for r in rows),
                     key=lambda t: (t.stage_code, t.title))


class TemplateUseService:
    """The one place ownership is checked, a use is logged, and the analytics this whole feature
    exists for is computed — see this module's own docstring on why outcome is never inferred."""

    def __init__(self, *, store, templates: TemplateService) -> None:
        self._s = store
        self._templates = templates

    async def _owned_lead(self, lead_id: str, affiliate_id: str) -> Lead:
        row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(row) if row else None
        if lead is None:
            raise OutreachError("العميل المحتمل غير موجود.", reason="not_found")
        if not await owns_lead(self._s, lead, affiliate_id):
            raise OutreachError("هذا العميل المحتمل مو مُسنَد لك أو لأحد بفريقك.",
                                reason="not_yours")
        return lead

    async def log_use(self, lead_id: str, *, template_id: str, used_by: str) -> TemplateUse:
        await self._owned_lead(lead_id, used_by)
        tpl = await self._templates.get(template_id)
        if tpl is None:
            raise OutreachError("القالب غير موجود.", reason="template_not_found")
        # A SNAPSHOT, not a live reference — see TemplateUse's own docstring: a template edited or
        # deactivated after this moment must never silently rewrite what already happened.
        use = TemplateUse(id=new_id(), lead_id=lead_id, template_id=template_id,
                          stage_code=tpl.stage_code, kind=tpl.kind, used_by=used_by,
                          used_at=int(time.time()), outcome=OUTCOME_PENDING)
        await self._s.put(TEMPLATE_USES, use.id, use.to_dict())

        row = await self._s.get(LEADS, lead_id)
        lead = Lead.from_dict(row)
        lead.notes.append({"at": use.used_at, "by": used_by,
                           "text": f"استخدم قالب «{tpl.title}» ({tpl.stage_code})",
                           "status_from": lead.status, "status_to": lead.status})
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return use

    async def set_decision_maker(self, lead_id: str, *, by: str, name: str = "",
                                 phone: str = "", role: str = "") -> Lead:
        lead = await self._owned_lead(lead_id, by)
        lead.decision_maker_name = name.strip()
        lead.decision_maker_phone = phone.strip()
        lead.decision_maker_role = role.strip()
        lead.notes.append({"at": int(time.time()), "by": by,
                           "text": f"سجَّل رقم صاحب القرار: {lead.decision_maker_name}",
                           "status_from": lead.status, "status_to": lead.status})
        await self._s.put(LEADS, lead.id, lead.to_dict())
        return lead

    async def set_outcome(self, use_id: str, *, outcome: str, by: str, note: str = "",
                          new_stage_code: str | None = None,
                          stages: OutreachStageService | None = None) -> TemplateUse:
        if outcome not in TEMPLATE_OUTCOMES:
            raise OutreachError("نتيجة غير معروفة.", reason="bad_outcome")
        row = await self._s.get(TEMPLATE_USES, use_id)
        if row is None:
            raise OutreachError("سجل الاستخدام غير موجود.", reason="not_found")
        use = TemplateUse.from_dict(row)

        lead_row = await self._s.get(LEADS, use.lead_id)
        lead = Lead.from_dict(lead_row) if lead_row else None
        if lead is None or not await owns_lead(self._s, lead, by):
            raise OutreachError("هذا السجل مو مُسنَد لك أو لأحد بفريقك.", reason="not_yours")

        use.outcome = outcome
        use.outcome_at = int(time.time())
        use.outcome_by = by
        use.note = note
        await self._s.put(TEMPLATE_USES, use.id, use.to_dict())

        # THE STAGE MOVE IS ITS OWN, EXPLICIT ARGUMENT — never inferred from outcome=="advanced".
        # A promoter names the destination stage himself; that is the only way "advanced" (this
        # use worked) and "advanced TO WHICH stage" can both be true facts rather than one guess
        # standing in for the other.
        if new_stage_code:
            if stages is not None:
                stage = await stages.get(new_stage_code)
                if stage is None or not stage.active:
                    raise OutreachError("مرحلة غير معروفة أو معطّلة.", reason="bad_stage")
            lead.notes.append({"at": use.outcome_at, "by": by,
                               "text": f"انتقل لمرحلة: {new_stage_code}",
                               "status_from": lead.outreach_stage_code,
                               "status_to": new_stage_code})
            lead.outreach_stage_code = new_stage_code
            await self._s.put(LEADS, lead.id, lead.to_dict())
        return use

    async def uses_for_lead(self, lead_id: str, *, limit: int = 200) -> list[TemplateUse]:
        rows, _ = await self._s.find(TEMPLATE_USES, {"lead_id": lead_id}, limit=limit,
                                     sort=("used_at", "desc"))
        return [TemplateUse.from_dict(r) for r in rows]

    # ── the whole point: which templates actually move a lead forward ───────────────────────────
    async def stats(self, *, stage_code: str = "", limit: int = 20000) -> list[dict[str, Any]]:
        """Per-template counts, computed on demand — never stored twice, same bounded-scan idiom
        as Lead.sector_stats(). `advance_rate` is the number a manager actually decides from."""
        query: dict[str, Any] = {"stage_code": stage_code} if stage_code else {}
        if query:
            rows, _ = await self._s.find(TEMPLATE_USES, query, limit=limit)
        else:
            rows = await self._s.scan_all(TEMPLATE_USES, limit)
        by_template: dict[str, dict[str, Any]] = {}
        for r in rows:
            tid = r.get("template_id", "")
            bucket = by_template.setdefault(tid, {
                "template_id": tid, "stage_code": r.get("stage_code", ""),
                "kind": r.get("kind", ""), "uses": 0,
                "pending": 0, "advanced": 0, "no_response": 0, "rejected": 0,
            })
            bucket["uses"] += 1
            outcome = r.get("outcome", OUTCOME_PENDING)
            if outcome in bucket:
                bucket[outcome] += 1
        out = []
        for bucket in by_template.values():
            tpl = await self._templates.get(bucket["template_id"])
            bucket["title"] = tpl.title if tpl else ""
            bucket["advance_rate"] = (bucket["advanced"] / bucket["uses"]) if bucket["uses"] else 0.0
            out.append(bucket)
        return sorted(out, key=lambda b: -b["advance_rate"])

    async def kind_stats(self, *, limit: int = 20000) -> list[dict[str, Any]]:
        """The same aggregate, one level coarser — WHICH CONTENT TYPE works, across every template
        sharing a `kind`, not just which single template happens to."""
        rows = await self._s.scan_all(TEMPLATE_USES, limit)
        by_kind: dict[str, dict[str, Any]] = {}
        for r in rows:
            kind = r.get("kind", "")
            bucket = by_kind.setdefault(kind, {
                "kind": kind, "uses": 0, "pending": 0, "advanced": 0, "no_response": 0,
                "rejected": 0,
            })
            bucket["uses"] += 1
            outcome = r.get("outcome", OUTCOME_PENDING)
            if outcome in bucket:
                bucket[outcome] += 1
        for bucket in by_kind.values():
            bucket["advance_rate"] = (bucket["advanced"] / bucket["uses"]) if bucket["uses"] else 0.0
        return sorted(by_kind.values(), key=lambda b: -b["advance_rate"])
