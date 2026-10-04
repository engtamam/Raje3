#!/usr/bin/env python3
"""EVERY `ssh`/`scp` CALL UNDER deploy/ NAMES AN IDENTITY FILE — `-i "$KEY"` (or `${KEY:+-i
"$KEY"}` when the flag is meant to be optional), NEVER A BARE CALL LEFT TO WHATEVER IDENTITY AN
AGENT OR `~/.ssh/config` HAPPENS TO HOLD.

WHAT HAPPENED, TWICE, IN THE SAME SESSION (2026-09-28). `deploy/ship.sh`'s own `SSH=(...)` array
had no identity flag at all; a human running it by hand, with the right key already loaded in an
ssh-agent, never noticed. Every unattended ship did — `ops-mcp`'s own `deploy_ship` sets `KEY` in
the environment for exactly this, but a script that never reads the variable cannot use it. That
one got fixed. `deploy/verify-fleet.sh` carried the IDENTICAL shape, one file over, and was found
only by grepping every other script for the same pattern rather than waiting for it to fail on
its own — worse, `deploy/cluster.sh`'s own ssh-mode `kubectl()` wrapper had the same gap, and it
looked like it was WORKING: the first ssh connection a run's correctly-keyed call opened got
reused by this wrapper's key-less calls over the same multiplexed control socket, right up until
a long-enough pause (`verify_running`'s own 10-minute poll loop, before this incident shortened
it) let that socket's idle timeout lapse — at which point every following call failed with
`Permission denied (publickey)` against a perfectly healthy fleet.

THE RULE. A line that runs `ssh`/`scp` against `$REMOTE`/`$TARGET`/a `$REMOTE`-shaped destination
must carry `-i` somewhere on it — literally, or through `${KEY:+...}`/`$SSH_OPTS`-style expansion
that itself carries `-i`. `pack.sh`'s own calls (`-i "$KEY"`, no `${KEY:+...}` guard) are the
plainer, REQUIRED-key shape this gate also accepts — the guard is a courtesy for scripts that
still work with an ambient identity, not a requirement every caller must offer.

WHAT THIS DOES NOT DO. It never runs a command or reaches a network — pure text matching, same
posture as check_every_deploy_script_finds_the_cluster.py right above it in ci/.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# A REAL CALL, NOT PROSE ABOUT ONE. `echo "ssh host cmd"` and a comment naming the command are
# both text, not a connection — skip anything that isn't code speaking for itself.
PROSE_OR_COMMENT = re.compile(r"^\s*(#|echo\b|printf\b|warn\b|ok\b|die\b|say\b|red\b|grn\b|note\b|hint\b|step\b|phase\b)")

# `ssh`/`scp` invoked as a real command — as the first word of a pipeline segment, inside an
# `SSH=(...)` array assignment, or via `"${SSH[@]}"`-style reuse (which this gate does not need to
# re-check per call site, since the array itself already carries -i once and every reuse inherits
# it — only the ARRAY ASSIGNMENT itself is checked). NEVER a bare occurrence of the word (a quoted
# string like `CLUSTER_VIA="ssh"`, or "ssh" inside a longer identifier) — only where it is actually
# the command being invoked: right after `=(`, a pipe, `&&`, `;`, backticks, or line-start.
SSH_CALL = re.compile(r"(?:^|[|;`(]|&&)\s*[\"']?(ssh|scp)\b(?!\s*=)")

# Carries an identity flag somewhere on the line — literal `-i`, or a `${KEY:+...}`/`$SSH_OPTS`
# style expansion (the exact shape this session's own fixes used).
HAS_IDENTITY = re.compile(r"(-i\s|KEY[:+}]|SSH_OPTS|SSH\[@\])")


def _offenders(path: pathlib.Path) -> list[tuple[int, str]]:
    out = []
    for i, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if PROSE_OR_COMMENT.match(line):
            continue
        if not SSH_CALL.search(line):
            continue
        if HAS_IDENTITY.search(line):
            continue
        out.append((i, line.strip()))
    return out


def main() -> int:
    offenders: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(DEPLOY.rglob("*.sh")):
        hits = _offenders(path)
        if hits:
            offenders[str(path.relative_to(ROOT))] = hits

    if not offenders:
        print(f"{C_G}✔ every ssh/scp call under deploy/ carries an identity flag{C_N}")
        return 0

    print(f"{C_R}✗ ssh/scp call(s) with no identity flag — falls back to an ambient "
          f"ssh-agent/~/.ssh/config identity, which an automated caller never has:{C_N}")
    for rel, hits in offenders.items():
        for lineno, text in hits:
            print(f"  {rel}:{lineno}: {text}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
