#!/usr/bin/env python3
"""The legal documents are complete before anybody can publish them.

WHY THIS EXISTS RATHER THAN TRUSTING THE PLATFORM'S OWN GUARD. compliance-service refuses to publish
a document with an unfilled `{{TOKEN}}` — a real and correct check. But the PDPL pack writes its
annexes with SINGLE brackets: `[PURPOSE]`, `[CATEGORIES]`, `[DURATION]`, `[NAME]`. The publish guard
scans for `{{...}}` and nothing else, so a Data Processing Agreement whose Annex A is entirely empty
publishes cleanly and reads as executed.

That is not a small gap. Annex A is Article 17-1 (a, b, c, g) itself — the purpose, the categories,
the duration and the sub-processors. An agreement missing them satisfies none of the four, and it is
the annexes rather than the clauses that decide, under Article 17-4, whether something we did was
instructed or was our own purpose.

Reported upstream. Guarded here in the meantime, because a control that depends on somebody else's
release is not a control we hold.

WHAT IT CHECKS, IN THE ORDER A FAILURE MATTERS:

  1. every {{TOKEN}} the document uses has a value in our file, and no value is an empty string
     that would render as a blank where a party's name belongs;
  2. no [SQUARE_BRACKET] placeholder survives anywhere in what we supply;
  3. exactly ONE document gates a subscription — two would make a shop sign twice for one
     engagement, none would leave nothing signed, and every document says which of the four it is:
     public (read, never signed) · accept (gates) · internal (produced on request) · reference;
  4. the two agreements carry the same VERSION, because they describe one engagement and a shop
     bound to v1.0 of one and v1.1 of the other is bound to two different sets of instructions;
  5. the annexes are sourced from one file rather than written twice.

DELIBERATELY BLANK VALUES ARE ALLOWED TO STAY BLANK — and are reported as WAITING rather than as
failing. The registered company name and the effective date are facts we do not yet hold, and
inventing them is the one failure worse than an unpublished document. The build stays green and
tells you what is still outstanding; publishing is what must not happen while they are empty.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OURS = ROOT / "deploy" / "seed" / "legal"
PACK = ROOT / "platform" / "services" / "compliance-service" / "app" / "data" / "pdpl-templates"

# Which of our files fills which template in the pack.
DOCS = {
    "terms.yaml": "",           # ours entirely — the PDPL pack has no service contract
    "affiliate-agreement.yaml": "",  # ours entirely — gates a different engagement (see rule 3)
    "affiliate-privacy-policy.yaml": "",  # ours entirely — public disclosure, no PDPL template fills it
    "processor-dpa.yaml": "doc14_processor_dpa.yaml",
    "processing-agreement.yaml": "doc13_processing_agreement.yaml",
    "ropa.yaml": "doc04_ropa.yaml",
    "data-subject-rights.yaml": "doc03_data_subject_rights.yaml",
    "privacy-policy.yaml": "doc01_privacy_policy.yaml",
    "dpia.yaml": "doc10_dpia.yaml",
    "cookies.yaml": "doc12_cookies.yaml",
}

# Values we know we do not have yet. Blank is honest for these and only for these; anything else
# blank is an oversight, and the difference is what keeps this check meaningful.
AWAITED = {"COMPANY_NAME", "PROCESSOR_NAME", "EFFECTIVE_DATE", "COMPANY_ADDRESS", "COMPANY_PHONE",
           "PRIVACY_EMAIL", "DPO_EMAIL", "DPO_PHONE", "COMPLAINT_CONTACT"}

TOKEN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
BRACKET = re.compile(r"\[([A-Z][A-Z0-9_/]{2,})\]")

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"
problems: list[str] = []
waiting: list[str] = []


def values_of(text: str) -> dict[str, str]:
    """The `values:` block, read without a YAML dependency — key: "value" at two-space indent.

    Deliberately shallow: this reads the flat scalar values, which is exactly the set the
    `{{TOKEN}}` substitution can consume. A nested value (a bilingual name, say) is a value that IS
    supplied, so it counts as present without needing to be parsed.
    """
    out: dict[str, str] = {}
    inside = False
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("values:"):
            inside = True
            continue
        if inside and line and not line.startswith((" ", "\t")):
            break
        if not inside or line.lstrip().startswith("#"):
            continue
        m = re.match(r'^  ([A-Z][A-Z0-9_]*):\s*(.*)$', line)
        if not m:
            continue
        key, rest = m.group(1), m.group(2).strip().strip('"').strip("'")
        # A KEY WITH NOTHING AFTER IT IS NOT AN EMPTY VALUE — it is the head of a block: a folded
        # scalar (`>-`) or a bilingual mapping on the lines below. Reading it as blank was this
        # check's own first bug, and it reported a fully written privacy policy as thirteen holes.
        if rest in ("", ">-", "|", ">", "|-"):
            nxt = next((ln for ln in lines[i + 1:]
                        if ln.strip() and not ln.lstrip().startswith("#")), "")
            rest = "<block>" if (len(nxt) - len(nxt.lstrip())) > 2 else ""
        out[key] = rest
    return out


for ours_name, pack_name in sorted(DOCS.items()):
    ours = OURS / ours_name
    pack = PACK / pack_name
    if not ours.exists():
        problems.append(f"{ours_name}: missing — the template exists and nothing fills it")
        continue
    text = ours.read_text(encoding="utf-8")
    # COMMENTS ARE NOT CONTENT. This file explains the bracket problem by naming it, and a check
    # that failed on its own explanation would teach us to stop explaining things.
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    vals = values_of(text)

    # 1 — every token the TEMPLATE uses is answered by us.
    if not pack_name:
        needed = set()          # a document of our own: nothing upstream declares its tokens
    if pack_name and pack.exists():
        needed = set(TOKEN.findall(pack.read_text(encoding="utf-8")))
        # CONTROLLER_NAME is answered by reference rather than by a scalar; a nested value counts.
        for tok in sorted(needed):
            if tok in vals or f"  {tok}:" in text:
                if tok in vals and not vals[tok]:
                    (waiting if tok in AWAITED else problems).append(
                        f"{ours_name}: {tok} is blank"
                        + ("" if tok in AWAITED else " — and is not a value we are waiting on"))
                continue
            problems.append(f"{ours_name}: the template uses {{{{{tok}}}}} and we supply no value")
    elif pack_name:
        problems.append(f"{ours_name}: names {pack_name}, which is not in the pack")

    # 2 — no square-bracket placeholder survives in OUR text. This is the check their guard cannot
    # make, and the annexes are where it bites.
    for stray in sorted(set(BRACKET.findall(body))):
        problems.append(f"{ours_name}: [{stray}] left unfilled — the publish guard does not see it")

# 3 — exactly one document gates EACH engagement.
#
# WHY THIS IS A CHECK AND NOT A CONVENTION. Acceptance is what makes the agreement binding, and the
# gate is default-deny: every document marked for acceptance must be accepted before the party it
# binds may proceed. Mark a second one for the SAME party and it is stopped at a screen asking it
# to accept two papers for one engagement — which is the drift we merged doc13 away to avoid,
# arriving by a different road. Mark none and nothing is ever signed.
#
# TWO PARTIES, TWO ENGAGEMENTS, EACH WITH ITS OWN GATE. A shop accepting terms.yaml and a marketer
# accepting affiliate-agreement.yaml are not the same signature required twice — they are different
# people entering different relationships with us, and `Application.agreed_terms_version` on the
# affiliate side is its own field for exactly that reason. So a document declares WHICH engagement
# it gates with `gates: <engagement>`; documents silent on it default to `shop`, which is every
# document this check knew about before the affiliate agreement existed. The invariant is still
# "exactly one accept per engagement" — it is just no longer assumed there is only one engagement.
modes: dict[str, str] = {}
gates_of: dict[str, str] = {}
for name in DOCS:
    f = OURS / name
    if f.exists():
        text = f.read_text(encoding="utf-8")
        m = re.search(r"^publication:\s*(\w+)", text, re.M)
        modes[name] = m.group(1) if m else ""
        g = re.search(r"^gates:\s*(\w+)", text, re.M)
        gates_of[name] = g.group(1) if g else "shop"
missing_mode = [n for n, m in modes.items() if not m]
if missing_mode:
    problems.append(f"no publication mode declared for {', '.join(sorted(missing_mode))} — "
                    f"whether a document is published, gated or internal is not a detail to infer")
# `annex` is bound by the acceptance of the master agreement rather than by one of its own — which
# is why it does not count here and must not be marked `accept`.
gated_by_engagement: dict[str, list[str]] = {}
for n, m in modes.items():
    if m == "accept":
        gated_by_engagement.setdefault(gates_of[n], []).append(n)
for engagement, names in sorted(gated_by_engagement.items()):
    if len(names) != 1:
        problems.append(
            f"{len(names)} document(s) marked `accept` for the {engagement} engagement "
            f"({', '.join(sorted(names))}) — exactly one agreement gates it; two would make that "
            f"party sign twice for one engagement")
if not gated_by_engagement:
    problems.append("no document marked `accept` for any engagement — nothing is ever signed")

# 4 — the two faces of one engagement move together.
try:
    a = values_of((OURS / "processor-dpa.yaml").read_text(encoding="utf-8")).get("VERSION")
    b = values_of((OURS / "processing-agreement.yaml").read_text(encoding="utf-8")).get("VERSION")
    if a != b:
        problems.append(
            f"the two processing agreements are at different versions ({a} vs {b}) — they describe "
            f"ONE engagement, so a shop would be bound to two different sets of instructions")
except OSError as exc:
    # A MISSING FILE IS THE FAILURE, NOT A REASON TO SKIP. This was `except OSError: pass`, so
    # deleting `processor-dpa.yaml` made the check vanish and the gate print «the two agreements
    # are in step» — a positive claim about a document that did not exist. The one thing worse
    # than an unchecked file is a green line asserting it was checked.
    problems.append(f"a processing agreement could not be read ({exc}) — this check makes a claim "
                    f"about both documents and cannot make it about a file that is not there")

# 5 — the annexes have one source.
try:
    mirror = (OURS / "processing-agreement.yaml").read_text(encoding="utf-8")
    if "annexes_from:" not in mirror:
        problems.append("processing-agreement.yaml no longer sources its annexes from the DPA — "
                        "two copies of Annex A will drift, and the difference is what a dispute "
                        "turns on")
except OSError as exc:
    problems.append(f"processing-agreement.yaml could not be read ({exc}) — the annex-sourcing "
                    f"rule cannot be confirmed, and unconfirmed is not satisfied")

for w in waiting:
    print(f"  {C_Y}…{C_N} {w}")
if problems:
    print(f"{C_R}  ✗ {len(problems)} legal document problem(s):{C_N}")
    for p in problems:
        print(f"    {C_R}{p}{C_N}")
    sys.exit(1)
print(f"{C_G}  ✔ legal documents are complete — every token answered, no bracket left unfilled, "
      f"the two agreements in step, annexes from one source{C_N}"
      + (f"\n  {C_Y}({len(waiting)} value(s) awaited before publishing){C_N}" if waiting else ""))
