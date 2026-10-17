"""Matching on concurrent VI VI schedules (Herrnstein, 1961) with a virtual subject.

Runs Herrnstein's four pairs of concurrent variable-interval schedules
(combined rate held at 40 reinforcers per hour, 1.5-s changeover delay)
through the public OperantKit pipeline (contingency-dsl → contingency-py
schedule → session-runner → experiment-io ``drive`` → OKL v1 log). Each
condition is run for five sessions of 60 reinforcers (4-s reinforcer) with
a fresh subject, and only the last session is analysed (the original study
pooled the last five of 17 to 44 sessions). It writes, next to this file:

- ``concurrent_vi_matching_<condition>.okl`` — the last session of each condition
- ``concurrent_vi_matching.png`` — relative responses on key A against
  relative reinforcement on key A, with the diagonal (perfect matching)

and prints the per-condition proportions and the generalized matching
law fit (sensitivity ``a``, bias ``log b``, R²) over the three conditions
that reinforce both keys.

Usage::

    python examples/concurrent_vi_matching/run.py
    python examples/concurrent_vi_matching/run.py --no-cod   # control
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from contingency.bridge import from_dsl  # noqa: E402
from contingency_dsl import parse  # noqa: E402
from contingency_dsl.annotations.temporal.extension import TemporalExtension  # noqa: E402
from contingency_dsl.extensions import ExtensionRegistry  # noqa: E402
from experiment_core import ReinforcementCountExit  # noqa: E402
from experiment_io import drive  # noqa: E402
from experiment_io.hw.backends.virtual import (  # noqa: E402
    ManualClock,
    MatchingSubject,
    MultiVirtualOperandum,
    RecordingReinforcer,
)
from session_analyzer.analytics.choice import compute_choice_allocation  # noqa: E402
from session_analyzer.analytics.matching import estimate_matching_parameters  # noqa: E402
from session_recorder import OklSink, iter_records  # noqa: E402
from session_runner import SessionConfig, SessionRunner, tee  # noqa: E402

# Herrnstein (1961): mean intervals in seconds for keys A and B; None = EXT.
CONDITIONS: tuple[tuple[str, float, float | None], ...] = (
    ("vi180_vi180", 180.0, 180.0),
    ("vi135_vi270", 135.0, 270.0),
    ("vi108_vi540", 108.0, 540.0),
    ("vi90_ext", 90.0, None),
)
COD_S = 1.5
REINFORCERS = 60
SESSIONS = 5
REINFORCER_DURATION_S = 4.0
SEED = 1961

_ANNOTATIONS = ExtensionRegistry.build(TemporalExtension())


@dataclass(frozen=True)
class ConditionResult:
    condition: str
    dsl: str
    responses: tuple[int, int]
    reinforcers: tuple[int, int]
    relative_responses: float
    relative_reinforcers: float


@dataclass(frozen=True)
class Summary:
    conditions: tuple[ConditionResult, ...]
    sensitivity: float
    bias: float
    r_squared: float
    max_deviation: float


def condition_dsl(a_s: float, b_s: float | None, *, cod: bool = True, seed: int = SEED) -> str:
    """The contingency-dsl source for one session of one condition."""
    key_b = "EXT" if b_s is None else f"VI {b_s:g}-s"
    cod_arg = f", COD={COD_S:g}-s" if cod else ""
    return (
        f'@algorithm("fleshler-hoffman", n=12, seed={seed})\nConc(VI {a_s:g}-s, {key_b}{cod_arg})'
    )


def build_subject(seed: int) -> MatchingSubject:
    # Default melioration rates; stay=0.9 keeps runs on one key long enough
    # that most responses fall outside the changeover delay.
    return MatchingSubject(rate_hz=1.0, learning_rate=0.003, step_size=0.01, stay=0.9, seed=seed)


def run_session(okl_path: Path, dsl: str, subject: MatchingSubject, *, name: str) -> Path:
    """Run one 60-reinforcer session and write its OKL v1 log to ``okl_path``."""
    clock = ManualClock()
    operanda = MultiVirtualOperandum(subject, clock).split()
    reinforcers = [RecordingReinforcer(operandum_index=i) for i in range(len(operanda))]
    metadata = {"dsl": dsl, "subject": "MatchingSubject"}

    # OklSink refuses to append a header to a non-empty file; each session
    # (and each re-run) replaces the previous log.
    okl_path.unlink(missing_ok=True)
    sink = OklSink(okl_path)
    sink.write_header(
        session_name=name,
        clock_type=type(clock).__name__,
        session_start=0.0,
        metadata=metadata,
    )
    runner = SessionRunner(
        SessionConfig(
            name=name,
            schedule=from_dsl(parse(dsl, extensions=_ANNOTATIONS)),
            exit_condition=ReinforcementCountExit(count=REINFORCERS),
            metadata=metadata,
        ),
        sink=tee(sink),
        clock=clock,
    )
    runner.start(start_time=clock())
    drive(
        runner,
        operanda=operanda,
        reinforcers=reinforcers,
        clock=clock,
        reinforcer_duration=REINFORCER_DURATION_S,
        max_steps=1_000_000,
    )
    return okl_path


def count_events(okl_path: Path) -> tuple[tuple[int, int], tuple[int, int]]:
    """Responses and reinforcers per key (A = operandum 0, B = operandum 1)."""
    responses = [0, 0]
    reinforcers = [0, 0]
    for record in iter_records(okl_path):
        if record.type == "response":
            responses[int(record.args["operandum"])] += 1
        elif record.type == "reinforcer_start":
            reinforcers[int(record.args["operandum"])] += 1
    return (responses[0], responses[1]), (reinforcers[0], reinforcers[1])


def run_condition(
    out_dir: Path, name: str, a_s: float, b_s: float | None, *, cod: bool = True, seed: int = SEED
) -> ConditionResult:
    """Run ``SESSIONS`` sessions of one condition with one subject; analyse the last."""
    subject = build_subject(seed)
    okl_path = out_dir / f"concurrent_vi_matching_{name}.okl"
    for session in range(SESSIONS):
        # Each session draws a fresh Fleshler-Hoffman sequence; the subject carries over.
        dsl = condition_dsl(a_s, b_s, cod=cod, seed=seed + session)
        run_session(okl_path, dsl, subject, name=f"concurrent_vi_matching_{name}")
    responses, reinforcers = count_events(okl_path)
    allocation = compute_choice_allocation(responses)
    return ConditionResult(
        condition=name,
        dsl=dsl,
        responses=responses,
        reinforcers=reinforcers,
        relative_responses=allocation.proportions[0],
        relative_reinforcers=reinforcers[0] / sum(reinforcers),
    )


def summarize(results: Sequence[ConditionResult]) -> Summary:
    """Fit the generalized matching law over the conditions that reinforce both keys."""
    both = [r for r in results if r.reinforcers[1] > 0 and r.responses[1] > 0]
    fit = estimate_matching_parameters(
        [r.responses[0] / r.responses[1] for r in both],
        [r.reinforcers[0] / r.reinforcers[1] for r in both],
    )
    return Summary(
        conditions=tuple(results),
        sensitivity=fit.sensitivity,
        bias=fit.bias,
        r_squared=fit.r_squared,
        max_deviation=max(abs(r.relative_responses - r.relative_reinforcers) for r in results),
    )


def run_experiment(out_dir: Path, *, cod: bool = True, seed: int = SEED) -> Summary:
    """Run all four conditions and return the matching summary."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [
        run_condition(out_dir, name, a_s, b_s, cod=cod, seed=seed + 10 * i)
        for i, (name, a_s, b_s) in enumerate(CONDITIONS)
    ]
    return summarize(results)


def plot_matching(summary: Summary, png_path: Path, *, title: str) -> Path:
    """Relative responses against relative reinforcement on key A (Herrnstein's Fig. 1)."""
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], color="0.6", linewidth=1, label="perfect matching")
    ax.scatter(
        [r.relative_reinforcers for r in summary.conditions],
        [r.relative_responses for r in summary.conditions],
        color="black",
        zorder=3,
        label="virtual subject",
    )
    for r in summary.conditions:
        ax.annotate(
            r.condition,
            (r.relative_reinforcers, r.relative_responses),
            textcoords="offset points",
            xytext=(6, -10),
            fontsize=8,
        )
    ax.set_xlim(0, 1.05)
    ax.set_ylim(0, 1.05)
    ax.set_aspect("equal")
    ax.set_xlabel("Relative reinforcement on key A")
    ax.set_ylabel("Relative responses on key A")
    ax.set_title(title, fontsize=10)
    ax.text(
        0.04,
        0.96,
        f"a = {summary.sensitivity:.2f}, log b = {summary.bias:.2f}, R² = {summary.r_squared:.2f}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
    )
    ax.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    fig.savefig(png_path, dpi=120)
    plt.close(fig)
    return png_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--no-cod", action="store_true", help="drop the changeover delay")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    out_dir = args.out_dir / "no_cod" if args.no_cod else args.out_dir
    summary = run_experiment(out_dir, cod=not args.no_cod, seed=args.seed)
    title = "Concurrent VI VI, no COD" if args.no_cod else f"Concurrent VI VI, COD {COD_S:g} s"
    png_path = plot_matching(summary, out_dir / "concurrent_vi_matching.png", title=title)

    report = asdict(summary)
    for row in report["conditions"]:
        row["relative_responses"] = round(row["relative_responses"], 3)
        row["relative_reinforcers"] = round(row["relative_reinforcers"], 3)
    for key in ("sensitivity", "bias", "r_squared", "max_deviation"):
        report[key] = round(report[key], 3)
    print(json.dumps({"png": str(png_path), **report}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
