"""Which subjects each law is expected to hold for.

Every subject in experiment-io's virtual backend has one entry per law:

- ``PREDICTS``: the subject's source (its docstring and the papers it
  cites) says the law should hold. Each check of the law must pass; a check
  that fails is a failure of the test (suspect the subject's
  implementation). A check listed in ``xfail`` is recorded as
  ``xfail(strict=True)`` with its reason: the source does not predict that
  check, or the prediction is not met for a stated reason. If such a check
  starts to pass, the strict xfail fails and the entry must be revised.
- ``CONTROL``: the constant-rate Poisson responder. It must fail the law and
  pass the procedure's invariants (judged by each law's control tests).
- ``OUT_OF_SCOPE``: not run, with the reason. Not an expected failure: the
  subject has no equation that applies to the law's procedure.

Parameters of the literature models (``RaCSubject``, ``MprSubject``) are the
published values and are not tuned to these tests.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

import pytest

PREDICTS = "predicts"
CONTROL = "control"
OUT_OF_SCOPE = "out of scope"

FI_SCALLOP = "fi_scallop"
RATIO_VS_INTERVAL = "ratio_vs_interval"
MATCHING = "matching"
LAWS = (FI_SCALLOP, RATIO_VS_INTERVAL, MATCHING)

SUBJECTS = (
    "VirtualSubject",
    "ScallopSubject",
    "SpacedRespondingSubject",
    "IrtCopyistSubject",
    "MatchingSubject",
    "RaCSubject",
    "MprSubject",
)


@dataclass(frozen=True)
class Expectation:
    status: str
    reason: str
    xfail: Mapping[str, str] = field(default_factory=dict)


_POISSON = Expectation(
    CONTROL, "constant-rate Poisson responder (two of them on concurrent VI VI)"
)
_SPACED = Expectation(
    OUT_OF_SCOPE, "built for the DRL example (spaced responding); no law in this suite tests it"
)
_SINGLE_ON_CONCURRENT = "single-operandum subject; the law needs two operanda"
_RAC_SINGLE = (
    "two-operandum model; with one operandum its rate is a function of the "
    "reinforcement rate only (Shahan & Craig, 2017)"
)

EXPECTATIONS: dict[tuple[str, str], Expectation] = {
    # FI scallop
    (FI_SCALLOP, "VirtualSubject"): _POISSON,
    (FI_SCALLOP, "ScallopSubject"): Expectation(
        PREDICTS, "rate rises with time since reinforcement (fourth power, CV 0.3)"
    ),
    (FI_SCALLOP, "SpacedRespondingSubject"): _SPACED,
    (FI_SCALLOP, "IrtCopyistSubject"): Expectation(
        OUT_OF_SCOPE, "copies reinforced IRTs; this suite runs it on ratio versus interval only"
    ),
    (FI_SCALLOP, "MatchingSubject"): Expectation(OUT_OF_SCOPE, "two-operandum subject"),
    (FI_SCALLOP, "RaCSubject"): Expectation(OUT_OF_SCOPE, _RAC_SINGLE),
    (FI_SCALLOP, "MprSubject"): Expectation(
        PREDICTS,
        "a pause of about half the interval, then a constant run rate (Killeen, 1994): "
        "a two-state pattern, not a gradual acceleration",
        xfail={
            "F1": (
                "the pause is half the interval (Killeen, 1994, 'about half'); the check's "
                "source puts the break at two-thirds (Schneider, 1969), and 0.5 is below "
                "its lower edge 0.52"
            ),
            "F2": "needs a rate that keeps rising; MPR runs at a constant rate after the pause",
            "F2aux": "needs a rate that keeps rising; MPR runs at a constant rate after the pause",
            "F3": "a pause of half the interval at a constant rate gives an index of 0.5 (< 0.56)",
            "F4": (
                "a constant run rate puts the peak in any of the last five segments, "
                "not mostly in the last three"
            ),
        },
    ),
    # Ratio versus yoked interval
    (RATIO_VS_INTERVAL, "VirtualSubject"): _POISSON,
    (RATIO_VS_INTERVAL, "ScallopSubject"): Expectation(
        OUT_OF_SCOPE, "its rate ramp is tied to a fixed interval (ramp_s)"
    ),
    (RATIO_VS_INTERVAL, "SpacedRespondingSubject"): _SPACED,
    (RATIO_VS_INTERVAL, "IrtCopyistSubject"): Expectation(
        PREDICTS,
        "emits the inter-response times that were reinforced (Tanno & Silberberg, 2012)",
        xfail={
            "V3": (
                "the copyist's VR / yoked VI rate ratio stays at 1.5-2.1 up to about "
                "1,100 reinforcers per hour and never falls to 1.1 (Baum: 300-600)"
            ),
        },
    ),
    (RATIO_VS_INTERVAL, "MatchingSubject"): Expectation(OUT_OF_SCOPE, "two-operandum subject"),
    (RATIO_VS_INTERVAL, "RaCSubject"): Expectation(
        OUT_OF_SCOPE,
        "rate is a function of the reinforcement rate only, so equal reinforcement "
        "rates give equal response rates",
    ),
    (RATIO_VS_INTERVAL, "MprSubject"): Expectation(
        PREDICTS,
        "interval schedules command lower rates than ratio schedules (Killeen, 1994); "
        "ratio parameters are the published rat VR values, interval parameters the "
        "published pigeon FI values (not one population)",
        xfail={
            "V2": (
                "not predicted: the rat VR values give about 218 responses/min on VR 25, "
                "so the yoked VI earns about 480 reinforcers/h, above the check's 300"
            ),
            "V3": (
                "not predicted: the ratio stays at 1.26-1.57 from 100 to 3,550 "
                "reinforcers/h and falls below 1 only at VR 200 (ratio strain), so it "
                "never converges from above"
            ),
        },
    ),
    # Generalized matching on concurrent VI VI
    (MATCHING, "VirtualSubject"): _POISSON,
    (MATCHING, "ScallopSubject"): Expectation(OUT_OF_SCOPE, _SINGLE_ON_CONCURRENT),
    (MATCHING, "SpacedRespondingSubject"): _SPACED,
    (MATCHING, "IrtCopyistSubject"): Expectation(OUT_OF_SCOPE, _SINGLE_ON_CONCURRENT),
    (MATCHING, "MatchingSubject"): Expectation(
        PREDICTS, "melioration: shifts responses toward the key with the higher local "
        "reinforcement rate (Herrnstein & Vaughan, 1980)"
    ),
    (MATCHING, "RaCSubject"): Expectation(
        PREDICTS,
        "B_T / B_Alt = b V_T / V_Alt with b = 1: sensitivity 1 when the values equal "
        "the arranged rates (Shahan & Craig, 2017; Shahan, Browning, & Nall, 2020)",
        xfail={
            "M1": (
                "undermatches: sensitivity 0.84 [0.73, 0.88] with ten sessions per "
                "condition and 0.85 [0.82, 0.89] with thirty. A likely cause, not "
                "verified: the values weight every session since the option was first "
                "reinforced, so the earlier conditions stay in them"
            ),
        },
    ),
    (MATCHING, "MprSubject"): Expectation(OUT_OF_SCOPE, _SINGLE_ON_CONCURRENT),
}


def expectation(law: str, subject: str) -> Expectation:
    return EXPECTATIONS[(law, subject)]


def predicted_subjects(law: str) -> list[str]:
    return [s for s in SUBJECTS if expectation(law, s).status == PREDICTS]


def law_cases(law: str, checks: Iterable[str]) -> list[object]:
    """``(subject, check)`` parameters for the subjects that are predicted to obey ``law``."""
    cases = []
    for subject in predicted_subjects(law):
        xfails = expectation(law, subject).xfail
        for check in checks:
            marks = (
                [pytest.mark.xfail(strict=True, reason=xfails[check])] if check in xfails else []
            )
            cases.append(pytest.param(subject, check, id=f"{subject}-{check}", marks=marks))
    return cases
