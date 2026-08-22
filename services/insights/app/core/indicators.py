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


def return_cycle_days(visits: list[dict], *, min_gaps: int = 20) -> int | None:
    """The median gap between one customer's consecutive visits, or None when we cannot say.

    MEDIAN, NOT MEAN, and the difference matters more here than almost anywhere else on this
    screen: one customer who returned after two years drags a mean into nonsense, and the number
    an owner reads as "my customers come back every N days" would then describe nobody.

    AND IT REFUSES UNDER `min_gaps`, like every other statistic on this screen — `retention_series`
    wants 20 customers in a window, `holdout_comparison` 15 a side, `opt_out_rate` 200 sends. This
    one had no threshold at all, so a shop with a single pair of visits published that pair's gap
    as «دورة العودة». Worse, two visits on the SAME DAY floor to a gap of 0, and the screen then
    told the owner his customers come back every 0 days — a sentence that is not merely wrong but
    unreadable, and one he cannot distinguish from «we have no idea».

    None, NEVER 0. The console skips a value that is not a number (`typeof raw !== 'number'`), so
    the tile disappears rather than printing a figure derived from nobody. A returned 0 would be
    indistinguishable from a real same-day shop, which is exactly the collapse to avoid.
    """
    gaps: list[int] = []
    for rows in _by_customer(visits).values():
        times = [int(r.get("occurred_at") or r.get("created_at") or 0) for r in rows]
        gaps.extend((b - a) // DAY for a, b in zip(times, times[1:]) if b > a)
    if len(gaps) < min_gaps:
        return None
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


def active_customers_trend(visits: list[dict], *, now: int, window_days: int = 90,
                           step_days: int = 30) -> dict[str, Any]:
    """`active_customers`, plus what it was one step earlier.

    THE SAME NUMBER CAN CLIMB WHILE REAL CUSTOMERS LEAVE — new ones backfilling the count is
    exactly how a lifetime figure hides churn happening underneath it. An owner watching only the
    level has no way to tell "growing" from "turning over," and this is the smallest change that
    tells them apart: the same trailing-window count, read twice, one step apart.

    `previous` IS None, NOT 0, WHEN THE HISTORY DOES NOT REACH BACK — same contract as
    `visits_in_window`. A shop whose whole history fits inside one window has no "before" to show,
    and printing 0 there would read as "you had no active customers a month ago," which is not
    what "we have no earlier window" means.
    """
    span = window_days * DAY
    step = step_days * DAY

    def _count(cutoff: int) -> int:
        return len({str(v.get("subject_ref")) for v in visits
                    if cutoff - span < int(v.get("occurred_at") or v.get("created_at") or 0) <= cutoff
                    and v.get("subject_ref")})

    times = [int(v.get("occurred_at") or v.get("created_at") or 0) for v in visits]
    covered = bool(times) and min(times) <= now - span - step
    return {"current": _count(now), "previous": _count(now - step) if covered else None}


def churn_rate_trend(visits: list[dict], *, now: int, slack: float = 1.5,
                     step_days: int = 30) -> dict[str, Any]:
    """`churn_rate`, plus what it was one step earlier — recomputed from the history AS IT STOOD
    then, never from visits that had not happened yet.

    Filtering to `occurred_at <= cutoff` before calling `churn_rate` again is the whole trick: the
    function itself never changes, only how much of the feed it is allowed to see, so "the past" is
    not a different calculation — it is the same one, asked earlier.
    """
    step = step_days * DAY
    cutoff = now - step
    times = [int(v.get("occurred_at") or v.get("created_at") or 0) for v in visits]
    covered = bool(times) and min(times) <= cutoff
    past = [v for v in visits if int(v.get("occurred_at") or v.get("created_at") or 0) <= cutoff]
    return {
        "current": churn_rate(visits, now=now, slack=slack),
        "previous": churn_rate(past, now=cutoff, slack=slack) if covered else None,
    }


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
    # ── the denominator is the shop's age, not the number of weeks it was busy ───────────────
    # This used to be `seen = [c for c in counts if c]` — every zero week dropped before the mean.
    # A car wash that closed for two weeks reported [40, 0, 0, 44] as 42 when the truth is 21, and
    # the number is used to STAFF A SHIFT: it says «expect what a normal week brings» to a shop
    # that has not had a normal month. A closure is not missing data. It is data, and it says zero.
    #
    # But a week BEFORE THE SHOP EXISTED is genuinely not data, and averaging over it would tell a
    # one-week-old shop doing forty visits to expect ten. So the denominator is how many of these
    # weeks the shop was actually open for — which is the one thing the visits themselves can say.
    lived = 0
    for v in visits:
        ts = int(v.get("occurred_at") or v.get("created_at") or 0)
        if ts:
            lived = max(lived, min(weeks, (now - ts) // (7 * DAY) + 1))
    if not lived:
        return 0
    return round(sum(counts[:lived]) / lived)


def visits_in_window(visits: list[dict], *, now: int, window_days: int = 7) -> dict[str, Any]:
    """This week's visits and last week's — the pair the weekly report is actually about (ي-2).

    THE HEADLINE OF «أسبوعك في …» WAS THE SHOP'S WHOLE LIFE. The digest read `snapshot.visits`,
    which is `len(visits)` over the feed since the beginning of time, and printed it as «الزيارات»
    directly above two lines computed over 30 days. Three periods under one heading, and the
    biggest number — the one an owner reads first and remembers — described a span nobody chose.

    THE COMPARISON COMES FROM HERE TOO, and that is the second half of the same defect. The digest
    accepted a `previous` snapshot to print «(+15)» and no caller ever passed one, so the delta was
    dead from the day it was written. Both numbers now come from ONE read of ONE list against ONE
    clock, which is the only arrangement in which they cannot disagree.

    `previous` IS None, NOT 0, WHEN THE HISTORY DOES NOT REACH BACK. A shop whose first visit was
    five days ago has no previous week — and calling that zero turns «we do not know» into «+40»,
    a triumph we invented out of the day he signed up. The caller prints no comparison instead.
    """
    span = window_days * DAY
    times = [int(v.get("occurred_at") or v.get("created_at") or 0) for v in visits]
    times = [t for t in times if t]

    current = sum(1 for t in times if now - span < t <= now)
    prior = sum(1 for t in times if now - 2 * span < t <= now - span)
    # THE FEED MUST REACH BACK PAST THE EARLIER WINDOW BEFORE ITS COUNT MEANS ANYTHING. A shop
    # whose first visit falls INSIDE that window was ramping up through it, and comparing a full
    # week against a partial one manufactures growth out of the signup date.
    #
    # `truncated` is not consulted here: this read keeps the NEWEST rows (see the peers adapter),
    # so a cap only ever removes history older than both windows — which makes `min(times)` early,
    # never late, and the test this guard performs stricter rather than looser.
    covered = bool(times) and min(times) <= now - 2 * span
    return {"visits": current, "previous": prior if covered else None,
            "window_days": window_days}


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


def engine_reserve(visits: list[dict], *, now: int, weeks: int = 8,
                   percentile: float = 0.95, floor: int = 0, outlier_factor: float = 2.0,
                   tz_offset_hours: int = 3) -> dict[str, Any]:
    """How much of today's WhatsApp ceiling to hold back for the automatic engine.

    WHY THE RESERVE EXISTS. The ceiling is shared between campaigns and the engine, and whoever
    arrives first eats it (spec §8.4.3). A campaign launched in the afternoon can silence the shop
    for the rest of the day — and the customer who walks in after Maghrib, the one person who
    genuinely deserved a message, is the one who does not get it.

    ────────────────────────────────────────────────────────────────────────────────────────────
    THE 95th PERCENTILE OF THE SAME WEEKDAY, AND WHY NOT THE OBVIOUS ANSWERS

      the average   Thursday is twice Tuesday in most of these shops. Reserve the average and half
                    of Thursday's visitors get nothing.
      the maximum   one Eid peak steals the ceiling every ordinary day for two months, and no
                    campaign ever launches.
      a fixed number does not know the difference between a shop seeing 30 visitors a day and one
                    seeing 400, which is most of the difference between our customers.

    Same weekday, because it catches the shop's real cycle: a car wash fills on Thursday and a
    workshop on Saturday, and neither pattern is visible in a daily average. The percentile rather
    than the mean because it absorbs a busy day while ignoring a freak one. A rolling window of
    weeks, because it then learns by itself — a shop that grew over two months gets a larger
    reserve with nobody touching anything.

    ────────────────────────────────────────────────────────────────────────────────────────────
    AND TWO GUARDS, each for a way the arithmetic fails on its own

      `floor`           a shop with no history has no percentile, and its first fortnight is
                        exactly when a dropped confirmation does the most damage. Below the floor
                        we reserve the floor and campaigns wait.
      `outlier_factor`  the percentile alone does not reject the outlier — see below.

    ────────────────────────────────────────────────────────────────────────────────────────────
    THE CEILING IS NOT CAPPED HERE, BECAUSE THIS SERVICE DOES NOT HOLD THE CEILING

    A shop's traffic can warrant more than its whole WhatsApp allowance — 300 wanted against a
    ceiling of 250 — and the reserve must not then swallow the campaign allowance whole. That cap
    belongs where the ceiling is a known number, which is campaigns/core/share.py: it reads the
    live ceiling from notification-service and subtracts this reserve from it.

    This function once took `ceiling` and `cap_share` and capped here. No caller ever passed
    them, so `if ceiling:` never fired and the cap was a paragraph of documentation with no
    machine behind it — while the one place that could cap subtracted the reserve unbounded.

    Returns the reserve and the working, because a number an owner cannot question is a number he
    does not trust — and because the day this is wrong, we will want to see which guard produced
    it.
    """
    weekday = ((now + tz_offset_hours * 3600) // DAY + 4) % 7
    horizon = now - weeks * 7 * DAY

    # Visits on THIS weekday, bucketed by which week they fell in.
    per_week: Counter = Counter()
    for v in visits:
        ts = int(v.get("occurred_at") or v.get("created_at") or 0)
        if not ts or ts < horizon or ts > now:
            continue
        local = ts + tz_offset_hours * 3600
        if (local // DAY + 4) % 7 != weekday:
            continue
        per_week[(now - ts) // (7 * DAY)] += 1

    # ── A WEEK THE SHOP WAS OPEN AND SAW NOBODY IS A SAMPLE OF ZERO ─────────────────────────
    # `per_week` only has keys for weeks that had a visit, so a workshop that closes every Friday
    # was measured on the Fridays it opened and nothing else: `counts` held two samples of 12 and
    # the reserve held back twelve messages every Friday for a day that reliably brings none.
    # Missing is not absent — it is zero, and the percentile has to see it to be a percentile of
    # anything real.
    #
    # BOUNDED BY THE SHOP'S AGE for the same reason as `expected_flow`: weeks before it opened are
    # not zeros, they are nothing, and padding with them would drive every young shop to the floor.
    lived = 0
    for v in visits:
        ts = int(v.get("occurred_at") or v.get("created_at") or 0)
        if ts and horizon <= ts <= now:
            lived = max(lived, min(weeks, (now - ts) // (7 * DAY) + 1))
    counts = sorted(per_week.get(w, 0) for w in range(lived))
    if not counts:
        # NO HISTORY IS NOT ZERO DEMAND. A new shop reserves the floor, and the campaign waits.
        return {"reserve": floor, "basis": "floor", "weekday": weekday, "samples": 0}

    # The percentile, by nearest rank — no interpolation, because a reserve of 12.4 visitors is a
    # precision we do not have and cannot act on.
    idx = min(len(counts) - 1, max(0, int(round(percentile * len(counts))) - 1))
    picked = counts[idx]

    # AND THE PERCENTILE ALONE DOES NOT REJECT THE OUTLIER, which was the whole reason for
    # choosing it. With eight weekly samples the 95th percentile IS the maximum — the rank is the
    # last one — so a single Eid Thursday would set the reserve for the next two months and no
    # campaign would launch. Caught by the test written to prove the opposite.
    #
    # So the percentile is clamped to a multiple of the MEDIAN, which is what actually makes it
    # robust: the median cannot be moved by one freak week, and a real trend moves both together.
    median = counts[len(counts) // 2]
    if median and picked > median * outlier_factor:
        picked = int(median * outlier_factor)

    want = max(picked, floor)
    basis = "percentile" if picked >= floor else "floor"

    return {"reserve": want, "basis": basis, "weekday": weekday, "samples": len(counts)}


def retention_series(visits: list[dict], *, now: int, points: int = 6,
                     window_days: int = 180, step_days: int = 30,
                     min_customers: int = 20) -> dict[str, Any]:
    """Return rate as a LINE, not a snapshot (spec: proof 1).

    EVERY OTHER NUMBER ON THIS SCREEN ANSWERS «كم الآن» AND NONE OF THEM ANSWERS «كم كان». An owner
    deciding whether to keep paying is asking the second question, and until now the product's own
    answer to it was a shrug — he had one figure with nothing to compare it against, so a return
    rate of 46% was neither good news nor bad.

    THE MEASUREMENT MUST NOT MOVE WHILE THE THING IT MEASURES DOES. Each point is the same
    calculation — `return_rate` over a trailing window of the same length — ending one step earlier
    than the point after it. Anything else (all visits to date, say) makes the early points a
    different measurement from the late ones, and the line then shows the method changing rather
    than the shop.

    A WINDOW WIDE ENOUGH TO CONTAIN A CYCLE. A workshop's customer returns every three months; a
    thirty-day window would call every one of them a one-time visitor and draw a flat line at zero
    for a shop doing fine. 180 days holds two cycles for most trades, and a step of 30 gives a
    point a month without the points being independent — which is the intent: this is a trend, and
    a trend is smoothed by construction.

    AND A POINT WITH TOO FEW PEOPLE IN IT IS NOT DRAWN. Six customers in a window make a rate that
    swings twenty points when one of them returns, and a line that jumps like that teaches its
    reader to ignore it. Those points are `None` — a gap in the line, not a zero, because a zero
    here reads as «nobody came back» which is a different and much worse sentence.
    """
    times = sorted(int(v.get("occurred_at") or v.get("created_at") or 0) for v in visits)
    if not times:
        return {"points": [], "learning": True, "have": 0, "need": min_customers}

    window = window_days * DAY
    step = step_days * DAY
    out: list[dict[str, Any]] = []
    for i in range(points - 1, -1, -1):
        end = now - i * step
        start = end - window
        slice_ = [v for v in visits
                  if start <= int(v.get("occurred_at") or v.get("created_at") or 0) <= end]
        people = len(_by_customer(slice_))
        out.append({
            "at": end,
            "customers": people,
            # None, never 0.0 — see the docstring. The screen draws a gap.
            "value": round(return_rate(slice_), 3) if people >= min_customers else None,
        })

    drawn = [p for p in out if p["value"] is not None]
    if not drawn:
        # STILL LEARNING IS A STATE, NOT AN ABSENCE — the same contract the association engine
        # uses, so the screen can render both with one component and one sentence.
        newest = out[-1]["customers"] if out else 0
        return {"points": [], "learning": True, "have": newest, "need": min_customers}

    first, last = drawn[0], drawn[-1]
    delta = round(last["value"] - first["value"], 3)
    return {
        "points": out,
        "learning": False,
        "first": first["value"],
        "last": last["value"],
        "delta": delta,
        # THE BASELINE IS THE OLDEST POINT WE CAN DEFEND, not the day he signed up: a shop that
        # joined last week has no before, and inventing one from three visits would make our own
        # improvement look enormous. When the history is short, first == last and delta is 0 —
        # honest, and it fixes itself as months accumulate.
        "months": len(drawn),
    }


def holdout_comparison(visits: list[dict], *, tenant: str, now: int,
                       window_days: int = 180, share: int = 10,
                       min_each: int = 15, enabled: bool = False) -> dict[str, Any]:
    """The two groups, side by side (proof 2).

    THE ONLY NUMBER IN THIS PRODUCT THAT IS NOT OUR WORD FOR OUR OWN WORK. Everything else says how
    his shop is doing; this says what our engine did to it, measured against the tenth of his
    customers it deliberately left alone.

    IT REFUSES FAR MORE OFTEN THAN IT SPEAKS, and that is the design. Fifteen people on each side is
    already a thin comparison, and below it a single returning customer moves the answer by seven
    points — which would let us claim a triumph, or confess a disaster, on the strength of one man
    changing his oil. When either side is too small the answer is «لم يكتمل القياس» and a count of
    how far along it is, exactly as the association engine does while it learns.

    NO VERDICT IS WRITTEN HERE. The function reports two rates and the gap between them; whether
    that gap is good news is a sentence for the screen, and one the owner is entitled to read
    against his own judgement rather than have asserted at him.
    """
    from app.core import holdout as H          # local: the module is a shared contract, not a dep

    # NOTHING WITHHELD MEANS NOTHING MEASURED, and saying so is the whole point of this file.
    #
    # This function splits customers by the same hash `reminders` uses — but if `reminders` has the
    # holdout switched OFF, the «held» tenth received every message the rest did. The two rates
    # then differ only by noise, and with enough traffic the card reports that noise as our
    # engine's effect: the one number in this product that is not our word for our own work,
    # manufactured out of nothing. The card must say it is not measuring rather than measure air.
    if not enabled:
        return {"ready": False, "reason": "holdout_off", "held": 0, "reached": 0,
                "need": min_each}

    cutoff = now - window_days * DAY
    recent = [v for v in visits
              if int(v.get("occurred_at") or v.get("created_at") or 0) >= cutoff]
    if not recent:
        return {"ready": False, "reason": "no_visits", "held": 0, "reached": 0, "need": min_each}

    held: list[dict] = []
    reached: list[dict] = []
    for v in recent:
        ref = str(v.get("subject_ref") or "")
        if not ref:
            continue
        (held if H.is_holdout(tenant, ref, share=share) else reached).append(v)

    held_people = len(_by_customer(held))
    reached_people = len(_by_customer(reached))
    if held_people < min_each or reached_people < min_each:
        return {"ready": False, "reason": "learning", "held": held_people,
                "reached": reached_people, "need": min_each}

    held_rate = round(return_rate(held), 3)
    reached_rate = round(return_rate(reached), 3)
    return {
        "ready": True,
        "held": held_people,
        "reached": reached_people,
        "held_rate": held_rate,
        "reached_rate": reached_rate,
        "gap": round(reached_rate - held_rate, 3),
        "window_days": window_days,
    }


def returned_after_reminder(visits: list[dict], sends: list[dict], *, now: int,
                            window_days: int = 30, attribute_days: int = 14,
                            have_log: bool = False, partial_log: bool = False) -> dict[str, Any]:
    """Visits that followed a reminder closely enough to be credited to it (proof 3).

    THE HONEST UNIT IS A VISIT, NOT A RIYAL. We hold no prices — the amount lives in his till and
    we deliberately never stored it — so «سدّدت الباقة نفسها» is his arithmetic to do: we say 64
    visits came back after a reminder, and he multiplies by the average bill only he knows.

    ATTRIBUTION IS DELIBERATELY MEAN TO US. A visit counts only if it happened within `attribute_days`
    of a message AND the customer had no visit in the same window before it. Anything looser starts
    crediting the engine with people who were coming anyway — which is the same self-flattery the
    ladder's own lock exists to prevent, arriving through the reporting side instead.

    IT IS A COUNT, NOT A RATE, on purpose. A percentage invites the question "of what?", and every
    honest denominator here (people messaged? people due? people alive?) is arguable. A count is
    not.

    ────────────────────────────────────────────────────────────────────────────────────────────
    THE COUNTED THING IS A VISIT, AND IT IS COUNTED ONCE (ي-4)

    The credit loop ran over MESSAGES. A customer who got a reminder on Sunday and another on
    Tuesday, and walked in on Wednesday, was two returned visits — one person, one visit, counted
    twice. The number was therefore inflated by roughly the messages-per-customer ratio, which is
    highest at exactly the shops sending most, and the owner multiplies it by his average bill to
    decide whether to renew. So the qualifying VISIT moments are collected into a set per customer
    and it is the set that is counted.

    ────────────────────────────────────────────────────────────────────────────────────────────
    AND IT REFUSES WHEN THERE IS NO SEND LOG TO JOIN AGAINST (ي-3)

    `reminders` holds the only send log there is. When that read fails the peer answers with an
    empty `sends` list — and an empty list through this function produced `0`, rendered as a
    confident «0 زيارة عادت بعد رسالة». That is our outage printed as the engine's failure, in the
    one number that argues for renewal. `have_log` is the caller stating that it actually read the
    log; absent, the answer is «لم نستطع القياس», which is what `opt_out_rate` beside it has always
    said in the same situation.

    `partial_log` says the log came back capped: older sends are missing, so the count is a FLOOR
    rather than the figure. Reported rather than hidden — the shops that hit the cap are the busy
    ones, and a floor they can see is worth more than a total they cannot check.
    """
    if not have_log:
        return {"ready": False, "reason": "no_send_log", "window_days": window_days}

    cutoff = now - window_days * DAY
    win = attribute_days * DAY

    by_customer: dict[str, list[int]] = {}
    for v in visits:
        ref = str(v.get("subject_ref") or "")
        at = int(v.get("occurred_at") or v.get("created_at") or 0)
        if ref and at:
            by_customer.setdefault(ref, []).append(at)
    for times in by_customer.values():
        times.sort()

    # customer -> the moments of their visits that some message can be credited with. A SET, so the
    # second message pointing at the same walk-in adds nothing.
    credited_visits: dict[str, set[int]] = {}
    for msg in sends:
        ref = str(msg.get("subject_ref") or "")
        sent_at = int(msg.get("at") or 0)
        if not ref or sent_at < cutoff:
            continue
        times = by_customer.get(ref) or []
        # the first visit after the message, inside the window
        after = next((t for t in times if sent_at <= t <= sent_at + win), 0)
        if not after:
            continue
        # AND NOBODY WHO WAS ALREADY IN THE SHOP. A visit the same week as the message, but BEFORE
        # it, means the person had already come back; crediting the message would be counting our
        # own confirmation as a return.
        before = any(sent_at - win <= t < sent_at for t in times)
        if not before:
            credited_visits.setdefault(ref, set()).add(after)

    return {"ready": True, "visits": sum(len(s) for s in credited_visits.values()),
            "window_days": window_days, "attribute_days": attribute_days,
            "partial": bool(partial_log)}


def opt_out_rate(sent_count: int, opt_outs: int, *, per: int = 1000,
                 min_sends: int = 200, have_log: bool = False,
                 partial_log: bool = False) -> dict[str, Any]:
    """Stops per thousand messages — the warning that arrives before a number is blocked (proof 4).

    A BLOCKED NUMBER DOES NOT LOSE A MESSAGE, IT LOSES THE CHANNEL — for every customer of that
    shop, for good. The signal that precedes it is people pressing stop, and until now that fact
    was a flag on a preference row with no moment attached to it, so nobody could see it rising.

    NOT COMPUTED UNDER TWO HUNDRED SENDS. One stop in fifty messages is twenty per thousand, which
    would light a warning on a shop that has done nothing wrong — and a warning that cries wolf in
    the first week is one nobody reads in the month it matters.

    «WE COULD NOT READ THE LOG» IS NOT «YOU SENT NOTHING» (ي-3). An unreadable send log used to
    arrive here as `sent_count = 0` — `int(x or 0)` on a missing field — and the card then told a
    shop that had sent forty thousand messages that it had sent none. `have_log` is the caller
    stating it actually read the log; without it the refusal names our failure rather than his.

    AND A CAPPED LOG IS A SAMPLE, NOT THE PERIOD (ي-6). `reminders` returns `truncated` when the
    window held more rows than it would send; both the stops and the sends are then counted over
    the newest slice, which is a real rate over a shorter period than the label claims. `partial`
    travels with the number so the screen can say which — the alternative is a card that goes
    quietest at the shops sending most, which is the opposite of what it is for.
    """
    if not have_log:
        return {"ready": False, "reason": "no_send_log", "need": min_sends}
    if sent_count < min_sends:
        return {"ready": False, "reason": "too_few_sends", "sent": sent_count, "need": min_sends}
    rate = round((opt_outs / sent_count) * per, 1)
    return {"ready": True, "sent": sent_count, "opt_outs": opt_outs, "per": per, "rate": rate,
            "partial": bool(partial_log)}
