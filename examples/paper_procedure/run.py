"""Run the procedure of a published experiment from its DOI.

Looks the DOI up in ``papers.json`` (next to this file), takes the
contingency-dsl string extracted from the paper's Method section, runs it
with the virtual subject chosen for that paper through the public
OperantKit pipeline (contingency-dsl → contingency-py schedule →
session-runner → experiment-io ``drive`` → OKL v1 log), and writes,
next to this file:

- ``<slug>.okl`` — the session event log
- ``<slug>.png`` — the cumulative record

It then judges whether the run shows the qualitative pattern the paper
reports for the figure listed in the catalog, and prints a JSON report.
Only the qualitative pattern is compared; the paper's numbers are not.

``--dsl-dir`` reads the DSL from a directory of generated DSL files named
after the DOI (``/`` replaced by ``_``, extension ``.dsl``) instead of
the catalog. A file with several blocks (separated by blank lines) needs
``--block``: a 1-based block number or the schedule line of the block.

Usage::

    python examples/paper_procedure/run.py --doi 10.1016/j.beproc.2004.08.007
    python examples/paper_procedure/run.py --doi 10.1016/j.beproc.2004.08.007 --control
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any

from contingency.bridge import from_dsl
from contingency_dsl import parse
from contingency_dsl.annotations.apparatus.extension import ApparatusExtension
from contingency_dsl.annotations.measurement.extension import MeasurementExtension
from contingency_dsl.annotations.stimulus.extension import StimulusExtension
from contingency_dsl.annotations.subjects.extension import SubjectsExtension
from contingency_dsl.annotations.temporal.extension import TemporalExtension
from contingency_dsl.extensions import ExtensionRegistry
from experiment_core import ReinforcementCountExit
from experiment_io import drive
from experiment_io.hw.backends.virtual import (
    ManualClock,
    MatchingSubject,
    MultiSubject,
    MultiVirtualOperandum,
    MultiVirtualSubject,
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

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "papers.json"
SEED = 2004
CONTROL_RATE_HZ = 1.0

_ANNOTATIONS = ExtensionRegistry.build(
    ApparatusExtension(),
    MeasurementExtension(),
    StimulusExtension(),
    SubjectsExtension(),
    TemporalExtension(),
)


@dataclass(frozen=True)
class Judgement:
    pattern: str
    matched: bool
    measures: dict[str, float]
    criterion: str


@dataclass(frozen=True)
class Report:
    doi: str
    dsl: str
    figure: str
    expected: str
    subject: str
    okl: str
    png: str
    responses: int
    reinforcers: int
    judgement: Judgement


def load_catalog(path: Path = CATALOG) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _entry(doi: str, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    try:
        return catalog[doi]
    except KeyError:
        raise KeyError(f"DOI {doi} is not in the catalog {CATALOG.name}") from None


def _blocks(text: str) -> list[str]:
    """Split a generated DSL file into blocks, dropping ``#`` comment lines."""
    blocks: list[str] = []
    current: list[str] = []
    for line in [*text.splitlines(), ""]:
        stripped = line.strip()
        if not stripped:
            if current:
                blocks.append("\n".join(current))
                current = []
        elif not stripped.startswith("#"):
            current.append(stripped)
    return blocks


def extract_dsl(doi: str, dsl_dir: Path, block: str | None = None) -> str:
    """Return one runnable DSL block from ``<dsl_dir>/<doi with / as _>.dsl``.

    ``block`` is a 1-based block number or the schedule line (the last
    line of the block, after its annotations). It is required when the
    file holds more than one block.
    """
    path = dsl_dir / (doi.replace("/", "_") + ".dsl")
    blocks = _blocks(path.read_text(encoding="utf-8"))
    if not blocks:
        raise ValueError(f"{path.name} holds no DSL")
    if block is None:
        if len(blocks) == 1:
            return blocks[0]
        raise ValueError(f"{path.name} holds {len(blocks)} blocks; choose one with --block")
    if block.isdigit():
        index = int(block)
        if not 1 <= index <= len(blocks):
            raise ValueError(f"--block {index} is out of range 1..{len(blocks)}")
        return blocks[index - 1]
    for candidate in blocks:
        if candidate.splitlines()[-1] == block:
            return candidate
    raise ValueError(f"no block in {path.name} ends with {block!r}")


def compile_dsl(dsl: str) -> Any:
    """Parse a DSL block (program-level annotations allowed) into a schedule."""
    return from_dsl(parse(dsl, extensions=_ANNOTATIONS))


DEFAULT_CONTROL = {"kind": "poisson", "rate_hz": CONTROL_RATE_HZ}

Subject = SingleSubject | MultiSubject


def control_spec(entry: dict[str, Any]) -> dict[str, Any]:
    """The control subject of a catalog entry (a 1-Hz Poisson subject by default)."""
    return entry.get("control", DEFAULT_CONTROL)


def build_subject(spec: dict[str, Any], seed: int) -> Subject:
    params = {k: v for k, v in spec.items() if k != "kind"}
    if spec["kind"] == "scallop":
        return ScallopSubject(seed=seed, **params)
    if spec["kind"] == "poisson":
        return VirtualSubject(seed=seed, **params)
    if spec["kind"] == "matching":
        return MatchingSubject(seed=seed, **params)
    if spec["kind"] == "poisson-keys":
        # Independent Poisson responders, one per key: indifferent to reinforcement.
        rates = params["rates_hz"]
        return MultiVirtualSubject(rates, [seed + i for i in range(len(rates))])
    raise ValueError(f"unknown subject kind {spec['kind']!r}")


def _operanda(subject: Subject, clock: ManualClock) -> list[Any]:
    if hasattr(subject, "next_event"):
        return list(MultiVirtualOperandum(subject, clock).split())
    return [VirtualOperandum(0, subject, clock)]


def run_session(
    okl_path: Path,
    dsl: str,
    subject: Subject,
    *,
    reinforcers: int,
    reinforcer_duration_s: float,
    metadata: dict[str, Any],
) -> Path:
    clock = ManualClock()
    operanda = _operanda(subject, clock)
    okl_path.unlink(missing_ok=True)
    sink = OklSink(okl_path)
    sink.write_header(
        session_name=okl_path.stem,
        clock_type=type(clock).__name__,
        session_start=0.0,
        metadata=metadata,
    )
    runner = SessionRunner(
        SessionConfig(
            name=okl_path.stem,
            schedule=compile_dsl(dsl),
            exit_condition=ReinforcementCountExit(count=reinforcers),
            metadata=metadata,
        ),
        sink=tee(sink),
        clock=clock,
    )
    runner.start(start_time=clock())
    drive(
        runner,
        operanda=operanda,
        reinforcers=[RecordingReinforcer(operandum_index=i) for i in range(len(operanda))],
        clock=clock,
        reinforcer_duration=reinforcer_duration_s,
        max_steps=1_000_000,
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


def judge_rate_rises_within_interval(okl_path: Path) -> Judgement:
    """Responding concentrates late in each inter-reinforcer interval.

    An interval runs from the end of one reinforcer (or session start) to
    the next reinforcer. It "accelerates" when its second half holds more
    responses than its first half. The quarter-life (session-analyzer) is
    about 0.25 for a constant rate and larger when responding is late.
    """
    responses, starts, ends = _event_times(okl_path)
    onsets = [0.0, *ends[: len(starts) - 1]]
    accelerating = 0
    for onset, stop in zip(onsets, starts, strict=True):
        mid = (onset + stop) / 2
        first = sum(1 for t in responses if onset <= t < mid)
        second = sum(1 for t in responses if mid <= t < stop)
        accelerating += second > first
    fraction = accelerating / len(starts) if starts else 0.0
    quarter_life = median(compute_quarter_life(onsets, responses)) if starts else 0.0
    return Judgement(
        pattern="rate_rises_within_interval",
        matched=fraction >= 0.8 and quarter_life >= 0.4,
        measures={
            "accelerating_fraction": round(fraction, 3),
            "median_quarter_life": round(quarter_life, 3),
        },
        criterion="second half > first half in at least 80% of intervals and median quarter-life >= 0.4",
    )


def _pauses_and_run_irts(okl_path: Path) -> tuple[list[float], list[float]]:
    """Per interval: the pause (reinforcer end to first response) and the later IRTs.

    An interval runs from the end of one reinforcer (or session start) to
    the onset of the next reinforcer.
    """
    responses, starts, ends = _event_times(okl_path)
    onsets = [0.0, *ends[: len(starts) - 1]]
    pauses: list[float] = []
    run_irts: list[float] = []
    for onset, stop in zip(onsets, starts, strict=True):
        within = [t for t in responses if onset <= t <= stop]
        if not within:
            continue
        pauses.append(within[0] - onset)
        run_irts.extend(b - a for a, b in zip(within, within[1:], strict=False))
    return pauses, run_irts


def judge_pause_then_run(okl_path: Path) -> Judgement:
    """Break-and-run: a pause after each reinforcer, then fast responding.

    The pause of an interval counts as a "break" when it is at least
    three times the median IRT within the runs of the session. A constant
    rate gives pauses about as long as an IRT.
    """
    pauses, run_irts = _pauses_and_run_irts(okl_path)
    run_irt = median(run_irts) if run_irts else 0.0
    breaks = sum(1 for p in pauses if run_irt > 0 and p >= 3 * run_irt)
    fraction = breaks / len(pauses) if pauses else 0.0
    return Judgement(
        pattern="pause_then_run",
        matched=fraction >= 0.8,
        measures={
            "break_fraction": round(fraction, 3),
            "median_pause_s": round(median(pauses), 3) if pauses else 0.0,
            "median_run_irt_s": round(run_irt, 3),
        },
        criterion="pause >= 3 x median run IRT in at least 80% of intervals",
    )


def judge_no_postreinforcement_pause(okl_path: Path) -> Judgement:
    """Steady responding: no pause after reinforcement, a straight record.

    Matches when the median pause after a reinforcer is at most twice the
    median IRT within the runs, at most 20% of intervals hold a "break"
    (pause >= 3 x median run IRT), and the median quarter-life is near
    the 0.25 of a constant rate (0.18 to 0.32).
    """
    pauses, run_irts = _pauses_and_run_irts(okl_path)
    run_irt = median(run_irts) if run_irts else 0.0
    pause = median(pauses) if pauses else 0.0
    breaks = sum(1 for p in pauses if run_irt > 0 and p >= 3 * run_irt)
    fraction = breaks / len(pauses) if pauses else 0.0
    responses, starts, ends = _event_times(okl_path)
    onsets = [0.0, *ends[: len(starts) - 1]]
    quarter_life = median(compute_quarter_life(onsets, responses)) if starts else 0.0
    return Judgement(
        pattern="no_postreinforcement_pause",
        matched=run_irt > 0
        and pause <= 2 * run_irt
        and fraction <= 0.2
        and 0.18 <= quarter_life <= 0.32,
        measures={
            "median_pause_s": round(pause, 3),
            "median_run_irt_s": round(run_irt, 3),
            "break_fraction": round(fraction, 3),
            "median_quarter_life": round(quarter_life, 3),
        },
        criterion=(
            "median pause <= 2 x median run IRT, breaks in at most 20% of intervals, "
            "and median quarter-life 0.18-0.32"
        ),
    )


def judge_constant_rate_within_interval(okl_path: Path) -> Judgement:
    """No acceleration within inter-reinforcer intervals (a constant local rate).

    Matches when the share of intervals whose second half holds more
    responses than the first is between 0.3 and 0.7 and the median
    quarter-life is near the 0.25 of a constant rate (0.15 to 0.35).
    """
    responses, starts, ends = _event_times(okl_path)
    onsets = [0.0, *ends[: len(starts) - 1]]
    accelerating = 0
    for onset, stop in zip(onsets, starts, strict=True):
        mid = (onset + stop) / 2
        first = sum(1 for t in responses if onset <= t < mid)
        second = sum(1 for t in responses if mid <= t < stop)
        accelerating += second > first
    fraction = accelerating / len(starts) if starts else 0.0
    quarter_life = median(compute_quarter_life(onsets, responses)) if starts else 0.0
    return Judgement(
        pattern="constant_rate_within_interval",
        matched=0.3 <= fraction <= 0.7 and 0.15 <= quarter_life <= 0.35,
        measures={
            "accelerating_fraction": round(fraction, 3),
            "median_quarter_life": round(quarter_life, 3),
        },
        criterion="second half > first half in 30-70% of intervals and median quarter-life 0.15-0.35",
    )


def _per_key_counts(okl_path: Path) -> tuple[list[int], list[int]]:
    responses = [0, 0]
    reinforcers = [0, 0]
    for record in iter_records(okl_path):
        if record.type == "response":
            responses[int(record.args["operandum"])] += 1
        elif record.type == "reinforcer_start":
            reinforcers[int(record.args["operandum"])] += 1
    return responses, reinforcers


def judge_relative_rate_matches_reinforcement(okl_path: Path, target: float = 0.75) -> Judgement:
    """Relative response rate on key A is near the relative reinforcement rate.

    Stubbs and Pliskoff's VI 1-min / VI 3-min condition programs a
    relative reinforcement rate of 0.75 on key A. Matches when key A's
    share of responses is within 0.10 of both 0.75 and the obtained
    relative reinforcement rate.
    """
    responses, reinforcers = _per_key_counts(okl_path)
    rel_responses = responses[0] / sum(responses) if sum(responses) else 0.0
    rel_reinforcers = reinforcers[0] / sum(reinforcers) if sum(reinforcers) else 0.0
    return Judgement(
        pattern="relative_rate_matches_reinforcement",
        matched=abs(rel_responses - target) <= 0.10 and abs(rel_responses - rel_reinforcers) <= 0.10,
        measures={
            "relative_responses_a": round(rel_responses, 3),
            "relative_reinforcers_a": round(rel_reinforcers, 3),
            "responses_a": float(responses[0]),
            "responses_b": float(responses[1]),
        },
        criterion=f"key A share of responses within 0.10 of {target} and of the obtained share of reinforcers",
    )


JUDGES = {
    "rate_rises_within_interval": judge_rate_rises_within_interval,
    "pause_then_run": judge_pause_then_run,
    "no_postreinforcement_pause": judge_no_postreinforcement_pause,
    "constant_rate_within_interval": judge_constant_rate_within_interval,
    "relative_rate_matches_reinforcement": judge_relative_rate_matches_reinforcement,
}


def run_paper(
    doi: str,
    out_dir: Path,
    *,
    control: bool = False,
    seed: int = SEED,
    dsl_dir: Path | None = None,
    block: str | None = None,
    catalog: dict[str, dict[str, Any]] | None = None,
) -> Report:
    entry = _entry(doi, catalog if catalog is not None else load_catalog())
    dsl = extract_dsl(doi, dsl_dir, block) if dsl_dir is not None else entry["dsl"]
    spec = control_spec(entry) if control else entry["subject"]
    subject_name = f"{spec['kind']}-control" if control else spec["kind"]
    stem = entry["slug"] + ("_control" if control else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    subject = build_subject(spec, seed)
    okl_path = out_dir / f"{stem}.okl"
    # Several sessions train a learning subject; only the last one is kept.
    for _ in range(entry.get("sessions", 1)):
        run_session(
            okl_path,
            dsl,
            subject,
            reinforcers=entry["reinforcers"],
            reinforcer_duration_s=entry["reinforcer_duration_s"],
            metadata={"doi": doi, "dsl": dsl, "subject": subject_name, "seed": seed},
        )
    png_path = out_dir / f"{stem}.png"
    plot_cumulative_record(okl_path, png_path)
    responses, starts, _ = _event_times(okl_path)
    return Report(
        doi=doi,
        dsl=dsl,
        figure=entry["figure"],
        expected=entry["expected"],
        subject=subject_name,
        okl=str(okl_path),
        png=str(png_path),
        responses=len(responses),
        reinforcers=len(starts),
        judgement=JUDGES[entry["judge"]](okl_path),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--doi", default=None, help="default: the first DOI in papers.json")
    parser.add_argument("--out-dir", type=Path, default=HERE)
    parser.add_argument("--dsl-dir", type=Path, default=None)
    parser.add_argument("--block", default=None)
    parser.add_argument(
        "--control", action="store_true", help="run the catalog's control subject instead"
    )
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    doi = args.doi if args.doi is not None else next(iter(load_catalog()))
    try:
        report = run_paper(
            doi,
            args.out_dir,
            control=args.control,
            seed=args.seed,
            dsl_dir=args.dsl_dir,
            block=args.block,
        )
    except (KeyError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
