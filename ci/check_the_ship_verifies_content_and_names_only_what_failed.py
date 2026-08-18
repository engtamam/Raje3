"""The ship's proof must compare what runs, and its summary must name only what failed.

TWO DEFECTS FOUND IN ONE SHIPMENT, BOTH IN THE FAMILY THIS REPOSITORY KEEPS RE-FINDING: a report
whose evidence does not support the sentence it prints.

ONE — THE PROOF COMPARED TWO DIFFERENT KINDS OF DIGEST.

`verify_running` read `imageID` and compared it to the pinned digest. On a multi-arch image those
are not the same kind of name: the pin is an INDEX digest (a manifest list), while `imageID` is
whatever index containerd already had associated with the content it resolved. Measured on the
cluster, loyalty reported

    spec:    …@sha256:225470f1…     (the pin — correct)
    imageID: …@sha256:0b9518d3…     (a different index)

and the ship printed «RUNNING 0b9518… but pinned 225470…», which reads as «your image did not
take». It had. Both indexes resolve to the SAME manifest (1d51c7b9…) and the SAME config
(5ca4425a…): identical content published twice, differing only in the attestation entry the
builder attaches. The pod was running exactly the code that was shipped.

That is worse than a false alarm. #300 exists because the proof once said green over an old image;
this is the same instrument lying in the other direction, and a proof that cries wolf gets muted.

So the comparison must reach CONTENT — resolve the pinned index to the manifest or config the node
actually runs — rather than compare one name to another name.

TWO — THE SUMMARY NAMED EVERY SERVICE WHEN ONE FAILED.

`ship_many` tracked a single `rc`, and the last line printed «did not ship: $*» — the whole
argument list. Six services verified green and the closing sentence named all seven as failures.
Whoever reads only the last line learns something false about six shipments that worked.

    python ci/check_the_ship_verifies_content_and_names_only_what_failed.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SHIP = ROOT / "deploy" / "ship.sh"

#: RESOLVING CONTENT means asking the node's content store what a digest points at — and the
#: resolver may live in its own function, so the evidence is in three parts: the script defines
#: one, it reads the content store, and verify_running CALLS it. A resolver nothing calls would
#: satisfy a looser check and leave the proof comparing names, which is this defect wearing the
#: fix's clothes.
RESOLVER_DEFINED = re.compile(r"^resolve_config\(\) \{", re.M)
#: THE CONTENT STORE, whether the call is written as a shell line or as an argv list — the
#: resolver grew from one hop to two and moved into python on the node, and a pattern that only
#: knew the shell spelling went red over a better fix.
CONTENT_STORE_READ = re.compile(r"content get|'content',\s*'get'")
VERIFY_CALLS_RESOLVER = re.compile(r"resolve_config\s")

#: THE SUMMARY MUST NAME A COLLECTED SET, not the raw argument list. `$*` is every service the
#: operator asked for, which is exactly the wrong list after a partial failure.
#:
#: THE ONE PLACE `$*` STAYS RIGHT is a failure before any rollout — publish died, nothing was
#: attributed to a service, and naming them all is then the truth. So what is forbidden is the
#: BARE line, closing straight after `$*`; a qualified one is allowed to say why.
NAMES_ALL_ARGUMENTS = re.compile(r'did not ship: \$\*"')
COLLECTS_FAILURES = re.compile(r'\$\{FAILED\[\*\]\}')


def _function_body(source: str, name: str) -> str:
    """The lines of one shell function, by brace depth — nested `{ }` included."""
    start = source.find(f"{name}() {{")
    if start < 0:
        return ""
    depth, i = 0, source.index("{", start)
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
        i += 1
    return source[start:]


def main() -> int:
    if not SHIP.is_file():
        print("deploy/ship.sh is missing — «cannot find the ship» is not a pass")
        return 1

    source = SHIP.read_text(encoding="utf-8")
    verify = _function_body(source, "verify_running")
    if not verify:
        # THE FUNCTION IS GONE OR RENAMED. Silence here would mean this gate quietly stopped
        # checking the proof, which is the one thing a gate over a proof may never do.
        print("  \033[31m✘ ship.sh has no verify_running — point this gate at what replaced "
              "it\033[0m")
        return 1

    problems: list[str] = []
    resolves = (RESOLVER_DEFINED.search(source) and CONTENT_STORE_READ.search(source)
                and VERIFY_CALLS_RESOLVER.search(verify))
    if not resolves:
        problems.append(
            "verify_running compares names, not content: it never resolves the pinned digest to "
            "the\n      manifest or config the node runs. A multi-arch pin and an imageID are two "
            "different\n      kinds of name, and comparing them fails a shipment that worked.")

    # THE SUMMARY, READ OUTSIDE ANY FUNCTION — the closing lines of the script.
    if NAMES_ALL_ARGUMENTS.search(source) or not COLLECTS_FAILURES.search(source):
        problems.append(
            "the closing summary prints the whole argument list after a partial failure, so six\n"
            "      shipments that verified green are named as failures by the last line anybody "
            "reads.")

    if problems:
        print("  \033[31m✘ the ship's proof does not say what it knows:\033[0m")
        for problem in problems:
            print(f"      \033[31m{problem}\033[0m")
        print("\n    A proof that cries wolf gets muted, and the next real drift ships behind it. "
              "Do not\n    exempt it here.")
        return 1

    print("  \033[32m✔ the ship verifies content and names only what failed\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
