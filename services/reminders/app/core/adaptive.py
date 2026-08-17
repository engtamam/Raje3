"""Learning one customer's rhythm for one service (spec 5.2 – 5.4).

THE PRODUCT CLAIM IS SPECIFIC: "the customer who returns every two months is reminded every two
months, and the one who returns every four months is adapted to gradually." Not a per-shop average
— that is one number for everybody, which is the thing this replaces.

THE METHOD is an exponentially weighted moving average: the new estimate is the old one nudged
toward what we just observed. It is chosen for three properties, in this order:

  It never jumps.        One observation moves the estimate by a fraction of the gap, so a single
                         odd visit cannot rewrite a customer's schedule.
  It needs no history.   The estimate is the state. We do not keep a list of past intervals, which
                         means no unbounded row and no window that quietly forgets.
  It is explainable.     An owner asking "why 97 days?" gets an answer: it started at 90 and three
                         visits pulled it toward 110. A model nobody can explain is a model an
                         owner switches off.

THREE GUARDS AROUND IT, AND EACH EXISTS BECAUSE THE BARE AVERAGE FAILS WITHOUT IT:

  BOUNDS (5.4)           A learned interval is clamped per service. Oil at 400 days is not
                         learning, it is a customer who moved away and came back — and a reminder
                         built on it arrives after the engine has already failed.

  ANOMALY FILTER (5.4)   A gap wildly outside the current estimate is DISCARDED from learning, and
                         counted. The customer who travelled for six months should not stretch
                         their own schedule for the rest of their life.

  A WARM-UP              Below two observations the estimate is the service's default wearing a
                         different hat. The API says so rather than presenting a guess as learning
                         — an owner who is told "learned: 90 days" from zero data stops trusting
                         every number the screen shows.

WHY THE PARAMETERS ARE SETTINGS AND NOT CONSTANTS: the right smoothing factor for a car wash is
not the right one for a workshop, and we do not know either of them yet. What we know is the
shape. Freezing a guess into code is how a tunable becomes a rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass

DAY = 86400


@dataclass(frozen=True)
class AdaptiveConfig:
    """The knobs, with defaults that are deliberate rather than round.

    `alpha = 0.3` moves the estimate roughly a third of the way toward each observation: three
    consistent visits get most of the way to a customer's true rhythm, while one outlier moves it
    by a tenth of the error. Faster and it chases noise; slower and a genuine change in habit takes
    a year to register.

    `anomaly_factor = 2.5` discards a gap more than two and a half times the current estimate. Wide
    on purpose — a customer who is merely late is signal, and a filter that trims real variation
    learns a rhythm nobody actually has.
    """
    alpha: float = 0.3
    anomaly_factor: float = 2.5
    min_days: float = 7.0
    max_days: float = 730.0
    # Observations before the estimate is presented as learned rather than defaulted.
    warmup: int = 2


def observe(*, current_days: float, observed_days: float, observations: int,
            cfg: AdaptiveConfig, min_days: float | None = None,
            max_days: float | None = None) -> tuple[float, bool]:
    """Fold one observed gap into the estimate.

    Returns `(new_interval_days, was_anomaly)`. The caller records the anomaly count rather than
    this function raising: a customer whose every visit is an anomaly is not an anomaly — it is a
    default that is wrong for them, and only that counter can ever reveal it.
    """
    lo = cfg.min_days if min_days is None else min_days
    hi = cfg.max_days if max_days is None else max_days

    # A non-positive gap is not an observation. Two visits in one day happen — three cars, one
    # owner — and treating that as "returns every 0 days" would drive the estimate to the floor
    # and put this customer on a weekly reminder for a service they get twice a year.
    if observed_days <= 0:
        return _clamp(current_days, lo, hi), False

    # THE FIRST REAL OBSERVATION IS TRUSTED MORE THAN THE DEFAULT, because the default is a guess
    # about a service and this is a fact about a person. Without this the first genuine visit moves
    # the estimate by alpha only, and a customer with a 30-day rhythm sits on a 90-day default for
    # four visits — long enough for the owner to conclude the feature does not work.
    if observations <= 0:
        return _clamp(observed_days, lo, hi), False

    # ANOMALY: too far from what we believe, in either direction. Checked BEFORE the blend, so a
    # discarded observation leaves the estimate untouched rather than half-moved.
    if observed_days > current_days * cfg.anomaly_factor or \
            observed_days * cfg.anomaly_factor < current_days:
        return _clamp(current_days, lo, hi), True

    blended = (1 - cfg.alpha) * current_days + cfg.alpha * observed_days
    return _clamp(blended, lo, hi), False


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp, and round to one decimal.

    Rounded because this number is shown to an owner and 96.87500000000001 reads as a bug in a
    screen that is otherwise plain. One decimal keeps the movement visible between visits — round
    to whole days and three consecutive visits can look like nothing happened.
    """
    return round(max(lo, min(hi, value)), 1)


def next_due_at(*, last_visit_at: int, interval_days: float, lead_days: float,
                now: int) -> int:
    """When the reminder for this service should go out (spec 5.7).

    LEAD DAYS ARE SUBTRACTED, not added: the message is meant to arrive with enough time to book,
    not on the day the service is already overdue. Five to seven days is the target, per service.

    NEVER SCHEDULES INTO THE PAST. A customer whose interval shrank — or whose visit was recorded
    late by an offline till draining a week of records — would otherwise get a reminder dated
    yesterday, which the tick sends immediately: an apparently random message with no cause the
    owner can see. Anything already due is pushed to a short grace period from now.
    """
    due = last_visit_at + int(interval_days * DAY) - int(lead_days * DAY)
    floor = now + int(0.5 * DAY)
    return max(due, floor)


def is_learned(observations: int, cfg: AdaptiveConfig) -> bool:
    """Whether the estimate may be PRESENTED as learned.

    Separate from whether it is used — a defaulted interval is still the best number we have and
    is still scheduled on. This only governs what the screen is allowed to claim.
    """
    return observations >= cfg.warmup
