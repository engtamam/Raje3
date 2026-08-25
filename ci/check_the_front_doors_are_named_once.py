"""The browser origins a service trusts are the product's own front doors — never invented per file.

WHAT THIS WAS WRITTEN AFTER. `deploy/verify-fleet.sh` was run against the cluster and reported the
same disagreement on SEVENTEEN services: `CORS_ALLOWED_ORIGINS` held the real origins on the box,
and the empty string in this repository. Somebody had configured the cluster by hand, or from a
revision since edited, and the values files went on saying «no browser may call this».

THAT IS NOT A COSMETIC DRIFT. `ship.sh` uploads a service's values file verbatim and `install.sh`
applies it. So the next install of any of those seventeen would have set CORS back to empty, every
call from `app.raje3.sa` would have failed its preflight, and the console would have gone dark for
every shop at once — with nothing in the repository looking wrong, because a blank field looks like
a field nobody has needed yet.

THE RULE, WITH NO EXCEPTIONS TABLE. Every origin named in any values file is one of the product's
own front doors, listed below. A service may trust a subset — the operator surface trusts only the
admin console, and that is a real distinction — and it may trust none, which is right for anything
no browser calls. What it may not do is name a HOST NOBODY DECLARED: a typo (`app.raje3.com`),
a stale staging domain, or a partner's origin added in a hurry and never removed. Each of those is
a browser we did not mean to trust, in a file nobody re-reads.

WHY A LIST HERE RATHER THAN A LOOKUP. These four strings are the product's public identity. They
change when a domain is bought, which is a decision, not a deployment — and a check that read them
from the same files it is checking would agree with any value it found, including a typo.

WHAT THIS CANNOT SEE, said plainly:
  · whether a service that SHOULD trust a browser has been left empty. Only the cluster and the
    console's own network calls know which services a browser reaches, and `verify-fleet.sh`
    answers that by comparing against what is actually running;
  · whether the cluster still agrees with these files. That is the same script, run over ssh, and
    it is the only thing that can answer it.

    python ci/check_the_front_doors_are_named_once.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy/services"

#: The product's own front doors. Adding one is a decision about what raje3 IS, so it is made here,
#: once, and every values file is measured against it.
FRONT_DOORS = {
    "https://app.raje3.sa",      # the shop owner's console
    "https://admin.raje3.sa",    # our own operator panel
    "https://my.raje3.sa",       # the customer's page (closed for the first release — #351)
    "https://kobo-cloud.com",    # the test box the pilot runs on
}

ORIGINS = re.compile(r"^\s*CORS_ALLOWED_ORIGINS:\s*\"([^\"]*)\"", re.M)


def main() -> int:
    if not VALUES.is_dir():
        # SILENCE IS NOT AGREEMENT. A moved directory makes this vacuous, and a gate that passes
        # for having read nothing is the failure it exists to prevent.
        print(f"FAIL: {VALUES.relative_to(ROOT)} is missing — this gate read nothing")
        return 1

    files = sorted(VALUES.glob("*.values.yaml"))
    checked = 0
    problems: list[str] = []
    for path in files:
        for m in ORIGINS.finditer(path.read_text(encoding="utf-8")):
            checked += 1
            for origin in [o.strip() for o in m.group(1).split(",") if o.strip()]:
                if origin not in FRONT_DOORS:
                    problems.append(f"  {path.name}: «{origin}» is not one of our front doors")

    if not checked:
        print("FAIL: no CORS_ALLOWED_ORIGINS found in any values file — either the key was renamed "
              "or the files moved, and in both cases this gate is asserting nothing")
        return 1

    if problems:
        print(f"FAIL: {len(problems)} origin(s) nobody declared:")
        for p in problems:
            print(p)
        print(f"\n  Our front doors are {sorted(FRONT_DOORS)}. An origin outside that set is a "
              f"browser we did not mean to trust — a typo, a retired staging host, or somebody "
              f"else's domain added in a hurry. If it is a real new door, add it above, once.")
        return 1

    print(f"OK: {checked} CORS declaration(s) across {len(files)} services, every origin a door we "
          f"declared")
    return 0


if __name__ == "__main__":
    sys.exit(main())
