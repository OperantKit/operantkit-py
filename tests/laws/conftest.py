"""Shared runner and measures for the behavioral-law suite.

Each law test runs a virtual subject on a contingency-dsl schedule through
the public pipeline (contingency-dsl → contingency-py schedule →
session-runner → experiment-io ``drive``) and judges the event record
against values published in the experimental literature. The thresholds
are fixed before the run and are not tuned to the subjects' output.

Every law is run under ten subject seeds (``SEEDS``) and must hold for all
of them. Schedule values (Fleshler-Hoffman sequences) use ``FH_SEED``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import median

from contingency.bridge import from_dsl
from contingency.entities import Outcome, Reinforcer
from contingency.entities import ResponseEvent as ScheduleResponse
from contingency.interfaces import Schedule
from contingency_dsl import parse
from contingency_dsl.annotations.temporal.extension import TemporalExtension
from contingency_dsl.extensions import ExtensionRegistry
from experiment_core import ReinforcementCountExit
from experiment_core.events import (
    ReinforcerEndEvent,
    ReinforcerStartEvent,
    ResponseEvent,
    SessionEvent,
)
from experiment_io import drive
from experiment_io.hw.backends.virtual import (
    ManualClock,
    MultiVirtualOperandum,
    RecordingReinforcer,
    VirtualOperandum,
)
from session_analyzer.analytics.schneider_segment import schneider_two_state
from session_runner import SessionConfig, SessionRunner

SEEDS = tuple(range(10))
FH_SEED = 42

_ANNOTATIONS = ExtensionRegistry.build(TemporalExtension())


@dataclass
class Record:
    """Event times from one session, split by operandum where it applies."""

    responses: list[float] = field(default_factory=list)
    response_operanda: list[int | None] = field(default_factory=list)
    reinforcer_starts: list[float] = field(default_factory=list)
    reinforcer_operanda: list[int | None] = field(default_factory=list)
    reinforcer_ends: list[float] = field(default_factory=list)

    def emit(self, event: SessionEvent) -> None:
        if isinstance(event, ResponseEvent):
            self.responses.append(event.timestamp)
            self.response_operanda.append(event.operandum)
        elif isinstance(event, ReinforcerStartEvent):
            self.reinforcer_starts.append(event.timestamp)
            self.reinforcer_operanda.append(event.operandum)
        elif isinstance(event, ReinforcerEndEvent):
            self.reinforcer_ends.append(event.timestamp)

    def count(self, operandum: int) -> tuple[int, int]:
        """Responses and reinforcers on one operandum."""
        return (
            sum(1 for o in self.response_operanda if o == operandum),
            sum(1 for o in self.reinforcer_operanda if o == operandum),
        )


def run_session(
    dsl: str,
    subject: object,
    *,
    reinforcers: int,
    reinforcer_duration_s: float,
    operanda: int = 1,
    schedule: Schedule | None = None,
) -> Record:
    """Run one session of ``dsl`` until ``reinforcers`` reinforcers and record it.

    ``schedule`` replaces the schedule built from ``dsl`` (used for the
    yoked VI, whose intervals come from another session); ``dsl`` is then
    only recorded in the session metadata.
    """
    if schedule is None:
        schedule = from_dsl(parse(dsl, extensions=_ANNOTATIONS))
    clock = ManualClock()
    if operanda == 1:
        ops = [VirtualOperandum(0, subject, clock)]
    else:
        ops = MultiVirtualOperandum(subject, clock).split()
    record = Record()
    runner = SessionRunner(
        SessionConfig(
            name="law",
            schedule=schedule,
            exit_condition=ReinforcementCountExit(count=reinforcers),
            metadata={"dsl": dsl},
        ),
        sink=record,
        clock=clock,
    )
    runner.start(start_time=clock())
    drive(
        runner,
        operanda=ops,
        reinforcers=[RecordingReinforcer(operandum_index=i) for i in range(len(ops))],
        clock=clock,
        reinforcer_duration=reinforcer_duration_s,
        max_steps=1_000_000,
    )
    return record


def intervals(record: Record) -> list[tuple[float, float, list[float]]]:
    """Inter-reinforcement intervals as ``(onset, end, responses)``.

    An interval runs from the end of the previous reinforcer (or the
    session start) to the next reinforcer; the reinforcer duration is
    excluded. ``responses`` holds the response times inside it, the
    reinforced response included.
    """
    onsets = [0.0, *record.reinforcer_ends[: len(record.reinforcer_starts) - 1]]
    out = []
    for onset, end in zip(onsets, record.reinforcer_starts, strict=True):
        out.append((onset, end, [t for t in record.responses if onset <= t <= end]))
    return out


class YokedVI:
    """Variable-interval schedule whose intervals are given in advance.

    The ``k``-th interval starts at the ``(k - 1)``-th reinforced response
    (at the session start for the first) and sets up a reinforcer for the
    first response at or after its end. Pass the inter-reinforcement times
    of a master session, each but the first lengthened by the reinforcer
    duration, to time each interval from the end of the previous
    reinforcer (Catania et al., 1977). After the last interval no further
    reinforcer is set up (the intervals are not repeated).
    """

    def __init__(self, intervals_s: Sequence[float]) -> None:
        if not intervals_s or any(v <= 0 for v in intervals_s):
            raise ValueError(f"intervals must be non-empty and > 0, got {intervals_s!r}")
        self._intervals = list(intervals_s)
        self.reset()

    def step(self, now: float, event: ScheduleResponse | None = None) -> Outcome:
        if event is None or now + 1e-9 < self._arm_time:
            return Outcome()
        if self._next < len(self._intervals):
            self._arm_time = now + self._intervals[self._next]
        else:
            self._arm_time = math.inf
        self._next += 1
        return Outcome(reinforced=True, reinforcer=Reinforcer(time=now))

    def reset(self) -> None:
        self._arm_time = self._intervals[0]
        self._next = 1


def response_rate(record: Record) -> float:
    """Responses per second over the inter-reinforcement intervals.

    Reinforcer time is excluded, as in Catania et al. (1977).
    """
    spans = intervals(record)
    return sum(len(r) for _, _, r in spans) / sum(end - onset for onset, end, _ in spans)


def segment_counts(onset: float, end: float, responses: Sequence[float], n: int) -> list[int]:
    """Response counts in ``n`` equal segments of ``[onset, end]``."""
    width = (end - onset) / n
    counts = [0] * n
    for t in responses:
        counts[min(n - 1, int((t - onset) / width))] += 1
    return counts


def increase_fraction(per_interval_counts: Sequence[Sequence[int]]) -> float:
    """Share of segment-to-segment steps with a higher rate (Dews, 1978).

    Steps are counted from the first segment with responding onward; the
    step into that first segment is excluded.
    """
    up = steps = 0
    for counts in per_interval_counts:
        first = next((i for i, c in enumerate(counts) if c > 0), None)
        if first is None:
            continue
        for i in range(first + 1, len(counts)):
            steps += 1
            up += counts[i] > counts[i - 1]
    return up / steps


def fifth_to_first_ratio(per_interval_counts: Sequence[Sequence[int]]) -> float:
    """Pooled rate in the 5th segment after responding starts over the 1st (Dews, 1978)."""
    first_total = fifth_total = 0
    for counts in per_interval_counts:
        first = next((i for i, c in enumerate(counts) if c > 0), None)
        if first is None or first + 4 >= len(counts):
            continue
        first_total += counts[first]
        fifth_total += counts[first + 4]
    return fifth_total / first_total


def index_of_curvature(onset: float, end: float, responses: Sequence[float], n: int = 4) -> float:
    """Fry, Kelleher & Cook's (1960) index of curvature.

    ``I = ((n - 1) R_n - 2 sum_{i<n} R_i) / (n R_n)`` with ``R_i`` the
    cumulative responses at the end of the ``i``-th of ``n`` equal
    divisions: 0 for a constant rate, up to ``(n - 1) / n`` for all
    responses in the last division.
    """
    counts = segment_counts(onset, end, responses, n)
    cumulative = [sum(counts[: i + 1]) for i in range(n)]
    r_n = cumulative[-1]
    return ((n - 1) * r_n - 2 * sum(cumulative[:-1])) / (n * r_n)


@dataclass(frozen=True)
class TwoState:
    """Two-line fit to one interval's cumulative record (Schneider, 1969)."""

    break_fraction: float
    low_rate: float
    high_rate: float


def two_state_fit(
    onset: float, end: float, responses: Sequence[float], *, grid: int = 200
) -> TwoState | None:
    """Schneider's (1969) least-squares breakpoint, from session-analyzer.

    The cumulative record of the interval is fitted by a line through the
    origin up to the breakpoint and a second line joined to it at the
    breakpoint; the breakpoint is moved along a grid of the interval and
    the one with the smallest sum of squared deviations is kept. Returns
    ``None`` for fewer than four responses.
    """
    fit = schneider_two_state(
        responses, interval_start=onset, interval_end=end, grid=grid
    )
    if fit is None:
        return None
    return TwoState(fit.pause_duration / (end - onset), fit.low_rate, fit.high_rate)


def spread(values: Sequence[float]) -> str:
    """``median [min, max]`` for assertion messages and the evidence log."""
    return f"{median(values):.3f} [{min(values):.3f}, {max(values):.3f}]"
