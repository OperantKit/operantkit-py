"""Schedule feedback functions: obtained reinforcement rate against closed forms.

A feedback function gives the rate of reinforcement ``r`` that a schedule
delivers to a given rate of responding ``B``. Here the subject is a Poisson
responder (``VirtualSubject``): inter-response times (IRTs) are independent
and exponential with mean ``1/B``, and the subject does not change its rate
when reinforced. Reinforcer duration is 0 s. Each schedule is swept over
``B`` = 0.05, 0.1, 0.2, 0.5, 1, 2, 3, 5 Hz with ten subject seeds per point
(seed ``1000 × point index + s``, so every point draws its own IRTs).

Closed forms and where they come from:

- ``VR 25``: ``r = B / 25``. Ratio schedules make the reinforcement rate
  strictly proportional to the response rate (Prelec, 1982).
- ``RI 30-s``: ``r = 1 / (30 + 1/B)``. With random responding the mean time
  between reinforcers is the mean scheduled interval plus the mean wait from
  set-up to the next response, ``1/B`` (Nevin & Baum, 1980, Equations 5 and
  6; Prelec, 1982).
- ``VI 30-s`` (Fleshler & Hoffman, 1962, 12 values): ``r = 1 / (30 + 1/B)``.
  Derived here: the wait after each interval is ``1/B`` on average for a
  Poisson responder whatever the interval distribution, so the mean over a
  cycle of the sequence is ``30 + 1/B``.
- ``FI 30-s``: ``r = 1 / (30 + 1/B)``. Derived here, as the VI with every
  interval equal to 30 s.
- ``DRL 5-s``: a response is reinforced when the IRT before it is at least
  5 s, with probability ``exp(-5B)``; the engine also reinforces the first
  response unconditionally. Derived here. The test compares the share of
  reinforced responses after the first, ``(reinforcers - 1) / (responses -
  1)``, with ``exp(-5B)``.

VR, RI, VI and FI end at the 120th reinforcer (ten cycles of the 12-value
sequence) and ``r = 120 / time of the 120th reinforcer``; ending at a fixed
time instead biases the rate low through the cut at the end. DRL ends at
``T = 200 / (B exp(-5B))`` seconds, kept within 3,600 to 20,000 s.

Band, fixed before the run: ``|mean of ten seeds - closed form| <= 4 ×``
the standard error that the closed form itself implies (the sample standard
error and ``z`` are printed only). For ``K`` reinforcers the relative
standard deviation of the time of the ``K``-th reinforcer is
``1/sqrt(n K)`` for VR n, ``1/(sqrt(K) (B t + 1))`` for FI t and VI t (the
intervals sum to a fixed total and only the waits vary) and
``sqrt(t² + 1/B²) / (sqrt(K) (t + 1/B))`` for RI t. For DRL the standard
error is binomial over the pooled responses after the first.

Exact checks from the schedule definitions (any single violation fails):
VR pays exactly ``25 × 120`` responses for 120 reinforcers; under FI every
inter-reinforcement interval is at least 30 s and the reinforced response
is the first one after 30 s; under DRL the reinforced responses are exactly
the first response and every response whose preceding IRT is at least 5 s.

With the fixed ``FH_SEED`` every subject seed meets the same RI intervals
(their mean over 120 is 29.59 s for seed 42), so all RI points share an
offset of about +1.4%; the formula's standard error, which treats the
intervals as random, is the right size for it.

Also printed, not judged: the coefficient of variation of the
inter-reinforcement times for VI and RI. With Poisson responding both have
the same mean, but RI intervals vary more.

References
----------
Fleshler, M., & Hoffman, H. S. (1962). A progression for generating
    variable-interval schedules. *Journal of the Experimental Analysis of
    Behavior*, *5*(4), 529–530. https://doi.org/10.1901/jeab.1962.5-529
Nevin, J. A., & Baum, W. M. (1980). Feedback functions for
    variable-interval reinforcement. *Journal of the Experimental Analysis of
    Behavior*, *34*(2), 207–217. https://doi.org/10.1901/jeab.1980.34-207
Prelec, D. (1982). Matching, maximizing, and the hyperbolic reinforcement
    feedback function. *Psychological Review*, *89*(3), 189–230.
    https://doi.org/10.1037/0033-295X.89.3.189
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from statistics import mean, pstdev, stdev

import pytest
from conftest import FH_SEED, SEEDS, Record, run_session
from experiment_core import TimeLimitExit
from experiment_io.hw.backends.virtual import VirtualSubject

RATES_HZ = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0)
K = 120
BAND = 4.0
T_SCHED = 30.0
RATIO = 25
DRL_T = 5.0
FH = f'@algorithm("fleshler-hoffman", n=12, seed={FH_SEED})\n'


def subject_seed(point: int, s: int) -> int:
    return 1000 * point + s


@dataclass(frozen=True)
class Point:
    rate_hz: float
    observed: float
    predicted: float
    se_formula: float
    se_sample: float
    note: str = ""

    @property
    def deviation(self) -> float:
        return (self.observed - self.predicted) / self.predicted

    @property
    def z(self) -> float:
        if self.se_sample == 0:
            return math.inf if self.observed != self.predicted else 0.0
        return (self.observed - self.predicted) / self.se_sample

    @property
    def inside(self) -> bool:
        return abs(self.observed - self.predicted) <= BAND * self.se_formula

    def row(self) -> str:
        return (
            f"B={self.rate_hz:<4} obs={self.observed:.6g} pred={self.predicted:.6g} "
            f"dev={self.deviation:+.4f} se_formula={self.se_formula:.3g} "
            f"z={self.z:+.2f} {'ok' if self.inside else 'OUT'} {self.note}"
        ).rstrip()


def report(name: str, points: list[Point]) -> str:
    text = "\n".join([f"[{name}]", *(p.row() for p in points)])
    print(text)
    return text


def run_count_limited(dsl: str, point: int, rate_hz: float) -> list[Record]:
    return [
        run_session(
            dsl,
            VirtualSubject(rate_hz=rate_hz, seed=subject_seed(point, s)),
            reinforcers=K,
            reinforcer_duration_s=0.0,
        )
        for s in SEEDS
    ]


def iri_cv(records: list[Record]) -> float:
    """Mean over seeds of the coefficient of variation of inter-reinforcement times."""
    cvs = []
    for rec in records:
        times = [0.0, *rec.reinforcer_starts]
        gaps = [b - a for a, b in zip(times, times[1:])]
        cvs.append(pstdev(gaps) / mean(gaps))
    return mean(cvs)


def rate_points(
    dsl: str,
    predict: Callable[[float], float],
    rel_sd: Callable[[float], float],
    *,
    with_cv: bool = False,
) -> tuple[list[Point], dict[float, list[Record]]]:
    points, runs = [], {}
    for i, b in enumerate(RATES_HZ):
        recs = run_count_limited(dsl, i, b)
        runs[b] = recs
        rates = [K / rec.reinforcer_starts[-1] for rec in recs]
        assert all(len(rec.reinforcer_starts) == K for rec in recs)
        p = predict(b)
        points.append(
            Point(
                rate_hz=b,
                observed=mean(rates),
                predicted=p,
                se_formula=p * rel_sd(b) / math.sqrt(len(SEEDS)),
                se_sample=stdev(rates) / math.sqrt(len(SEEDS)),
                note=f"iri_cv={iri_cv(recs):.3f}" if with_cv else "",
            )
        )
    return points, runs


def interval_rate(b: float) -> float:
    return 1.0 / (T_SCHED + 1.0 / b)


def assert_band(name: str, points: list[Point]) -> None:
    text = report(name, points)
    outside = [p for p in points if not p.inside]
    assert not outside, f"{len(outside)} point(s) outside ±{BAND} SE:\n{text}"


def test_vr_rate_is_proportional_to_response_rate() -> None:
    points, runs = rate_points(
        FH + f"VR {RATIO}",
        lambda b: b / RATIO,
        lambda b: 1.0 / math.sqrt(RATIO * K),
    )
    for b, recs in runs.items():
        for rec in recs:
            assert len(rec.responses) == RATIO * K, (b, len(rec.responses))
    assert_band(f"VR {RATIO}", points)


def test_ri_rate_follows_hyperbola() -> None:
    points, _ = rate_points(
        FH + f"RI {T_SCHED:g}-s",
        interval_rate,
        lambda b: math.sqrt(T_SCHED**2 + 1 / b**2) / (math.sqrt(K) * (T_SCHED + 1 / b)),
        with_cv=True,
    )
    assert_band(f"RI {T_SCHED:g}-s", points)


def test_vi_fleshler_hoffman_rate_follows_hyperbola() -> None:
    points, _ = rate_points(
        FH + f"VI {T_SCHED:g}-s",
        interval_rate,
        lambda b: 1.0 / (math.sqrt(K) * (b * T_SCHED + 1)),
        with_cv=True,
    )
    assert_band(f"VI {T_SCHED:g}-s (FH 12)", points)


def test_fi_rate_follows_hyperbola() -> None:
    points, runs = rate_points(
        f"FI {T_SCHED:g}-s",
        interval_rate,
        lambda b: 1.0 / (math.sqrt(K) * (b * T_SCHED + 1)),
    )
    for b, recs in runs.items():
        for rec in recs:
            onsets = [0.0, *rec.reinforcer_starts[:-1]]
            for onset, sr in zip(onsets, rec.reinforcer_starts, strict=True):
                assert sr - onset >= T_SCHED - 1e-9, (b, onset, sr)
                eligible = [t for t in rec.responses if onset + T_SCHED - 1e-9 <= t <= sr]
                assert eligible and eligible[0] == pytest.approx(sr, abs=1e-9), (b, onset, sr)
    assert_band(f"FI {T_SCHED:g}-s", points)


def drl_session_length(b: float) -> float:
    return min(max(3600.0, 200.0 / (b * math.exp(-DRL_T * b))), 20_000.0)


def test_drl_reinforces_irts_at_least_the_requirement() -> None:
    points = []
    for i, b in enumerate(RATES_HZ):
        length = drl_session_length(b)
        reinforced = eligible = 0
        rates = []
        for s in SEEDS:
            rec = run_session(
                f"DRL {DRL_T:g}-s",
                VirtualSubject(rate_hz=b, seed=subject_seed(i, s)),
                reinforcer_duration_s=0.0,
                exit_condition=TimeLimitExit(limit=length),
            )
            resp = rec.responses
            assert resp[-1] < length, (b, s)
            expected = [resp[0]] + [t for p, t in zip(resp, resp[1:]) if t - p >= DRL_T]
            assert rec.reinforcer_starts == pytest.approx(expected, abs=1e-9), (b, s)
            reinforced += len(rec.reinforcer_starts) - 1
            eligible += len(resp) - 1
            rates.append((len(rec.reinforcer_starts) - 1) / length)
        p = math.exp(-DRL_T * b)
        points.append(
            Point(
                rate_hz=b,
                observed=reinforced / eligible,
                predicted=p,
                se_formula=math.sqrt(p * (1 - p) / eligible),
                se_sample=math.sqrt(p * (1 - p) / eligible),
                note=(
                    f"T={length:.0f}s reinforced={reinforced} "
                    f"r_obs={mean(rates):.5f} r_pred={b * p:.5f}"
                ),
            )
        )
    assert_band(f"DRL {DRL_T:g}-s (share of reinforced responses)", points)
