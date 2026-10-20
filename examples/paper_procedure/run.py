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


def build_subject(spec: dict[str, Any], seed: int, *, control: bool = False) -> SingleSubject:
    if control:
        # Memoryless control: a constant rate regardless of reinforcement.
        return VirtualSubject(rate_hz=CONTROL_RATE_HZ, seed=seed)
    params = {k: v for k, v in spec.items() if k != "kind"}
    if spec["kind"] == "scallop":
        return ScallopSubject(seed=seed, **params)
    if spec["kind"] == "poisson":
        return VirtualSubject(seed=seed, **params)
    raise ValueError(f"unknown subject kind {spec['kind']!r}")


def run_session(
    okl_path: Path,
    dsl: str,
    subject: SingleSubject,
    *,
    reinforcers: int,
    reinforcer_duration_s: float,
    metadata: dict[str, Any],
) -> Path:
    clock = ManualClock()
    operanda = [VirtualOperandum(0, subject, clock)]
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
        reinforcers=[RecordingReinforcer(operandum_index=0)],
        clock=clock,
        reinforcer_duration=reinforcer_duration_s,
        max_steps=200_000,
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


JUDGES = {"rate_rises_within_interval": judge_rate_rises_within_interval}


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
    subject_name = "poisson-control" if control else entry["subject"]["kind"]
    stem = entry["slug"] + ("_control" if control else "")
    out_dir.mkdir(parents=True, exist_ok=True)
    okl_path = run_session(
        out_dir / f"{stem}.okl",
        dsl,
        build_subject(entry["subject"], seed, control=control),
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
    parser.add_argument("--control", action="store_true", help="run a constant-rate Poisson subject")
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
