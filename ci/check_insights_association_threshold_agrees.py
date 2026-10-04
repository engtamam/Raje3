"""One number, believed in three places, same shape as ci/check_ai_unit_pricing_defaults_agree.py.

`ASSOC_MIN_BASKETS` — how many real visits «ما يُطلب معًا»/الباقات المقترحة need before the engine
stops saying «قيد التعلّم» and starts naming a pattern — lives in three spots that must all say the
same thing: `associations.py`'s own `Thresholds` dataclass (the library's fallback, used by tests
and any caller that does not wire a live setting), `config.py`'s `Settings.ASSOC_MIN_BASKETS` (what
an unconfigured deployment gets), and `deploy/services/insights.values.yaml` (the ops-tunable value
actually running in production — see that file's own comment on why it lives there, not in code).

THE DAY THEY STOP MATCHING. An owner asks to lower the threshold (as happened 2026-09-26, 200→100)
and only config.py gets edited — the dataclass fallback and the deployed value silently keep the old
number, so tests believe one thing, a fresh local run believes another, and production believes a
third. Nothing anywhere compares them.

`config.py` IS THE ONE PLACE TO EDIT. The other two are read here and must agree with it.

    python ci/check_insights_association_threshold_agrees.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSOCIATIONS_PY = ROOT / "services" / "insights" / "app" / "core" / "associations.py"
CONFIG_PY = ROOT / "services" / "insights" / "app" / "config.py"
VALUES_YAML = ROOT / "deploy" / "services" / "insights.values.yaml"
C_G, C_R, C_N = "\033[32m", "\033[31m", "\033[0m"


def _config_default() -> str | None:
    m = re.search(r"^\s+ASSOC_MIN_BASKETS\s*:\s*int\s*=\s*(\d+)", CONFIG_PY.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def _dataclass_default() -> str | None:
    m = re.search(r"^\s+min_baskets\s*:\s*int\s*=\s*(\d+)", ASSOCIATIONS_PY.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def _values_yaml() -> str | None:
    m = re.search(r'^\s+ASSOC_MIN_BASKETS\s*:\s*"?(\d+)"?', VALUES_YAML.read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else None


def main() -> int:
    canonical = _config_default()
    dataclass_default = _dataclass_default()
    values = _values_yaml()

    missing = [(name, val) for name, val in [
        ("config.py's Settings.ASSOC_MIN_BASKETS", canonical),
        ("associations.py's Thresholds.min_baskets", dataclass_default),
        ("insights.values.yaml's ASSOC_MIN_BASKETS", values),
    ] if val is None]
    if missing:
        print(f"{C_R}  ✘ could not read: {', '.join(name for name, _ in missing)}{C_N}")
        return 1

    broken = []
    if dataclass_default != canonical:
        broken.append(
            f"associations.py's Thresholds.min_baskets defaults to {dataclass_default}, but "
            f"config.py's ASSOC_MIN_BASKETS (the one place to edit) is {canonical} — a caller "
            f"that does not wire live settings (a test, a direct tick.py call) still sees the "
            f"old number")
    if values != canonical:
        broken.append(
            f"deploy/services/insights.values.yaml pins ASSOC_MIN_BASKETS to {values}, but "
            f"config.py's own default is {canonical} — production is running a different "
            f"threshold than the code believes it ships with")

    if broken:
        print(f"{C_R}  ✘ ASSOC_MIN_BASKETS disagrees across the fleet:{C_N}")
        for line in broken:
            print(f"{C_R}      {line}{C_N}")
        return 1

    print(f"{C_G}  ✔ ASSOC_MIN_BASKETS agrees everywhere ({canonical}) — config.py, "
          f"associations.py's own fallback, and the deployed values file{C_N}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
