"""Is this box idle enough to run something expensive right now — the ONE question
`translations_jobs_run` (api/internal.py) asks before it lets `Nllb200TranslationEngine` load a
model and burn CPU on a weak, shared server.

NO SEPARATE SCHEDULER, NO K8S CronJob RESOURCE — job-service's own schedule (a plain cron timer,
`deploy/hooks/job-schedule.sh`) fires this route every couple of minutes regardless of load; the
"only when idle" behaviour lives ENTIRELY in this one cheap check at the top of that route. A
schedule that fires and finds the box busy just returns immediately, tries again next time — the
same "delayed, never lost" posture `salla_refresh_scan`'s own docstring already gives a scan that
finds nothing to do.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def is_idle(threshold: float = 0.7) -> bool:
    """`os.getloadavg()[0]` (the 1-minute load average) against the box's own CPU count — the
    standard, dependency-free Linux signal for "how busy is this machine right now", read fresh
    on every call (never cached: the whole point is this minute's answer, not five minutes ago's).

    `threshold` IS A FRACTION OF CPU COUNT, NOT A RAW LOAD NUMBER — 0.7 means "idle" until the
    1-minute average crosses 70% of every core this box has, so the same threshold means the same
    thing on a 2-core box and a 16-core one, instead of a raw cutoff someone has to re-tune every
    time the server is resized.

    UNSUPPORTED PLATFORM (Windows, or any sandbox `getloadavg` is not wired on) OR ANY OTHER
    FAILURE READING IT ANSWERS TRUE — "idle" — deliberately, not "busy": this function exists to
    let real work through on a genuinely quiet box, and the failure mode of "we could not tell, so
    we never translate anything" is worse than the failure mode of "we could not tell, so we ran
    the job-service route's OWN caller check would have refused it (as `TranslationEngineUnavailable`
    on a broken model does) if that guess turned out wrong. Logged, once per failure, never silently.
    """
    try:
        load1, _load5, _load15 = os.getloadavg()
        cpus = os.cpu_count() or 1
        return load1 <= threshold * cpus
    except (OSError, AttributeError) as exc:
        logger.warning("is_idle: load average unavailable (%s) — treating as idle", exc)
        return True
