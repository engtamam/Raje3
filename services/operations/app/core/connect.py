"""WhatsApp connection — receiving the Embedded Signup result, and a code that lives 30 seconds.

WHAT EMBEDDED SIGNUP ACTUALLY HANDS BACK, and why almost every part of it is a trap.

Meta opens a popup over the owner's browser. When he finishes, the popup posts a message back to
our page carrying three identifiers and an authorization code. The code is exchangeable for about
THIRTY SECONDS. There is no queue for it, no retry, no background task: it is exchanged inside the
request that carries it or it dies, and the owner starts the whole flow again from the beginning.

That single fact decides the shape of everything here:

  · the browser must call us the instant it receives the code, not after a page navigation;
  · our route must do no slow work before the exchange — no audit round-trip, no lookup;
  · a failure must be reported precisely, because "try again" costs him the whole popup journey.

────────────────────────────────────────────────────────────────────────────────────────────────
AND CLOSING THE POPUP IS NOT ALWAYS A CANCELLATION

The popup also posts a CANCEL message carrying the step he stopped at. Six steps, and they are not
equivalent: stopping at BUSINESS_ACCOUNT_SELECTION means he has not started, while closing on the
FINAL screen means Meta CONSIDERS THE SIGNUP DONE — the account exists, and treating that as a
cancellation would tell an owner his connection failed when it succeeded.

So the step is recorded, not discarded, and it is the difference between "he gave up early" and
"he is connected and does not know it".

────────────────────────────────────────────────────────────────────────────────────────────────
WHY THE EXCHANGE IS BEHIND A PORT AND NOT DONE HERE

The exchange needs OUR Meta app secret — the credential that identifies us as the Tech Provider —
and it produces the shop's access token, which can send in the shop's name. Neither may live in
this service: notification-service holds the secret store, does the exchange in its core, and never
lets the token reach a route.

THE ORIGINAL USER-TIER ROUTE REQUIRES A PLATFORM CAPABILITY (platform.secrets), which a shop owner
does not hold and must never hold — so the owner's browser could never call it directly. RESOLVED:
the platform shipped the internal, service-token twin this needed (notification-service's own
`POST /internal/whatsapp/embedded-signup`, WHATSAPP_ONBOARDING_DRIVER="http") — this deployment
already runs it (see `deploy/services/operations.values.yaml`). `HttpExchange` is live; `NullExchange`
below is now only what a driver flip to "null" (or a missing NOTIFICATION_SERVICE_URL) falls back
to, same "refuse honestly, never fake success" posture as every other unconfigured peer in this
product — not a gap waiting on anyone.

WHAT STILL BLOCKS A REAL CONNECTION, and it is entirely external: META_APP_ID/META_APP_SECRET (our
own Tech Provider identity, issued by Meta only after they verify this business) are not sealed on
this deployment yet. Nothing here can substitute for that — it is Meta's own verification, not a
configuration value we control.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from app.adapters import internal_http

from app.core.sending_identity import SEPARATOR as SI_SEPARATOR

CONNECTIONS = "whatsapp_connections"
#: How far each scheduled sweep has got. One row per (sweep, tenant), holding only when it was last
#: done — the smallest thing that turns a capped pass from «the same head every hour» into a
#: rotation that reaches everybody.
SWEEP_MARKS = "sweep_marks"

# The six steps Meta names when the owner cancels. A CLOSED vocabulary, transcribed from its
# documentation rather than invented: an unknown step is recorded as-is instead of being mapped to
# a guess, because a wrong step name here becomes a wrong sentence on his screen.
STEP_BUSINESS = "BUSINESS_ACCOUNT_SELECTION"
STEP_PHONE_PICKER = "WABA_PHONE_PROFILE_PICKER"
STEP_PROFILE = "WHATSAPP_BUSINESS_PROFILE_SETUP"
STEP_PHONE = "PHONE_NUMBER_SETUP"
STEP_VERIFY = "PHONE_NUMBER_VERIFICATION"
STEP_PERMISSIONS = "PERMISSIONS"

# THE ONE THAT IS NOT A CANCELLATION. Closing the popup on the permissions screen — the last one —
# means Meta has already created the account: the flow completed and the window was dismissed. An
# owner told "you cancelled" here would go looking for a problem that does not exist, and worse,
# might run the whole journey again against an account that is already connected.
FINAL_STEP = STEP_PERMISSIONS

STATE_CONNECTED = "connected"
STATE_STOPPED = "stopped"
STATE_FINISHED_UNCONFIRMED = "finished_unconfirmed"
STATE_FAILED = "failed"
# WE ASKED THE PLATFORM TO SEAL CREDENTIALS AND HAVE NOT YET HEARD BACK (ز-12).
#
# The exchange used to run with no row written first, so a crash between the seal and our write
# left credentials in the vault that nothing in this service knew about: the screen said «غير
# مربوط», and Meta's code — thirty seconds of life — was already spent, so no retry could ever
# finish it. The owner's only route was a support conversation about a connection that had, in
# fact, succeeded.
#
# Written BEFORE the call, so the crash leaves a row that names the question rather than nothing at
# all. `whatsapp_health` answers it against the platform, which is the only party that knows.
STATE_EXCHANGING = "exchanging"


def _now() -> int:
    return int(time.time())


# What to tell the owner at each step he stopped on. Written as the next thing to DO rather than as
# a description of what went wrong — he does not need to be told he closed a window.
_SENTENCE = {
    STEP_BUSINESS: "لم تختر حساب أعمالك بعد. افتح الربط مرة أخرى واختر حساب أعمالك على فيسبوك.",
    STEP_PHONE_PICKER: "بقي اختيار الرقم الذي سترسل منه. افتح الربط وأكمل من حيث توقفت.",
    STEP_PROFILE: "بقي إكمال ملف نشاطك على واتساب — الاسم والوصف. افتح الربط وأكمله.",
    STEP_PHONE: "بقي إدخال رقم الجوال الذي سترسل منه. ويشترط ألّا يكون مستخدماً في تطبيق واتساب العادي.",
    STEP_VERIFY: "بقي إدخال رمز التحقق الذي وصل إلى رقمك. افتح الربط وأدخله.",
}

_DEFAULT_SENTENCE = "لم يكتمل الربط. افتح الربط مرة أخرى وأكمل الخطوات."

# ── WHOSE FAULT THE FAILURE WAS, NAMED RATHER THAN DESCRIBED (هـ-5) ───────────────────────────
# A failed exchange carries a `detail` for support. Two of its causes are OURS and neither is
# anything the owner can act on: no onboarding credentials wired at all, and notification-service
# unreachable while we held Meta's thirty-second code. Told «حاول مرة أخرى» he tries, fails,
# tries again, and concludes the fault is in his Facebook account.
#
# The register route two files over has said this correctly since it was written — NOT_CONFIGURED
# is one of its five sentences — and the same reason on the same journey read differently
# depending on which half of it the owner was standing in.
#
# These are reason CODES, matched on the part before the colon so a detail may still carry the
# transport error after it. Anything not listed is Meta refusing the code, which IS his to retry.
EXCHANGE_NOT_CONFIGURED = "NOT_CONFIGURED"
EXCHANGE_UNREACHABLE = "UNREACHABLE"

_OURS_SENTENCE = {
    EXCHANGE_NOT_CONFIGURED: ("تفعيل الربط غير مُهيَّأ لدينا بعد — عُطلٌ عندنا لا في حسابك. "
                              "لا حاجة لإعادة المحاولة، وسنبلغك فور تشغيله."),
    EXCHANGE_UNREACHABLE: ("تعذّر الوصول إلى أنظمتنا أثناء إتمام الربط — عُطلٌ عندنا لا في "
                           "حسابك. أعد المحاولة بعد قليل."),
}


@dataclass
class Attempt:
    """One journey through Embedded Signup, in whatever state it ended."""

    tenant: str
    state: str
    step: str = ""
    waba_id: str = ""
    phone_number_id: str = ""
    business_id: str = ""
    detail: str = ""
    at: int = field(default_factory=_now)
    # WHICH BRANCH THIS NUMBER BELONGS TO — empty for the establishment's own number, which is
    # every shop today and every shop in the default mode (spec 12.2).
    branch_id: str = ""

    @property
    def key(self) -> str:
        """The row's id — and the defect it closes.

        THE SECOND CONNECT USED TO ERASE THE FIRST. The row was keyed on the tenant alone, so a
        chain connecting its Jeddah number overwrote Riyadh's `waba_id` and `phone_number_id` —
        gone, with no copy anywhere and no way to send from the first number again. Nothing failed:
        the screen said «تم الربط» about the number that had just replaced the other one.

        AND THE ESTABLISHMENT'S OWN ROW KEEPS ITS OLD KEY, byte for byte. A shop with no branch on
        its connection is stored under its tenant id exactly as before, so every existing row is
        found by the same lookup and nothing is migrated.
        """
        return f"{self.tenant}|{self.branch_id}" if self.branch_id else self.tenant

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.key, "tenant": self.tenant, "state": self.state, "step": self.step,
                "waba_id": self.waba_id, "phone_number_id": self.phone_number_id,
                "business_id": self.business_id, "detail": self.detail, "at": self.at,
                "branch_id": self.branch_id}

    def public(self, *, can_send: bool = True) -> dict[str, Any]:
        """What the owner's screen may see. NO identifiers of Meta's — they are ours to hold and
        his to never need, and a WABA id on a screen is one more thing that can be pasted into a
        support chat.

        `can_send` IS NOT ABOUT HIM. It is whether THIS DEPLOYMENT can put a message on WhatsApp at
        all — see `sentence_for`. Carried in the answer so the screen can show the truth instead of
        deciding it for itself.
        """
        return {"state": self.state, "step": self.step,
                "message": sentence_for(self, can_send=can_send),
                "can_send": bool(can_send) or self.state != STATE_CONNECTED,
                "at": self.at, "branch_id": self.branch_id}


def sentence_for(attempt: Attempt, *, can_send: bool = True) -> str:
    """The sentence the owner reads. Never a step name and never an English error.

    «جاهز للإرسال» IS A CLAIM, AND UNTIL TODAY WE MADE IT WITHOUT CHECKING. The exchange succeeding
    means Meta gave us a token — it does not mean a message can leave. On this deployment nothing
    can be delivered at all yet, so an owner finished the whole journey, read «حسابك جاهز للإرسال»,
    recorded visits all week and wondered where his messages went. That is this product's signature
    failure written into the one screen whose entire job is to report the truth.

    SO THE CLAIM IS SPLIT IN TWO. The connection succeeded — that part is true and his to keep. The
    sending is not open yet, and the sentence says so, says it is OURS, and tells him he need do
    nothing. A shop that is told to wait waits; a shop that is told it is ready blames itself, then
    us, then leaves.
    """
    if attempt.state == STATE_CONNECTED:
        if not can_send:
            return ("تم الربط، وحسابك محفوظ. والإرسال لم يُفتح بعد من طرفنا — "
                    "لا ينقصك شيء، وسنبلغك فور تشغيله.")
        return "تم الربط. حسابك جاهز للإرسال."
    if attempt.state == STATE_EXCHANGING:
        # THE ONLY MOMENT WE GENUINELY DO NOT KNOW (ز-12). We handed Meta's code to the platform to
        # seal and did not hear the result. Claiming «تم الربط» could be a lie he plans a week
        # around; claiming failure could throw away a connection that succeeded. So it says what is
        # true — we are finishing it — and it resolves itself within the hour without him.
        return "جارٍ إتمام الربط. لا حاجة لإعادة العملية — سنُحدّث الحالة خلال ساعة."
    if attempt.state == STATE_FINISHED_UNCONFIRMED:
        # HE FINISHED. Meta created the account and the popup closed before we heard the code — so
        # the honest sentence is neither "connected" nor "cancelled", and it says what we will do
        # rather than asking him to do it again for nothing.
        # THE PROMISE WE COULD NOT KEEP (د-6). This used to say «نتحقق من اكتمال الربط خلال
        # دقائق، ولا حاجة لإعادة العملية» — and NOTHING checks. The exchange needs the code
        # from the popup, the code lives thirty seconds, and no path anywhere completes it
        # later. So he waited for minutes that never came, and then the health sweep passed,
        # found no credentials, and told him his connection had been CUT — a false diagnosis
        # about a connection that was never made, on top of a false promise.
        #
        # The truth is short and it is actionable: the account exists on WhatsApp's side, we
        # did not receive the code, and repeating the button finishes it without creating a
        # second account.
        return ("أنشأتَ الحساب على واتساب، ولم يصلنا رمز الإكمال قبل انتهاء صلاحيته. "
                "اضغط «ربط واتساب» مرة أخرى لإتمامها — لن يُنشأ حساب جديد.")
    if attempt.state == STATE_FAILED:
        # OURS OR HIS — see the reason codes above. The detail is never shown; only the code in
        # front of it chooses which of the three sentences he reads.
        ours = _OURS_SENTENCE.get((attempt.detail or "").split(":")[0].strip())
        if ours:
            return ours
        return "تعذّر إكمال الربط. حاول مرة أخرى، وإن تكرر تواصل معنا."
    # A CONNECTION THAT ENDED AFTER IT WORKED IS NOT AN UNFINISHED ONE. The sweep stops a row whose
    # access was revoked and writes WHY into `detail`; a stopped row carries a `step` only when the
    # owner closed the popup partway through. Without this line a shop that sent for a year read
    # «لم يكتمل الربط» and went looking for a step it had completed long ago.
    if not attempt.step and attempt.detail:
        return attempt.detail
    return _SENTENCE.get(attempt.step, _DEFAULT_SENTENCE)


def classify_cancel(step: str) -> str:
    """A CANCEL message is not always a cancellation — see FINAL_STEP."""
    return STATE_FINISHED_UNCONFIRMED if (step or "").upper() == FINAL_STEP else STATE_STOPPED


class ConnectionStore:
    """One row per establishment: the latest attempt and how it ended.

    LATEST, NOT A HISTORY. What the screen and support need is "where does this shop stand now";
    keeping every abandoned attempt would build a log of somebody's fumbling that nothing reads and
    that a retention sweep would then have to reason about.
    """

    def __init__(self, store: Any) -> None:
        self._s = store

    async def record(self, attempt: Attempt) -> Attempt:
        await self._s.put(CONNECTIONS, attempt.key, attempt.to_dict())
        return attempt

    async def get(self, tenant: str, branch_id: str = "") -> Attempt | None:
        key = f"{tenant}|{branch_id}" if branch_id else tenant
        row = await self._s.get(CONNECTIONS, key)
        if not row:
            return None
        return Attempt(tenant=str(row.get("tenant") or tenant), state=str(row.get("state") or ""),
                       step=str(row.get("step") or ""), waba_id=str(row.get("waba_id") or ""),
                       phone_number_id=str(row.get("phone_number_id") or ""),
                       business_id=str(row.get("business_id") or ""),
                       detail=str(row.get("detail") or ""), at=int(row.get("at") or 0),
                       branch_id=str(row.get("branch_id") or branch_id))

    async def for_tenant(self, tenant: str, *, limit: int = 50) -> list[Attempt]:
        """Every number this establishment has connected — the shop's own and its branches'.

        FOR THE SCREEN THAT ASKS «which of my places can send», which cannot exist while the store
        answers one row per shop.
        """
        rows, _ = await self._s.find(CONNECTIONS, {"tenant": tenant}, limit=max(1, limit),
                                     sort=("at", "desc"))
        return [Attempt(tenant=str(r.get("tenant") or tenant), state=str(r.get("state") or ""),
                        step=str(r.get("step") or ""), waba_id=str(r.get("waba_id") or ""),
                        phone_number_id=str(r.get("phone_number_id") or ""),
                        business_id=str(r.get("business_id") or ""),
                        detail=str(r.get("detail") or ""), at=int(r.get("at") or 0),
                        branch_id=str(r.get("branch_id") or "")) for r in rows]


    async def live_connections(self, *, limit: int = 500) -> list[Attempt]:
        """Every NUMBER that is supposed to be able to send — the health sweep's work list.

        NUMBERS, NOT TENANTS. `live_tenants` answers «which shops are live» for callers that work
        per establishment; a chain loses access one number at a time, and a sweep keyed on the
        tenant would ask about one number and then clear — or condemn — all of them.
        """
        cap = max(1, min(2000, limit))
        out: list[Attempt] = []
        # EXCHANGING IS IN THE WORK LIST, and it is the one this pass exists for twice over (ز-12).
        # A row left in it means we asked the platform to seal credentials and never learned the
        # answer; the platform holds the fact, and this is what goes and reads it.
        for state in (STATE_CONNECTED, STATE_FINISHED_UNCONFIRMED, STATE_EXCHANGING):
            rows, _ = await self._s.find(CONNECTIONS, {"state": state}, limit=cap,
                                         sort=("at", "desc"))
            out.extend(Attempt(
                tenant=str(r.get("tenant") or ""), state=str(r.get("state") or ""),
                step=str(r.get("step") or ""), waba_id=str(r.get("waba_id") or ""),
                phone_number_id=str(r.get("phone_number_id") or ""),
                business_id=str(r.get("business_id") or ""), detail=str(r.get("detail") or ""),
                at=int(r.get("at") or 0), branch_id=str(r.get("branch_id") or ""))
                for r in rows if r.get("tenant"))
        return out[:cap]

    async def mark_swept(self, sweep: str, tenant: str, at: int) -> None:
        """Record that `sweep` has just finished with `tenant`.

        A SEPARATE COLLECTION, NOT A FIELD ON THE CONNECTION. A tenant may hold several connection
        rows — one per branch — so «which row carries the mark» would have no honest answer, and
        `record()` rewrites a connection row whole, which would erase a marker written between two
        connects. A mark is about a SWEEP's progress, not about a number.
        """
        await self._s.put(SWEEP_MARKS, f"{sweep}|{tenant}",
                          {"id": f"{sweep}|{tenant}", "sweep": sweep, "tenant": tenant,
                           "at": int(at)})

    async def live_tenants(self, *, limit: int = 500, sweep: str = "") -> list[str]:
        """Every establishment whose connection reached WhatsApp — the sweep's work list.

        BOTH LIVE STATES, and the second is the one that matters. `finished_unconfirmed` means the
        popup closed on Meta's final screen: the account EXISTS and we did not hear the code. A
        sweep that read only `connected` would skip exactly the shops whose state we are least sure
        of, which is the opposite of what a reconciliation is for.

        A cap rather than a full scan: a sweep is a repair pass that runs again in an hour, and
        progress beats completeness on a repair path.

        AND `sweep` IS WHAT MAKES «PROGRESS» TRUE RATHER THAN A HOPE. Without it this returned the
        newest connections first, every hour, in the same order — so a pass that ran out of window
        did not resume where it stopped; it restarted at the head and re-did the same shops. The
        establishments at the end of the list were never reached at all, and for
        `template-publish` that means their library is never registered, no template is ever
        approved, and the send path refuses every message for ever. Green screen, silent shop.

        Given a sweep name the order becomes LEAST-RECENTLY-SWEPT FIRST, so each run takes the
        oldest slice and every shop comes round in a bounded number of ticks. A shop with no mark
        sorts first, which is the honest reading of «never done».

        THE ORDERING IS DONE HERE RATHER THAN IN THE QUERY, deliberately: the marks live in their
        own collection, so no store needs to support a join or a sort over a field that may not
        exist on a row. The live set is read whole (the cap is 2000 against a fleet in the
        hundreds) and ordered in hand — exact, and free of any driver's opinion about missing keys.
        """
        # ONE QUERY PER STATE, not one scan filtered in memory: the datastore refuses an empty
        # `where` on purpose (scan_all exists for whole-collection reads and is not what a sweep
        # of live connections wants), and a filtered read stays cheap as the fleet grows.
        cap = max(1, min(2000, limit))
        # THE WHOLE LIVE SET IS READ, and only then cut. Reading `cap` rows and cutting there would
        # rotate inside a window that never moves — the newest `cap` shops would take turns among
        # themselves while everything behind them stayed invisible.
        wide = 2000
        out: list[str] = []
        for state in (STATE_CONNECTED, STATE_FINISHED_UNCONFIRMED):
            rows, _ = await self._s.find(CONNECTIONS, {"state": state}, limit=wide,
                                         sort=("at", "desc"))
            for row in rows:
                tenant = str(row.get("tenant") or "")
                if tenant and tenant not in out:
                    out.append(tenant)
        if not sweep:
            return out[:cap]

        marks: dict[str, int] = {}
        rows, _ = await self._s.find(SWEEP_MARKS, {"sweep": sweep}, limit=wide, sort=("at", "asc"))
        for row in rows:
            tenant = str(row.get("tenant") or "")
            if tenant:
                marks[tenant] = int(row.get("at") or 0)
        # STABLE, so two shops that have never been swept keep the order the read gave them — which
        # is newest-first, and right: a shop that connected this morning wants its library today.
        out.sort(key=lambda t: marks.get(t, 0))
        return out[:cap]


class Registration:
    """Registering the number, and reading whether it can actually send.

    THE STEP EMBEDDED SIGNUP STOPS BEFORE. The exchange stores a token; Meta refuses to SEND from a
    number until it is REGISTERED with the business's 6-digit two-step-verification PIN. Until
    v0.16.10 the platform had no route for it at all — the escalation this closes — and every
    connection ended «أخضر ولا يرسل».

    THREE REFUSALS, NEVER ONE. A mistyped PIN is his to correct; the 10-attempts-per-72-hours lock
    is a WAIT and retrying makes it worse; unreachable is ours. Collapsing them into one «تعذّر»
    would have an owner burn his remaining attempts on a problem no attempt can fix.

    AND THE PIN IS NEVER STORED HERE. It travels through this call into the platform's sealed store
    and is not written to any row, log or audit of ours — see the register route, which seals it per
    number so a re-registration needs no human.
    """

    driver = "http"

    def __init__(self, *, base_url: str, register_path: str, status_path: str, token: str,
                 timeout: int = 20) -> None:
        self._register = (base_url.rstrip("/") + register_path) if base_url else ""
        self._status = (base_url.rstrip("/") + status_path) if base_url else ""
        self._token = token
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self._register)

    async def register(self, *, tenant: str, phone_number_id: str = "",
                       pin: str = "") -> tuple[bool, str]:
        """`(registered, reason)` — the reason is one of Meta's, passed through untranslated."""
        import json
        import urllib.error

        if not self._register:
            return False, "NOT_CONFIGURED"
        body: dict[str, Any] = {"tenant": tenant}
        if phone_number_id:
            body["phone_number_id"] = phone_number_id
        if pin:
            body["pin"] = pin
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out = internal_http.post_json(self._register, body, self._token, self._timeout)
            return bool(out.get("registered")), str(out.get("reason") or "")
        except urllib.error.HTTPError as exc:
            try:
                out = json.loads(exc.read() or b"{}")
                return False, str(out.get("reason") or exc.code)
            except (ValueError, OSError):
                return False, str(exc.code)
        except (urllib.error.URLError, OSError) as exc:
            return False, f"UNREACHABLE: {exc}"

    async def status(self, tenant: str, phone_number_id: str = "") -> dict[str, Any]:
        """What Meta says about the number right now. `{}` means we could not ask — NOT «not ready».

        THE THIRD STATE, AGAIN. An unreadable status must never render as «غير جاهز»: the shop may
        be perfectly able to send, and a screen that says otherwise sends him chasing a fault that
        is ours or nobody's.
        """
        import json
        import urllib.error
        import urllib.parse
        import urllib.request

        if not self._status or not tenant:
            return {}
        query = urllib.parse.urlencode(
            {"tenant": tenant, **({"phone_number_id": phone_number_id} if phone_number_id else {})})
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            out = internal_http.get_json(f"{self._status}?{query}", self._token, self._timeout)
            return out if isinstance(out, dict) else {}
        except (urllib.error.HTTPError, urllib.error.URLError, OSError, ValueError):
            return {}


def build_registration(settings: Any) -> Registration:
    return Registration(
        base_url=getattr(settings, "NOTIFICATION_SERVICE_URL", "") or "",
        register_path=getattr(settings, "WHATSAPP_REGISTER_PATH", "/internal/whatsapp/register"),
        status_path=getattr(settings, "WHATSAPP_STATUS_PATH", "/internal/whatsapp/status"),
        token=getattr(settings, "INTERNAL_SERVICE_TOKEN", ""),
        timeout=int(getattr(settings, "PEER_TIMEOUT_SECONDS", 20) or 20))


class NullExchange:
    """No Tech Provider credentials wired, or no route to reach them with.

    ANSWERS FAILED AND SAYS WHY, rather than pretending the connection worked. A shop told it is
    connected when it is not will record visits all week and wonder where its messages went — the
    failure that costs a customer rather than a request.
    """

    configured = False

    async def exchange(self, *, tenant: str, code: str, waba_id: str,
                       phone_number_id: str) -> tuple[bool, str]:
        # THE REASON IS A CODE, because the owner's sentence depends on it: nothing wired here is
        # ours, and telling him to try again would send him hunting through his Facebook account
        # for a fault that is on our side of the wire.
        return False, f"{EXCHANGE_NOT_CONFIGURED}: onboarding is not configured"


class HttpExchange:
    """Hand the code to notification-service, which holds the app secret and does the exchange.

    LIVE — this deployment's own values already point at it (WHATSAPP_ONBOARDING_DRIVER="http",
    see this module's own docstring). What still blocks a real connection is entirely external
    (Meta's own Tech Provider verification), never this class or its route.

    IN-REQUEST AND NOTHING ELSE. No retry, no queue, no backoff: Meta's code is valid for about
    thirty seconds, so a retry would be an exchange of an expired code and a second failure that
    tells the owner nothing new.
    """

    configured = True

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 20) -> None:
        self._url = base_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def exchange(self, *, tenant: str, code: str, waba_id: str,
                       phone_number_id: str) -> tuple[bool, str]:
        import json
        import urllib.error
        import urllib.request

        body = json.dumps({"tenant": tenant, "code": code, "waba_id": waba_id,
                           "phone_number_id": phone_number_id}).encode()
        try:
            # Built in adapters/internal_http.py, the one place this service attaches the token.
            internal_http.read(self._url, self._timeout, method="POST", body=body,
                               content_type=internal_http.JSON, token=self._token)
            return True, ""
        except urllib.error.HTTPError as exc:
            # THE REASON IS CARRIED, NOT SWALLOWED. "Meta rejected the code" and "our app secret is
            # wrong" are the same 400 to a caller that discards the body, and they are entirely
            # different problems — one is the owner's to retry and one is ours to fix.
            try:
                detail = json.loads(exc.read() or b"{}")
                return False, str(detail.get("detail") or detail.get("message") or exc.code)
            except (ValueError, OSError):
                return False, str(exc.code)
        except (urllib.error.URLError, OSError) as exc:
            # OURS, AND NAMED AS SUCH. A peer we cannot reach is not a code Meta rejected, and the
            # owner is told to wait rather than to repeat a journey that cannot succeed yet.
            return False, f"{EXCHANGE_UNREACHABLE}: {exc}"


class NullMetaConfig:
    """No path to notification-service, or the driver is off. Answers honestly rather than
    letting the console's popup button open with an empty/undefined app id — same "refuse,
    never fake success" posture as `NullExchange` right above."""

    async def read(self) -> dict[str, Any]:
        return {"configured": False}


class HttpMetaConfig:
    """Asks notification-service for the App ID / Config ID it already holds sealed, rather than
    this service holding a second copy that could drift from the one actually used for the token
    exchange. GET, not a value ever cached here: this is asked once per Connect-pane open (the
    console's own dedupe, see meta.ts), and a sealed value can change from the admin panel at any
    time — a stale copy here would show a popup that opens with yesterday's app id."""

    def __init__(self, *, base_url: str, path: str, token: str, timeout: int = 8) -> None:
        self._url = base_url.rstrip("/") + path
        self._token = token
        self._timeout = timeout

    async def read(self) -> dict[str, Any]:
        import json
        import urllib.error

        try:
            out: dict[str, Any] = json.loads(internal_http.read(
                self._url, self._timeout, method="GET",
                token=self._token) or b"{}")
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            # OURS, NEVER HIS — a peer we cannot reach reads exactly like "not configured yet" to
            # the console (same button state, same sentence), never a raw error or a hung spinner.
            return {"configured": False}
        out.setdefault("configured", False)
        return out


def build_meta_config(settings: Any) -> Any:
    if not (getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""):
        return NullMetaConfig()
    return HttpMetaConfig(base_url=settings.NOTIFICATION_SERVICE_URL,
                          path=settings.WHATSAPP_META_CONFIG_PATH,
                          token=settings.INTERNAL_SERVICE_TOKEN,
                          timeout=settings.PEER_TIMEOUT_SECONDS)


def build_exchange(settings: Any) -> Any:
    driver = (getattr(settings, "WHATSAPP_ONBOARDING_DRIVER", "") or "null").lower()
    # DRIVER `http` WITH NO PEER URL IS NOT A DRIVER, and it fails in the worst possible place.
    # `"" + "/internal/…"` is a relative URL, and urllib raises ValueError building the Request —
    # a bare exception, outside the try below, so the owner's connect request 500s and Meta's
    # thirty-second code dies with it. He is told nothing, and the whole popup journey is lost.
    # The deployment shipped exactly this state: driver http, NOTIFICATION_SERVICE_URL unset.
    if driver == "null" or not (getattr(settings, "NOTIFICATION_SERVICE_URL", "") or ""):
        return NullExchange()
    return HttpExchange(base_url=settings.NOTIFICATION_SERVICE_URL,
                        path=settings.WHATSAPP_ONBOARDING_PATH,
                        token=settings.INTERNAL_SERVICE_TOKEN,
                        timeout=settings.PEER_TIMEOUT_SECONDS)


# WHAT THE OWNER IS TOLD WHEN THE ACCESS IS GONE. Written as the one thing that restores it: nobody
# can re-grant a revoked permission except him, from the same button he used the first time.
DISCONNECTED_SENTENCE = ("انقطع ربط واتساب — لم يعد لدينا إذن الوصول إلى حساب أعمالك. "
                         "افتح الربط مرة أخرى لإعادة التفعيل.")

# AND WHAT HE IS TOLD WHEN IT NEVER COMPLETED (د-6) — a different fact and a different act.
# «انقطع» about a connection that was never made is a diagnosis of an event that did not
# happen, and it sends him hunting a permission he never granted.
UNFINISHED_SENTENCE = ("لم يكتمل ربط واتساب — أُنشئ الحساب ولم يصلنا رمز الإكمال. "
                       "افتح الربط مرة أخرى لإتمامه، ولن يُنشأ حساب جديد.")


async def health_sweep(store: ConnectionStore, registration: Registration, *,
                       limit: int = 500) -> dict[str, Any]:
    """Ask Meta about every live number, and stop the ones whose access is gone.

    THE FAILURE THIS CLOSES. Access ends outside our product — an owner removes our app in his
    Business Manager, or Meta disables the number. Nothing tells us. The row stays `connected`, the
    screen keeps saying «مربوط», and every message is attempted against credentials that no longer
    exist. The shop learns from a customer who mentions he stopped hearing from them.

    ONLY A DEFINITE ANSWER FLIPS A ROW, and that is the whole design. `NOT_CONNECTED` means the
    platform holds no credentials for that number — a fact, not a failure to read. Every other
    non-ok answer is counted as UNREADABLE and changes nothing: an unreachable Graph, a timeout, a
    rejection we cannot classify. Marking a working shop as disconnected on a network blip would
    stop its reminders and walk its owner through the entire connect journey for nothing — a worse
    outcome than learning of a real disconnection an hour later.

    Returns the counts, so a sweep that could read nothing is visible as exactly that rather than as
    a fleet in perfect health.
    """
    if not registration.configured:
        return {"checked": 0, "stopped": 0, "unreadable": 0, "stopped_keys": [],
                "reason": "NOT_CONFIGURED"}
    checked = stopped = unreadable = settled = 0
    stopped_keys: list[str] = []
    for attempt in await store.live_connections(limit=limit):
        checked += 1
        # The SENDING IDENTITY, exactly as the credentials were sealed — a branch's number is not
        # reachable under the bare tenant.
        who = f"{attempt.tenant}{SI_SEPARATOR}{attempt.branch_id}" if attempt.branch_id             else attempt.tenant
        live = await registration.status(who, attempt.phone_number_id)
        if live.get("ok"):
            # THE ANSWER TO THE UNFINISHED QUESTION (ز-12). Credentials exist for this number, and
            # the row still says we were mid-exchange — so the seal DID happen and only our write
            # was lost. Settling it here is the whole repair: the shop is connected, it stops
            # reading «غير مربوط», and nobody has to re-run a journey whose one-use code is gone.
            if attempt.state == STATE_EXCHANGING:
                attempt.state = STATE_CONNECTED
                attempt.step = ""
                attempt.detail = ""
                attempt.at = _now()
                await store.record(attempt)
                settled += 1
            continue
        if str(live.get("reason") or "") != "NOT_CONNECTED":
            unreadable += 1
            continue
        # WHICH FACT «NO CREDENTIALS» IS DEPENDS ON WHERE THE ROW WAS (د-6).
        #
        # On a CONNECTED row it means access that worked has ended — somebody removed our app
        # in Business Manager, or Meta disabled the number.
        #
        # On a FINISHED_UNCONFIRMED row it means the exchange never happened: the popup closed
        # before we heard the code. Calling that «انقطع ربط واتساب» tells an owner something
        # ended that never began, and sends him looking for a permission he never granted.
        # AND ON AN EXCHANGING ROW IT IS A THIRD FACT (ز-12): the seal never landed. Meta's code is
        # spent either way, so the only honest answer is the one `finished_unconfirmed` already
        # gives — the account exists on WhatsApp's side, press the button again, no second account
        # is created. Calling this «انقطع ربط واتساب» would announce the end of something that
        # never began.
        if attempt.state == STATE_EXCHANGING:
            attempt.state = STATE_FINISHED_UNCONFIRMED
            attempt.step = ""
            attempt.detail = "exchange did not complete"
            attempt.at = _now()
            await store.record(attempt)
            settled += 1
            continue

        was_connected = attempt.state == STATE_CONNECTED
        attempt.state = STATE_STOPPED
        # NO STEP: this row did not stop partway through the journey, and a leftover step would
        # make `sentence_for` describe a screen he never saw.
        attempt.step = ""
        attempt.detail = DISCONNECTED_SENTENCE if was_connected else UNFINISHED_SENTENCE
        attempt.at = _now()
        await store.record(attempt)
        stopped += 1
        stopped_keys.append(attempt.key)
    return {"checked": checked, "stopped": stopped, "unreadable": unreadable,
            # COUNTED APART FROM «stopped» (ز-12). A settled row is a connection we had lost track
            # of, not one that ended — reporting them together would make a healthy fleet look like
            # a fleet losing access.
            "settled": settled,
            "stopped_keys": stopped_keys, "reason": ""}
