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

BUT ITS ROUTE REQUIRES A PLATFORM CAPABILITY (platform.secrets), which a shop owner does not hold
and must never hold. So the owner's browser cannot call it, and there is no internal, service-token
variant of that route to call on his behalf. That gap is escalated.

Until it lands, `NullExchange` records the attempt and answers honestly that the exchange is not
configured. Everything around it — the states, the storage, the reporting, the refusal sentences —
is real and tested, so closing the gap is a configuration change rather than a project.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

CONNECTIONS = "whatsapp_connections"

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
    if attempt.state == STATE_FINISHED_UNCONFIRMED:
        # HE FINISHED. Meta created the account and the popup closed before we heard the code — so
        # the honest sentence is neither "connected" nor "cancelled", and it says what we will do
        # rather than asking him to do it again for nothing.
        return ("أكملت الخطوات على واتساب. نتحقق من اكتمال الربط خلال دقائق، "
                "ولا حاجة لإعادة العملية.")
    if attempt.state == STATE_FAILED:
        return "تعذّر إكمال الربط. حاول مرة أخرى، وإن تكرر تواصل معنا."
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


    async def live_tenants(self, *, limit: int = 500) -> list[str]:
        """Every establishment whose connection reached WhatsApp — the sweep's work list.

        BOTH LIVE STATES, and the second is the one that matters. `finished_unconfirmed` means the
        popup closed on Meta's final screen: the account EXISTS and we did not hear the code. A
        sweep that read only `connected` would skip exactly the shops whose state we are least sure
        of, which is the opposite of what a reconciliation is for.

        A cap rather than a full scan: a sweep is a repair pass that runs again in an hour, and
        progress beats completeness on a repair path.
        """
        # ONE QUERY PER STATE, not one scan filtered in memory: the datastore refuses an empty
        # `where` on purpose (scan_all exists for whole-collection reads and is not what a sweep
        # of live connections wants), and a filtered read stays cheap as the fleet grows.
        cap = max(1, min(2000, limit))
        out: list[str] = []
        for state in (STATE_CONNECTED, STATE_FINISHED_UNCONFIRMED):
            rows, _ = await self._s.find(CONNECTIONS, {"state": state}, limit=cap,
                                         sort=("at", "desc"))
            for row in rows:
                tenant = str(row.get("tenant") or "")
                if tenant and tenant not in out:
                    out.append(tenant)
        return out[:cap]


class NullExchange:
    """No Tech Provider credentials wired, or no route to reach them with.

    ANSWERS FAILED AND SAYS WHY, rather than pretending the connection worked. A shop told it is
    connected when it is not will record visits all week and wonder where its messages went — the
    failure that costs a customer rather than a request.
    """

    configured = False

    async def exchange(self, *, tenant: str, code: str, waba_id: str,
                       phone_number_id: str) -> tuple[bool, str]:
        return False, "onboarding is not configured"


class HttpExchange:
    """Hand the code to notification-service, which holds the app secret and does the exchange.

    THE PATH IS CONFIGURATION, and that is not the usual reason. The route that exists today
    requires a platform capability an owner cannot hold, and the internal variant we need does not
    exist yet — so the path this points at is the one that will land, and pointing at it is a
    values change rather than a release. Until then the driver stays null and NullExchange answers.

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
        req = urllib.request.Request(
            self._url, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Internal-Token": self._token})
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:   # nosec B310
                resp.read()
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
            return False, f"unreachable: {exc}"


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
