"""Ratio versus interval responding under yoked reinforcement, judged against published values.

A subject that copies the inter-response times (IRTs) that were reinforced
(``IrtCopyistSubject``) runs ``VR 25`` for 90 reinforcers; a second subject
then runs a VI whose intervals are the first one's inter-reinforcement
times (yoked VI), so both are reinforced at the same rate. Ten pairs, one
per seed. The two members of a pair start from the same pool of IRTs but
emit independent response streams; with the same stream the yoked VI would
reinforce the very responses the VR reinforced and reproduce the master
record exactly (``test_yoked_vi_with_the_same_stream_reproduces_the_master``).
Catania et al. (1977) likewise yoked a second pigeon to the first.

- V1, rate ratio: Catania, Matthews, Silverman & Yohalem (1977) — "VR
  response rates were about twice those for VI schedules for both directions
  of yoking" (91 vs. 49 and 94 vs. 41 responses per minute), higher in 17 of
  19 pairs. Pass: VR rate ÷ yoked VI rate > 1.0 for every pair, and the
  median is at least 1.5 (three quarters of "about twice", this suite's
  margin).
- V2, range of reinforcement rates: Baum (1993) — the VI rate rose to the VR
  rate around 600 to 1,000 reinforcers per hour (300 to 600 after correcting
  for pausing). Pass: the yoked VI earns fewer than 300 reinforcers per hour.

Invariants of the procedure (the Poisson control must pass them too): the VR
pays one reinforcer per 25 ± 2 responses on average, and the yoked VI earns
reinforcers at 0.9 to 1.1 times the VR rate (Baum: the yoking "equalized the
rates of reinforcement"; the VI rate runs slightly lower because the subject
collects a set-up reinforcer only at its next response).

A constant-rate Poisson responder is the control: both members of a pair
respond at the same rate whatever the schedule, so the ratio must stay
within 0.9 to 1.1.

The pool size (70) and IRT variation (CV 0.2) were chosen from a sweep of the
model's own parameters (pool 5–200, CV 0.1–0.5, 60–200 reinforcers); the
thresholds above were not changed.

References
----------
Baum, W. M. (1993). Performances on ratio and interval schedules of
    reinforcement: Data and theory. *Journal of the Experimental Analysis of
    Behavior*, *59*(2), 245–264. https://doi.org/10.1901/jeab.1993.59-245
Catania, A. C., Matthews, T. J., Silverman, P. J., & Yohalem, R. (1977).
    Yoked variable-ratio and variable-interval responding in pigeons.
    *Journal of the Experimental Analysis of Behavior*, *28*(2), 155–161.
    https://doi.org/10.1901/jeab.1977.28-155
Tanno, T., & Silberberg, A. (2012). The copyist model of response emission.
    *Psychonomic Bulletin & Review*, *19*(5), 759–778.
    https://doi.org/10.3758/s13423-012-0267-1
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from statistics import median

import pytest
from conftest import (
    FH_SEED,
    SEEDS,
    Record,
    YokedVI,
    intervals,
    response_rate,
    run_session,
    spread,
)
from experiment_io.hw.backends.virtual import IrtCopyistSubject, VirtualSubject

VR_DSL = f'@algorithm("fleshler-hoffman", n=12, seed={FH_SEED})\nVR 25'
YOKED_DSL = "yoked VI"
RATIO = 25
REINFORCERS = 90
REINFORCER_DURATION_S = 0.5
POOL_SIZE = 70
CV = 0.2
POISSON_RATE_HZ = 1.0
YOKED_SEED_OFFSET = 100

RATE_RATIO_MIN = 1.0  # Catania et al. (1977): VR above VI
RATE_RATIO_MEDIAN = 1.5  # three quarters of Catania et al.'s "about twice"
MAX_REINFORCERS_PER_HOUR = 300.0  # Baum (1993), lower edge of convergence
RESPONSES_PER_REINFORCER_MARGIN = 2.0
EQUALIZED = (0.9, 1.1)  # Baum (1993), "equalized"
CONTROL_RATIO = (0.9, 1.1)


@dataclass(frozen=True)
class Pair:
    vr: Record
    vi: Record

    @property
    def rate_ratio(self) -> float:
        return response_rate(self.vr) / response_rate(self.vi)

    @property
    def vi_reinforcers_per_hour(self) -> float:
        return 3600.0 * REINFORCERS / _session_time(self.vi)

    @property
    def reinforcement_rate_ratio(self) -> float:
        """Yoked VI reinforcement rate over the VR's."""
        return _session_time(self.vr) / _session_time(self.vi)

    @property
    def vr_responses_per_reinforcer(self) -> float:
        return sum(len(r) for _, _, r in intervals(self.vr)) / REINFORCERS


def _session_time(record: Record) -> float:
    """Time in the inter-reinforcement intervals (reinforcer time excluded)."""
    return sum(end - onset for onset, end, _ in intervals(record))


def yoked_intervals(master: Record) -> list[float]:
    """The master's inter-reinforcement times, timed from each reinforcer's end."""
    iris = [end - onset for onset, end, _ in intervals(master)]
    return [iris[0], *(iri + REINFORCER_DURATION_S for iri in iris[1:])]


def run_pair(make_subject: Callable[[bool], object]) -> Pair:
    """Run the VR master, then the yoked VI on its inter-reinforcement times."""
    vr = run_session(
        VR_DSL,
        make_subject(False),
        reinforcers=REINFORCERS,
        reinforcer_duration_s=REINFORCER_DURATION_S,
    )
    vi = run_session(
        YOKED_DSL,
        make_subject(True),
        reinforcers=REINFORCERS,
        reinforcer_duration_s=REINFORCER_DURATION_S,
        schedule=YokedVI(yoked_intervals(vr)),
    )
    return Pair(vr, vi)


def copyist(seed: int) -> Callable[[bool], object]:
    pool = IrtCopyistSubject(pool_size=POOL_SIZE, cv=CV, seed=seed).pool

    def make(yoked: bool) -> IrtCopyistSubject:
        return IrtCopyistSubject(
            pool_size=POOL_SIZE,
            cv=CV,
            initial_irts=pool,
            seed=seed + YOKED_SEED_OFFSET if yoked else seed,
        )

    return make


def poisson(seed: int) -> Callable[[bool], object]:
    def make(yoked: bool) -> VirtualSubject:
        return VirtualSubject(
            rate_hz=POISSON_RATE_HZ, seed=seed + YOKED_SEED_OFFSET if yoked else seed
        )

    return make


@pytest.fixture(scope="module")
def copyist_pairs() -> list[Pair]:
    return [run_pair(copyist(seed)) for seed in SEEDS]


@pytest.fixture(scope="module")
def poisson_pairs() -> list[Pair]:
    return [run_pair(poisson(seed)) for seed in SEEDS]


def test_vr_rate_exceeds_yoked_vi_rate(copyist_pairs: list[Pair]) -> None:
    ratios = [p.rate_ratio for p in copyist_pairs]
    assert min(ratios) > RATE_RATIO_MIN, f"VR / yoked VI rate {spread(ratios)}"
    assert median(ratios) >= RATE_RATIO_MEDIAN, f"VR / yoked VI rate {spread(ratios)}"


def test_yoked_vi_stays_below_the_convergence_range(copyist_pairs: list[Pair]) -> None:
    per_hour = [p.vi_reinforcers_per_hour for p in copyist_pairs]
    assert max(per_hour) < MAX_REINFORCERS_PER_HOUR, f"yoked VI per hour {spread(per_hour)}"


@pytest.mark.parametrize("pairs_fixture", ["copyist_pairs", "poisson_pairs"])
def test_procedure_invariants(pairs_fixture: str, request: pytest.FixtureRequest) -> None:
    pairs: list[Pair] = request.getfixturevalue(pairs_fixture)
    per_reinforcer = [p.vr_responses_per_reinforcer for p in pairs]
    mean_per_reinforcer = sum(per_reinforcer) / len(per_reinforcer)
    assert abs(mean_per_reinforcer - RATIO) <= RESPONSES_PER_REINFORCER_MARGIN, (
        f"VR responses per reinforcer {spread(per_reinforcer)}"
    )
    equalized = [p.reinforcement_rate_ratio for p in pairs]
    low, high = EQUALIZED
    assert all(low <= e <= high for e in equalized), (
        f"yoked VI / VR reinforcement rate {spread(equalized)}"
    )
    assert all(len(p.vi.reinforcer_starts) == REINFORCERS for p in pairs)


def test_poisson_control_shows_no_rate_difference(poisson_pairs: list[Pair]) -> None:
    ratios = [p.rate_ratio for p in poisson_pairs]
    low, high = CONTROL_RATIO
    assert all(low <= r <= high for r in ratios), f"control VR / yoked VI rate {spread(ratios)}"


def test_yoked_vi_with_the_same_stream_reproduces_the_master() -> None:
    def same_stream(yoked: bool) -> IrtCopyistSubject:
        return IrtCopyistSubject(pool_size=POOL_SIZE, cv=CV, seed=SEEDS[0])

    pair = run_pair(same_stream)
    assert pair.vi.responses == pair.vr.responses
    assert pair.vi.reinforcer_starts == pair.vr.reinforcer_starts
