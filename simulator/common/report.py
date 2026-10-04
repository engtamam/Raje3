"""Stage 8 of the simulator's own build plan (see ../README.md): observation — capturing what
happened AND the explicit pass/fail tolerance against it, together (Chaos Toolkit's own "steady-
state hypothesis + tolerances" pairing — see the README's own research section for why these two
travel together rather than being left for a human to eyeball a raw number and decide for
themselves).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .action import ActionResult
from .checks import CheckResult


@dataclass
class Report:
    """One summary over a batch of ActionResults. `durations` is optional — a plain `run_one`/
    `run_concurrent` call carries no timing, only `common/load.py::run_load` does; a Report built
    without durations simply answers `None` for every latency figure rather than fabricating one."""

    count: int
    ok_count: int
    fail_count: int
    error_count: int
    durations: list[float] = field(default_factory=list)

    @property
    def error_rate(self) -> float:
        return self.fail_count / self.count if self.count else 0.0

    def _percentile(self, p: float) -> float | None:
        if not self.durations:
            return None
        ordered = sorted(self.durations)
        # nearest-rank method — simple, deterministic, no interpolation needed for this scale.
        index = max(0, min(len(ordered) - 1, int(round(p * (len(ordered) - 1)))))
        return ordered[index]

    @property
    def mean_seconds(self) -> float | None:
        return sum(self.durations) / len(self.durations) if self.durations else None

    @property
    def p95_seconds(self) -> float | None:
        return self._percentile(0.95)

    @property
    def max_seconds(self) -> float | None:
        return max(self.durations) if self.durations else None

    def __repr__(self) -> str:
        lat = f", p95={self.p95_seconds:.3f}s" if self.durations else ""
        return (f"<Report {self.ok_count}/{self.count} ok, "
               f"error_rate={self.error_rate:.1%}{lat}>")


def summarize(results: list[ActionResult], *, durations: list[float] | None = None) -> Report:
    return Report(
        count=len(results),
        ok_count=sum(1 for r in results if r.ok),
        fail_count=sum(1 for r in results if not r.ok),
        error_count=sum(1 for r in results if r.error is not None),
        durations=list(durations) if durations else [],
    )


@dataclass
class Tolerance:
    """A scenario's own explicit pass/fail gate against a Report — never left implicit. Any field
    left `None` is simply not checked; a Tolerance with every field `None` always passes, which is
    a real, valid choice (a scenario that only wants the raw numbers, not a verdict)."""

    max_error_rate: float | None = None
    max_p95_seconds: float | None = None
    max_mean_seconds: float | None = None

    def check(self, report: Report) -> CheckResult:
        violations: list[str] = []
        if self.max_error_rate is not None and report.error_rate > self.max_error_rate:
            violations.append(
                f"error_rate {report.error_rate:.1%} > tolerance {self.max_error_rate:.1%}")
        if self.max_p95_seconds is not None and report.p95_seconds is not None \
                and report.p95_seconds > self.max_p95_seconds:
            violations.append(
                f"p95 {report.p95_seconds:.3f}s > tolerance {self.max_p95_seconds:.3f}s")
        if self.max_mean_seconds is not None and report.mean_seconds is not None \
                and report.mean_seconds > self.max_mean_seconds:
            violations.append(
                f"mean {report.mean_seconds:.3f}s > tolerance {self.max_mean_seconds:.3f}s")
        if violations:
            return CheckResult(ok=False, detail="; ".join(violations))
        return CheckResult(ok=True, detail=f"within tolerance ({report!r})")
