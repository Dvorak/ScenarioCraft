from __future__ import annotations

from pathlib import Path

import pytest

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.probes import run_pedestrian_occlusion_timing_probes
from scenariocraft.repair.providers import FakeRepairProvider
from scenariocraft.application.demo_cases import DEMO_CASES, get_demo_case, prepare_demo_case, run_demo_case


EXPECTED_CASE_IDS = {
    "normal_good_scenario",
    "geometry_van_in_ego_lane",
    "geometry_trigger_after_conflict",
    "artifact_xosc_actor_pose_drift",
}


def test_demo_case_registry_contains_exactly_the_required_cases() -> None:
    assert {case.case_id for case in DEMO_CASES} == EXPECTED_CASE_IDS
    assert len(DEMO_CASES) == 4
    assert {case.fault_domain for case in DEMO_CASES} == {"none", "geometry", "artifact"}
    assert {case.repair_expectation for case in DEMO_CASES} == {
        "not_needed",
        "repairable_with_fake_provider",
        "detection_only",
    }
    assert get_demo_case("normal_good_scenario").display_name == "Normal Good Scenario"


def test_normal_case_passes_without_mutation_or_provider_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = _canonical_spec()
    original_json = spec.to_json()

    def forbidden_provider_call(*args, **kwargs):
        raise AssertionError("Normal case requested a repair proposal.")

    monkeypatch.setattr(FakeRepairProvider, "propose_patch", forbidden_provider_call)

    result = run_demo_case("normal_good_scenario", spec, tmp_path)

    assert result.terminal_status == "passed"
    assert result.provider_requested is False
    assert result.proposed_patch is None
    assert result.patch_applied is False
    assert all(probe.passed for probe in result.initial_geometry_probe_results)
    assert all(probe.passed for probe in result.artifact_probe_results)
    assert spec.to_json() == original_json
    assert result.experiment_spec.to_dict() == spec.to_dict()


def test_van_case_fails_then_repairs_with_fake_provider(tmp_path: Path) -> None:
    spec = _canonical_spec()
    original_json = spec.to_json()
    assert spec.layout is not None
    original_pose = spec.layout.actor_poses["parked_van"]

    result = run_demo_case("geometry_van_in_ego_lane", spec, tmp_path)

    assert any(
        probe.name == "parked_van_footprint_in_parking_strip" and not probe.passed
        for probe in result.initial_geometry_probe_results
    )
    assert result.experiment_spec.layout is not None
    faulty_pose = result.experiment_spec.layout.actor_poses["parked_van"]
    assert faulty_pose.x_m == original_pose.x_m
    assert faulty_pose.heading_rad == original_pose.heading_rad
    assert faulty_pose.y_m == 0.0
    assert result.provider_requested is True
    assert result.provider_name == "deterministic_fake"
    assert result.proposed_patch is not None
    assert result.proposed_patch.operations[0].to_dict()["op"] == "reposition_actor_to_band"
    assert result.patch_applied is True
    parking_band = next(
        band for band in spec.layout.road_bands if band.id == "ego_side_parking_strip"
    )
    expected_repaired_y = (parking_band.y_min_m + parking_band.y_max_m) / 2.0
    assert result.setup_values["after_repair"]["y_m"] == expected_repaired_y
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert all(probe.passed for probe in result.artifact_probe_results)
    assert result.terminal_status == "passed"
    assert spec.to_json() == original_json
    orchestrator_path = tmp_path / "demo_experiments" / "geometry_van_in_ego_lane" / "orchestrator_result.json"
    assert orchestrator_path.exists()
    assert result.repair_run_result is not None
    assert result.repair_run_result.terminal_status == "passed"


def test_trigger_case_fails_then_repairs_with_fake_provider(tmp_path: Path) -> None:
    spec = _canonical_spec()
    original_json = spec.to_json()
    assert spec.layout is not None

    result = run_demo_case("geometry_trigger_after_conflict", spec, tmp_path)

    faulty_trigger = result.experiment_spec.layout.points["trigger_point"]
    conflict = result.experiment_spec.layout.points["conflict_point"]
    ego_lane = next(
        band for band in result.experiment_spec.layout.road_bands if band.id == "ego_driving_lane"
    )
    assert faulty_trigger.x_m > conflict.x_m
    assert ego_lane.y_min_m <= faulty_trigger.y_m <= ego_lane.y_max_m
    assert any(
        probe.name == "trigger_point_before_conflict_and_in_ego_lane" and not probe.passed
        for probe in result.initial_geometry_probe_results
    )
    assert result.provider_requested is True
    assert result.proposed_patch is not None
    assert result.proposed_patch.operations[0].to_dict()["op"] == "set_named_point"
    assert result.patch_applied is True
    assert result.setup_values["after_repair"]["x_m"] < conflict.x_m
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert result.terminal_status == "passed"
    assert spec.to_json() == original_json


def test_trigger_case_preparation_exposes_timing_probe_failures(tmp_path: Path) -> None:
    spec = _canonical_spec()

    prepared = prepare_demo_case("geometry_trigger_after_conflict", spec, tmp_path)
    timing_results = run_pedestrian_occlusion_timing_probes(prepared.experiment_spec)
    failures = {result.name for result in timing_results if not result.passed}

    assert "ego_lead_time_to_conflict_positive" in failures
    assert "ego_lead_time_within_timing_policy" in failures
    assert "pedestrian_conflict_timing_alignment" in failures


def test_artifact_drift_is_detection_only_and_scenario_spec_remains_canonical(
    tmp_path: Path,
    monkeypatch,
) -> None:
    spec = _canonical_spec()
    original_json = spec.to_json()

    def forbidden_provider_call(*args, **kwargs):
        raise AssertionError("Artifact consistency case requested a geometry repair.")

    monkeypatch.setattr(FakeRepairProvider, "propose_patch", forbidden_provider_call)

    result = run_demo_case("artifact_xosc_actor_pose_drift", spec, tmp_path)

    assert spec.to_json() == original_json
    assert result.original_spec.to_dict() == spec.to_dict()
    assert result.experiment_spec.to_dict() == spec.to_dict()
    assert all(probe.passed for probe in result.initial_geometry_probe_results)
    failures = [probe for probe in result.artifact_probe_results if not probe.passed]
    assert [probe.name for probe in failures] == ["xosc_actor_poses_match_layout"]
    pose_probe = failures[0]
    assert pose_probe.measured["position_error_m"]["parked_van"] == pytest.approx(0.75)
    assert pose_probe.measured["position_error_m"]["ego"] == 0.0
    assert pose_probe.measured["position_error_m"]["pedestrian"] == 0.0
    assert pose_probe.measured["heading_error_rad"] == {
        "ego": 0.0,
        "parked_van": 0.0,
        "pedestrian": 0.0,
    }
    assert all(
        probe.passed
        for probe in result.artifact_probe_results
        if probe.name != "xosc_actor_poses_match_layout"
    )
    assert result.provider_requested is False
    assert result.proposed_patch is None
    assert result.patch_applied is False
    assert result.terminal_status == "artifact_validation_failed"
    assert "detection-only" in result.terminal_reason


@pytest.mark.parametrize("case_id", sorted(EXPECTED_CASE_IDS))
def test_every_demo_case_writes_only_beneath_its_isolated_directory(
    case_id: str,
    tmp_path: Path,
) -> None:
    normal_xosc = tmp_path / "scenario.xosc"
    normal_spec = tmp_path / "scenario_spec.json"
    normal_preview = tmp_path / "preview_2d.png"
    normal_playback = tmp_path / "playback.gif"
    normal_xodr = tmp_path / "urban_two_way_parking.xodr"
    sentinels = (normal_xosc, normal_spec, normal_preview, normal_playback, normal_xodr)
    for path in sentinels:
        path.write_text(f"sentinel:{path.name}", encoding="utf-8")

    result = run_demo_case(case_id, _canonical_spec(), tmp_path)

    expected_root = (tmp_path / "demo_experiments" / case_id).resolve()
    assert result.artifact_paths
    assert all(path.resolve().is_relative_to(expected_root) for path in result.artifact_paths)
    for path in sentinels:
        assert path.read_text(encoding="utf-8") == f"sentinel:{path.name}"


def test_demo_cases_do_not_call_runtime_external_or_model_tools(tmp_path: Path, monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Demo case called a forbidden runtime, external, or model tool.")

    monkeypatch.setattr("scenariocraft.runtime.run_esmini", forbidden)
    monkeypatch.setattr("scenariocraft.runtime.run_esmini_playback", forbidden)
    monkeypatch.setattr("scenariocraft.runtime.run_asam_qc", forbidden)
    monkeypatch.setattr("scenariocraft.repair.providers.OpenAIRepairProvider", forbidden)

    for case in DEMO_CASES:
        result = run_demo_case(case.case_id, _canonical_spec(), tmp_path)
        assert result.terminal_status in {"passed", "artifact_validation_failed"}


def _canonical_spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
