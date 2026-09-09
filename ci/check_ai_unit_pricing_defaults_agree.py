"""One number, believed in two places, and the day an admin trusts the wrong one.

AdminProviderSecrets.tsx's «إعدادات وحدات الذكاء» panel opens with a SUGGESTED starting value for
each of the five PRICING_AI_UNIT_* fields — not a live read of the current effective value (this
screen schedules a NEW value, it never displays the one already in force; see that component's own
comment on `googleInputSar`/`multiplier` for why the same is already true of the seven pricing keys
above it). That suggestion is a hardcoded literal, typed once, matching whatsapp-assistant's own
`Settings` default at the time this panel was built.

THE DAY THEY STOP MATCHING. Nothing keeps them in step. An operator raises
PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER's *deploy-time* default in config.py for a new environment,
or a future change edits one side and not the other — and the panel now opens on a number that was
never true, on a field an admin is about to schedule a real, money-moving change from. He reads
"5", assumes that is today's margin, and schedules "8" believing he raised it by 3 — when the real
current value was 6 the whole time. The gap is invisible: both numbers are perfectly plausible on
their own, and nothing anywhere compares them.

SAME SHAPE AS ci/check_paired_config.py, ONE LANGUAGE PAIR WIDER. That script already holds two
Python config.py defaults to the same value; this is the one place in the fleet a Python default
and a TypeScript literal make the same promise, so it gets its own small check rather than teaching
the shared one a second language.

    python ci/check_ai_unit_pricing_defaults_agree.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PY = ROOT / "services" / "whatsapp-assistant" / "app" / "config.py"
CONSOLE_TSX = ROOT / "apps" / "console" / "src" / "admin" / "AdminProviderSecrets.tsx"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"

# (Settings field name, console useState variable name)
NUMERIC_PAIRS = [
    ("PRICING_AI_UNIT_UNITS_PER_HALALA", "unitsPerHalala"),
    ("PRICING_AI_UNIT_INPUT_MARGIN_MULTIPLIER", "inputMargin"),
    ("PRICING_AI_UNIT_OUTPUT_MARGIN_MULTIPLIER", "outputMargin"),
    ("PRICING_AI_UNIT_USD_TO_SAR", "usdToSar"),
]


def _config_default(field: str) -> str | None:
    """`FIELD: type = value` on one line — every numeric AI-unit field is declared this way."""
    m = re.search(rf"^\s+{re.escape(field)}\s*:\s*(?:int|float)\s*=\s*([\d.]+)\s*$",
                  CONFIG_PY.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def _config_model_costs_json() -> dict | None:
    """PRICING_AI_UNIT_MODEL_COSTS_JSON's default is a parenthesized, line-wrapped string
    concatenation (a real multi-model registry would not fit readably on one line) — join the
    adjacent string literals rather than assume a single-line declaration."""
    text = CONFIG_PY.read_text(encoding="utf-8")
    m = re.search(r'PRICING_AI_UNIT_MODEL_COSTS_JSON\s*:\s*str\s*=\s*\((.*?)\)', text, re.S)
    if not m:
        return None
    literals = re.findall(r"'([^']*)'", m.group(1))
    try:
        return json.loads("".join(literals))
    except ValueError:
        return None


def _console_number(var: str) -> str | None:
    """`const [var, setVar] = useState('N');` — the exact literal an admin sees pre-filled."""
    m = re.search(rf"\[{re.escape(var)},\s*set\w+\]\s*=\s*useState\('([^']+)'\)",
                  CONSOLE_TSX.read_text(encoding="utf-8"))
    return m.group(1) if m else None


def _console_model_costs_json() -> dict | None:
    text = CONSOLE_TSX.read_text(encoding="utf-8")
    m = re.search(r"\[modelCostsJson,\s*setModelCostsJson\]\s*=\s*useState\(\s*'([^;]*?)'\s*\)",
                  text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def main() -> int:
    broken: list[str] = []
    missing: list[str] = []

    for field, var in NUMERIC_PAIRS:
        backend = _config_default(field)
        frontend = _console_number(var)
        if backend is None or frontend is None:
            side = "config.py" if backend is None else "AdminProviderSecrets.tsx"
            missing.append(f"{field}/{var} not found in {side} — this check could not read it")
            continue
        if float(backend) != float(frontend):
            broken.append(
                f"{field}: config.py defaults to {backend}, but the console's «{var}» suggestion "
                f"still opens on {frontend} — an admin scheduling a change from this panel is "
                f"reading the wrong starting point")

    backend_costs = _config_model_costs_json()
    frontend_costs = _console_model_costs_json()
    if backend_costs is None or frontend_costs is None:
        side = "config.py" if backend_costs is None else "AdminProviderSecrets.tsx"
        missing.append(f"PRICING_AI_UNIT_MODEL_COSTS_JSON not found/parseable in {side}")
    elif backend_costs != frontend_costs:
        broken.append(
            f"PRICING_AI_UNIT_MODEL_COSTS_JSON: config.py's default is {backend_costs!r}, the "
            f"console's suggestion is {frontend_costs!r} — they must name the same model(s) at the "
            f"same real cost, or the panel opens on a fiction")

    if missing:
        print(f"{C_R}  ~ {len(missing)} AI-unit default(s) this check could not read:{C_N}")
        for line in missing:
            print(f"{C_R}      {line}{C_N}")

    if broken:
        print(f"{C_R}  ✘ {len(broken)} AI-unit default(s) disagree between backend and console:{C_N}")
        for line in broken:
            print(f"{C_R}      {line}{C_N}")
        return 1

    if missing:
        return 1

    print(f"{C_G}  ✔ every AI-unit pricing default agrees between config.py and the console's own "
          f"scheduling panel ({len(NUMERIC_PAIRS) + 1} fields){C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
