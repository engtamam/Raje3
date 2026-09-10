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
TONES = ("warm", "feminine")

# WHO FILLS EACH BLANK, IN ORDER (§8.4). Meta approves the WORDS, so the numbered blanks are the
# only thing a shop decides, and every one of them belongs to somebody: to us at send time
# («system»), to a tap on his own service list («catalogue»), to a typed value with a shape
# («amount», «code», «date»), or to him («owner» — the one free blank, at most one per template).
#
# IT IS READ FROM THE DOC, like everything else here. `fills` was once hand-written into the
# generated JSON, which this generator then overwrote on its next run — the field vanished, every
# reader fell back to «system», and the owner's discount reached no slot. A value that only one
# writer can write cannot be lost that way.
FILLS = ("system", "catalogue", "owner", "amount", "date", "invite", "stop_link",
         # THE RATING APP'S OWN CLAUSE (rating-app-feature.md) — a whole sentence computed
         # server-side (points-participation line, or a neutral one when no points are configured),
         # never a template-level condition. Same discipline as «invite»: WhatsApp refuses an
         # empty variable, so this is always a full sentence, never blank.
         "rating_cta")
FREE = "owner"

# THE LAST BLANK OF EVERY TEMPLATE, AND IT IS NOT A STYLE RULE.
#
# Marketing is opt-IN: without a grant no promotional message may lawfully leave. And a grant needs
# somewhere to be given — a screen the customer can reach from a message he already trusts. There
# was no such place. The library declared a `button` on sixty of sixty-six templates; nothing
# submits buttons to Meta (submission.py sends name, language, category, body, variables, examples
# and nothing else) and notification-service has no notion of one anywhere in its source. So the
# link existed in our data, reached no template, and no customer was ever able to say yes.
#
# The whole marketing engine — built, complete, sold as an app — could therefore never send, and
# nothing anywhere reported it.
#
# So the address moves into the BODY, where we control it end to end:
#
#   invite      utility classes. Resolves to the grant screen for somebody who has not agreed,
#               and to a plain line with no link for somebody who has. Never both.
#   stop_link   marketing only, and mandatory (§8.3): one tap to stop, in every promotional
#               message, with no exception any establishment can switch off.
#
# AND THE INVITE STAYS QUIET ON PURPOSE. A utility template whose text sells is re-categorised by
# Meta as MARKETING — a higher price per message and a service message that suddenly needs consent
# to send. That is what SELLING_WORDS below already guards for the awareness class; the invitation
# obeys the same rule by carrying no price, no discount and no offer. All of the persuasion lives
# on the screen the link opens, which is ours and which Meta does not review.
LAST_FILL = {"marketing": "stop_link"}
LAST_FILL_DEFAULT = "invite"

# An awareness or warning template carrying any of these is not awareness — it is marketing by its
# text, whatever it is labelled (spec §8.4.1). Meta re-categorises it and bills accordingly, and
# the establishment is then sending promotion under a utility consent.
SELLING_WORDS = ("خصم", "عرض", "ريال", "مجاناً", "مجانا", "اشترِ", "اشتري", "احجز", "زُرنا",
                 "زرنا", "سعر", "تخفيض")

C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"


def _vars(text: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\{\{(\d+)\}\}", text)})


DEFERRALS = ("drop", "defer", "priority")


def deferral_map(doc: str) -> tuple[dict[str, str], set[str]]:
    """The policy per type, read from the table in the specification (§8.4.3) — and separately,
    the names DELIBERATELY struck through in that same table (`~~name~~`), which is the spec's own
    way of saying "written, approved in spirit, not yet seeded" (see `awr_seasonal_care`, #389).

    WHY IT IS PARSED AND NOT LISTED HERE. A policy in this file is a policy nobody reviewing the
    product ever sees, and the question it answers — "does this message still make sense tomorrow?"
    — is about the TEXT, not about the engine. It belongs where the texts are argued over.

    THE ROWS ARE PATTERNS, not only names, because ten marketing templates share one answer and
    ten identical rows is ten chances to get one wrong.

    THE EXCLUDED SET EXISTS SO A STRIKETHROUGH ROW IS NOT ALSO A BUILD FAILURE. Before this, a
    name struck through here still had a full `**`name` — title**` block earlier in the doc (the
    text itself, kept for the day it IS seeded), so `parse()` found it, found no policy for it —
    correctly, `—` is not a policy — and reported "no deferral policy" as though somebody had
    simply forgotten to fill in a row. The generator has refused to write `deploy/seed/
    templates.json` at all since the day that strikethrough was added, and nothing said so beyond
    a red exit code nobody connected to `awr_seasonal_care`'s own deliberate omission a few lines
    above it in the same table.
    """
    out: dict[str, str] = {}
    excluded: set[str] = set()
    block = doc.split("## 8.4.3", 1)
    if len(block) < 2:
        return out, excluded
    block = block[1].split("## 8.5", 1)[0]
    for line in block.splitlines():
        if not line.startswith("|") or "`" not in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue
        names = re.findall(r"`([a-z_*]+)`", cells[0])
        policy = cells[1].strip(" `*")
        if "~~" in cells[0]:
            excluded.update(names)
            continue
        if policy not in DEFERRALS:
            continue
        for name in names:
            out[name] = policy
    return out, excluded


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

    policies, excluded = deferral_map(doc)
    types: list[dict] = []
    problems: list[str] = []
    seen: set[str] = set()

    for name, title, body in blocks:
        if name in excluded:
            # Written, struck through in the 8.4.3 table on purpose (see deferral_map's doc) —
            # skipped silently, not a problem: the spec is stating an intent, not a mistake.
            continue
        tones = dict(re.findall(r"\|\s*`_(warm|feminine)`\s*\|\s*(.+?)\s*\|", body))
        if len(tones) != 2:
            problems.append(f"{name}: has {sorted(tones)} — every text needs both tones, "
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
        # ── and who fills each of those blanks ─────────────────────────────────────────────────
        row = re.search(r"\|\s*الفراغات\s*\|\s*(.+?)\s*\|", body)
        fills = [f.strip() for f in row.group(1).split("·")] if row else []
        slots = per_tone[TONES[0]]
        if not fills:
            problems.append(f"{name}: no «الفراغات» row — every blank defaults to «system» then, "
                            f"so anything the shop types reaches no slot and the preview draws «…»")
            continue
        if len(fills) != len(slots):
            problems.append(f"{name}: {len(slots)} blanks in the body, {len(fills)} declared — the "
                            f"list is read BY POSITION, so one missing entry shifts every blank "
                            f"after it onto the wrong source")
            continue
        unknown = [f for f in fills if f not in FILLS]
        if unknown:
            problems.append(f"{name}: unknown filler {unknown} — the readers branch on these by "
                            f"name and treat anything else as «system». Use one of {FILLS}")
            continue
        # ── the address every message has to carry, and exactly one of them ────────────────────
        wanted = LAST_FILL.get(cls, LAST_FILL_DEFAULT)
        if fills[-1] != wanted:
            problems.append(
                f"{name}: last blank is «{fills[-1]}», must be «{wanted}» — a {cls} template ends "
                f"with the one address it owes its reader. Marketing owes a one-tap stop (§8.3); "
                f"everything else owes the invitation that is the only way consent can ever be "
                f"given. Without it the message is a dead end and the campaigns engine can never "
                f"lawfully send.")
            continue
        stray = [f for f in fills[:-1] if f in ("invite", "stop_link")]
        if stray:
            problems.append(
                f"{name}: {stray} appears before the last blank — an address mid-sentence reads as "
                f"a broken line on a phone, and two of them in one message is two calls to action "
                f"competing for the same tap")
            continue
        if fills.count(FREE) > 1:
            problems.append(f"{name}: asks the owner to write {fills.count(FREE)} free blanks. One "
                            f"at most — two is a form he abandons halfway, and the customer never "
                            f"hears")
            continue

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
            "fills": fills,
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
            "ALL OF THEM, not the half of one tone. The tone is in the NAME and a name",
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
            "3": {"name": "service", "example": "قص شعر",
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
        # LF, WHOEVER RAN IT. Without `newline`, Python writes CRLF on Windows, so the file this
        # generator produces differs from the one CI produces in every single line — and the diff
        # that matters is hidden inside a whole-file rewrite.
        OUT.write_text(text, encoding="utf-8", newline="\n")

    counts = Counter(t["cls"] for t in types)
    print(f"{C_G}  ✔ {len(types)} texts x {len(TONES)} tones = {len(types) * len(TONES)} "
          f"templates{C_N}")
    print(f"    {dict(counts)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
