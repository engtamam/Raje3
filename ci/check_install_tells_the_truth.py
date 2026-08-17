"""The installer must not report an install it did not perform.

TWO SHAPES, both found in the same read of `deploy/` (ل-3, ل-8), both invisible at every step.

1. A STEP WHOSE FAILURE IS SWALLOWED. `bash seed/seed-plans.sh || echo "  (plans: see above)"`
   prints a line and moves on, and `echo` in a subprocess raises no flag anywhere: the run ends
   «اكتمل التثبيت» with no plans, no legal documents and no backup targets. Without plans nothing
   can be sold; without legal nobody can register a company; without backup targets the scheduler
   reports success against an empty list and the first sign of it is a restore that finds nothing.
   A swallowed failure is allowed — some steps genuinely are optional — but it must MARK the run.

2. AN IMAGE REFERENCE COMMITTED AGAINST A LOCAL REGISTRY. `image: 127.0.0.1:5055/raje3/console@…`
   is the address of a registry running on the machine that shipped it. Applied to a fresh host
   that manifest resolves to nothing: every step succeeds, the pod sits in ImagePullBackOff, and
   the edge routes `/*` at it — so the domain opens on nothing. The node-registry rewrite belongs
   to ship time, on the node; a repository file must name a registry the world can reach.

Both are checked against the repository, so neither needs a cluster.

    python ci/check_install_tells_the_truth.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEPLOY = ROOT / "deploy"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

#: A step, not a value. `$(cmd || echo 0)` is a default for a READ — the swallow this looks for is
#: at statement level, where the command was run for its effect and its failure decides whether
#: the install is real.
#:
#: `|| echo`, NEVER `|| true`. The two are not the same act. `kubectl delete … || true` says «I do
#: not care whether this existed», out loud, and an idempotent teardown genuinely does not care.
#: `|| echo "  (plans: see above)"` is the opposite: it NOTICES the failure, prints a line shaped
#: like a footnote, and lets the run end «complete» anyway. Flagging `|| true` as well would put
#: ten deliberate teardowns beside four real lies, and a check whose findings are mostly noise is
#: one people learn to scroll past.
STEP = re.compile(r"^\s*(bash|sh|python3?|kubectl|helm)\b[^|]*\|\|\s*echo\b")

#: What marks the run: any assignment or call that the script's own ending can read.
MARKS = ("FAILED", "WARNED", "fail ", "die ", "exit 1")

#: A registry that only exists on the machine that wrote the line.
LOCAL_REGISTRY = re.compile(r"image:\s*(127\.0\.0\.1|localhost|0\.0\.0\.0):\d+/")


def swallowed_steps() -> list[str]:
    out: list[str] = []
    for path in sorted(DEPLOY.rglob("*.sh")):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            before = line.split("||")[0]
            if "$(" in before:
                continue
            # INSIDE A QUOTED ARGUMENT IS SOMEBODY ELSE'S SHELL — `sh -c 'a && echo X || echo Y'`
            # is a probe reporting its own result, not this script swallowing a step.
            if before.count("'") % 2 or before.count('"') % 2:
                continue
            if not STEP.match(line):
                continue
            # THE MARK MUST BE AN ACT, NOT A WORD INSIDE THE MESSAGE — د-4.
            #
            # This read `any(m in line ...)` — the WHOLE line, `echo` text included. So
            # `|| echo "(plans FAILED: see above)"` excused itself: the word «FAILED» appears in
            # the string it prints, and the check that exists precisely to catch a swallowed step
            # was talked out of it by the swallowed step's own footnote.
            #
            # A mark is something the script's ending can READ — a flag it sets, a `die`, an
            # `exit 1`. Printing the word is the opposite: it is what a line does INSTEAD of
            # recording the failure. So the message is cut away and only what follows it counts.
            tail = line.split("||", 1)[1] if "||" in line else line
            after_echo = tail.split("echo", 1)[1] if "echo" in tail else tail
            # Everything after the closing quote of the echoed message: `; FAILED=1`, `&& die`.
            for q in ('"', "'"):
                if after_echo.count(q) >= 2:
                    after_echo = after_echo.split(q)[2] if len(after_echo.split(q)) > 2 else ""
                    break
            if any(m in after_echo for m in MARKS):
                continue
            out.append(f"{rel}:{i}  {line.strip()[:110]}")
    return out


def local_images() -> list[str]:
    out: list[str] = []
    for path in sorted(DEPLOY.rglob("*.yaml")):
        rel = str(path.relative_to(ROOT)).replace("\\", "/")
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if LOCAL_REGISTRY.search(line):
                out.append(f"{rel}:{i}  {line.strip()[:110]}")
    return out


def _scripts_seen() -> int:
    return sum(1 for _ in DEPLOY.rglob("*.sh"))


def main() -> int:
    swallowed = swallowed_steps()
    local = local_images()

    if swallowed:
        print(f"{C_R}  ✘ {len(swallowed)} step(s) whose failure is swallowed without marking the "
              f"run — the install ends «complete» either way:{C_N}")
        for line in swallowed:
            print(f"{C_R}      {line}{C_N}")
    if local:
        print(f"{C_R}  ✘ {len(local)} image reference(s) pinned to a registry that exists only on "
              f"the machine that wrote them:{C_N}")
        for line in local:
            print(f"{C_R}      {line}{C_N}")

    if swallowed or local:
        print(f"{C_R}    Record the failure and say so at the end, and name a registry a fresh "
              f"host can reach.{C_N}")
        return 1

    # AND SILENCE IS NOT AGREEMENT — the other half of د-4. With no scripts found this printed the
    # same green line it prints after reading forty of them. A rename, a moved directory, a glob
    # that stops matching: all of them read as «nothing wrong» rather than «nothing checked».
    seen = _scripts_seen()
    if seen == 0:
        print(f"{C_R}  ✘ no shell scripts found under deploy/ — this check read nothing, which is "
              f"not the same as finding nothing wrong{C_N}")
        return 1

    print(f"{C_G}  ✔ every swallowed step in {seen} scripts marks the run, and every committed "
          f"image names a reachable registry{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
