"""A surface designed to be reached without a token is not locked at the gateway (ط-6).

WHAT HAPPENED. `reminders/api/v1/prefs.py` opens by explaining that it is reached from a link at
the end of a WhatsApp message, that the link carries nothing, and that this is the whole security
design of the surface: an opaque reference, no name, no phone, no history, rate limited hard. The
gateway had it as `"auth":"required"`.

Nothing failed and nothing looked wrong, because the direction is the safe one — a route locked
tighter than intended raises no alarm anywhere. The customer taps «إيقاف الرسائل», lands on a login
screen for an account he does not have, and PDPL's right to object is a dead button. Refusing to
hear «stop» is not the safe side of this one.

HOW THIS IS DETECTED. Two files, written by two people, months apart, that must agree and share no
symbol. So the gate reads BOTH: a service module that declares itself token-free in its own words
must appear in the gateway's route table as `auth: none`.

THE DECLARATION IS A MARKER, NOT PROSE. `# gateway: auth none` on its own line — the check must not
depend on how somebody phrased a paragraph, and a module that means it says so in one place a
reader and a machine agree about.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
GATEWAY = ROOT / "deploy" / "services" / "api-gateway.values.yaml"
SERVICES = ROOT / "services"
MARKER = re.compile(r"^#\s*gateway:\s*auth\s+none\s*$", re.MULTILINE)
ROUTE = re.compile(r'\{"prefix":"(?P<prefix>[^"]+)"[^}]*"auth":"(?P<auth>[^"]+)"')


def _declared() -> dict[str, pathlib.Path]:
    """prefix -> the module that declared it open, from `# gateway: auth none` plus its own path."""
    out: dict[str, pathlib.Path] = {}
    for path in sorted(SERVICES.rglob("app/api/v1/*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
            raise SystemExit(1) from exc
        if MARKER.search(text):
            out[f"/api/v1/{path.stem}"] = path
    return out


def main() -> int:
    if not GATEWAY.exists():
        print(f"cannot find {GATEWAY.relative_to(ROOT).as_posix()} — this gate needs re-pointing")
        return 1
    table = {m.group("prefix"): m.group("auth")
             for m in ROUTE.finditer(GATEWAY.read_text(encoding="utf-8"))}

    declared = _declared()
    if not declared:
        # SILENCE IS NOT AGREEMENT. `prefs` carries the marker; an empty set means the marker was
        # renamed or the tree moved, and a check with nothing to check must say so rather than
        # print ok.
        print("no module declares `# gateway: auth none` — the marker or the tree moved")
        return 1

    bad = []
    for prefix, path in sorted(declared.items()):
        auth = table.get(prefix)
        where = path.relative_to(ROOT).as_posix()
        if auth is None:
            bad.append(f"{where} declares {prefix} open, and the gateway has no route for it")
        elif auth != "none":
            bad.append(f'{where} declares {prefix} open, and the gateway has "auth":"{auth}"')

    if bad:
        print("A surface built to be reached without a token is locked at the door:")
        for line in bad:
            print("  " + line)
        print("\nThe person holding the link has no account. He taps the link and gets a login "
              "screen.")
        return 1
    print(f"{len(declared)} token-free route(s), open at the door " + json.dumps(sorted(declared)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
