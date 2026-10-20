"""Run a published procedure from its DOI and judge the expected pattern."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "examples" / "paper_procedure" / "run.py"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
HIGA = "10.1016/j.beproc.2004.08.007"


@pytest.fixture(scope="module")
def paper() -> ModuleType:
    spec = importlib.util.spec_from_file_location("example_paper_procedure", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_command_writes_okl_and_png_from_a_doi(tmp_path: Path) -> None:
    result = _run("--doi", HIGA, "--out-dir", str(tmp_path))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["dsl"] == "FI30s"
    assert Path(report["okl"]).stat().st_size > 0
    assert Path(report["png"]).read_bytes()[:8] == PNG_MAGIC
    assert report["reinforcers"] == 30


def test_higa_simm_pattern_matches(paper: ModuleType, tmp_path: Path) -> None:
    report = paper.run_paper(HIGA, tmp_path)
    assert report.judgement.matched, report.judgement


def test_poisson_control_does_not_match(paper: ModuleType, tmp_path: Path) -> None:
    # The judge must tell the expected pattern from a constant rate.
    report = paper.run_paper(HIGA, tmp_path, control=True)
    assert not report.judgement.matched, report.judgement


def test_reproducible_under_seed(paper: ModuleType, tmp_path: Path) -> None:
    a = paper.run_paper(HIGA, tmp_path / "a")
    b = paper.run_paper(HIGA, tmp_path / "b")
    assert Path(a.okl).read_bytes() == Path(b.okl).read_bytes()


def test_dsl_is_read_from_a_generated_dsl_directory(paper: ModuleType, tmp_path: Path) -> None:
    (tmp_path / "10.1016_j.beproc.2004.08.007.dsl").write_text("FI30s\n", encoding="utf-8")
    assert paper.extract_dsl(HIGA, tmp_path) == "FI30s"


def test_one_block_is_chosen_from_a_multi_block_file(paper: ModuleType, tmp_path: Path) -> None:
    text = '# EXPERIMENT 1\n@species("pigeon")\nVI12s\n\n# EXPERIMENT 2\n@species("pigeon")\n@n(3)\nFI30s\n'
    (tmp_path / "10.9999_x.dsl").write_text(text, encoding="utf-8")
    assert paper.extract_dsl("10.9999/x", tmp_path, block="FI30s") == '@species("pigeon")\n@n(3)\nFI30s'
    assert paper.extract_dsl("10.9999/x", tmp_path, block="1") == '@species("pigeon")\nVI12s'
    with pytest.raises(ValueError, match="2 blocks"):
        paper.extract_dsl("10.9999/x", tmp_path)


def test_annotated_block_compiles(paper: ModuleType) -> None:
    schedule = paper.compile_dsl('@species("pigeon")\n@n(3)\nFI30s')
    assert type(schedule).__name__ == "FI"


def test_unknown_doi_fails_with_a_message(tmp_path: Path) -> None:
    result = _run("--doi", "10.9999/not-in-catalog", "--out-dir", str(tmp_path))
    assert result.returncode != 0
    assert "not in the catalog" in result.stderr
