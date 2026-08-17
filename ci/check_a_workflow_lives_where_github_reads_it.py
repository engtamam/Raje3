#!/usr/bin/env python3
"""A CI WORKFLOW SITS WHERE GITHUB READS IT — or it is a YAML file pretending to be a pipeline.

WHAT THIS FOUND, AND IT HAD BEEN TRUE FOR MONTHS.

Six services each carried `services/<name>/.github/workflows/security.yml`: checkout, install,
`pytest -q`, `security_gate.py --strict`. Correct, complete, identical but for a comment. And
GitHub Actions reads workflows ONLY from `.github/workflows/` at the repository root — a workflow
in a subdirectory is an ordinary file that nothing looks at.

So 3,593 tests and six strict security gates ran exactly when a human remembered to run them, and
every one of those files looked like proof that they ran on every push. Nobody was careless: the
files are well written. They were simply in a place that means nothing, and there is no signal
anywhere that says so — no warning, no empty run list, nothing red.

THE RULE, AND IT HAS NO EXCEPTIONS TABLE. A file under any `.github/workflows/` directory that is
not the repository root is refused. Not «warned about» — refused, because the failure mode is a
pipeline that appears to exist.

WHY NOT ALSO CHECK THE ROOT ONES RUN. Because that is not decidable by reading, and a gate that
overreaches gets loosened. This closes the one case that IS decidable and was the actual defect:
a workflow parked where the runner never looks.

SCOPE: our own tree. `platform/` is a submodule with its own CI, and `node_modules` ships hundreds
of vendored workflows that are none of our business — sweeping those in is how a gate acquires an
exceptions table.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Not ours to police: a submodule runs its own CI, and vendored packages carry their authors'.
NOT_OURS = ("platform", "node_modules", ".git", ".claude")


def main() -> int:
    bad: list[str] = []
    root_workflows = 0

    for path in sorted(ROOT.rglob(".github/workflows/*.y*ml")):
        rel = path.relative_to(ROOT)
        if any(part in NOT_OURS for part in rel.parts):
            continue
        # `.github/workflows/x.yml` at the root is exactly three parts deep.
        if rel.parts[0] == ".github":
            root_workflows += 1
            continue
        bad.append(
            f"{rel.as_posix()}: GitHub reads workflows only from `.github/workflows/` at the "
            f"REPOSITORY ROOT. This one has never run and never will — and it reads, to anyone "
            f"who opens it, as a pipeline that guards every push")

    if bad:
        print(f"{C_R}a workflow is parked where the runner never looks{C_N}")
        for line in bad:
            print(f"  {line}")
        print("\n  Move it to .github/workflows/ — see services.yml, which runs all six suites.")
        return 1

    if root_workflows == 0:
        print(f"{C_R}no workflows at all under .github/workflows — nothing runs on a push, and an "
              f"empty set is not agreement{C_N}")
        return 1

    print(f"{C_G}ok{C_N}  {root_workflows} workflows, every one where GitHub reads it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
