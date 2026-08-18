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

# (key, service_a, service_b, why) — or (key_a, service_a, key_b, service_b, why) when the two
# sides spell the same fact under different names.
#
# THE SECOND SHAPE EXISTS BECAUSE A FACT DOES NOT ALWAYS DESERVE THE SAME NAME ON BOTH SIDES. The
# ceiling on one visits read is `VISITS_PAGE_MAX` to the service that enforces it and
# `SNAPSHOT_VISIT_LIMIT` to the service that asks for it — two true names for one number. Forcing
# one name would have made one of them lie about its own job; leaving them unpaired is what let
# them drift to 1000 and 5000 and take the whole dashboard down.
PAIRS: list[tuple, ...] = [
    ("HOLDOUT_ENABLED", "reminders", "insights",
     "reminders withholds the control group; insights measures it. If they disagree, the "
     "proof-of-value card compares two groups that both received every message — and reports the "
     "noise between them as our engine's effect"),
    ("HOLDOUT_SHARE_PERCENT", "reminders", "insights",
     "both sides must select the SAME tenth by the same share, or the group insights calls «held» "
     "is not the group reminders withheld from"),
    # ── THE QUIET HOURS, AND THEY ARE THE SAME PROMISE MADE BY TWO SERVICES ──────────────────
    # «لا نراسل عملاءك قبل السابعة ولا بعد العاشرة» is one sentence to a shop owner, and it is
    # enforced twice: `reminders` defers a reminder to the morning, `campaigns` holds a launch.
    # They agree today by coincidence — nothing has ever compared them — and the day one moves,
    # the product keeps its promise for reminders and breaks it for campaigns. What the customer
    # sees is an offer at 06:40 from a shop that is shut, which is the message that earns a block.
    ("SEND_WINDOW_START_HOUR", "reminders", "campaigns",
     "one shop-facing promise about quiet hours, enforced separately by both services: a campaign "
     "that launches before reminders would send is the promise broken on the louder half"),
    ("SEND_WINDOW_END_HOUR", "reminders", "campaigns",
     "the same window's other edge — a campaign still going out after reminders have stopped for "
     "the night is the same defect an hour later"),
    # ── THE CEILING ON ONE VISITS READ, AND THE DAY THE TWO NUMBERS PARTED ───────────────────
    # operations declared `le=1000` on the route's `limit`; insights asked for 5000. Neither is
    # wrong on its own — 5000 is what ninety-day indicators need on a busy shop, 1000 is what a
    # request may safely hold in memory — and nothing had ever put them side by side. So EVERY
    # snapshot computation was rejected 422 before it reached any logic: the dashboard was never
    # computed, for any establishment, and «حدّث الآن» answered 500. The nightly sweep logged
    # `{"computed": 0}` and nobody read it.
    #
    # ONE NUMBER, TWO NAMES, AND A CHECK BETWEEN THEM. There is no runtime variable two processes
    # can share; the closest honest thing is one fact declared on both sides and a gate that fails
    # the build the moment they differ. That is this line.
    ("VISITS_PAGE_MAX", "operations", "SNAPSHOT_VISIT_LIMIT", "insights",
     "the most visit rows one read may carry: operations enforces it on the route, insights asks "
     "for exactly it. If the asker's number is the larger, every snapshot is refused 422 before "
     "any work is done — the whole dashboard, silently, for every shop"),
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

    for pair in PAIRS:
        key_a, a, key_b, b, why = pair if len(pair) == 5 else (pair[0], pair[1], pair[0], pair[2],
                                                              pair[3])
        name = key_a if key_a == key_b else f"{key_a}/{key_b}"
        da, db = declared_default(a, key_a), declared_default(b, key_b)
        if da is None or db is None:
            side, k = (a, key_a) if da is None else (b, key_b)
            missing.append(f"{k} is not declared in {side}/app/config.py — the pair cannot hold "
                           f"if one side does not have the key at all")
            continue
        checked += 1
        # The DEFAULTS must agree, because a deployment that sets neither still runs both.
        if not _same(da, db):
            broken.append(f"{name}: {a} defaults to {da}, {b} defaults to {db} — {why}")
        # And wherever the deployment sets one, it must set the other to the same value.
        ca, cb = configured(a, key_a), configured(b, key_b)
        if (ca is None) != (cb is None):
            side = a if ca is not None else b
            other = b if ca is not None else a
            broken.append(f"{name} is set for {side} in deploy/services/{side}.values.yaml and NOT "
                          f"for {other} — {why}")
        elif ca is not None and not _same(ca, cb):
            broken.append(f"{name}: {a}={ca} but {b}={cb} in their values files — {why}")

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
