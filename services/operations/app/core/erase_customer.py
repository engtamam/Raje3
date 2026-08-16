"""Erase one customer, at the establishment's own hand — because the establishment is the controller.

WHOSE OBLIGATION THIS IS. Under the PDPL the shop is the controller of its customers' data and we
are its processor: when a customer tells the workshop «امسح بياناتي», the workshop owes him the
erasure — not us, and not in thirty days through a support conversation. Until this existed the
product had a complete erasure engine (compliance-service fans out to every service, each one
acknowledges, the ack is recorded) and no way for the person who actually receives the request to
start it. The obligation was his and the button was nobody's.

WE DO NOT ERASE ANYTHING OURSELVES HERE, and that is the point. A second erasure path is a second
answer to «was this person deleted?», and the first disagreement between them is the one a
regulator reads. This opens a DSAR of compliance's own `erasure` type, marks it verified —
the shop received the request in person, which is the strongest verification this product has —
and asks compliance to dispatch it. Every store that holds anything of his, including ours, is
erased by the fan-out that already existed and already keeps the receipts.

AND IT TRAVELS ON THE OWNER'S OWN TOKEN, never on an internal one. compliance scopes the request to
the caller's tenant and requires `compliance.manage`; forwarding his authorization means the
erasure is HIS act, recorded against his name in the audit trail, and it means we cannot erase a
customer of an establishment that did not ask. An internal token would make this service able to
erase anyone in the fleet, which is exactly the power this product should not hold.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


#: COMPLIANCE'S WORD, NOT OURS — and the difference cost every erasure this product has ever been
#: asked for (ب-1). Our own vocabulary for what a customer may ask his shop is («export», «erase»),
#: which is right for us and readable on his page. compliance's is
#: («access», «export», «erasure», «correction»), and it validates the field: `erase` is answered
#: 422 by the FIRST of the three calls below. So the owner pressed «احذف بياناته», the request was
#: never created, nothing fanned out, and he was shown `compliance answered 422` — a log line, in
#: English, on a legal deadline.
#:
#: Named here, once, at the only place our word would otherwise cross the boundary. The mapping is
#: not «erase → erasure» for its own sake: it is that two services own two vocabularies, and the
#: caller translates rather than the callee guessing.
COMPLIANCE_ERASURE = "erasure"

#: compliance's DSAR statuses, its words again — the ones in which the fan-out has ALREADY been
#: started and a second `process` would only do damage (see `erase_subject`).
#:
#: NAMED AS THE THING WE SKIP FOR, never as the thing we dispatch for, and the difference is the
#: whole safety of it. An absent status, or one compliance adds later, is not in this tuple, so
#: the erasure is dispatched: an extra round trip is the wrong answer we can afford, and «we
#: assumed it was already running» on a customer's erasure is not.
ALREADY_DISPATCHED = ("in_progress", "completed")
REFUSED = "refused"


class EraseFailed(RuntimeError):
    """The erasure did not happen. Carries what to tell the person who pressed the button."""


def _post(url: str, *, authorization: str, body: dict[str, Any] | None = None,
          timeout: int = 10) -> dict[str, Any]:
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json", "Authorization": authorization})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:          # nosec B310
            if not 200 <= resp.status < 300:
                # SAME REASON AS THE HTTPError PATH BELOW: this reaches an owner.
                raise EraseFailed(
                    "تعذّر تنفيذ الحذف الآن. أعد المحاولة، وإن تكرّر فتواصل معنا.")
            return json.loads(resp.read() or b"{}")
    except EraseFailed:
        raise
    except urllib.error.HTTPError as exc:                                   # noqa: PERF203
        # 403 IS THE ONE WORTH NAMING. It means the role lacks `compliance.manage`, which is a
        # thing an owner can fix on his own team page — and «تعذّر الحذف» would send him looking
        # for a fault in us instead.
        if exc.code == 403:
            raise EraseFailed("هذا الحساب لا يملك صلاحية تنفيذ طلبات الخصوصية") from exc
        # EVERY OTHER CODE REACHES A PERSON, so it stops being a log line. This sentence was
        # `compliance answered 422` and an owner read it, in English, with a thirty-day legal
        # deadline running — and 422 is exactly what the wrong request type produced, so this is
        # the sentence the whole of ب-1 was showing.
        raise EraseFailed("تعذّر تنفيذ الحذف الآن. أعد المحاولة، وإن تكرّر فتواصل معنا.") from exc
    except Exception as exc:                                                # noqa: BLE001
        # A TIMEOUT, A DNS FAILURE, A BROKEN SOCKET. `str(exc)` here is a Python repr — it named a
        # host and a port to a shop owner. What he needs to know is only whether it happened.
        raise EraseFailed("تعذّر الوصول إلى خدمة الخصوصية الآن. أعد المحاولة بعد قليل.") from exc


def erase_subject(*, compliance_url: str, authorization: str, subject_ref: str) -> dict[str, Any]:
    """Open, verify and dispatch an erasure for one customer. Returns compliance's own result.

    THREE CALLS, AND THE MIDDLE ONE IS NOT OPTIONAL. compliance refuses to dispatch an unverified
    request, correctly: an erasure that runs on an unproven claim is a way to delete a stranger's
    history. The verification token comes back exactly once, from the creation call, and is spent
    immediately — it never touches a screen, a log, or a message.

    AND THE SECOND PRESS DOES NOT RE-DISPATCH. compliance re-uses the existing request rather than
    opening a duplicate (`created: false`), but `process` on a request already `in_progress` rebuilds
    its per-target acknowledgement map from scratch — every target that had already confirmed the
    erasure goes back to «not yet», the request can no longer reach `completed`, and the shop's
    proof that it honoured the request is gone. The subject's thirty-day clock keeps running.

    So a request that is already fanning out is left alone: the sweeper on the other side resumes
    from exactly the state we would be destroying, and pressing the button again has never had
    anything to add to a dispatch already under way. Reported as ز-6; the map rebuild itself is
    compliance-service's line to fix.
    """
    if not compliance_url:
        # A DEPLOYMENT FAULT, AND HE STILL READS IT. He can do nothing about it, so the
        # sentence says that plainly instead of naming a setting he has never heard of.
        raise EraseFailed("خدمة الخصوصية غير مهيّأة لدينا. تواصل معنا وسنكملها فوراً.")
    base = compliance_url.rstrip("/") + "/api/v1/compliance"

    opened = _post(f"{base}/dsar", authorization=authorization,
                   body={"subject": subject_ref, "type": COMPLIANCE_ERASURE})
    dsar_id = str(opened.get("id") or "")
    if not dsar_id:
        # OUR BUG OR A CONTRACT CHANGE, and either way not his to parse.
        raise EraseFailed("تعذّر تنفيذ الحذف الآن. أعد المحاولة، وإن تكرّر فتواصل معنا.")

    status = str(opened.get("status") or "")
    if status == REFUSED:
        # A REFUSAL SURVIVES THE SECOND PRESS. `process` on a refused request answers
        # `{"ok": true, "reason": "already_final"}` — true, and read as «تم» by the branch at the
        # bottom of this function. The only reason compliance refuses an erasure is a legal hold,
        # so the owner is told the thing that is actually stopping it rather than that it worked.
        raise EraseFailed("هذا العميل تحت حجزٍ نظاميّ، ولا يمكن حذف بياناته الآن.")
    if status in ALREADY_DISPATCHED:
        # ALREADY UNDER WAY OR FINISHED — AND PRESSING AGAIN DESTROYS EVIDENCE. See the docstring:
        # a second `process` on an `in_progress` request rebuilds the per-target acknowledgement
        # map and every target that had already confirmed goes back to «not yet».
        return {"dsar_id": dsar_id, "dispatched": True}

    token = str(opened.get("verification_token") or "")
    if token:
        # ONLY ON A FRESHLY CREATED REQUEST. A re-press returns no token because the first one was
        # already spent — and an already-verified request is exactly what we want to dispatch.
        _post(f"{base}/dsar/{dsar_id}/verify?token={urllib.parse.quote(token)}",
              authorization=authorization)

    result = _post(f"{base}/dsar/{dsar_id}/process", authorization=authorization)

    # ── A REFUSAL ARRIVES AS 200, AND IT USED TO ARRIVE AS «تم» (د-3) ─────────────────────────
    #
    # compliance answers HTTP 200 with `{"ok": false, "reason": ...}` for every refusal except
    # NOT_FOUND — a legal hold over this subject, a request it will not dispatch, a target that
    # would not take it. Nothing above raises, because nothing failed at the HTTP layer.
    #
    # This line read `result.get("ok", True)`: the refusal set `dispatched` to False and the route
    # still answered `{"ok": True, ...}`, which is the field the screen reads. So the owner pressed
    # «احذف بياناته», compliance declined, and he was told it was done — with a legal deadline
    # running and no reason to look again. And the default made the same true of any answer whose
    # shape we did not expect.
    #
    # A LEGAL HOLD IS NAMED, because it is the one refusal that is not a fault and not retryable:
    # the law is overriding the erasure, and the owner needs to know that rather than press again.
    if not result.get("ok", False):
        reason = str(result.get("reason") or "")
        if "HOLD" in reason.upper():
            raise EraseFailed("هذا العميل تحت حجزٍ نظاميّ، ولا يمكن حذف بياناته الآن.")
        raise EraseFailed("لم يُنفَّذ الحذف. أعد المحاولة، وإن تكرّر فتواصل معنا.")

    # NO `targets` IN THE ANSWER. It was carried for a screen that never read it, and the two
    # paths above disagreed about what it even was: compliance answers `targets` as a COUNT from
    # `/process` and as a LIST from the creation call, so one press returned `12` and the next
    # returned `["operations", "reminders"]` under one name. A field with two meanings and no
    # reader is how the next screen gets it wrong — the reader that eventually needs the target
    # list can ask compliance for it in the shape compliance actually publishes.
    return {"dsar_id": dsar_id, "dispatched": True}
