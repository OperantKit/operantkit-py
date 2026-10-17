"""The generalized matching law on concurrent VI VI, judged against published values.

A melioration subject (``MatchingSubject``) runs Herrnstein's (1961) three
pairs of concurrent VI VI schedules that reinforce both keys
(``VI 180-s : VI 180-s``, ``VI 135-s : VI 270-s``, ``VI 108-s : VI 540-s``,
1.5-s changeover delay) under each of ten seeds. The same subject goes
through the three conditions in order. Each condition runs ten sessions of
60 reinforcers, and, as in Herrnstein (1961), the last five sessions are
pooled. The generalized matching law
``log(B1/B2) = a log(r1/r2) + log b`` (Baum, 1979) is fitted over the
three conditions. The thresholds come from the papers:

- M1, sensitivity: Baum (1979) — over 103 data sets, ``a`` measured with
  response counts had a median of .83, and "values of a between .90 and
  1.11 can be considered good approximations to matching". Pass:
  0.83 <= a <= 1.11.
- M2, per-condition deviation: Herrnstein (1961) — relative responses
  matched relative reinforcement within about 0.08. Pass:
  |relative responses − relative reinforcers| <= 0.10 (0.02 is this
  suite's margin).
- R² and ``log b`` are reported but not judged.

Two independent constant-rate Poisson responders are the control: they
must fail M1 (a < 0.5) and M2 and pass the schedule invariant: no
reinforcer within the changeover delay after a changeover.

References
----------
Baum, W. M. (1979). Matching, undermatching, and overmatching in studies of
    choice. *Journal of the Experimental Analysis of Behavior*, *32*(2),
    269–281. https://doi.org/10.1901/jeab.1979.32-269
Herrnstein, R. J. (1961). Relative and absolute strength of response as a
    function of frequency of reinforcement. *Journal of the Experimental
    Analysis of Behavior*, *4*(3), 267–272.
    https://doi.org/10.1901/jeab.1961.4-267
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pytest
from conftest import FH_SEED, SEEDS, Record, run_session, spread
from experiment_io.hw.backends.virtual import MatchingSubject, MultiVirtualSubject
from session_analyzer.analytics.matching import estimate_matching_parameters

# Mean intervals (s) for keys A and B: Herrnstein's pairs that reinforce both keys.
CONDITIONS = ((180.0, 180.0), (135.0, 270.0), (108.0, 540.0))
COD_S = 1.5
REINFORCERS = 60
SESSIONS = 10
POOLED = 5  # Herrnstein (1961) pooled the last five sessions
REINFORCER_DURATION_S = 4.0

SENSITIVITY_LOW = 0.83  # Baum (1979), median a for response measures
SENSITIVITY_HIGH = 1.11  # Baum (1979), upper end of "good approximations"
MAX_DEVIATION = 0.10  # Herrnstein (1961) about 0.08, plus this suite's 0.02
CONTROL_SENSITIVITY = 0.5


def condition_dsl(a_s: float, b_s: float, session: int) -> str:
    return (
        f'@algorithm("fleshler-hoffman", n=12, seed={FH_SEED + session})\n'
        f"Conc(VI {a_s:g}-s, VI {b_s:g}-s, COD={COD_S:g}-s)"
    )


@dataclass(frozen=True)
class Condition:
    responses: tuple[int, int]
    reinforcers: tuple[int, int]
    shortest_post_changeover_s: float
    post_changeover_reinforcers: int

    @property
    def deviation(self) -> float:
        return abs(
            self.responses[0] / sum(self.responses) - self.reinforcers[0] / sum(self.reinforcers)
        )


@dataclass(frozen=True)
class MatchingMeasures:
    conditions: tuple[Condition, ...]
    sensitivity: float
    bias: float
    r_squared: float


def post_changeover_times(record: Record) -> list[float]:
    """Time from the changeover to each reinforced response that follows one."""
    out = []
    run_key: int | None = None
    run_start = 0.0
    changed = False
    reinforced = list(zip(record.reinforcer_starts, record.reinforcer_operanda))
    r = 0
    for t, key in zip(record.responses, record.response_operanda):
        if key != run_key:
            changed = run_key is not None
            run_key, run_start = key, t
        while r < len(reinforced) and reinforced[r][0] < t:
            r += 1
        if r < len(reinforced) and reinforced[r] == (t, key) and changed:
            out.append(t - run_start)
    return out


def pool(records: list[Record]) -> Condition:
    responses = tuple(sum(rec.count(k)[0] for rec in records) for k in (0, 1))
    reinforcers = tuple(sum(rec.count(k)[1] for rec in records) for k in (0, 1))
    gaps = [g for rec in records for g in post_changeover_times(rec)]
    return Condition(responses, reinforcers, min(gaps, default=float("inf")), len(gaps))


def run_experiment(
    new_subject: Callable[[int], object], *, carry: bool, sessions: int, pooled: int
) -> MatchingMeasures:
    """Run the three conditions; ``carry`` keeps one subject throughout."""
    subject = new_subject(0) if carry else None
    conditions = []
    for c, (a_s, b_s) in enumerate(CONDITIONS):
        records = []
        for s in range(sessions):
            current = subject if carry else new_subject(c * sessions + s)
            records.append(
                run_session(
                    condition_dsl(a_s, b_s, s),
                    current,
                    reinforcers=REINFORCERS,
                    reinforcer_duration_s=REINFORCER_DURATION_S,
                    operanda=2,
                )
            )
        conditions.append(pool(records[-pooled:]))
    fit = estimate_matching_parameters(
        [c.responses[0] / c.responses[1] for c in conditions],
        [c.reinforcers[0] / c.reinforcers[1] for c in conditions],
    )
    return MatchingMeasures(tuple(conditions), fit.sensitivity, fit.bias, fit.r_squared)


@pytest.fixture(scope="module")
def melioration() -> list[MatchingMeasures]:
    # One subject carries its allocation through the three conditions.
    return [
        run_experiment(
            lambda _, seed=seed: MatchingSubject(rate_hz=1.0, stay=0.5, seed=seed),
            carry=True,
            sessions=SESSIONS,
            pooled=POOLED,
        )
        for seed in SEEDS
    ]


@pytest.fixture(scope="module")
def poisson() -> list[MatchingMeasures]:
    # Memoryless: history does not matter, so one session per condition.
    return [
        run_experiment(
            lambda i, seed=seed: MultiVirtualSubject(
                [0.5, 0.5], [1000 * seed + 2 * i, 1000 * seed + 2 * i + 1]
            ),
            carry=False,
            sessions=1,
            pooled=1,
        )
        for seed in SEEDS
    ]


@pytest.mark.parametrize("subject", ["melioration", "poisson"])
def test_matching_invariant_no_reinforcer_inside_the_changeover_delay(
    subject: str, request: pytest.FixtureRequest
) -> None:
    rows = request.getfixturevalue(subject)
    conditions = [c for r in rows for c in r.conditions]
    assert all(c.post_changeover_reinforcers > 0 for c in conditions)
    v = [c.shortest_post_changeover_s for c in conditions]
    assert min(v) >= COD_S, spread(v)


def test_matching_sensitivity_within_published_range(melioration: list[MatchingMeasures]) -> None:
    v = [r.sensitivity for r in melioration]
    print(f"a {spread(v)}")
    print(f"log b {spread([r.bias for r in melioration])}")
    print(f"R^2 {spread([r.r_squared for r in melioration])}")
    assert all(SENSITIVITY_LOW <= a <= SENSITIVITY_HIGH for a in v), spread(v)


def test_matching_relative_responses_track_relative_reinforcers(
    melioration: list[MatchingMeasures],
) -> None:
    v = [c.deviation for r in melioration for c in r.conditions]
    assert max(v) <= MAX_DEVIATION, spread(v)


def test_matching_poisson_control_is_insensitive(poisson: list[MatchingMeasures]) -> None:
    v = [r.sensitivity for r in poisson]
    print(f"control a {spread(v)}")
    assert all(a < CONTROL_SENSITIVITY for a in v), spread(v)


def test_matching_poisson_control_misses_the_unequal_condition(
    poisson: list[MatchingMeasures],
) -> None:
    # VI 108-s : VI 540-s, where reinforcement is most unequal.
    v = [r.conditions[-1].deviation for r in poisson]
    assert all(d > MAX_DEVIATION for d in v), spread(v)
