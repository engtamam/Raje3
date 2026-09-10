"""error-collector — admin actions declared for the platform admin panel.

The panel aggregates what every service declares HERE (served on /internal/manifest, so the code is
the source and the panel can never drift). Each action is a PURE literal dict — the safety:admin CI
gate reads it with ast.literal_eval, so no variables and no f-strings.

Rules the gate enforces: the path must exist in this service's manifest `endpoints`, and the
capability must be advertised in the manifest's `capabilities`. The panel is a MAP, never the
AUTHORITY — every action is re-checked at its own route on every call, and
`ci/check_capability_truth.py` compares the capability declared here against the one the handler
actually enforces, because a panel that renders a button for whoever holds the wrong capability is
a panel whose every click is a 403.

WHAT IS DELIBERATELY ABSENT: `POST /api/v1/signals/report`. It is a route any authenticated
person's browser calls automatically when something breaks in front of them — not an action an
operator performs, and a button labelled «أبلغ عن خطأ» on an admin panel would collect the
operator's own idle clicks and nothing else. The internal-token routes (ingest, reap) are absent
for the contract's own reason: an operator surface must be gated by a capability a person holds and
an audit that names them, never by a shared service token.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "errors.list",
        "label": "سجل الأخطاء",
        "method": "GET",
        "path": "/api/v1/signals",
        "capability": "platform.observability",
        "group": "المنصة",
        # WHY THIS EXISTS AT ALL, in one sentence an operator can act on: the answer to «الشاشة
        # وقفت عند فلان» used to require a developer with a kubeconfig reading pod logs by hand.
        "help": "كل خطأ سجّلته المنصة — من خوادمها ومن متصفحات المستخدمين — في مكان واحد، "
                "مع وقته والخدمة التي أصدرته ونصّه كاملاً. يُحفظ عشرة أيام ثم يُمحى تلقائياً.",
        # tenant/subject_ref: hand-built by AdminSignals.tsx's own customer-lookup, not this
        # generic form — declared for documentation parity with the live route, same as every
        # other catalog entry names what it actually accepts.
        "params": [
            {"name": "tenant", "in": "query", "type": "string", "required": False,
             "help": "أخطاء منشأة واحدة فقط"},
            {"name": "subject_ref", "in": "query", "type": "string", "required": False,
             "help": "أخطاء عميل واحد بعينه — يُحترَم فقط مع tenant"},
        ],
    },
    # ── the platform's own operator surface, inherited from _template ─────────────────────────
    # OURS, not an establishment's: these are the credentials and knobs our operators manage for
    # this service. Declared because a user-facing route with no action is a route the console
    # cannot render — and nothing anywhere fails to say so.
    {
        "id": "error-collector.operator_secrets", "label": "اعتمادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets", "group": "المنصة",
        # THE NAMES ONLY — a route that returned a value would put a credential in a screenshot.
        # This service holds no service-specific credential of its own today (the token Fluent Bit
        # presents is the shared INTERNAL_SERVICE_TOKEN, minted like every other service's, not set
        # here); kept from the scaffold so the door exists the day one is added.
        "help": "أي اعتمادات مضبوطة لهذه الخدمة، بأسمائها لا بقيمها.",
    },
    {
        "id": "error-collector.operator_secret_set", "label": "تعيين اعتماد", "method": "PUT",
        "path": "/api/v1/operator/secrets", "capability": "platform.secrets",
        "confirm": True, "group": "المنصة",
        "help": "يضبط قيمة اعتماد تشغيلي لهذه الخدمة.",
    },
    {
        "id": "error-collector.operator_secret_clear", "label": "مسح اعتماد", "method": "DELETE",
        "path": "/api/v1/operator/secrets/{name}", "capability": "platform.secrets",
        "params": [{"name": "name", "in": "path", "type": "string", "required": True}],
        "confirm": True, "danger": True, "group": "المنصة",
        "help": "يحذف اعتماداً تشغيلياً — تعود الخدمة لقيمته الافتراضية إن وُجدت.",
    },
    {
        "id": "error-collector.operator_config", "label": "إعدادات التشغيل", "method": "GET",
        "path": "/api/v1/operator/config", "capability": "platform.config", "group": "المنصة",
        # THE ONLY TWO SETTINGS TODAY: how long a signal is kept (SIGNAL_RETENTION_DAYS) and how
        # many rows one reap sweep may delete (SIGNAL_REAP_LIMIT) — see app/core/signals.py's own
        # header for why ten days is a privacy decision, not a disk-space one.
        "help": "القيم الفعّالة الآن لمدة الاحتفاظ بالأخطاء وحجم دفعة الحذف الدوري — كل واحدة إما افتراضية أو مُعدَّلة يدوياً.",
    },
    {
        "id": "error-collector.operator_config_set", "label": "تعديل إعداد تشغيلي", "method": "PUT",
        "path": "/api/v1/operator/config", "capability": "platform.config",
        "confirm": True, "group": "المنصة",
        "help": "يغيّر مدة الاحتفاظ أو حجم دفعة الحذف من الآن فصاعداً.",
    },
    {
        "id": "error-collector.operator_config_clear", "label": "إرجاع إعداد لقيمته",
        "method": "DELETE",
        "path": "/api/v1/operator/config/{key}", "capability": "platform.config",
        "params": [{"name": "key", "in": "path", "type": "string", "required": True}],
        "confirm": True, "group": "المنصة",
        "help": "يعيد إعداداً إلى قيمته الافتراضية.",
    },
    {
        "id": "error-collector.ping", "label": "فحص الاتصال", "method": "GET",
        "path": "/api/v1/signals/admin/ping", "capability": "platform.observability", "group": "المنصة",
        # From the generated scaffold and kept: what a client calls to confirm its token is accepted
        # at all, which is the first question asked when something else is failing.
        "help": "يؤكّد أن الخدمة تستقبل رمزك وتردّ.",
    },
    {
        "id": "error-collector.whoami", "label": "من أنا", "method": "GET",
        # The route itself enforces no capability — grouped under platform.observability here
        # only so it shows up alongside this service's own operator screens, same pattern as
        # loyalty's own admin_actions.py.
        "path": "/api/v1/signals/whoami", "capability": "platform.observability", "group": "المنصة",
        "help": "المنشأة والصلاحيات التي يحملها رمزك الآن.",
    },
]
