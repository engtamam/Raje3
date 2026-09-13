"""The library, against Meta's documented template rules — before anything is submitted.

WHY THIS RUNS BEFORE FIRST CONTACT AND NOT AFTER IT.

A template name cannot be reused with different content, and cannot be renamed once approved. So a
rejection does not cost a retry — it burns the name. With three tones per text, one bad rule costs
twenty-four names per tone, and the replacement names are worse than the originals for ever
(`svc_service_reminder_v2`, and then `_v3`).

The rejection also does not arrive at submission time. The API accepts the payload and a human
reviews it hours later, so the feedback loop that would normally teach us is a day long and
destroys inventory on every turn.

Every rule below is from Meta's own documentation, not inferred from the platform's adapter — the
adapter is not the contract (playbook 4.32). Each one carries the failure it prevents.

WHAT THIS CANNOT DO is tell us whether a reviewer will judge the content acceptable. It checks the
mechanical rules, which are the ones that are worth catching for free.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
#: THE FILE THAT IS ACTUALLY SUBMITTED — `library.register`, run the moment a shop connects, reads
#: this one. `SPEC` below (parsed fresh, no stored intermediate file since 2026-09-13) is what the
#: manual seeder script (`deploy/seed/seed-templates.sh --emit`) builds its own submissions from.
#: The gate used to check only the generated file, so it stayed green while all 66 live rows went
#: to Meta with an empty example list: refused on arrival, «connected» in green, every send «under
#: review» for ever.
LIVE = ROOT / "services" / "operations" / "data" / "templates.seed.json"

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_templates import build, parse  # noqa: E402

# Lowercase letters, digits and underscores only, up to 512 characters. Anything else is refused at
# creation — the one class of failure that IS immediate.
NAME_RE = re.compile(r"^[a-z0-9_]{1,512}$")

# Meta's component limits.
BODY_MAX = 1024
HEADER_MAX = 60
FOOTER_MAX = 60

CATEGORIES = {"MARKETING", "UTILITY", "AUTHENTICATION"}

VAR = re.compile(r"\{\{(\d+)\}\}")


def check(t: dict) -> list[str]:
    problems: list[str] = []
    name = str(t.get("name") or "")
    body = str(t.get("body") or "")

    if not NAME_RE.match(name):
        problems.append(f"name {name!r} is not lowercase alphanumeric-and-underscore within 512 "
                        f"characters — refused at creation")

    if len(body) > BODY_MAX:
        problems.append(f"body is {len(body)} characters, over Meta's {BODY_MAX}")
    if len(str(t.get("header") or "")) > HEADER_MAX:
        problems.append(f"header is over {HEADER_MAX} characters")
    if len(str(t.get("footer") or "")) > FOOTER_MAX:
        problems.append(f"footer is over {FOOTER_MAX} characters")

    category = str(t.get("category") or "").upper()
    if category not in CATEGORIES:
        problems.append(f"category {category!r} is not one of {sorted(CATEGORIES)}")

    nums = [int(n) for n in VAR.findall(body)]

    # NUMBERED FROM 1 WITH NO GAP. gen_templates.py already checks this against the specification;
    # it is repeated here against the SEED, because the seed is what is actually submitted and the
    # two could drift.
    if nums and sorted(set(nums)) != list(range(1, len(set(nums)) + 1)):
        problems.append(f"variables {sorted(set(nums))} are not numbered 1..n without a gap")

    # AN EXAMPLE FOR EVERY PARAMETER. Meta: "you must include an example value for each parameter."
    # A template with a placeholder and no example is refused.
    examples = list(t.get("examples") or [])
    if len(set(nums)) != len(examples):
        problems.append(f"{len(set(nums))} variable(s) but {len(examples)} example(s) — Meta "
                        f"requires one example value per parameter")

    # AND A NAME IS NOT AN EXAMPLE. Their review rejects placeholder-looking example values, and
    # this is the exact mistake we shipped for a day when the port grew a second list.
    variables = list(t.get("variables") or [])
    for i, (var, ex) in enumerate(zip(variables, examples), 1):
        if var == ex:
            problems.append(f"variable {i}: the example is the parameter NAME ({var!r})")

    # THE BODY MAY NOT BEGIN OR END WITH A PARAMETER. Meta rejects both — a message that opens with
    # a substituted value reads as spam to their reviewer, and one that ends with it looks
    # truncated.
    stripped = body.strip()
    if stripped.startswith("{{"):
        problems.append("the body BEGINS with a variable — Meta rejects this")
    if stripped.endswith("}}"):
        problems.append("the body ENDS with a variable — Meta rejects this")

    # AND TWO PARAMETERS MAY NOT BE ADJACENT. `{{1}} {{2}}` with only whitespace between them is
    # refused: there is no text for a reviewer to judge the message by.
    if re.search(r"\}\}\s*\{\{", body):
        problems.append("two variables are adjacent with only whitespace between them — refused")

    return problems


#: The two blanks that carry an ADDRESS. Named and exampled by what they ARE rather than by where
#: they sit, because they sit somewhere different in every text. Kept equal to the seeder's own
#: table by `ci/check_who_fills_a_blank_is_one_vocabulary.py` naming the same sources.
# A BLANK IS NAMED BY WHAT FILLS IT, AND THE POSITION TABLE IS THE FALLBACK — not the rule.
#
# This started as two entries for the two address slots, with everything else read out of
# `variables` by POSITION. That was already wrong and nobody could see it: `mkt_offer` slot 3 is a
# discount amount and position 3 is called «الخدمة», so Meta's reviewer received a variable named
# «service» whose example was «قص شعر» sitting where «20%» goes. The reviewer approves the
# WORDS, and we were describing them inaccurately.
#
# It became visible only when an offer grew a seventh blank and the position table — which stops
# at five — raised KeyError. The crash was the honest failure; the silent one had been running for
# months.
FILL_SLOTS = {
    "invite": {"name": "invite_line",
               "example": "تحب توصلك عروضنا على واتساب؟ فعّلها من هنا: https://my.raje3.sa/p/nakheel.sub_rj7k2m/allow"},
    "stop_link": {"name": "stop_link",
                  "example": "https://my.raje3.sa/p/nakheel.sub_rj7k2m/stop"},
    "amount": {"name": "offer_value", "example": "20%"},
    "code": {"name": "coupon_code", "example": "RJ-7K2M"},
    "date": {"name": "expires_on", "example": "12 سبتمبر"},
    "catalogue": {"name": "service", "example": "قص شعر"},
    "owner": {"name": "owner_line", "example": "افتتحنا فرعنا الجديد في حي الياسمين"},
}


def expand(lib: dict) -> list[dict]:
    """The 72 submissions, built the way deploy/seed/seed-templates.sh builds them.

    EXPANDED HERE RATHER THAN READ AS STORED, because the seed holds 24 texts x 3 tones and what
    Meta receives is 72 rows. Checking the stored shape would check something nobody submits — and
    building it the same way cross-checks the seeder's own expansion, which is where the name and
    the variable order are decided.
    """
    out: list[dict] = []
    variables = lib["variables"]
    for ty in lib.get("types") or []:
        fills = list(ty.get("fills") or [])
        for tone, text in (ty.get("tones") or {}).items():
            used = sorted({int(n) for n in VAR.findall(text)})
            # THE ADDRESS SLOT IS NAMED BY ITS FILL, NOT BY ITS POSITION — the same rule
            # deploy/seed/seed-templates.sh follows, and for the same reason: the last blank is the
            # invitation on a utility text and the one-tap stop on a marketing one, and it lands on
            # slot 3 in a visit confirmation and slot 6 in an offer. Keyed by number alone this
            # raised a KeyError on '6' — which is the honest failure; the quiet one would have been
            # submitting «الخدمة / قص شعر» to Meta's reviewer where a link belongs.
            by_pos = {n: (fills[i] if i < len(fills) else "") for i, n in enumerate(used)}
            names, examples = [], []
            for i in used:
                slot = FILL_SLOTS.get(by_pos.get(i, ""))
                names.append(slot["name"] if slot else variables[str(i)]["name"])
                examples.append(slot["example"] if slot else variables[str(i)]["example"])
            out.append({
                "name": ty["name"] + "_" + tone,
                "language": "ar",            # Arabic only today; English is a second row, later
                "category": ty["category"],
                "body": text,
                "header": ty.get("header", ""),
                "variables": names,
                "examples": examples,
            })
    return out


def live_rows() -> list[dict]:
    """The library as `library.register` submits it — examples resolved off `variable_examples`,
    exactly as `library.examples_for` resolves them. Checked here so a row that Meta would refuse
    fails in CI rather than at 66 shops on their first morning."""
    lib = json.loads(LIVE.read_text(encoding="utf-8"))
    by_number = lib.get("variable_examples") or {}
    out: list[dict] = []
    for row in lib.get("templates") or []:
        used = list(row.get("variables") or [])
        # THE ROW'S OWN EXAMPLES FIRST, EXACTLY AS `library.examples_for` PREFERS THEM. This read
        # the by-number table alone, and that table stops at six because it was written when the
        # longest wording had six blanks — so an offer that grew a coupon blank arrived at Meta
        # with seven placeholders and six examples, which Meta refuses outright. Reading it the way
        # the shipping code reads it is the only way this check answers the question it prints.
        explicit = [str(e).strip() for e in (row.get("examples") or []) if str(e).strip()]
        examples = explicit if len(explicit) == len(used) else [
            e for e in (str(by_number.get(str(n), "")).strip() for n in used) if e]
        out.append({**row,
                    "variables": [f"var_{n}" for n in used],
                    "examples": examples})
    return out


def main() -> int:
    if not LIVE.exists():
        print(f"[31m  x {LIVE} is missing[0m")
        return 1
    types, problems = parse()
    if problems:
        print(f"[31m  x the specification itself has {len(problems)} problem(s) - run: python ci/gen_templates.py[0m")
        return 1
    lib = build(types)
    templates = expand(lib)
    if not templates:
        print("[31m  x the seed carries no templates[0m")
        return 1

    problems: list[str] = []
    # ONE PASS PER SOURCE, AND THE UNIQUENESS SET IS PER SOURCE TOO. Both files describe the SAME
    # 66 templates — the generated one for the manual seeder, the live one that `library.register`
    # submits when a shop connects — so a shared `seen` set would report every row as «defined
    # twice» and say nothing true. Every OTHER rule applies to both, because Meta applies it to
    # whichever of the two actually reaches it.
    checked = 0
    for label, rows in (("generated", templates), ("live", live_rows())):
        seen: set = set()
        checked += len(rows)
        for t in rows:
            name, lang = t["name"], t["language"]
            # UNIQUE PER (name, language). A duplicate is not two templates: the second submission
            # EDITS the first, and editing an approved template re-opens it for review.
            if (name, lang) in seen:
                problems.append(f"[{label}] {name} [{lang}]: defined twice - the second submission "
                                "would EDIT the first and re-open it for review")
            seen.add((name, lang))
            for pr in check(t):
                problems.append(f"[{label}] {name}: {pr}")

    for p in problems:
        print(f"\033[31m  x {p}\033[0m")
    if problems:
        print(f"\n\033[31m  x {len(problems)} problem(s) — every one is a name burned on "
              f"submission\033[0m")
        return 1
    print(f"\033[32m  ok {checked} templates pass Meta's documented rules "
          f"({len(templates)} generated + {len(live_rows())} live)\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())
