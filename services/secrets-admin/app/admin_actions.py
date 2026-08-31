"""secrets-admin — admin actions declared for the platform admin panel.

The panel aggregates what every service declares HERE (served on /internal/manifest, so the code is
the source and the panel can never drift). Each action is a PURE literal dict (the safety:admin CI
gate reads it with ast.literal_eval — no variables, no f-strings).

TWO ACTIONS, AND THERE WILL NEVER BE A THIRD OF THE OBVIOUS KIND. There is no `secrets.reveal`, not
declared and not implemented, and that is the product decision this whole service is built on: a
credential a panel can display is a credential in every screenshot and every screen-share of
everybody who ever held the capability. What the panel shows is the last four characters captured
at the moment of writing, which is enough to answer «هل هذا هو المفتاح الذي أرسلته لكم؟» and not
enough to be one.

BOTH CARRY `platform.secrets_manage`, which is what the routes enforce — ci/check_capability_truth.py
compares the two and fails on a mismatch, because a panel that renders a button for whoever holds
the wrong capability is a panel whose every click is a 403.
"""
from __future__ import annotations

from typing import Any


ADMIN_ACTIONS: list[dict[str, Any]] = [
    {
        "id": "secrets.list",
        "label": "مفاتيح المزوّدين",
        "method": "GET",
        "path": "/api/v1/secrets",
        "capability": "platform.secrets_manage",
        "group": "المنصة",
        # The screen this feeds shows a status and four characters. It never shows a value, and
        # the route it calls is structurally incapable of returning one.
        "help": "حالة كل مفتاح: مُعدّ أو لا، وآخر أربعة أحرف منه، ومن غيّره ومتى. القيمة نفسها "
                "لا تُعرض أبداً.",
    },
    {
        "id": "secrets.update",
        "label": "تحديث مفتاح",
        "method": "POST",
        "path": "/api/v1/secrets/{key}",
        "capability": "platform.secrets_manage",
        "params": [
            {"name": "key", "in": "path", "type": "string", "required": True},
            {"name": "value", "in": "body", "type": "string", "required": True},
        ],
        # CONFIRMED AND DANGEROUS, and `danger` is not decoration here: the write restarts a live
        # service, and a wrong paste stops every WhatsApp message on the product until somebody
        # notices. It must never fire on a stray click.
        "confirm": True,
        "danger": True,
        "group": "المنصة",
        "help": "يُستبدل المفتاح فوراً وتُعاد تشغيل الخدمة التي تقرأه — انقطاع ثوانٍ. "
                "القيمة لا يمكن استرجاعها بعد الحفظ.",
    },
]
