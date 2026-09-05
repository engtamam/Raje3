"""A rule fed by a field that nothing writes is not a cautious rule — it is an absent one.

WHY THIS EXISTS. `ladder.is_locked(first_rung_returns)` stops offering a discount to a customer who
already comes back on the first reminder alone (spec 5.6.1). It was written, tested, and read the
count off the learning row. Nothing in production ever incremented it — the only writers were the
tests that proved the lock works. So the field was 0 for every customer for ever, the lock never
engaged once, and the shop paid the loyal exactly what it paid the lapsed. The unit tests were
green the entire time, because they wrote the field themselves.

THIS IS THE SILENT-SUCCESS FAMILY, in its quietest form. A dead engine is noticeable — nothing
happens. A field nobody writes produces a DEFAULT, and a default behaves: the code runs, returns an
answer, and the answer is the same one it would give if the feature had never been built.

WHAT IT CHECKS. Every `<name>.get("field")` read in a service's `app/` must have a matching write
in that same service's `app/` — a `x["field"] = ...` assignment or a `"field": ...` entry in a dict
literal. Tests do not count as writers, deliberately: a field whose only writer is a test is the
exact defect.

WHAT IT CANNOT SEE, said plainly:
  · a field written by a PEER and read here — those cross a network boundary and are declared in
    FROM_A_PEER with the name of the writer;
  · a field written through `row.update(...)` or `**kwargs`;
  · a field read via `[...]` subscript rather than `.get`.
Those are blind spots, not passes. When one bites, it is added here as a check, not an exception.

    python ci/check_unwritten_fields.py
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVICES = ROOT / "services"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# Fields that arrive from OUTSIDE this service — a peer's payload, a platform row, an event. Each
# entry names who writes it, because «it comes from somewhere else» is a claim that has to be
# checkable by the next reader.
FROM_A_PEER: dict[str, str] = {
    # Meta's own webhook payload shape — reminders/rating_reply.py and whatsapp-assistant/
    # inbound_parse.py read a customer's raw inbound WhatsApp message, which this product never
    # constructs itself (notification-service forwards Meta's JSON verbatim onto the bus).
    "nfm_reply": "Meta's WhatsApp webhook — a Flow reply, forwarded verbatim onto the bus",
    "response_json": "Meta's WhatsApp webhook — the Flow's own completion payload, inside nfm_reply",
    "button_reply": "Meta's WhatsApp webhook — a template button tap, forwarded verbatim onto the bus",
    "list_reply": "Meta's WhatsApp webhook — an interactive-list selection, forwarded verbatim",
    "geometry": "Google Places API's own response shape (lead_sourcing.py's search step)",
    "formatted_phone_number": "Google Places API's own response shape (lead_sourcing.py's details step)",
}

# DELIBERATELY UNFED, AND FAILING CLOSED. Not every unwritten field is a defect: one may be a
# placeholder for data we do not hold yet, where the code chooses the SAFE answer rather than the
# convenient one. The distinction is not «somebody wrote a comment» — it is that the unfed value
# makes the feature reach NOBODY rather than everybody. Each entry says which.
NOT_YET_HELD: dict[str, str] = {
    "occasion_today": "campaigns' «occasion» goal — we hold no birthdays. audience.py returns "
                      "False for every customer rather than True, so the campaign reaches nobody "
                      "and the owner sees a reach of 0 before he sends. Reaching EVERYONE under a "
                      "name that promises a personal occasion is the failure this avoids.",
    "quantities": "insights' group-basket detector (task 105) has two signals: «more than one of "
                  "the same service» and «basket much larger than this shop's median». Only the "
                  "second runs — the visit row operations stores carries `service_ids` as a SET "
                  "and no per-line quantity, so `quantities` arrives empty from every visit. The "
                  "detector then under-claims rather than over-claims: a family of three cars is "
                  "still caught by size, and a basket wrongly called personal only costs us a "
                  "pair we do not suggest. Carrying quantity through the visit record is task 301.",
}


def _reads_and_writes(path: pathlib.Path) -> tuple[set[str], set[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return set(), set()
    reads: set[str] = set()
    writes: set[str] = set()
    for node in ast.walk(tree):
        # x.get("field")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and node.args \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            reads.add(node.args[0].value)
        # x["field"] = ...
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Subscript) and isinstance(tgt.slice, ast.Constant) \
                        and isinstance(tgt.slice.value, str):
                    writes.add(tgt.slice.value)
        # {"field": ...}
        elif isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    writes.add(k.value)
        # A DECLARED RECORD FIELD IS A WRITE: `fired_by: str = "system"` on a dataclass, or
        # `product_id: str = Field(...)` on a pydantic model. The value comes to rest in an object
        # this codebase defines, which is the same thing a row assignment does.
        #
        # CLASS BODIES ONLY, NEVER FUNCTION PARAMETERS — and that line is the whole difficulty.
        # `ladder.build(*, first_rung_returns: int = 0)` declares a parameter with a default, and
        # counting it would say the field is fed when the default is precisely the problem.
        elif isinstance(node, (ast.ClassDef,)):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    writes.add(stmt.target.id)
        # A KEYWORD ARGUMENT IS NOT A WRITE, and counting it as one made this gate useless against
        # the very defect it was written for. `L.build(first_rung_returns=rule.get(...))` FORWARDS
        # the value it just read — the whole chain is reads, and the field is still fed by nothing.
        # The first version counted it, ran green on the unfixed code, and would have shipped as a
        # gate that proves nothing. A write is a value coming to REST somewhere: an assignment into
        # a row, or a key in a literal that gets stored.
    return reads, writes


def main() -> int:
    problems: list[str] = []
    checked = 0

    # WHO ELSE IN THE FLEET WRITES THIS FIELD — computed, never hand-listed.
    #
    # A field read here and written by `operations` is a payload crossing a boundary, and that is
    # normal. An allow-list would say the same thing, but it would say it once and then rot: the day
    # the peer stops writing the field, the entry keeps vouching for it. Deriving the answer means
    # the gate re-checks the claim on every run, and a peer that drops a field is caught by the same
    # code that permits it.
    # AND THE PLATFORM IS PART OF THE FLEET. identity-service writes `invite_token`, billing writes
    # `limits_snapshot` — fields that arrive here fully formed. Scanning only our own services would
    # report every one of them, which is how a gate earns its reputation for crying wolf.
    fleet: dict[str, set[str]] = {}
    roots = [p for p in SERVICES.iterdir() if (p / "app").is_dir()]
    platform_services = ROOT / "platform" / "services"
    if platform_services.is_dir():
        roots += [p for p in platform_services.iterdir() if (p / "app").is_dir()]
    for other in sorted(roots):
        for path in (other / "app").rglob("*.py"):
            for field in _reads_and_writes(path)[1]:
                fleet.setdefault(field, set()).add(other.name)

    for service in sorted(p for p in SERVICES.iterdir() if (p / "app").is_dir()):
        # READS FROM THE DECISION LAYER ONLY. `api/` reads headers and JWT claims, `adapters/`
        # reads whatever a peer sent, and a router decorator is literally `router.get("/health")` —
        # none of those are a rule feeding on a stored field, and a gate that reports them is one
        # people learn to skip (the first version of this file reported 246 of them).
        reads: dict[str, str] = {}
        writes: set[str] = set()
        for path in sorted((service / "app").rglob("*.py")):
            r, w = _reads_and_writes(path)
            writes |= w
            if "core" not in path.relative_to(service / "app").parts:
                continue
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            for field in r:
                reads.setdefault(field, rel)

        # AND THE TELL IS THE TEST. A field whose ONLY writer is a test is the exact defect: the
        # suite proves the rule works by feeding it by hand, and production never does. A field
        # nobody writes anywhere is usually a peer's payload; a field only the tests write is a
        # rule that has never once fired.
        test_writes: set[str] = set()
        for path in sorted((service / "tests").rglob("*.py")) if (service / "tests").is_dir() else []:
            test_writes |= _reads_and_writes(path)[1]

        for field, where in sorted(reads.items()):
            checked += 1
            if field in writes or field in FROM_A_PEER or field in NOT_YET_HELD \
                    or field not in test_writes:
                continue
            if fleet.get(field, set()) - {service.name}:
                continue    # a peer writes it; it crosses a boundary rather than going unwritten
            problems.append(f"{service.name}: «{field}» is read at {where}, written by the tests, "
                            f"and written nowhere in app/ — the rule has never once fired")

    if problems:
        print(f"{C_R}  ✘ {len(problems)} field(s) that a decision reads and nothing writes:{C_N}")
        for line in problems:
            print(f"{C_R}      {line}{C_N}")
        print(f"{C_R}    Write it where it is earned, or declare its writer in FROM_A_PEER. A "
              f"field nobody writes returns a DEFAULT, and a default behaves.{C_N}")
        return 1

    print(f"{C_G}  ✔ every field a decision reads is written by something other than a test "
          f"({checked} fields){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
