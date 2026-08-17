"""An idempotency key is derived from what is being done, never drawn fresh at random.

WHAT AN IDEMPOTENCY KEY IS FOR. Two replicas of the reminders tick can claim the same row in the
same second — the store has no compare-and-set, so the claim narrows the race rather than closing
it. Everything downstream survives that because the key travelling with the send is the same on
both paths: the quota consumes one unit, and the notifier refuses the second call. The key IS the
crossing guard, and every layer above it is written as if it were.

WHAT WENT WRONG. `tick.py` read the key off the row and, when the row had never been sent and
carried none, minted `f"rem_{uuid.uuid4().hex}"`. Two winners, two different UUIDs, nothing in
common — so the guard was absent on exactly the send it was written for: the FIRST one. The
customer read «حان موعد صيانتك» twice in the same minute and the shop was billed twice.

A fresh random is indistinguishable from a real key at every point downstream — same shape, same
type, passes every assertion — and it is the one thing a key must never be. So it is refused here
rather than reviewed: a key must be a function of the thing being done, and two callers doing the
same thing must arrive at the same string.

NO EXCEPTIONS TABLE. There is no send whose key may be random. If a new path needs one, it needs a
deterministic identity for its occasion — which is the design question this gate exists to force.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

#: Our own services. `platform/` is vendored and read-only; its own duplicate barrier is ز-3,
#: escalated rather than edited here.
TREE = ROOT / "services"
SKIP_DIRS = {"__pycache__", ".pytest_cache", "tests", ".venv"}

RANDOM = re.compile(r"uuid4\(\)|uuid1\(\)|token_hex|token_urlsafe|random\.|secrets\.")

#: A NAME IS NOT ENOUGH, AND THE FIRST VERSION OF THIS GATE USED ONE. `key` matched
#: `key = f"rj3_{secrets.token_urlsafe(32)}"` in partners.py — a partner's API CREDENTIAL, which
#: must be random and unguessable, the exact opposite requirement. Two things share the word.
#:
#: So the scope is USE, not spelling: a name is judged here only if the file hands it to something
#: as `idempotency_key=`. That is what makes it an idempotency key rather than a key, and it is
#: precisely how the defect looked — `key = uuid4()` five lines above `idempotency_key=key`.
USED_AS_IDEM = re.compile(r"idempotency_key\s*=\s*([A-Za-z_]\w*)")
ASSIGNED = r"^\s*{}\s*=\s*(.+)$"

#: And a random passed straight in, with no name to inspect at all.
INLINE = re.compile(r"idempotency_key\s*=\s*[^\n]*(?:uuid4\(\)|token_hex|token_urlsafe)")


def main() -> int:
    hits: list[str] = []
    scanned = 0
    for path in sorted(TREE.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            # A GATE THAT CANNOT READ MUST FAIL LOUDLY.
            print(f"cannot read {path.relative_to(ROOT).as_posix()}: {exc}")
            return 1
        scanned += 1
        lines = text.splitlines()
        # Every name this file ever hands to something as `idempotency_key=`.
        names = {m.group(1) for m in USED_AS_IDEM.finditer(text)}
        for line_no, line in enumerate(lines, start=1):
            if line.lstrip().startswith("#"):
                continue
            if INLINE.search(line):
                hits.append(f"{path.relative_to(ROOT).as_posix()}:{line_no}: {line.strip()[:110]}")
                continue
            for name in names:
                m = re.match(ASSIGNED.format(re.escape(name)), line)
                if m and RANDOM.search(m.group(1)):
                    hits.append(
                        f"{path.relative_to(ROOT).as_posix()}:{line_no}: {line.strip()[:110]}")
                    break

    if not scanned:
        # SILENCE IS NOT AGREEMENT: scanning nothing is not the same as finding nothing.
        print("scanned no files — this gate needs re-pointing")
        return 1
    if hits:
        print(f"An idempotency key is drawn at random in {len(hits)} place(s):")
        for line in hits:
            print("  " + line)
        print("\nDerive it from the thing being done: two callers doing the same thing must "
              "arrive at the same string, or the key guards nothing on the first attempt.")
        return 1
    print(f"{scanned} files: every idempotency key is derived, none is drawn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
