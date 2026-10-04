"""A new WhatsApp-outbound code path calls Meta's own Graph API directly, instead of going through
notification-service's one audited door — which is the ONLY place in this entire platform that
hands control of a conversation back to Meta's own AI agent after we send a message.

WHY THIS MATTERS, AND WHY IT FAILS SILENTLY IF MISSED. WhatsApp's Meta AI agent platform has no
"return control automatically" behaviour: the moment our platform sends ANY message to a customer,
we implicitly TAKE control of that conversation thread from Meta's AI — and Meta's AI stays muted
for that customer FOREVER unless something explicitly calls its `thread_control` "release" action
afterward (`POST .../phone_numbers/{id}/thread_control`, `action: "release"`). There is no error, no
log on Meta's side, nothing a human would ever notice — a customer who had Meta AI happily answering
him simply stops getting AI replies, permanently, the moment ANY of our own messages reaches him
through a path that skips this release call.

A DEEP AUDIT (2026-10-03) CONFIRMED THE RELEASE LOGIC ALREADY EXISTS, AND IS ALREADY CENTRALISED.
`platform/services/notification-service/app/core/notifier.py`'s four outbound-send methods
(`_deliver_whatsapp`, `_wa_resend`, `send_interactive`, `send_carousel`) each call
`_release_thread_control()` right after a successful send, which — when the destination number is
in `meta` handover mode — durably queues and retries the real release call to Meta
(`core/release_control.py`). Every send path found anywhere in this codebase (reminders, campaigns
— which the audit confirmed never sends anything itself, whatsapp-assistant's template/interactive/
carousel senders) already funnels through this ONE door, reached either in-process or via
notification-service's own `/internal/notify*` routes.

THE ONLY WAY TO BREAK THAT GUARANTEE GOING FORWARD is a NEW piece of code, anywhere in this
platform, that calls Meta's Graph API's own message-send endpoint directly — bypassing notifier.py
entirely, and with it, bypassing the release-control call that keeps Meta's AI usable. This gate
exists to catch exactly that, the moment it is written, rather than the day an owner notices a
shop's Meta AI has gone quiet with no explanation.

WHAT IT DOES. Scans every `.py` file under `services/` and `platform/services/` (worktrees and test
directories excluded — a test asserting against the literal URL is not a live send path) for a file
that references BOTH Meta's Graph API domain (`graph.facebook.com`) AND a `/messages` endpoint
path — the two facts that together mean "this file actually POSTs an outbound WhatsApp message to
Meta", as opposed to the Catalog, Payments, onboarding or admin APIs, which share the same domain
for entirely different endpoints and carry no such risk.

A file flagged this way is either the one already-audited sender, or it needs the exact same
`_release_thread_control()` call notifier.py already makes — or a written-down reason in ALLOWLIST
below for why it genuinely does not (e.g. a different, non-customer-facing Graph API surface that
only happens to share the domain string).

    python ci/check_whatsapp_send_bypasses_meta_ai_handover.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCAN_ROOTS = (ROOT / "services", ROOT / "platform" / "services")
EXCLUDE_DIR_PARTS = {".venv", "__pycache__", "node_modules", "tests", "test"}
EXCLUDE_PATH_SUBSTRINGS = (".claude/worktrees/",)

DOMAIN_MARKER = "graph.facebook.com"
SEND_MARKER = "/messages"

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# Every entry here is a file this gate would otherwise flag, kept out of CI red by a reviewed,
# written-down reason — never by weakening the two-marker heuristic itself.
#
#   key: "relative/path.py"
ALLOWLIST: dict[str, str] = {
    "platform/services/notification-service/app/adapters/whatsapp/meta.py": (
        "the one audited sender — notifier.py's four send methods call this and each already calls "
        "_release_thread_control() right after a successful send (confirmed by direct read, "
        "2026-10-03); this IS the door every other path must go through, not a bypass of it"
    ),
    "platform/services/notification-service/app/config.py": (
        "config constants only, no HTTP call — WHATSAPP_GRAPH_BASE/WHATSAPP_ONBOARDING_GRAPH_BASE "
        "are just the domain string, and the '/messages' marker only matches unrelated email/SMS "
        "provider comments (Mailgun/Unifonic/Taqnyat) a few lines above them"
    ),
}


def _is_excluded(path: pathlib.Path) -> bool:
    posix = path.as_posix()
    if any(sub in posix for sub in EXCLUDE_PATH_SUBSTRINGS):
        return True
    return any(part in EXCLUDE_DIR_PARTS for part in path.parts)


def _scan() -> tuple[list[str], list[str]]:
    ok, bad = [], []
    for scan_root in SCAN_ROOTS:
        if not scan_root.is_dir():
            continue
        for path in sorted(scan_root.rglob("*.py")):
            if _is_excluded(path):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if DOMAIN_MARKER not in text or SEND_MARKER not in text:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if rel in ALLOWLIST:
                ok.append(f"{rel} (exempt: {ALLOWLIST[rel]})")
            else:
                bad.append(rel)
    return ok, bad


def main() -> int:
    ok, bad = _scan()

    seen = {k.split(" (exempt:")[0] for k in ok}
    for key, reason in ALLOWLIST.items():
        if not reason.strip():
            print(f"{C_R}ALLOWLIST entry {key!r} has an empty reason — every exemption must be "
                  f"written down{C_N}")
            return 1
        if key not in seen:
            print(f"{C_Y}ALLOWLIST entry {key!r} no longer matches anything this gate scans — "
                  f"remove it{C_N}")
            return 1

    if bad:
        print(f"{C_R}A new WhatsApp-send-shaped file calls Meta's Graph API directly, outside the "
              f"one audited door:{C_N}")
        for rel in bad:
            print(f"  {rel}")
        print("\nEither route this send through notification-service's existing "
              "notifier.py chokepoint (which already calls _release_thread_control() after every "
              "send), or — if this genuinely is not a customer-facing message send — add it to "
              "ALLOWLIST in this script with a real, reviewed reason.")
        return 1

    print(f"{C_G}{len(ok)} Graph-API-messaging file(s) checked, all are the one audited door — "
          f"no new path bypasses the Meta AI handover{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
