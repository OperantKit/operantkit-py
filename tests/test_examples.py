"""Run the classic-experiment examples and check the behavioral pattern."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def _load(name: str) -> ModuleType:
    path = EXAMPLES / name / "run.py"
    spec = importlib.util.spec_from_file_location(f"example_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fi_scallop() -> ModuleType:
    return _load("fi_scallop")


def test_fi_scallop_command_writes_okl_and_png(tmp_path: Path) -> None:
    script = EXAMPLES / "fi_scallop" / "run.py"
    result = subprocess.run(
        [sys.executable, str(script), "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "fi_scallop.okl").stat().st_size > 0
    assert (tmp_path / "fi_scallop.png").read_bytes()[:8] == PNG_MAGIC


def test_fi_scallop_responding_accelerates_within_intervals(
    fi_scallop: ModuleType, tmp_path: Path
) -> None:
    okl = fi_scallop.run_session(tmp_path / "s.okl")
    summary = fi_scallop.summarize(okl)
    assert summary.reinforcers == 30
    assert summary.accelerating_intervals >= 25
    assert summary.median_quarter_life > 0.5


def test_fi_poisson_control_shows_no_scallop(fi_scallop: ModuleType, tmp_path: Path) -> None:
    okl = fi_scallop.run_session(tmp_path / "p.okl", subject="poisson")
    summary = fi_scallop.summarize(okl)
    assert summary.reinforcers == 30
    # Constant-rate responding puts a quarter of the responses a quarter of
    # the way through the interval.
    assert 0.2 <= summary.median_quarter_life <= 0.3
    assert summary.accelerating_intervals < 25


def test_fi_scallop_is_reproducible_under_seed(fi_scallop: ModuleType, tmp_path: Path) -> None:
    a = fi_scallop.run_session(tmp_path / "a.okl")
    b = fi_scallop.run_session(tmp_path / "b.okl")
    assert a.read_bytes() == b.read_bytes()
