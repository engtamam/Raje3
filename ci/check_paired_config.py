"""One fact, two services, and the day they stop agreeing.

WHY THIS EXISTS. `reminders` decides whether a tenth of each shop's customers is WITHHELD from —
the control group that makes «أثر الرسائل، مقيساً» a measurement instead of our word for our own
work. `insights` measures the two groups. Neither knows the other's setting.

So when `HOLDOUT_ENABLED` is false in reminders, every customer is messaged — and insights still
splits them by the same hash and reports the difference between the two rates as our engine's
effect. With enough traffic it stops refusing and starts publishing noise, confidently, as the one
number in this product that is not a claim about itself.

It fails in the direction that flatters us, which is the direction nobody checks.

THE SHAPE, NOT THE KEY. This is not «holdout» — it is «the same fact configured in two places».
Every entry below is a pair that must hold the same value in every environment, with the reason
written next to it, because a pair whose reason nobody can state is a pair somebody will «fix» by
deleting one side.

    python ci/check_paired_config.py
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
VALUES = ROOT / "deploy" / "services"
SERVICES = ROOT / "services"
C_G, C_R, C_Y, C_N = "\033[32m", "\033[31m", "\033[33m", "\033[0m"

# (key, service_a, service_b, why)
PAIRS: list[tuple[str, str, str, str]] = [
    ("HOLDOUT_ENABLED", "reminders", "insights",
     "reminders withholds the control group; insights measures it. If they disagree, the "
     "proof-of-value card compares two groups that both received every message — and reports the "
     "noise between them as our engine's effect"),
    ("HOLDOUT_SHARE_PERCENT", "reminders", "insights",
     "both sides must select the SAME tenth by the same share, or the group insights calls «held» "
     "is not the group reminders withheld from"),
]


def declared_default(service: str, key: str) -> str | None:
    """The value in the service's own config.py — what an unconfigured deployment gets."""
    path = SERVICES / service / "app" / "config.py"
    if not path.exists():
        return None
    m = re.search(rf"^\s+{re.escape(key)}\s*:\s*[^=]+=\s*(.+?)\s*$",
                  path.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else None


def configured(service: str, key: str) -> str | None:
    """The value in the deployment's values file, or None when it is not set there."""
    path = VALUES / f"{service}.values.yaml"
    if not path.exists():
        return None
    m = re.search(rf"^\s+{re.escape(key)}\s*:\s*\"?([^\"\n#]+)\"?", path.read_text(encoding="utf-8"),
                  re.M)
    return m.group(1).strip() if m else None


def _same(a: str | None, b: str | None) -> bool:
    def norm(v: str | None) -> str:
        if v is None:
            return ""
        return v.strip().strip('"').strip("'").lower().replace("true", "1").replace("false", "0")
    return norm(a) == norm(b)


def main() -> int:
    broken: list[str] = []
    missing: list[str] = []
    checked = 0

    for key, a, b, why in PAIRS:
        da, db = declared_default(a, key), declared_default(b, key)
        if da is None or db is None:
            side = a if da is None else b
            missing.append(f"{key} is not declared in {side}/app/config.py — the pair cannot hold "
                           f"if one side does not have the key at all")
            continue
        checked += 1
        # The DEFAULTS must agree, because a deployment that sets neither still runs both.
        if not _same(da, db):
            broken.append(f"{key}: {a} defaults to {da}, {b} defaults to {db} — {why}")
        # And wherever the deployment sets one, it must set the other to the same value.
        ca, cb = configured(a, key), configured(b, key)
        if (ca is None) != (cb is None):
            side = a if ca is not None else b
            other = b if ca is not None else a
            broken.append(f"{key} is set for {side} in deploy/services/{side}.values.yaml and NOT "
                          f"for {other} — {why}")
        elif ca is not None and not _same(ca, cb):
            broken.append(f"{key}: {a}={ca} but {b}={cb} in their values files — {why}")

    if missing:
        print(f"{C_Y}  ~ {len(missing)} pair(s) this check could not read:{C_N}")
        for line in missing:
            print(f"{C_Y}      {line}{C_N}")

    if broken:
        print(f"{C_R}  ✘ {len(broken)} paired setting(s) disagree — each produces an answer that "
              f"looks measured and is not:{C_N}")
        for line in broken:
            print(f"{C_R}      {line}{C_N}")
        return 1

    print(f"{C_G}  ✔ every paired setting agrees across the services that share it "
          f"({checked} pairs){C_N}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
