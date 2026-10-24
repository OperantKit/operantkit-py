"""Punishment intensity and free-operant avoidance, judged against published findings.

Unlike the other law tests, these subjects run in the Gymnasium environments
of contingency-py (``contingency/PunishedVI-v0`` and
``contingency/SidmanAvoidance-v0``), where a punisher or shock is a negative
reward. The subject is tabular one-step Q-learning
(``contingency.envs.tabular``: alpha 0.1, gamma 0.95, epsilon 0.1, 100
training sessions, then one greedy 600-s session) under each of ten seeds.
The control is a random responder (press or not with probability 1/2 on
every 1-s step). Thresholds are orders taken from the papers and are not
tuned to the subjects' output; each ordered pair of levels passes when it
holds strictly for at least 9 of the 10 seeds (one-sided sign test,
P(X >= 9 | n = 10, p = .5) = 11/1024).

- P1, punishment intensity: Azrin (1960) — on VI food reinforcement with
  every response punished, "the more intense punishment produces a greater
  reduction of responding". Every response on VI 60 s is punished with
  reward −p, p = 0.003, 0.01, 0.03; the suppression ratio (punished rate /
  rate at p = 0, same seed) must fall as p rises: 0.003 > 0.01 > 0.03.
  The shock voltages of the paper have no counterpart in p, so only the
  order is judged; the medians are printed next to Azrin's stable values
  (about 0.32 at 50 V and 0.05 at 100 V).
- A1, avoidance (recorded as xfail): Sidman (1953) — with the shock-shock
  (S-S) interval fixed, response rate falls as the response-shock (R-S)
  interval lengthens to the right of its maximum. S-S 10 s, R-S 20, 40,
  80 s, each response costing 0.01. Not reproduced: the order 20 > 40 holds
  but 40 > 80 does not, because at R-S 80 s half the seeds settle on a
  faster rate that still takes shocks.

The random control must fail P1 (its suppression ratio has a median within
1 ± 0.1 and no pair holds for any seed) and A1, and pass the schedule
invariants, as must the subjects: a punisher follows every ``ratio``-th
response and nothing else, and every shock comes exactly R-S after the last
response or S-S after the last shock (or the session start), the next one
being due then.

References
----------
Azrin, N. H. (1960). Effects of punishment intensity during
    variable-interval reinforcement. *Journal of the Experimental Analysis
    of Behavior*, *3*(2), 123–142. https://doi.org/10.1901/jeab.1960.3-123
Sidman, M. (1953). Two temporal parameters of the maintenance of avoidance
    behavior by the white rat. *Journal of Comparative and Physiological
    Psychology*, *46*(4), 253–261. https://doi.org/10.1037/h0060730
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from statistics import median
from typing import Any

import numpy as np
import pytest
from conftest import SEEDS, spread
from contingency.envs.presets import make_punished_vi_env, make_sidman_env
from contingency.envs.tabular import FI_N_STATES, fi_state, greedy, train_q
from session_analyzer.analytics import analyze_avoidance, analyze_punishment

EPISODES = 100
DURATION_S = 600.0
DT_S = 1.0  # environment step
EVAL_SEED_OFFSET = 1000  # evaluation session seed = 1000 + training seed
PASS_SEEDS = 9  # of 10, per ordered pair

VI_MEAN_S = 60.0
PUNISHMENTS = (0.003, 0.01, 0.03)
CONTROL_RATIO = 0.1  # random control: median suppression ratio within 1 ± 0.1

SS_S = 10.0
RS_LEVELS = (20.0, 40.0, 80.0)
AVOID_RESPONSE_COST = 0.01
AVOID_N_STATES = (12, 12)

Policy = Callable[[dict[str, Any], np.random.Generator], int]


@dataclass(frozen=True)
class Session:
    """One evaluation session. ``*_times`` are the environment's ``info["time"]``."""

    responses: list[float]
    shocks: list[float]
    reinforcers: int
    # Step numbers, from 1; the schedule sees step ``k`` at time ``k * DT_S``.
    response_steps: list[int]
    shock_steps: list[int]
    n_shock: int


def run(env: Any, policy: Policy, seed: int) -> Session:
    """One session; rng and reset both use ``seed`` (as ``tabular.run_greedy``)."""
    rng = np.random.default_rng(seed)
    obs, _ = env.reset(seed=seed)
    responses: list[float] = []
    shocks: list[float] = []
    response_steps: list[int] = []
    shock_steps: list[int] = []
    reinforcers = 0
    prev_shock = 0
    k = 0
    while True:
        action = policy(obs, rng)
        obs, _, terminated, truncated, info = env.step(action)
        k += 1
        t = float(info["time"])
        if action:
            responses.append(t)
            response_steps.append(k)
        if info["n_shock"] > prev_shock:
            shocks.append(t)
            shock_steps.append(k)
            prev_shock = info["n_shock"]
        reinforcers += int(obs["last_sr"])
        if terminated or truncated:
            return Session(
                responses, shocks, reinforcers, response_steps, shock_steps, info["n_shock"]
            )


def q_policy(q: np.ndarray, state: Callable[[dict[str, Any]], tuple[int, ...]]) -> Policy:
    return lambda obs, rng: greedy(q[state(obs)], rng)


def random_policy(obs: dict[str, Any], rng: np.random.Generator) -> int:
    return int(rng.integers(2))


def never_policy(obs: dict[str, Any], rng: np.random.Generator) -> int:
    return 0


def avoid_state(obs: dict[str, Any]) -> tuple[int, int]:
    """10-s bins (up to 120 s) of the time since the last response and shock."""
    r = int(float(obs["time_since_response"][0]) // 10)
    s = int(float(obs["time_since_shock"][0]) // 10)
    return min(r, 11), min(s, 11)


def wins(a: Sequence[float], b: Sequence[float]) -> int:
    """Seeds where ``a > b`` strictly (seed-paired)."""
    return sum(1 for x, y in zip(a, b, strict=True) if x > y)


# --- P1: punishment intensity -------------------------------------------------


def punished_sessions(subject: str) -> dict[float, list[Session]]:
    out: dict[float, list[Session]] = {}
    for p in (0.0, *PUNISHMENTS):
        rows = []
        for seed in SEEDS:
            env = make_punished_vi_env(mean=VI_MEAN_S, punishment=p)
            if subject == "q":
                q = train_q(env, episodes=EPISODES, seed=seed, state=fi_state, n_states=FI_N_STATES)
                policy = q_policy(q, fi_state)
            else:
                policy = random_policy
            rows.append(run(env, policy, EVAL_SEED_OFFSET + seed))
        out[p] = rows
    return out


def suppression(sessions: dict[float, list[Session]]) -> dict[float, list[float]]:
    out = {}
    for p in PUNISHMENTS:
        out[p] = [
            analyze_punishment(
                base.responses,
                cur.responses,
                DURATION_S,
                DURATION_S,
                punisher_times=cur.shocks,
            ).suppression_ratio
            for base, cur in zip(sessions[0.0], sessions[p], strict=True)
        ]
    return out


@pytest.fixture(scope="module")
def q_punished() -> dict[float, list[Session]]:
    return punished_sessions("q")


@pytest.fixture(scope="module")
def random_punished() -> dict[float, list[Session]]:
    return punished_sessions("random")


@pytest.mark.parametrize("subject", ["q_punished", "random_punished"])
def test_punishment_invariant_every_response_is_punished(
    subject: str, request: pytest.FixtureRequest
) -> None:
    sessions: dict[float, list[Session]] = request.getfixturevalue(subject)
    for p, rows in sessions.items():
        for s in rows:
            expected = len(s.responses) if p > 0 else 0
            assert s.n_shock == expected, (p, s.n_shock, len(s.responses))
            assert s.shock_steps == (s.response_steps if p > 0 else [])


@pytest.mark.parametrize("ratio", [1, 5])
def test_punishment_invariant_every_ratio_th_response_is_punished(ratio: int) -> None:
    env = make_punished_vi_env(mean=VI_MEAN_S, punishment=0.01, ratio=ratio)
    for seed in SEEDS:
        s = run(env, random_policy, EVAL_SEED_OFFSET + seed)
        assert s.n_shock == len(s.responses) // ratio
        assert s.shock_steps == s.response_steps[ratio - 1 :: ratio]


def test_punishment_suppression_falls_with_intensity(
    q_punished: dict[float, list[Session]],
) -> None:
    ratios = suppression(q_punished)
    for p in PUNISHMENTS:
        print(f"p={p:g} suppression ratio {spread(ratios[p])}")
    print("Azrin (1960) stable values: about 0.32 at 50 V, 0.05 at 100 V (not judged)")
    for lo, hi in zip(PUNISHMENTS, PUNISHMENTS[1:]):
        k = wins(ratios[lo], ratios[hi])
        assert k >= PASS_SEEDS, f"{lo:g} > {hi:g} in {k}/10 seeds"
    medians = [median(ratios[p]) for p in PUNISHMENTS]
    assert medians == sorted(medians, reverse=True), medians


def test_punishment_random_control_is_not_suppressed(
    random_punished: dict[float, list[Session]],
) -> None:
    ratios = suppression(random_punished)
    for p in PUNISHMENTS:
        assert abs(median(ratios[p]) - 1.0) <= CONTROL_RATIO, spread(ratios[p])
    for lo, hi in zip(PUNISHMENTS, PUNISHMENTS[1:]):
        assert wins(ratios[lo], ratios[hi]) < PASS_SEEDS


# --- A1: free-operant avoidance -----------------------------------------------


def expected_shock_steps(
    response_steps: Sequence[int], n_steps: int, rs: float, ss: float
) -> list[int]:
    """Shock steps under Sidman's rule for a given response record.

    The first shock is due S-S after the session start; a response sets the
    next one R-S after it (a response at the due step cancels that shock);
    a shock sets the next one S-S after it.
    """
    responded = set(response_steps)
    due = ss
    out = []
    for k in range(1, n_steps + 1):
        now = k * DT_S
        if k in responded:
            due = now + rs
        elif now + 1e-9 >= due:
            out.append(k)
            due = now + ss
    return out


def avoidance_sessions(subject: str) -> dict[float, list[Session]]:
    out: dict[float, list[Session]] = {}
    for rs in RS_LEVELS:
        rows = []
        for seed in SEEDS:
            env = make_sidman_env(rs=rs, ss=SS_S, response_cost=AVOID_RESPONSE_COST)
            if subject == "q":
                q = train_q(
                    env, episodes=EPISODES, seed=seed, state=avoid_state, n_states=AVOID_N_STATES
                )
                policy = q_policy(q, avoid_state)
            elif subject == "random":
                policy = random_policy
            else:
                policy = never_policy
            rows.append(run(env, policy, EVAL_SEED_OFFSET + seed))
        out[rs] = rows
    return out


def response_rates(sessions: dict[float, list[Session]]) -> dict[float, list[float]]:
    return {
        rs: [
            analyze_avoidance(
                s.responses, s.shocks, DURATION_S, shock_shock_interval=SS_S
            ).response_rate
            for s in rows
        ]
        for rs, rows in sessions.items()
    }


@pytest.fixture(scope="module")
def q_avoidance() -> dict[float, list[Session]]:
    return avoidance_sessions("q")


@pytest.fixture(scope="module")
def random_avoidance() -> dict[float, list[Session]]:
    return avoidance_sessions("random")


@pytest.mark.parametrize("subject", ["q_avoidance", "random_avoidance", "never"])
def test_avoidance_invariant_shocks_follow_sidmans_rule(
    subject: str, request: pytest.FixtureRequest
) -> None:
    sessions = (
        avoidance_sessions("never") if subject == "never" else request.getfixturevalue(subject)
    )
    n_steps = int(DURATION_S / DT_S)
    for rs, rows in sessions.items():
        for s in rows:
            assert s.shock_steps == expected_shock_steps(s.response_steps, n_steps, rs, SS_S)
            assert s.n_shock == len(s.shock_steps)
            if not s.response_steps:
                # No responding: one shock per S-S interval.
                assert abs(s.n_shock - math.floor(DURATION_S / SS_S)) <= 1, s.n_shock


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Q-learning response rate falls from R-S 20 s to 40 s in 10/10 seeds but from "
        "40 s to 80 s in only 5/10: at 80 s half the seeds respond faster and still take shocks"
    ),
)
def test_avoidance_rate_falls_as_response_shock_interval_lengthens(
    q_avoidance: dict[float, list[Session]],
) -> None:
    rates = response_rates(q_avoidance)
    for rs in RS_LEVELS:
        print(f"R-S {rs:g} s response rate {spread(rates[rs])} per min")
    for lo, hi in zip(RS_LEVELS, RS_LEVELS[1:]):
        k = wins(rates[lo], rates[hi])
        assert k >= PASS_SEEDS, f"R-S {lo:g} > {hi:g} in {k}/10 seeds"


def test_avoidance_random_control_rate_does_not_follow_the_interval(
    random_avoidance: dict[float, list[Session]],
) -> None:
    rates = response_rates(random_avoidance)
    for lo, hi in zip(RS_LEVELS, RS_LEVELS[1:]):
        assert wins(rates[lo], rates[hi]) == 0
