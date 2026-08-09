"""The eleven that need nothing but a visit (spec §10.6.1).

AN OWNER WHO NEVER OPENS A SETTINGS SCREEN SEES A FULL DASHBOARD ON THE DAY HE SIGNS UP. That is
the governing choice of this file, and everything in it computes from three fields a visit always
has: when, which services, and whose.

Cycle completion is here rather than behind a setting, and that was a correction: `cycle_days` is
already in the service catalogue because `reminders` cannot schedule without it. The information
existed before anyone thought to ask for it — which is worth remembering the next time an indicator
looks like it needs configuration.

EVERY FUNCTION IS PURE. Visits in, a number out, no clock and no store. The tick supplies `now`,
which is what makes "what did this look like last Tuesday" answerable and every one of these
testable across its whole space.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable

DAY = 86400


def _by_customer(visits: Iterable[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for v in visits:
        ref = str(v.get("subject_ref") or "")
        if ref:
            out.setdefault(ref, []).append(v)
    for rows in out.values():
        rows.sort(key=lambda r: int(r.get("occurred_at") or r.get("created_at") or 0))
    return out


def return_rate(visits: list[dict]) -> float:
    """Of the people who came at all, how many came more than once.

    THE FIRST NUMBER AN OWNER SHOULD SEE, because a shop where nobody returns has one problem and
    it is not which service to bundle. Every other indicator here assumes returning customers.
    """
    per = _by_customer(visits)
    if not per:
        return 0.0
    repeat = sum(1 for rows in per.values() if len(rows) > 1)
    return round(repeat / len(per), 3)


def return_cycle_days(visits: list[dict]) -> int:
    """The median gap between one customer's consecutive visits.

    MEDIAN, NOT MEAN, and the difference matters more here than almost anywhere else on this
    screen: one customer who returned after two years drags a mean into nonsense, and the number
    an owner reads as "my customers come back every N days" would then describe nobody.
    """
    gaps: list[int] = []
    for rows in _by_customer(visits).values():
        times = [int(r.get("occurred_at") or r.get("created_at") or 0) for r in rows]
        gaps.extend((b - a) // DAY for a, b in zip(times, times[1:]) if b > a)
    if not gaps:
        return 0
    gaps.sort()
    mid = len(gaps) // 2
    return gaps[mid] if len(gaps) % 2 else (gaps[mid - 1] + gaps[mid]) // 2


def active_customers(visits: list[dict], *, now: int, window_days: int = 90) -> int:
    return len({str(v.get("subject_ref")) for v in visits
                if int(v.get("occurred_at") or v.get("created_at") or 0) >= now - window_days * DAY
                and v.get("subject_ref")})


def churn_rate(visits: list[dict], *, now: int, slack: float = 1.5) -> float:
    """Who is overdue against THEIR OWN cycle, not against a number we picked.

    A COFFEE CUSTOMER MISSING A WEEK IS A WORRY; AN OIL CUSTOMER MISSING EIGHTY DAYS IS PUNCTUAL.
    A fixed "no visit in 60 days" would call the first one healthy and the second one lost, and it
    would be wrong about both in the same shop. So absence is measured in multiples of the person's
    own interval — the same rule `campaigns` already uses for win-back, deliberately.
    """
    per = _by_customer(visits)
    lapsed = eligible = 0
    for rows in per.values():
        times = [int(r.get("occurred_at") or r.get("created_at") or 0) for r in rows]
        if len(times) < 2:
            # One visit tells us nothing about their rhythm. Counting them would make every new
            # customer look like a churn risk, which is the opposite of the truth.
            continue
        gaps = [(b - a) // DAY for a, b in zip(times, times[1:]) if b > a]
        if not gaps:
            continue
        own = sum(gaps) / len(gaps)
        eligible += 1
        if (now - times[-1]) / DAY > own * slack:
            lapsed += 1
    return round(lapsed / eligible, 3) if eligible else 0.0


def at_risk(visits: list[dict], *, now: int, slack: float = 1.5,
            limit: int = 200) -> list[dict[str, Any]]:
    """Not an indicator — a LIST TO ACT ON (spec §10.7).

    Returns the people, so the screen can end in a button rather than a number. An owner told "12%
    of your customers are lapsing" does nothing; an owner handed twelve names presses send.
    """
    out: list[dict[str, Any]] = []
    for ref, rows in _by_customer(visits).items():
        times = [int(r.get("occurred_at") or r.get("created_at") or 0) for r in rows]
        if len(times) < 2:
            continue
        gaps = [(b - a) // DAY for a, b in zip(times, times[1:]) if b > a]
        if not gaps:
            continue
        own = sum(gaps) / len(gaps)
        overdue = (now - times[-1]) / DAY - own
        if overdue > own * (slack - 1):
            out.append({"subject_ref": ref, "days_overdue": int(overdue),
                        "own_cycle_days": int(own), "visits": len(times)})
    out.sort(key=lambda r: -r["days_overdue"])
    return out[:limit]


def new_vs_returning(visits: list[dict], *, now: int, window_days: int = 30) -> dict[str, int]:
    since = now - window_days * DAY
    per = _by_customer(visits)
    new = returning = 0
    for rows in per.values():
        times = [int(r.get("occurred_at") or r.get("created_at") or 0) for r in rows]
        recent = [t for t in times if t >= since]
        if not recent:
            continue
        # First-ever visit inside the window = new. Anyone else who came is returning.
        if min(times) >= since:
            new += 1
        else:
            returning += 1
    return {"new": new, "returning": returning}


def service_popularity(visits: list[dict], *, limit: int = 20) -> list[dict[str, Any]]:
    c: Counter = Counter()
    for v in visits:
        for s in set(v.get("service_ids") or []):
            c[str(s)] += 1
    total = sum(c.values()) or 1
    return [{"service_id": s, "count": n, "share": round(n / total, 3)}
            for s, n in c.most_common(limit)]


def weak_services(visits: list[dict], *, catalogue: list[str],
                  bottom: float = 0.2) -> list[str]:
    """The quietest fifth of HIS OWN distribution (spec §10.6.1).

    "Weak" is a judgement, not a fact: a service asked for twice a month is a disaster in a car
    wash and excellent in a body shop. So we do not invent a threshold and we do not ask him for
    one — we rank his own catalogue and name the bottom fifth. A service nobody has EVER taken is
    weakest of all and must appear, which is why the catalogue is passed in rather than derived
    from the visits.
    """
    counts = {s: 0 for s in catalogue}
    for v in visits:
        for s in set(v.get("service_ids") or []):
            if str(s) in counts:
                counts[str(s)] += 1
    if not counts:
        return []
    ranked = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]))
    take = max(1, int(len(ranked) * bottom))
    # EVERYTHING TIED WITH THE LAST ONE IS INCLUDED. Three services with zero visits are equally
    # weak, and naming one of them while hiding the other two is a list the owner cannot act on —
    # he fixes the one we showed and the other two stay dead. The cut is a threshold, not a quota.
    cutoff = ranked[take - 1][1]
    return [s for s, n in ranked if n <= cutoff]


def services_per_visit(visits: list[dict]) -> float:
    if not visits:
        return 0.0
    return round(sum(len(set(v.get("service_ids") or [])) for v in visits) / len(visits), 2)


def peak_map(visits: list[dict], *, tz_offset_hours: int = 3) -> dict[str, Any]:
    """Busiest days and hours, in RIYADH time.

    The offset is applied here rather than left to the screen: a heat map rendered in UTC puts a
    Saudi shop's evening rush at three in the afternoon, and it looks plausible enough that nobody
    questions it.
    """
    grid: Counter = Counter()
    for v in visits:
        ts = int(v.get("occurred_at") or v.get("created_at") or 0)
        if not ts:
            continue
        local = ts + tz_offset_hours * 3600
        day = (local // DAY + 4) % 7          # 0 = Sunday, the week's first day here
        hour = (local % DAY) // 3600
        grid[f"{day}:{hour}"] += 1
    return {"grid": dict(grid), "busiest": max(grid, key=grid.get) if grid else ""}


def expected_flow(visits: list[dict], *, now: int, weeks: int = 4) -> int:
    """Next week's expected visits — the mean of the last four, and nothing cleverer.

    A regression on four points would be a decoration on the same information. This number is used
    to staff a shift, and a staffing number that cannot be explained in one sentence is one nobody
    acts on.
    """
    counts = [0] * weeks
    for v in visits:
        ts = int(v.get("occurred_at") or v.get("created_at") or 0)
        weeks_ago = (now - ts) // (7 * DAY)
        if 0 <= weeks_ago < weeks:
            counts[weeks_ago] += 1
    seen = [c for c in counts if c]
    return round(sum(seen) / len(seen)) if seen else 0


def cycle_completion(visits: list[dict], *, cycles: dict[str, int], now: int) -> float:
    """Of the customers who ever took a periodic service, how many are still current on it.

    FREE, because `cycle_days` is already in the catalogue — `reminders` cannot schedule without
    it. This was written down as needing configuration in a first draft, and it did not: the
    information had been there since the owner set up his services.
    """
    periodic = {s: d for s, d in (cycles or {}).items() if d > 0}
    if not periodic:
        return 0.0
    on_time = total = 0
    for rows in _by_customer(visits).values():
        last: dict[str, int] = {}
        for r in rows:
            ts = int(r.get("occurred_at") or r.get("created_at") or 0)
            for s in set(r.get("service_ids") or []):
                if str(s) in periodic:
                    last[str(s)] = max(last.get(str(s), 0), ts)
        for s, ts in last.items():
            total += 1
            if (now - ts) <= periodic[s] * DAY:
                on_time += 1
    return round(on_time / total, 3) if total else 0.0
