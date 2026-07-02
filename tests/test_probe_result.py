import json

import pytest

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.probes import run_probes
from scenariocraft.core.schemas import ProbeResult, ScenarioSpec
from scenariocraft.core.schemas.probe_result import ProbeResultError


def test_probe_result_round_trips_through_json_compatible_dict() -> None:
    result = ProbeResult(
        name="demo_probe",
        passed=False,
        severity="failure",
        message="Measured value is outside the target range.",
        measured={"distance_m": 1.25, "labels": ["near", "blocked"]},
        suggested_operations=(
            {"operation": "future_patch_placeholder", "path": "layout.points.conflict_point"},
        ),
    )

    loaded = ProbeResult.from_dict(json.loads(json.dumps(result.to_dict())))

    assert loaded == result
    assert loaded.name == "demo_probe"
    assert loaded.passed is False
    assert loaded.severity == "failure"
    assert loaded.message
    assert loaded.measured["distance_m"] == 1.25
    assert loaded.suggested_operations[0]["operation"] == "future_patch_placeholder"


def test_probe_result_omits_empty_optional_fields_from_dict() -> None:
    result = ProbeResult(name="note_probe", passed=True, severity="note", message="Looks fine.")

    assert result.to_dict() == {
        "name": "note_probe",
        "passed": True,
        "severity": "note",
        "message": "Looks fine.",
    }


def test_probe_result_rejects_invalid_required_fields() -> None:
    with pytest.raises(ProbeResultError):
        ProbeResult(name="", passed=True, severity="note", message="ok")
    with pytest.raises(ProbeResultError):
        ProbeResult(name="probe", passed=True, severity="note", message="")
    with pytest.raises(ProbeResultError):
        ProbeResult(name="probe", passed=True, severity="info", message="ok")


def test_probe_result_rejects_non_json_compatible_values() -> None:
    with pytest.raises(ProbeResultError):
        ProbeResult(name="probe", passed=True, severity="note", message="ok", measured={"bad": object()})
    with pytest.raises(ProbeResultError):
        ProbeResult(
            name="probe",
            passed=True,
            severity="note",
            message="ok",
            suggested_operations=({"bad": object()},),
        )


def test_run_probes_preserves_order() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    probes = [_FakeProbe("first", True), _FakeProbe("second", False)]

    results = run_probes(spec, probes)

    assert [result.name for result in results] == ["first", "second"]
    assert [result.passed for result in results] == [True, False]


def test_run_probes_does_not_swallow_exceptions() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    with pytest.raises(RuntimeError, match="boom"):
        run_probes(spec, [_ExplodingProbe()])


class _FakeProbe:
    def __init__(self, name: str, passed: bool) -> None:
        self.name = name
        self._passed = passed

    def run(self, spec: ScenarioSpec) -> ProbeResult:
        return ProbeResult(name=self.name, passed=self._passed, severity="note", message=spec.scenario_type)


class _ExplodingProbe:
    name = "exploding"

    def run(self, spec: ScenarioSpec) -> ProbeResult:
        raise RuntimeError("boom")
