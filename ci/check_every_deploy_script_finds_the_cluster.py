#!/usr/bin/env python3
"""EVERY SCRIPT THAT TOUCHES THE CLUSTER ASKS THE SAME PLACE WHERE IT IS.

WHAT HAPPENED. `deploy/` held thirty-two scripts and three different answers to «which machine?».
`verify-fleet.sh` read `target.env`. `ship.sh` read it and then defaulted to `<ssh-user>@127.0.0.1:2224`
if it said nothing. The eighteen `prove-*.sh` never read it and called the local `kubectl`. When
the cluster moved to a real host, one of the three was updated — because nothing tied the other
two to it, so there was nothing to notice.

The result was not an error message. It was eighteen proofs reporting «connection refused to
localhost:8080» against a fleet that was up, right after a ship, which is when an operator is
least able to tell a broken proof from a broken deploy.

Worse, the same line said it thirty-two times: `export KUBECONFIG="${KUBECONFIG:-/etc/rancher/
k3s/k3s.yaml}"` — the path k3s writes ON THE NODE, in scripts run from a laptop where no such file
exists. kubectl does not complain about a kubeconfig that is not there; it falls back to
localhost:8080 and says «connection refused».

THE RULE, AND IT HAS NO EXCEPTIONS TABLE.

  1. A script under `deploy/` that runs `kubectl` or `helm` sources `cluster.sh`, which is the one
     place that reads `target.env`, walks the ladder from an explicit KUBECONFIG down to ssh, and
     STOPS LOUDLY when there is no rung left.
  2. No script decides for itself which kubeconfig to use, and none names an ssh destination. Not
     as a default, not as a fallback, not in a `${VAR:-...}`. A default target is precisely how a
     script reaches confidently for a machine that does not exist — `ship.sh` and `registry.sh`
     both carried `<ssh-user>@127.0.0.1`, an address that stopped meaning anything the day its tunnel
     was retired, and neither of them said so.

WHY NOT «reads target.env somehow». Because that was the old state: three scripts all read it,
each slightly differently, and the differences were the defect. One seam or none.

THE SHAPE IS REMOVED, NOT LISTED. There is nothing left for a new script to get wrong except
forgetting the source line, and that is the single thing this gate checks.
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
SEAM = "cluster.sh"

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# The commands that only mean something once you know which cluster you are talking to. `ssh` and
# `scp` are deliberately NOT here: a script may legitimately reach the node itself rather than its
# cluster, and rule 2 below is what keeps that honest by refusing a hardcoded destination.
NEEDS_CLUSTER = re.compile(r"(?<![-\w./])(kubectl|helm)(?![-\w])")

# AN SSH DESTINATION, WHICH IS THE ONLY PLACE A HOST LITERAL DOES HARM. `127.0.0.1` inside a
# probe URL or a listen address is a script talking to itself and is correct; `ssh … <ssh-user>@
# 127.0.0.1` is a script talking to a tunnel that no longer exists. The scope is narrowed to
# `ssh`/`scp` arguments rather than the pattern loosened to spare the innocent ones.
A_DESTINATION = re.compile(
    # The lookbehind spares `--ssh` style flags but NOT `${SSH:-ssh …}`, which is where
    # prove-ladder.sh kept its dead tunnel: a hyphen before `ssh` is far more often a default
    # than a flag.
    r"(?<![\w./])(?:ssh|scp)\s[^|;&]*?"
    r"(?<![\w.@-])((?:[a-z_][\w.-]*@[\w.-]+)|\d{1,3}(?:\.\d{1,3}){3})(?![\w.-])",
    re.IGNORECASE)

# AND THE FALLBACK THAT LOOKS LIKE CAUTION AND IS NOT: `REMOTE="${REMOTE:-<ssh-user>@127.0.0.1}"`.
# A default here does not make the script more robust — it makes it unable to say «I was not
# told where to go», which is the one thing it needed to say.
A_DEFAULT_HOST = re.compile(
    r':-\s*((?:[a-z_][\w.-]*@[\w.-]+)|\d{1,3}(?:\.\d{1,3}){3})[}"\']', re.IGNORECASE)

# AND THE LINE THAT WAS THE WHOLE DEFECT: a script naming a kubeconfig. The node's path is right
# on the node and silent nonsense on a laptop, and `cluster.sh` is where that difference is known.
A_KUBECONFIG = re.compile(r"(?<![-\w])KUBECONFIG\s*=")

# Said aloud in prose is fine — «ssh <node> 'sudo bash …'» in a hint, an example address in a
# comment. A comment cannot connect to anything, and neither can a sentence: `install.sh` warns
# «الحافة لا تخدم: kubectl -n $NS get pods», which is advice to a human and not a call. Quoted
# spans are emptied for the same reason comments are dropped.
CODE_ONLY = re.compile(r"^\s*#")
QUOTED = re.compile(r'"[^"]*"|\'[^\']*\'', re.DOTALL)

# A LINE THAT SPEAKS RATHER THAN ACTS. Quote-stripping is right for the whole-file question («does
# anything here CALL kubectl?») and wrong for the per-line ones, because
# `SSH="${SSH:-ssh -p 2224 <ssh-user>@127.0.0.1}"` is entirely inside quotes and is exactly the defect.
# So the per-line rules read the raw line and skip only the lines whose verb is speech.
PROSE = re.compile(r"^\s*(echo|printf|warn|ok|die|say|red|note|hint|step|phase)\b")


def _sources_seam(text: str) -> bool:
    """Does this script pull in the shared seam?

    Matched on the filename rather than an exact incantation: the path to it differs between a
    script in `deploy/` and one that may later live a directory down, and pinning the spelling
    would make the gate an argument about quoting instead of about reaching the cluster.
    """
    return any(SEAM in line and re.match(r"\s*(\.|source)\s", line)
               for line in text.splitlines())


def main() -> int:
    bad: list[str] = []
    checked = 0

    scripts = sorted(DEPLOY.rglob("*.sh"))
    if not scripts:
        print(f"{C_R}no scripts under deploy/ — this gate has nothing to check, which is not the "
              f"same as finding nothing wrong{C_N}")
        return 1

    for path in scripts:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            # REPORTED, NOT SKIPPED. A file this gate cannot read is a file it cannot clear.
            bad.append(f"{rel}: cannot read it — {exc}")
            continue
        checked += 1

        # The seam is the answer; it does not source itself.
        is_seam = path.name == SEAM

        code = [ln for ln in text.splitlines() if not CODE_ONLY.match(ln)]
        body = QUOTED.sub('""', "\n".join(code))

        if not is_seam and NEEDS_CLUSTER.search(body) and not _sources_seam(text):
            cmd = NEEDS_CLUSTER.search(body).group(1)
            bad.append(f"{rel}: runs `{cmd}` without sourcing {SEAM} — so it resolves against "
                       f"whatever kubeconfig the operator happens to have, and says «connection "
                       f"refused» rather than «I do not know where the cluster is»")

        for n, line in enumerate(text.splitlines(), 1):
            if CODE_ONLY.match(line) or PROSE.match(line):
                continue
            host = A_DESTINATION.search(line) or A_DEFAULT_HOST.search(line)
            if host:
                bad.append(f"{rel}:{n}: names an ssh destination — `{host.group(1)}`. The target "
                           f"comes from target.env through {SEAM}, and a default is how a script "
                           f"reaches confidently for a machine nobody has run in months")
            if not is_seam and A_KUBECONFIG.search(line):
                bad.append(f"{rel}:{n}: sets KUBECONFIG itself. That path is the node's, it is "
                           f"absent on the machine this runs from, and kubectl answers a missing "
                           f"kubeconfig with «connection refused to localhost» rather than with "
                           f"the truth. {SEAM} knows which rung applies")

    if bad:
        print(f"{C_R}a deploy script decides for itself where the cluster is{C_N}")
        for line in bad:
            print(f"  {line}")
        print(f"\n  Source the seam once, at the top, after `set -`:")
        print(f'    . "$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)/{SEAM}"')
        return 1

    print(f"{C_G}ok{C_N}  {checked} deploy scripts — all of them ask {SEAM} where the cluster is")
    return 0


if __name__ == "__main__":
    sys.exit(main())
