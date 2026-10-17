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


# The FI pattern itself is judged against published values in tests/laws/.


def test_fi_scallop_is_reproducible_under_seed(fi_scallop: ModuleType, tmp_path: Path) -> None:
    a = fi_scallop.run_session(tmp_path / "a.okl")
    b = fi_scallop.run_session(tmp_path / "b.okl")
    assert a.read_bytes() == b.read_bytes()


@pytest.fixture(scope="module")
def matching() -> ModuleType:
    return _load("concurrent_vi_matching")


@pytest.fixture(scope="module")
def matching_summary(matching: ModuleType, tmp_path_factory: pytest.TempPathFactory) -> object:
    return matching.run_experiment(tmp_path_factory.mktemp("matching"))


def test_matching_command_writes_okl_and_png(tmp_path: Path) -> None:
    script = EXAMPLES / "concurrent_vi_matching" / "run.py"
    result = subprocess.run(
        [sys.executable, str(script), "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "concurrent_vi_matching.png").read_bytes()[:8] == PNG_MAGIC
    okls = sorted(tmp_path.glob("concurrent_vi_matching_*.okl"))
    assert len(okls) == 4
    assert all(p.stat().st_size > 0 for p in okls)


def test_matching_fits_the_generalized_matching_law(matching_summary: object) -> None:
    # Fitted over the three conditions that reinforce both keys.
    assert 0.8 <= matching_summary.sensitivity <= 1.2
    assert matching_summary.r_squared > 0.9


def test_matching_relative_responses_track_relative_reinforcers(
    matching_summary: object,
) -> None:
    assert len(matching_summary.conditions) == 4
    for row in matching_summary.conditions:
        assert sum(row.reinforcers) == 60
        assert abs(row.relative_responses - row.relative_reinforcers) <= 0.10, row


def test_matching_is_reproducible_under_seed(
    matching: ModuleType, matching_summary: object, tmp_path: Path
) -> None:
    first = matching.run_experiment(tmp_path / "a")
    second = matching.run_experiment(tmp_path / "b")
    assert first == second == matching_summary
    for name, _, _ in matching.CONDITIONS:
        okl = f"concurrent_vi_matching_{name}.okl"
        assert (tmp_path / "a" / okl).read_bytes() == (tmp_path / "b" / okl).read_bytes()


@pytest.fixture(scope="module")
def drl() -> ModuleType:
    return _load("drl_irt")


def test_drl_command_writes_okl_and_pngs(tmp_path: Path) -> None:
    script = EXAMPLES / "drl_irt" / "run.py"
    result = subprocess.run(
        [sys.executable, str(script), "--out-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "drl_irt.okl").stat().st_size > 0
    assert (tmp_path / "drl_irt_histogram.png").read_bytes()[:8] == PNG_MAGIC
    assert (tmp_path / "drl_irt_cumulative.png").read_bytes()[:8] == PNG_MAGIC


def test_drl_spaces_responses_past_the_interval(drl: ModuleType, tmp_path: Path) -> None:
    summary = drl.summarize(drl.run_session(tmp_path / "s.okl"))
    # Share of IRTs >= 10 s among responses in the last 600 s of the session.
    assert summary.late_long_fraction >= 0.5
    assert summary.late_long_fraction > summary.early_long_fraction
    # The overall rate falls, as in Ferster and Skinner's drl.
    assert summary.late_rate < summary.early_rate


def test_drl_poisson_control_rarely_waits(drl: ModuleType, tmp_path: Path) -> None:
    summary = drl.summarize(drl.run_session(tmp_path / "p.okl", subject="poisson"))
    assert summary.long_fraction < 0.05


def test_drl_is_reproducible_under_seed(drl: ModuleType, tmp_path: Path) -> None:
    a = drl.run_session(tmp_path / "a.okl")
    b = drl.run_session(tmp_path / "b.okl")
    assert a.read_bytes() == b.read_bytes()


@pytest.mark.parametrize("name", ["fi_scallop", "drl_irt"])
def test_example_command_can_rerun_over_its_own_output(name: str, tmp_path: Path) -> None:
    # The repository ships each example's output, so the first run after a
    # clone writes over an existing OKL log.
    script = EXAMPLES / name / "run.py"
    for _ in range(2):
        result = subprocess.run(
            [sys.executable, str(script), "--out-dir", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
