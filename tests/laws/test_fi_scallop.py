"""The fixed-interval scallop, judged against published values.

A subject whose response rate grows with time since reinforcement
(``ScallopSubject``) runs ``FI 60-s`` for 30 reinforcers under each of ten
seeds. Its rate rises as the fourth power of the time since reinforcement
up to 2 responses/s at 60 s, and its IRTs at a constant rate have a
coefficient of variation of 0.3 (more regular than a Poisson process). Both
are needed: with the rate rising as the square of time the index of
curvature stays near the cubic record's 0.469, and with Poisson IRTs the
count noise between 6-s segments keeps the share of rising steps near 0.6.
Four measures of the within-interval pattern are compared with values
reported for pigeons and monkeys; the thresholds come from the papers, not
from this subject's output:

- F1, breakpoint: Schneider (1969) — the transition from the low to the
  high rate falls "at about two-thirds of the way through the interval"
  (slope 0.67). Pass: the median breakpoint is 0.67 ± 0.15 of the interval
  (the ±0.15 is this suite's own margin).
- F2, segment-to-segment increase: Dews (1978) — the rate rose from one
  segment to the next in 303 of 389 and 310 of 419 segments. Pass: at least
  0.74 of the steps rise (the lower animal). Auxiliary: the fifth segment
  after responding starts has at least twice the rate of the first (half of
  Dews's 4.5, this suite's margin).
- F3, index of curvature: Fry, Kelleher & Cook (1960) — scalloped records
  gave +.560 to +.715 with four divisions, flattened records −.054 and
  +.010. Pass: the median index is at least 0.56.
- F4, location of the rate peak: Lowe & Harzem (1977) — the peak of the
  within-interval rate curve lay at 0.80 to 0.92 of the interval in
  pigeons. Pass: the highest of ten segments is one of the last three in at
  least 24 of 30 intervals (the 80% is this suite's margin).
- F5, quarter-life (Herrnstein & Morse, 1957) is reported but not judged.

A constant-rate Poisson responder is the control: it must fail F1–F4
(failing the law) and pass the schedule invariant (successive reinforcers
at least 60 s apart). If the control broke the invariant, the fault would
lie in the schedule engine rather than in the subject.

Killeen's (1994) MPR (``MprSubject``, interval coupling, published pigeon FI
values) runs the same procedure. It predicts a pause of about half the
interval followed by a constant rate, so the checks that need a rising rate
are recorded as strict expected failures (``expectations.py``). The pause
fraction 0.5 and the reinforcement rate assumed before the first reinforcer
(one per minute) are this suite's choices, not fitted values.

References
----------
Dews, P. B. (1978). Studies on responding under fixed-interval schedules of
    reinforcement: II. The scalloped pattern of the cumulative record.
    *Journal of the Experimental Analysis of Behavior*, *29*(1), 67–75.
    https://doi.org/10.1901/jeab.1978.29-67
Fry, W., Kelleher, R. T., & Cook, L. (1960). A mathematical index of
    performance on fixed-interval schedules of reinforcement. *Journal of the
    Experimental Analysis of Behavior*, *3*(3), 193–199.
    https://doi.org/10.1901/jeab.1960.3-193
Lowe, C. F., & Harzem, P. (1977). Species differences in temporal control of
    behavior. *Journal of the Experimental Analysis of Behavior*, *28*(2),
    189–201. https://doi.org/10.1901/jeab.1977.28-189
Schneider, B. A. (1969). A two-state analysis of fixed-interval responding
    in the pigeon. *Journal of the Experimental Analysis of Behavior*,
    *12*(5), 677–687. https://doi.org/10.1901/jeab.1969.12-677
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cache
from statistics import median

import pytest
from conftest import (
    SEEDS,
    increase_fraction,
    fifth_to_first_ratio,
    index_of_curvature,
    intervals,
    run_session,
    segment_counts,
    spread,
    two_state_fit,
)
from expectations import FI_SCALLOP, law_cases
from experiment_io.hw.backends.virtual import MprSubject, ScallopSubject, VirtualSubject
from session_analyzer.analytics.prp import compute_quarter_life

DSL = "FI 60-s"
INTERVAL_S = 60.0
REINFORCERS = 30
REINFORCER_DURATION_S = 0.5
SCALLOP_MAX_RATE_HZ = 2.0
SCALLOP_EXPONENT = 4.0
SCALLOP_CV = 0.3

BREAKPOINT = 0.67  # Schneider (1969)
BREAKPOINT_MARGIN = 0.15  # this suite's margin
INCREASE_FRACTION = 0.74  # Dews (1978), 310 / 419
FIFTH_TO_FIRST = 2.0  # half of Dews's (1978) 4.5
CURVATURE = 0.56  # Fry et al. (1960), lowest scalloped example, n = 4
CURVATURE_MIN_RESPONSES = 8
FLAT_CURVATURE = 0.1  # around Fry et al.'s flattened −.054 / +.010
LATE_PEAK_SEGMENTS = 3  # peak at >= 0.8 of the interval, Lowe & Harzem (1977)
LATE_PEAK_INTERVALS = 24  # of 30, this suite's margin
MPR_PAUSE_FRACTION = 0.5  # Killeen (1994): "about half of the interval"
MPR_INITIAL_R = 1.0 / 60.0  # reinforcers/s before the first reinforcer (this suite's choice)


@dataclass(frozen=True)
class FiMeasures:
    reinforcers: int
    shortest_gap: float
    breakpoint: float
    low_to_high: float
    increase_fraction: float
    fifth_to_first: float
    curvature: float
    late_peaks: int
    quarter_life: float


def measure(subject: object) -> FiMeasures:
    record = run_session(
        DSL, subject, reinforcers=REINFORCERS, reinforcer_duration_s=REINFORCER_DURATION_S
    )
    ivs = intervals(record)
    fits = [f for f in (two_state_fit(*iv) for iv in ivs) if f is not None]
    segments = [segment_counts(onset, end, rs, 10) for onset, end, rs in ivs]
    starts = record.reinforcer_starts
    return FiMeasures(
        reinforcers=len(starts),
        shortest_gap=min(b - a for a, b in zip(starts, starts[1:])),
        breakpoint=median(f.break_fraction for f in fits),
        low_to_high=median(f.low_rate / f.high_rate for f in fits if f.high_rate > 0),
        increase_fraction=increase_fraction(segments),
        fifth_to_first=fifth_to_first_ratio(segments),
        curvature=median(
            index_of_curvature(*iv) for iv in ivs if len(iv[2]) >= CURVATURE_MIN_RESPONSES
        ),
        late_peaks=sum(1 for c in segments if c.index(max(c)) >= 10 - LATE_PEAK_SEGMENTS),
        quarter_life=median(compute_quarter_life([0.0, *starts], record.responses)),
    )


SUBJECTS: dict[str, Callable[[int], object]] = {
    "ScallopSubject": lambda seed: ScallopSubject(
        max_rate_hz=SCALLOP_MAX_RATE_HZ,
        ramp_s=INTERVAL_S,
        exponent=SCALLOP_EXPONENT,
        cv=SCALLOP_CV,
        seed=seed,
    ),
    "MprSubject": lambda seed: MprSubject(
        coupling="interval",
        initial_r=MPR_INITIAL_R,
        pause_fraction=MPR_PAUSE_FRACTION,
        seed=seed,
    ),
    "VirtualSubject": lambda seed: VirtualSubject(rate_hz=1.0, seed=seed),
}


@cache
def rows(subject: str) -> list[FiMeasures]:
    """Measures of ``subject`` under each seed (computed once per process)."""
    return [measure(SUBJECTS[subject](s)) for s in SEEDS]


def values(rows: list[FiMeasures], name: str) -> list[float]:
    return [getattr(r, name) for r in rows]


def _check(name: str, ok: Callable[[float], bool]) -> Callable[[str], tuple[bool, str]]:
    def judge(subject: str) -> tuple[bool, str]:
        v = values(rows(subject), name)
        return all(ok(x) for x in v), spread(v)

    return judge


CHECKS: dict[str, Callable[[str], tuple[bool, str]]] = {
    "F1": _check("breakpoint", lambda x: abs(x - BREAKPOINT) <= BREAKPOINT_MARGIN),
    "F2": _check("increase_fraction", lambda x: x >= INCREASE_FRACTION),
    "F2aux": _check("fifth_to_first", lambda x: x >= FIFTH_TO_FIRST),
    "F3": _check("curvature", lambda x: x >= CURVATURE),
    "F4": _check("late_peaks", lambda x: x >= LATE_PEAK_INTERVALS),
}
CHECK_LABELS = {
    "F1": "breakpoint 0.67 ± 0.15 (Schneider, 1969)",
    "F2": "share of rising segment steps ≥ 0.74 (Dews, 1978)",
    "F2aux": "5th / 1st segment rate ≥ 2 (Dews, 1978)",
    "F3": "index of curvature ≥ 0.56 (Fry et al., 1960)",
    "F4": "peak in the last 3 of 10 segments in ≥ 24 of 30 intervals (Lowe & Harzem, 1977)",
}
REPORTED = {"quarter_life": "quarter-life (not judged)", "low_to_high": "low / high rate"}


# Schedule invariant: holds for every subject that runs.


@pytest.mark.parametrize("subject", list(SUBJECTS))
def test_fi_invariant_reinforcers_are_at_least_an_interval_apart(subject: str) -> None:
    measured = rows(subject)
    assert all(r.reinforcers == REINFORCERS for r in measured)
    gaps = values(measured, "shortest_gap")
    assert min(gaps) >= INTERVAL_S, spread(gaps)


# The law: every subject predicted to obey it (``expectations.py``).


@pytest.mark.parametrize(("subject", "check"), law_cases(FI_SCALLOP, CHECKS))
def test_fi_law(subject: str, check: str) -> None:
    ok, detail = CHECKS[check](subject)
    assert ok, detail


def test_fi_quarter_life_is_reported() -> None:
    # Not judged: the source (Herrnstein & Morse, 1957) was not read.
    for subject in SUBJECTS:
        print(f"quarter-life {subject} {spread(values(rows(subject), 'quarter_life'))}")
    assert all(0 < x < 1 for x in values(rows("ScallopSubject"), "quarter_life"))


# The control: a constant-rate responder fails the law.


@pytest.fixture(scope="module")
def poisson() -> list[FiMeasures]:
    return rows("VirtualSubject")

def test_fi_poisson_control_has_no_low_rate_state(poisson: list[FiMeasures]) -> None:
    # Constant responding does not split into a low and a high rate.
    v = values(poisson, "low_to_high")
    assert all(x >= 0.5 for x in v), spread(v)


def test_fi_poisson_control_rises_only_by_chance(poisson: list[FiMeasures]) -> None:
    v = values(poisson, "increase_fraction")
    assert all(x < INCREASE_FRACTION and abs(x - 0.5) <= 0.15 for x in v), spread(v)


def test_fi_poisson_control_record_is_flat(poisson: list[FiMeasures]) -> None:
    v = values(poisson, "curvature")
    assert all(abs(x) <= FLAT_CURVATURE for x in v), spread(v)


def test_fi_poisson_control_peak_is_anywhere(poisson: list[FiMeasures]) -> None:
    v = values(poisson, "late_peaks")
    assert all(x < 15 for x in v), spread(v)
