import json

import pytest

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.checks import run_checks
from scenariocraft.core.schemas import CheckResult, ScenarioSpec
from scenariocraft.core.schemas.check_result import CheckResultError


def test_check_result_round_trips_through_json_compatible_dict() -> None:
    result = CheckResult(
        name="demo_check",
        passed=False,
        severity="failure",
        message="Measured value is outside the target range.",
        category="intent_alignment",
        intent_relation="mismatches_intent",
        repair_action="repair",
        expected={"distance_m": 2.0},
        measured={"distance_m": 1.25, "labels": ["near", "blocked"]},
        suggested_operations=(
            {"operation": "future_patch_placeholder", "path": "layout.points.conflict_point"},
        ),
    )

    loaded = CheckResult.from_dict(json.loads(json.dumps(result.to_dict())))

    assert loaded == result
    assert loaded.name == "demo_check"
    assert loaded.passed is False
    assert loaded.severity == "failure"
    assert loaded.message
    assert loaded.category == "intent_alignment"
    assert loaded.intent_relation == "mismatches_intent"
    assert loaded.repair_action == "repair"
    assert loaded.expected == {"distance_m": 2.0}
    assert loaded.measured["distance_m"] == 1.25
    assert loaded.suggested_operations[0]["operation"] == "future_patch_placeholder"


def test_check_result_includes_check_semantic_defaults_in_dict() -> None:
    result = CheckResult(name="note_check", passed=True, severity="note", message="Looks fine.")

    assert result.to_dict() == {
        "name": "note_check",
        "passed": True,
        "severity": "note",
        "message": "Looks fine.",
        "category": "unknown",
        "intent_relation": "unknown",
    }


def test_check_result_loads_legacy_dict_with_check_defaults() -> None:
    result = CheckResult.from_dict(
        {
            "name": "legacy_check",
            "passed": True,
            "severity": "note",
            "message": "Legacy check result.",
        }
    )

    assert result.category == "unknown"
    assert result.intent_relation == "unknown"
    assert result.repair_action is None
    assert result.expected is None


def test_check_result_rejects_invalid_required_fields() -> None:
    with pytest.raises(CheckResultError):
        CheckResult(name="", passed=True, severity="note", message="ok")
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="note", message="")
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="info", message="ok")
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="warning", message="ok", category="bad")
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="warning", message="ok", intent_relation="bad")
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="warning", message="ok", repair_action="bad")


def test_check_result_rejects_non_json_compatible_values() -> None:
    with pytest.raises(CheckResultError):
        CheckResult(name="check", passed=True, severity="note", message="ok", measured={"bad": object()})
    with pytest.raises(CheckResultError):
        CheckResult(
            name="check",
            passed=True,
            severity="note",
            message="ok",
            suggested_operations=({"bad": object()},),
        )


def test_run_checks_preserves_order() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    checks = [_FakeCheck("first", True), _FakeCheck("second", False)]

    results = run_checks(spec, checks)

    assert [result.name for result in results] == ["first", "second"]
    assert [result.passed for result in results] == [True, False]


def test_run_checks_does_not_swallow_exceptions() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    with pytest.raises(RuntimeError, match="boom"):
        run_checks(spec, [_ExplodingCheck()])


class _FakeCheck:
    def __init__(self, name: str, passed: bool) -> None:
        self.name = name
        self._passed = passed

    def run(self, spec: ScenarioSpec) -> CheckResult:
        return CheckResult(name=self.name, passed=self._passed, severity="note", message=spec.scenario_type)


class _ExplodingCheck:
    name = "exploding"

    def run(self, spec: ScenarioSpec) -> CheckResult:
        raise RuntimeError("boom")
