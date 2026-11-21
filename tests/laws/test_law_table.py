"""The expectation table is complete and the law-suite documents are current."""

from __future__ import annotations

import pytest
from expectations import EXPECTATIONS, LAWS, OUT_OF_SCOPE, SUBJECTS
from law_table import TEXT, doc_path, render


def test_every_subject_has_an_expectation_for_every_law() -> None:
    assert set(EXPECTATIONS) == {(law, s) for law in LAWS for s in SUBJECTS}


def test_out_of_scope_entries_have_no_expected_failures() -> None:
    # Out of scope means not run, which is different from an expected failure.
    assert all(not e.xfail for e in EXPECTATIONS.values() if e.status == OUT_OF_SCOPE)


@pytest.mark.parametrize("lang", list(TEXT))
def test_law_suite_document_is_current(lang: str) -> None:
    path = doc_path(lang)
    assert path.read_text(encoding="utf-8") == render(lang), (
        f"{path} is out of date; run .venv/bin/python tests/laws/law_table.py"
    )
