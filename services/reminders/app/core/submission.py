"""Handing the shop's OWN text to Meta — on his number, with no review of ours in between.

THE DECISION THIS IMPLEMENTS, in the owner's words: «احنا ما نراجع، هو يرفع مباشرة على ميتا لانه
اساسا على رقمه». The template is submitted to HIS WhatsApp Business Account, judged by Meta, and
we are not a checkpoint. What we still owe him is the plumbing — a generated name he never sees,
and a refusal carried back in Meta's own words so «ساعدوني» has something true to send.

WHAT WAS MISSING. `custom_templates.py` could draft, version and record a verdict, and nothing
could hand a draft to Meta: registering and submitting were user-tier routes needing a JWT whose
signing key must stay in identity-service. He wrote a text, pressed nothing, and it sat as a draft
for ever. base-services v0.16.6 added the internal twins in answer to our escalation.

TWO CALLS, AND THE FIRST ONE IS NOT OPTIONAL. `register` puts the body in notification-service's
registry — a local upsert, no Meta call — and `submit` is what reaches Meta. Submitting a name that
was never registered is a 404 from the peer, and the owner would read it as a rejection of his text.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
from typing import Any

from app.adapters import internal_http


class NullSubmitter:
    """No peer configured. Refuses, and says why — never a quiet success.

    A DRAFT REPORTED AS SUBMITTED is the worst answer here: the owner stops waiting for a verdict
    that will never come, and the text he wrote reaches nobody while the screen says it is under
    review.
    """

    driver = "null"

    def __init__(self) -> None:
        self.submitted: list[tuple[str, str]] = []

    async def submit(self, tenant: str, template: dict[str, Any]) -> dict[str, Any]:
        return {"ok": False, "reason": "الرفع إلى واتساب غير مهيّأ الآن — حاول بعد قليل."}


def _examples(template: dict[str, Any]) -> list[str]:
    """One example value per numbered slot, in the order Meta expects them.

    `sample_slots` returns a map keyed by the slot NUMBER; Meta wants a positional list, and the
    order has to follow `variables` rather than the dictionary — a body whose slots are {{2}},{{1}}
    is legal and would otherwise be described backwards.
    """
    from app.core.reasons import sample_slots

    numbers = [str(v) for v in (template.get("variables") or [])]
    if not numbers:
        return []
    filled = sample_slots(template, establishment=str(template.get("establishment") or "محلّك"))
    # NEVER THE NUMBER ITSELF as a fallback — that is the exact value Meta rejects, and returning
    # it here would reproduce the defect while looking like a fix.
    return [filled.get(n) or "مثال" for n in numbers]


class HttpSubmitter:
    """notification-service's internal register + submit twins."""

    driver = "http"

    def __init__(self, *, notify_url: str, register_path: str, submit_path: str,
                 token: str, timeout: int = 8) -> None:
        base = notify_url.rstrip("/")
        self._register = base + register_path
        self._submit = base + submit_path
        self._token = token
        self._timeout = timeout

    def _post(self, url: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        data = json.dumps(body).encode() if body is not None else b""
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            status, raw = internal_http.send(
                url, timeout=self._timeout, method="POST", body=data,
                content_type=internal_http.JSON, token=self._token)
            return status, json.loads(raw or b"{}")
        except urllib.error.HTTPError as exc:
            return exc.code, {"detail": exc.read().decode()[:300]}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return 503, {"detail": str(exc)[:160]}

    async def submit(self, tenant: str, template: dict[str, Any]) -> dict[str, Any]:
        """Register the body, then hand it to Meta. Returns what the OWNER should be told.

        THE CATEGORY IS HIS. He chose «خدمي» or «تسويقي» when he wrote it, and Meta re-categorises
        whatever it disagrees with — a classifier of ours between them would be one more thing to
        be wrong about, and the owner asked for exactly the opposite (§custom_templates).
        """
        name = str(template.get("name", ""))
        language = str(template.get("language") or "ar")
        status, out = self._post(self._register, {
            "tenant": tenant, "name": name, "language": language,
            "category": _category(str(template.get("cls", "service"))),
            "body": str(template.get("body", "")),
            "variables": [str(v) for v in (template.get("variables") or [])],
            # AN EXAMPLE PER SLOT, OR META REJECTS THE TEXT FOR A REASON HE CANNOT ACT ON.
            #
            # `CustomTemplate.to_dict()` has no `examples` key, so this sent `[]`. The meta driver
            # then falls back per slot to the variable NAME — literally "1" and "2" — and Meta's
            # review refuses placeholder-looking examples. The owner's own words came back rejected,
            # he pressed «ساعدوني», and a human spent time on a defect of ours. The LIBRARY path
            # never had this: the seed carries real examples, so only a shop's own text went out
            # bare.
            #
            # BUILT FROM THE FILLS HE ALREADY CHOSE, through the same `SAMPLE` table the preview
            # uses — so what Meta reviews is what he saw before he pressed send.
            "examples": _examples(template),
        })
        if status >= 400:
            return {"ok": False, "reason": _sentence(out, "تعذّر تجهيز النص للإرسال.")}

        path = self._submit.format(name=urllib.parse.quote(name),
                                   language=urllib.parse.quote(language))
        status, out = self._post(path, {"tenant": tenant})
        if status >= 400:
            return {"ok": False, "reason": _sentence(out, "رفضت واتساب استقبال النص.")}
        return {"ok": True, "status": str(out.get("status", "pending"))}


def _category(cls: str) -> str:
    """Our class word in Meta's vocabulary. MARKETING for anything that sells, UTILITY otherwise.

    THE CLASS IS ALREADY THE AUTHORITY on consent, the quiet window and the monthly cap here, so
    this is a translation and never a second decision — two places deciding a category is how a
    marketing text ends up submitted under an exemption.
    """
    return "MARKETING" if cls == "marketing" else "UTILITY"


def _sentence(out: Any, fallback: str) -> str:
    """Meta's own words when there are any, ours when there are not.

    RE-WORDING A REJECTION SENDS HIM LOOKING FOR A PROBLEM WE INVENTED. «ساعدوني» carries this
    string into a request a human answers, so it has to be what Meta actually said.
    """
    if isinstance(out, dict):
        said = out.get("detail") or out.get("message") or out.get("error")
        if said:
            return str(said)[:300]
    return fallback


def build_submitter(settings: Any) -> Any:
    url = getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""
    register = getattr(settings, "NOTIFICATION_TEMPLATE_REGISTER_PATH", "") or ""
    submit = getattr(settings, "NOTIFICATION_TEMPLATE_SUBMIT_PATH", "") or ""
    if not url or not register or not submit:
        return NullSubmitter()
    return HttpSubmitter(notify_url=url, register_path=register, submit_path=submit,
                         token=getattr(settings, "INTERNAL_SERVICE_TOKEN", "") or "",
                         timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 8) or 8))
