"""A test that skips for want of a server must have that server given to it by CI.

WHAT IS TRUE TODAY, AND IT IS THE LARGEST SILENT HOLE LEFT IN THIS REPOSITORY.

`.github/workflows/services.yml` installs each service and runs `pytest -q`. It provides no
postgres and no object store. So in every one of the six services, `tests/contracts/` skips:

    tests/contracts/test_datastore_contract.py  — 19 tests, «set DATASTORE_TEST_DSN»
    tests/contracts/test_object_store_contract.py — 7 tests, «OBJECTSTORE_TEST_ENDPOINT not set»

That is a hundred and fifty-six tests that have never run anywhere but on somebody's laptop, if
ever — and they are the ones that hold the REAL adapters to the contract. Every other test in the
product runs against `MemoryDataStore`, whose `asyncio.Lock` serialises writers and hides every
race a real database has to handle. The contract file says so itself, in its own words.

AND THE SUITE REPORTS «930 passed, 27 skipped» — a confident green over the layer that actually
holds every shop's data. The workflow beside it insists on `--strict` for the security gate,
because «without it the gate is allowed to skip checks it cannot run and still exit zero — which
reads as a pass and is not one». The same sentence applies to the line above it and was not applied.

THE RULE. If a test decides whether to run by reading an environment variable, the workflow that
runs that test must set it. Skipping is a decision, and a decision nobody made is not one: either
CI provides the thing, or the test is not a guard and should not read as one.

    python ci/check_ci_provides_what_the_tests_wait_for.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "services"
WORKFLOW = ROOT / ".github" / "workflows" / "services.yml"

#: An environment read inside a file that can skip. Both spellings, because both are used.
READ = re.compile(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]+)"|os\.getenv\(\s*"([A-Z][A-Z0-9_]+)"')


def _gates_of_skipping() -> dict[str, set[str]]:
    """Every env var a test consults, in files that can skip — with who reads it."""
    out: dict[str, set[str]] = {}
    for service in sorted(p for p in SERVICES.iterdir() if p.is_dir()):
        tests = service / "tests"
        if not tests.is_dir():
            continue
        for path in sorted(tests.rglob("*.py")):
            source = path.read_text(encoding="utf-8", errors="ignore")
            # NOT EVERY ENV READ — only the ones a file uses to decide whether to run at all. A
            # test that reads a variable and runs regardless is configuration, not a guard that
            # excuses itself.
            #
            # AND OMITTING A PARAMETER IS ALSO DECIDING NOT TO RUN — quieter than a skip, because
            # it produces no line in any summary. The contracts hold each driver by adding it to
            # `_PARAMS` when its server is reachable; a variable that gates that list gates real
            # coverage exactly as a `skip` does, and the first version of this gate could not see
            # it.
            if "skip" not in source and "_PARAMS" not in source:
                continue
            for first, second in READ.findall(source):
                out.setdefault(first or second, set()).add(
                    path.relative_to(ROOT).as_posix())
    return out


def main() -> int:
    if not WORKFLOW.is_file():
        print(f"{WORKFLOW.relative_to(ROOT)} is missing — the workflow that runs the suites is "
              f"not where it was, and «cannot find it» is not a pass")
        return 1

    workflow = WORKFLOW.read_text(encoding="utf-8")
    waiting = _gates_of_skipping()
    if not waiting:
        print("  \033[32m✔ no test decides whether to run by reading the environment\033[0m")
        return 0

    missing = {name: files for name, files in waiting.items() if name not in workflow}
    if missing:
        print("  \033[31m✘ tests wait for something CI never provides — so they never run:\033[0m")
        for name, files in sorted(missing.items()):
            print(f"      \033[31m{name} — read by {len(files)} test file(s), absent from "
                  f"{WORKFLOW.relative_to(ROOT).as_posix()}\033[0m")
        print("\n    Give the job the service and set the variable, or delete the test. A guard "
              "that is skipped\n    on every run is not a guard — and it reads as a pass, which "
              "is worse than not having it.\n    Do not exempt it here.")
        return 1

    print(f"  \033[32m✔ CI provides everything the suites wait for "
          f"({len(waiting)} variable(s))\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
