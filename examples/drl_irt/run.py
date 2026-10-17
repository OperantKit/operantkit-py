"""Differential reinforcement of low rate (DRL) with a virtual subject.

Runs ``DRL 10-s`` for 1800 s of session time through the public
OperantKit pipeline (contingency-dsl → contingency-py schedule →
session-runner → experiment-io ``drive`` → OKL v1 log). A response is
reinforced only when at least 10 s have passed since the previous
response. It writes, next to this file:

- ``drl_irt.okl`` — the session event log
- ``drl_irt_histogram.png`` — inter-response time (IRT) histograms of the
  first and last 600 s, with the 10-s interval marked
- ``drl_irt_cumulative.png`` — the IRT-coded cumulative record (same as
  ``session-analyzer diff-plot drl_irt.okl --threshold 10 --output drl_irt_cumulative.png``)

and prints the share of IRTs at or above 10 s and the response rate in
the first and last 600 s.

Usage::

    python examples/drl_irt/run.py
    python examples/drl_irt/run.py --subject poisson   # control
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
from experiment_core import TimeLimitExit  # noqa: E402
from experiment_io import drive  # noqa: E402
from experiment_io.hw.backends.virtual import (  # noqa: E402
    ManualClock,
    RecordingReinforcer,
    SingleSubject,
    SpacedRespondingSubject,
    VirtualOperandum,
    VirtualSubject,
)
from session_analyzer.visualizer.cumulative_diff import (  # noqa: E402
    plot_irt_coded_cumulative_record,
)
from session_recorder import OklSink, iter_records  # noqa: E402
from session_runner import SessionConfig, SessionRunner, tee  # noqa: E402

DSL = "DRL 10-s"
INTERVAL_S = 10.0
SESSION_S = 1800.0
WINDOW_S = 600.0
REINFORCER_DURATION_S = 0.5
SEED = 1953
SUBJECTS = ("spaced", "poisson")


@dataclass(frozen=True)
class Summary:
    responses: int
    reinforcers: int
    long_fraction: float
    early_long_fraction: float
    late_long_fraction: float
    early_rate: float
    late_rate: float


def build_subject(kind: str, seed: int) -> SingleSubject:
    if kind == "spaced":
        # Mean IRT starts at 1 s and is shaped by which IRTs are reinforced.
        return SpacedRespondingSubject(seed=seed)
    if kind == "poisson":
        # Memoryless control: a constant 1 Hz regardless of reinforcement.
        return VirtualSubject(rate_hz=1.0, seed=seed)
    raise ValueError(f"unknown subject {kind!r}; choose from {SUBJECTS}")


def run_session(okl_path: Path, *, subject: str = "spaced", seed: int = SEED) -> Path:
    """Run one DRL session and write its OKL v1 log to ``okl_path``."""
    clock = ManualClock()
    operanda = [VirtualOperandum(0, build_subject(subject, seed), clock)]
    reinforcers = [RecordingReinforcer(operandum_index=0)]
    metadata = {"dsl": DSL, "subject": subject, "seed": seed}

    # OklSink refuses to append a header to a non-empty file; a re-run
    # replaces the previous log.
    okl_path.unlink(missing_ok=True)
    sink = OklSink(okl_path)
    sink.write_header(
        session_name="drl_irt",
        clock_type=type(clock).__name__,
        session_start=0.0,
        metadata=metadata,
    )
    runner = SessionRunner(
        SessionConfig(
            name="drl_irt",
            schedule=from_dsl(parse(DSL)),
            exit_condition=TimeLimitExit(limit=SESSION_S),
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


def _irts(okl_path: Path) -> tuple[list[tuple[float, float]], int]:
    """Return (time of response, IRT ending at it) pairs and the reinforcer count.

    The IRT is measured between consecutive responses, as the DRL
    contingency measures it; the first response has no IRT.
    """
    times: list[float] = []
    reinforcers = 0
    for record in iter_records(okl_path):
        if record.type == "response":
            times.append(record.timestamp)
        elif record.type == "reinforcer_start":
            reinforcers += 1
    pairs = [(t, t - prev) for prev, t in zip(times, times[1:], strict=False)]
    return pairs, reinforcers


def _long_fraction(irts: Sequence[float]) -> float:
    return sum(1 for irt in irts if irt >= INTERVAL_S) / len(irts) if irts else 0.0


def _windows(pairs: Sequence[tuple[float, float]]) -> tuple[list[float], list[float]]:
    early = [irt for t, irt in pairs if t < WINDOW_S]
    late = [irt for t, irt in pairs if t >= SESSION_S - WINDOW_S]
    return early, late


def summarize(okl_path: Path) -> Summary:
    """Compute the DRL measures from an OKL log.

    The early and late windows are the first and last 600 s of the
    session. Each IRT is assigned to the window of the response that ends
    it. Rates are responses per second within the window.
    """
    pairs, reinforcers = _irts(okl_path)
    early, late = _windows(pairs)
    return Summary(
        responses=len(pairs) + 1 if pairs else 0,
        reinforcers=reinforcers,
        long_fraction=_long_fraction([irt for _, irt in pairs]),
        early_long_fraction=_long_fraction(early),
        late_long_fraction=_long_fraction(late),
        early_rate=len(early) / WINDOW_S,
        late_rate=len(late) / WINDOW_S,
    )


def plot_irt_histogram(okl_path: Path, png_path: Path) -> Path:
    """Overlay the IRT histograms of the first and last 600 s."""
    early, late = _windows(_irts(okl_path)[0])
    bins = [i * 1.0 for i in range(0, 31)]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(early, bins=bins, alpha=0.5, label=f"first {WINDOW_S:g} s (n={len(early)})")
    ax.hist(late, bins=bins, alpha=0.5, label=f"last {WINDOW_S:g} s (n={len(late)})")
    ax.axvline(INTERVAL_S, color="black", linestyle="--", label=f"DRL {INTERVAL_S:g} s")
    ax.set_xlabel("Inter-response time (s)")
    ax.set_ylabel("Responses")
    ax.set_title(f"{DSL}: IRT distribution")
    ax.legend()
    fig.tight_layout()
    fig.savefig(png_path, dpi=100, metadata={"Software": None})
    plt.close(fig)
    return png_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--subject", choices=SUBJECTS, default="spaced")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stem = "drl_irt" if args.subject == "spaced" else f"drl_irt_{args.subject}"
    okl_path = run_session(args.out_dir / f"{stem}.okl", subject=args.subject, seed=args.seed)
    histogram = plot_irt_histogram(okl_path, args.out_dir / f"{stem}_histogram.png")
    cumulative = args.out_dir / f"{stem}_cumulative.png"
    plot_irt_coded_cumulative_record(okl_path, cumulative, irt_threshold_sec=INTERVAL_S)

    summary = summarize(okl_path)
    print(
        json.dumps(
            {
                "okl": str(okl_path),
                "histogram": str(histogram),
                "cumulative": str(cumulative),
                **asdict(summary),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
