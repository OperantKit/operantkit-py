"""Fixed-interval scallop (Ferster & Skinner, 1957) with a virtual subject.

Runs ``FI 60-s`` for 30 reinforcers through the public OperantKit
pipeline (contingency-dsl → contingency-py schedule → session-runner →
experiment-io ``drive`` → OKL v1 log) and writes, next to this file:

- ``fi_scallop.okl`` — the session event log
- ``fi_scallop.png`` — the cumulative record (same as
  ``session-analyzer plot fi_scallop.okl --output fi_scallop.png``)

and prints the quarter-life and within-interval acceleration measures.

Usage::

    python examples/fi_scallop/run.py
    python examples/fi_scallop/run.py --subject poisson   # control
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

from contingency.bridge import from_dsl
from contingency_dsl import parse
from experiment_core import ReinforcementCountExit
from experiment_io import drive
from experiment_io.hw.backends.virtual import (
    ManualClock,
    RecordingReinforcer,
    ScallopSubject,
    SingleSubject,
    VirtualOperandum,
    VirtualSubject,
)
from session_analyzer.analytics.prp import compute_quarter_life
from session_analyzer.visualizer.cumulative_record import plot_cumulative_record
from session_recorder import OklSink, iter_records
from session_runner import SessionConfig, SessionRunner, tee

DSL = "FI 60-s"
INTERVAL_S = 60.0
REINFORCERS = 30
REINFORCER_DURATION_S = 0.5
SEED = 1957
SUBJECTS = ("scallop", "poisson")


@dataclass(frozen=True)
class Summary:
    responses: int
    reinforcers: int
    accelerating_intervals: int
    intervals: int
    median_quarter_life: float


def build_subject(kind: str, seed: int) -> SingleSubject:
    if kind == "scallop":
        # Hazard rises as (t / 60 s)^2 since the last reinforcer, up to 2 Hz.
        return ScallopSubject(max_rate_hz=2.0, ramp_s=INTERVAL_S, seed=seed)
    if kind == "poisson":
        # Memoryless control: a constant 1 Hz regardless of reinforcement.
        return VirtualSubject(rate_hz=1.0, seed=seed)
    raise ValueError(f"unknown subject {kind!r}; choose from {SUBJECTS}")


def run_session(okl_path: Path, *, subject: str = "scallop", seed: int = SEED) -> Path:
    """Run one FI session and write its OKL v1 log to ``okl_path``."""
    clock = ManualClock()
    operanda = [VirtualOperandum(0, build_subject(subject, seed), clock)]
    reinforcers = [RecordingReinforcer(operandum_index=0)]
    metadata = {"dsl": DSL, "subject": subject, "seed": seed}

    sink = OklSink(okl_path)
    sink.write_header(
        session_name="fi_scallop",
        clock_type=type(clock).__name__,
        session_start=0.0,
        metadata=metadata,
    )
    runner = SessionRunner(
        SessionConfig(
            name="fi_scallop",
            schedule=from_dsl(parse(DSL)),
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
        max_steps=100_000,
    )
    return okl_path


def _event_times(okl_path: Path) -> tuple[list[float], list[float], list[float]]:
    responses: list[float] = []
    starts: list[float] = []
    ends: list[float] = []
    for record in iter_records(okl_path):
        if record.type == "response":
            responses.append(record.timestamp)
        elif record.type == "reinforcer_start":
            starts.append(record.timestamp)
        elif record.type == "reinforcer_end":
            ends.append(record.timestamp)
    return responses, starts, ends


def summarize(okl_path: Path) -> Summary:
    """Compute the FI pattern measures from an OKL log.

    Each interval runs from the end of the previous reinforcer (or the
    session start) to the next reinforcer. An interval "accelerates" when
    its second half holds more responses than its first half. The
    quarter-life is the fraction of the
    interval elapsed when a quarter of its responses have occurred:
    about 0.25 for a constant rate, higher when responding accelerates.
    """
    responses, starts, ends = _event_times(okl_path)
    onsets = [0.0, *ends[: len(starts) - 1]]
    accelerating = 0
    for onset, stop in zip(onsets, starts, strict=True):
        mid = (onset + stop) / 2
        first = sum(1 for t in responses if onset <= t < mid)
        second = sum(1 for t in responses if mid <= t < stop)
        if second > first:
            accelerating += 1
    quarter_lives = compute_quarter_life([0.0, *starts], responses)
    return Summary(
        responses=len(responses),
        reinforcers=len(starts),
        accelerating_intervals=accelerating,
        intervals=len(starts),
        median_quarter_life=median(quarter_lives),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--subject", choices=SUBJECTS, default="scallop")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = "fi_scallop" if args.subject == "scallop" else f"fi_scallop_{args.subject}"
    okl_path = run_session(args.out_dir / f"{stem}.okl", subject=args.subject, seed=args.seed)
    png_path = args.out_dir / f"{stem}.png"
    plot_cumulative_record(okl_path, png_path)

    summary = summarize(okl_path)
    print(json.dumps({"okl": str(okl_path), "png": str(png_path), **asdict(summary)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
