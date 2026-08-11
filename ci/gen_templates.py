#!/usr/bin/env python3
# =============================================================================
# gen_templates.py — build deploy/seed/templates.json FROM THE SPECIFICATION.
#
# The library is not typed here. Every word of it lives in docs/وصف-منصة-راجع.md §8.4.1, and this
# reads it. A second copy typed by hand drifts from the wording that was reviewed — and the copy
# that drifts is the one Meta approved, so the message a customer receives stops being the message
# anybody agreed to.
#
# Run it after editing the spec:   python ci/gen_templates.py
# Check it in CI without writing:  python ci/gen_templates.py --check
#
# THE CHECKS ARE THE POINT, not the generation. Each one is a rejection that would otherwise arrive
# from Meta hours later, against a template name that is then burned — a name cannot be reused with
# different content and cannot be changed after approval.
# =============================================================================
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "docs" / "وصف-منصة-راجع.md"
OUT = ROOT / "deploy" / "seed" / "templates.json"

CLASS = {"svc": "service", "per": "personal", "awr": "awareness",
         "wrn": "warning", "mkt": "marketing"}
# Meta's category decides the PRICE and the odds of acceptance. Getting it wrong means they
# re-categorise and bill at the marketing rate (spec §8.5).
CATEGORY = {"service": "UTILITY", "personal": "UTILITY", "awareness": "UTILITY",
            "warning": "UTILITY", "marketing": "MARKETING"}
TONES = ("brief", "warm", "formal")

# An awareness or warning template carrying any of these is not awareness — it is marketing by its
# text, whatever it is labelled (spec §8.4.1). Meta re-categorises it and bills accordingly, and
# the establishment is then sending promotion under a utility consent.
SELLING_WORDS = ("خصم", "عرض", "ريال", "مجاناً", "مجانا", "اشترِ", "اشتري", "احجز", "زُرنا",
                 "زرنا", "سعر", "تخفيض")

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _vars(text: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", text)})


DEFERRALS = ("drop", "defer", "priority")


def deferral_map(doc: str) -> dict[str, str]:
    """The policy per type, read from the table in the specification (§8.4.3).

    WHY IT IS PARSED AND NOT LISTED HERE. A policy in this file is a policy nobody reviewing the
    product ever sees, and the question it answers — "does this message still make sense tomorrow?"
    — is about the TEXT, not about the engine. It belongs where the texts are argued over.

    THE ROWS ARE PATTERNS, not only names, because ten marketing templates share one answer and
    ten identical rows is ten chances to get one wrong.
    """
    out: dict[str, str] = {}
    block = doc.split("## 8.4.3", 1)
    if len(block) < 2:
        return out
    block = block[1].split("## 8.5", 1)[0]
    for line in block.splitlines():
        if not line.startswith("|") or "`" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        policy = cells[1].strip(" `*")
        if policy not in DEFERRALS:
            continue
        for name in re.findall(r"`([a-z_*]+)`", cells[0]):
            out[name] = policy
    return out


def deferral_for(name: str, policies: dict[str, str]) -> str | None:
    if name in policies:
        return policies[name]
    for pattern, policy in policies.items():
        if pattern.endswith("*") and name.startswith(pattern[:-1]):
            return policy
    return None


def parse() -> tuple[list[dict], list[str]]:
    doc = SPEC.read_text(encoding="utf-8").replace("\r\n", "\n")
    blocks = re.findall(
        r"\*\*`((?:svc|per|awr|wrn|mkt)_[a-z_]+)`\s*—\s*([^*\n]+)\*\*\n(.*?)(?=\n\*\*`|\n---|\n## )",
        doc, re.S)

    policies = deferral_map(doc)
    types: list[dict] = []
    problems: list[str] = []
    seen: set[str] = set()

    for name, title, body in blocks:
        tones = dict(re.findall(r"\|\s*`_(brief|warm|formal)`\s*\|\s*(.+?)\s*\|", body))
        if len(tones) != 3:
            problems.append(f"{name}: has {sorted(tones)} — every text needs all three tones, "
                            f"because the tone is a live switch and a missing one is a message "
                            f"that cannot be sent after he changes it")
            continue
        if name in seen:
            problems.append(f"{name}: defined twice — a name is frozen after approval, so two "
                            f"definitions is two different messages under one approved name")
            continue
        seen.add(name)

        cls = CLASS[name.split("_", 1)[0]]

        # ── the gaps Meta rejects, found here instead of hours later ───────────────────────────
        per_tone = {t: _vars(v) for t, v in tones.items()}
        for tone, v in per_tone.items():
            if v and v != list(range(1, len(v) + 1)):
                problems.append(f"{name}_{tone}: variables {v} have a gap — Meta numbers them and "
                                f"rejects the submission, hours later, against a burned name")
        if len({tuple(v) for v in per_tone.values()}) != 1:
            problems.append(f"{name}: the tones disagree on variables {per_tone} — the tone is a "
                            f"live switch, so changing it would leave a variable unfilled and "
                            f"Meta refuses an empty variable")

        # ── the category that has to be true rather than declared ──────────────────────────────
        if cls in ("awareness", "warning"):
            for tone, text in tones.items():
                hit = [w for w in SELLING_WORDS if w in text]
                if hit:
                    problems.append(f"{name}_{tone}: contains {hit} — an awareness template with "
                                    f"a price or an invitation is MARKETING by its text (§8.4.1), "
                                    f"and Meta will re-categorise and bill it as such")

        # NO TEMPLATE WITHOUT A POLICY. When the day's WhatsApp ceiling is exhausted the engine
        # has to decide whether this message is worth sending tomorrow, and there is no safe
        # default: deferring a visit confirmation sends something strange, dropping a follow-up
        # loses a message that cost nothing to delay. So whoever adds a text answers the question.
        deferral = deferral_for(name, policies)
        if deferral is None:
            problems.append(f"{name}: no deferral policy in the 8.4.3 table — when the ceiling "
                            f"runs out, is this message still worth sending tomorrow? There is no "
                            f"default that is right for both a visit confirmation and an offer")
            continue

        types.append({
            "name": name,
            "deferral": deferral,
            "title": title.strip(),
            "cls": cls,
            "category": CATEGORY[cls],
            # The warning class is the only one with a header (spec §8.4.1): a bold word above the
            # message earns its purpose — that he reads it — without spending a line of the body.
            "header": "تنبيه" if cls == "warning" else "",
            "tones": {t: tones[t] for t in TONES},
        })
    return types, problems


def check_variables(lib_vars: dict) -> list[str]:
    """A NAME IS NOT AN EXAMPLE, and Meta's review is where that is discovered otherwise.

    We shipped the example values in the names field for a day — correct against a port with one
    list, wrong the moment it became two. Nothing failed loudly: the API accepted it, and the
    rejection would have arrived from a human reviewer hours later, against 72 names that cannot
    then be reused or renamed.
    """
    problems: list[str] = []
    names = [v["name"] for v in lib_vars.values()]
    if len(set(names)) != len(names):
        problems.append(f"variables: two parameters share a name {names} — a send substitutes by "
                        f"name, so the second would overwrite the first")
    for num, v in lib_vars.items():
        if v["name"] == v["example"]:
            problems.append(f"variable {num}: the example IS the name ({v['name']!r}) — Meta's "
                            f"review rejects placeholder-looking examples")
        if not v["example"].strip():
            problems.append(f"variable {num}: no example — Meta refuses a template whose text "
                            f"carries a placeholder with no example value")
        if re.fullmatch(r"[a-z_]+", v["name"]) is None:
            problems.append(f"variable {num}: name {v['name']!r} is not a plain identifier")


    return problems


def build(types: list[dict]) -> dict:
    return {
        "_comment": [
            "GENERATED by ci/gen_templates.py from docs/وصف-منصة-راجع.md §8.4.1. Do not hand-edit:",
            "a library retyped by hand drifts from the wording that was reviewed and approved, and",
            "the drifted copy is the one a customer receives.",
            "",
            "AUTHORED ONCE, APPROVED PER ESTABLISHMENT (§6.6.1). A template at Meta belongs to one",
            "WhatsApp Business Account and every shop has its own — which is the whole basis of the",
            "promise that messages arrive under the shop's name and not ours. So this file is",
            "submitted in full to every account that connects.",
            "",
            "ALL OF THEM, not the twenty-four of one tone. The tone is in the NAME and a name",
            "cannot change after approval, so submitting a single tone makes a later change a",
            "second review the owner waits through. Submitting all makes it a switch.",
        ],
        # THREE THINGS PER NUMBER, AND THE LAST TWO ARE NOT THE SAME THING.
        #
        # `name` is the parameter's NAME — the key a send substitutes by, whose ORDER maps it to a
        # position, because Meta fills by position and does not name anything.
        #
        # `example` is an example VALUE, and Meta REQUIRES one for every parameter at creation: a
        # component whose text contains a placeholder is refused without it. Every text here has at
        # least one, so without examples not a single template can be created.
        #
        # AND A NAME IS NOT A VALID EXAMPLE. Meta's review rejects placeholder-looking examples, so
        # sending "customer_name" where "محمد" belongs fails review rather than the API — hours
        # later, against a name that cannot then be reused or renamed. We sent examples in the
        # name field for a day, which was correct against the older contract and wrong against this
        # one; the two are separate here so they cannot be confused again.
        #
        # `means` is for us. It never leaves this file.
        "variables": {
            "1": {"name": "customer_name", "example": "محمد",
                  "means": "the customer's name or its substitute — never empty; Meta rejects an "
                           "empty variable"},
            "2": {"name": "establishment", "example": "مغسلة النخيل",
                  "means": "the establishment's name — its identity, never ours"},
            "3": {"name": "service", "example": "غيار الزيت",
                  "means": "the service or the content"},
            "4": {"name": "detail", "example": "1234",
                  "means": "a second detail: a date, an amount, a transaction reference"},
            # THE FIFTH EXISTS FOR ONE TEXT, and it was missing while that text was live.
            # `svc_visit_redeemed` numbers five, the library declared four, and a submission whose
            # placeholder has no example is refused by Meta at creation — hours later, against a
            # name that cannot then be reused. The generator's own checker crashed on it, which is
            # how it was found: a KeyError is a better messenger than a rejection email.
            "5": {"name": "balance", "example": "40",
                  "means": "what is LEFT after the act — today the points balance that remains"},
        },
        "tones": list(TONES),
        "types": types,
    }


def main() -> int:
    check = "--check" in sys.argv
    types, problems = parse()
    problems += check_variables(build([])["variables"])

    for p in problems:
        print(f"{C_R}  ✗ {p}{C_N}")
    if problems:
        print(f"\n{C_R}  ✗ {len(problems)} problem(s) in the library{C_N}")
        return 1

    payload = build(types)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    if check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print(f"{C_R}  ✗ {OUT.name} is out of date — run: python ci/gen_templates.py{C_N}")
            return 1
    else:
        OUT.write_text(text, encoding="utf-8")

    counts = Counter(t["cls"] for t in types)
    print(f"{C_G}  ✔ {len(types)} texts x {len(TONES)} tones = {len(types) * len(TONES)} "
          f"templates{C_N}")
    print(f"    {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
