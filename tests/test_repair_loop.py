from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

import scenariocraft.loop.repair_loop as repair_loop_module
from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.loop import ALLOWED_OPERATION_TYPES, run_bounded_repair_loop
from scenariocraft.probes import run_pedestrian_occlusion_timing_probes
from scenariocraft.repair.providers import FakeRepairProvider
from scenariocraft.schemas import FootprintSpec, Point2D, Pose2D, ProbeResult


def test_canonical_spec_passes_without_requesting_provider_patch(tmp_path: Path) -> None:
    spec = _canonical_spec()
    provider = FakeRepairProvider()
    propose_patch = Mock(wraps=provider.propose_patch)
    provider.propose_patch = propose_patch

    result = run_bounded_repair_loop(spec, provider=provider, output_dir=tmp_path)

    assert result.terminal_status == "passed"
    assert result.rounds == ()
    assert propose_patch.call_count == 0
    assert result.xosc_path is not None and result.xosc_path.is_file()
    assert result.xodr_path is not None and result.xodr_path.is_file()
    assert result.final_geometry_probe_results
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert result.final_artifact_probe_results
    assert all(probe.passed for probe in result.final_artifact_probe_results)
    json.dumps(result.to_dict())


def test_van_failure_is_repaired_revalidated_built_without_mutating_original(tmp_path: Path) -> None:
    spec = _van_outside_parking_strip()
    original_json = spec.to_json()

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
        user_intent="Keep the van in the parking strip.",
    )

    assert result.terminal_status == "passed"
    assert len(result.rounds) == 1
    round_trace = result.rounds[0]
    assert any(
        probe.name == "parked_van_footprint_in_parking_strip" and not probe.passed
        for probe in round_trace.input_probe_results
    )
    assert round_trace.allowed_operation_types == ALLOWED_OPERATION_TYPES
    assert round_trace.provider_name == "deterministic_fake"
    assert round_trace.proposed_patch is not None
    assert round_trace.proposed_patch.operations[0].to_dict()["op"] == "reposition_actor_to_band"
    assert round_trace.patch_applied is True
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert spec.to_json() == original_json
    assert result.final_spec.to_json() != original_json


def test_trigger_after_conflict_is_repaired_and_revalidated(tmp_path: Path) -> None:
    spec = _trigger_after_conflict()

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "passed"
    assert len(result.rounds) == 1
    patch = result.rounds[0].proposed_patch
    assert patch is not None
    assert patch.operations[0].to_dict()["op"] == "set_named_point"
    assert patch.operations[1].to_dict()["op"] == "set_trigger_point_by_lead_time"
    trigger_probe = next(
        probe
        for probe in result.final_geometry_probe_results
        if probe.name == "trigger_point_before_conflict_and_in_ego_lane"
    )
    assert trigger_probe.passed is True
    assert all(probe.passed for probe in run_pedestrian_occlusion_timing_probes(result.final_spec))


def test_timing_failure_is_repaired_with_lead_time_operation(tmp_path: Path) -> None:
    spec = _trigger_too_close_to_conflict()

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "passed"
    assert len(result.rounds) == 1
    patch = result.rounds[0].proposed_patch
    assert patch is not None
    assert [operation.to_dict()["op"] for operation in patch.operations] == ["set_trigger_point_by_lead_time"]
    assert any(
        probe.name == "ego_lead_time_within_timing_policy" and not probe.passed
        for probe in result.rounds[0].input_probe_results
    )
    assert all(probe.passed for probe in result.final_geometry_probe_results)


def test_unsupported_geometry_failure_stops_on_provider_refusal_without_build(
    tmp_path: Path, monkeypatch
) -> None:
    spec = _pedestrian_outside_sidewalk()

    def forbidden_build(*args, **kwargs):
        raise AssertionError("Build must not run after provider refusal.")

    monkeypatch.setattr(repair_loop_module, "build_openscenario", forbidden_build)

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "provider_refused"
    assert len(result.rounds) == 1
    assert result.rounds[0].proposed_patch is None
    assert result.rounds[0].patch_applied is False
    assert result.xosc_path is None
    assert result.xodr_path is None


def test_ineffective_repairs_stop_exactly_at_max_rounds(tmp_path: Path, monkeypatch) -> None:
    spec = _van_outside_parking_strip()
    provider = FakeRepairProvider()
    propose_patch = Mock(wraps=provider.propose_patch)
    provider.propose_patch = propose_patch
    monkeypatch.setattr(repair_loop_module, "apply_patch", lambda current, patch: current)

    result = run_bounded_repair_loop(
        spec,
        provider=provider,
        output_dir=tmp_path,
        max_rounds=2,
    )

    assert result.terminal_status == "max_rounds_reached"
    assert len(result.rounds) == 2
    assert propose_patch.call_count == 2
    assert all(round_trace.patch_applied for round_trace in result.rounds)
    assert any(not probe.passed for probe in result.final_geometry_probe_results)
    assert result.xosc_path is None


def test_artifact_failure_stops_without_requesting_actor_repair(tmp_path: Path, monkeypatch) -> None:
    spec = _canonical_spec()
    provider = FakeRepairProvider()
    propose_patch = Mock(wraps=provider.propose_patch)
    provider.propose_patch = propose_patch
    failed_artifact_probe = ProbeResult(
        name="xosc_actor_poses_match_layout",
        passed=False,
        severity="failure",
        message="Controlled artifact mismatch.",
        measured={"controlled_test_double": True},
        suggested_operations=({"op": "rebuild_artifacts"},),
    )
    monkeypatch.setattr(
        repair_loop_module,
        "run_artifact_consistency_probes",
        lambda *args, **kwargs: (failed_artifact_probe,),
    )

    result = run_bounded_repair_loop(spec, provider=provider, output_dir=tmp_path)

    assert result.terminal_status == "artifact_validation_failed"
    assert propose_patch.call_count == 0
    assert result.rounds == ()
    assert result.final_artifact_probe_results == (failed_artifact_probe,)
    assert result.xosc_path is not None and result.xosc_path.is_file()
    assert result.xodr_path is not None and result.xodr_path.is_file()


def test_patch_application_failure_is_terminal_and_inspectable(tmp_path: Path) -> None:
    spec = _oversized_van_outside_parking_strip()

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "patch_application_failed"
    assert len(result.rounds) == 1
    assert result.rounds[0].patch_applied is False
    assert "wider than road band" in result.rounds[0].application_error
    assert result.final_artifact_probe_results == ()


def test_layout_free_or_other_scenario_is_explicitly_unsupported(tmp_path: Path) -> None:
    spec = replace(_canonical_spec(), layout=None, spatial_relations=(), timing=None)

    result = run_bounded_repair_loop(
        spec,
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "unsupported_scenario"
    assert result.rounds == ()
    assert result.final_geometry_probe_results == ()


def test_missing_geometry_probe_evidence_never_claims_success(tmp_path: Path, monkeypatch) -> None:
    provider = FakeRepairProvider()
    propose_patch = Mock(wraps=provider.propose_patch)
    provider.propose_patch = propose_patch
    monkeypatch.setattr(repair_loop_module, "run_pedestrian_occlusion_probes", lambda spec: ())

    result = run_bounded_repair_loop(
        _canonical_spec(),
        provider=provider,
        output_dir=tmp_path,
    )

    assert result.terminal_status == "geometry_validation_failed"
    assert propose_patch.call_count == 0
    assert result.xosc_path is None


def test_missing_artifact_probe_evidence_never_claims_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        repair_loop_module,
        "run_artifact_consistency_probes",
        lambda *args, **kwargs: (),
    )

    result = run_bounded_repair_loop(
        _canonical_spec(),
        provider=FakeRepairProvider(),
        output_dir=tmp_path,
    )

    assert result.terminal_status == "artifact_validation_failed"
    assert result.final_artifact_probe_results == ()
    assert "No static artifact consistency probe evidence" in result.terminal_reason


def test_zero_round_bound_never_requests_provider_or_builds(tmp_path: Path, monkeypatch) -> None:
    provider = FakeRepairProvider()
    propose_patch = Mock(wraps=provider.propose_patch)
    provider.propose_patch = propose_patch

    def forbidden_build(*args, **kwargs):
        raise AssertionError("Build must not run while geometry failures remain.")

    monkeypatch.setattr(repair_loop_module, "build_openscenario", forbidden_build)

    result = run_bounded_repair_loop(
        _van_outside_parking_strip(),
        provider=provider,
        output_dir=tmp_path,
        max_rounds=0,
    )

    assert result.terminal_status == "max_rounds_reached"
    assert propose_patch.call_count == 0
    assert result.rounds == ()


@pytest.mark.parametrize("max_rounds", [-1, 1.5, True])
def test_invalid_max_rounds_is_rejected(max_rounds, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        run_bounded_repair_loop(
            _canonical_spec(),
            provider=FakeRepairProvider(),
            output_dir=tmp_path,
            max_rounds=max_rounds,
        )


def _canonical_spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")


def _van_outside_parking_strip():
    spec = _canonical_spec()
    assert spec.layout is not None
    pose = spec.layout.actor_poses["parked_van"]
    actor_poses = {
        **spec.layout.actor_poses,
        "parked_van": Pose2D(pose.x_m, 0.0, pose.heading_rad),
    }
    return replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))


def _trigger_after_conflict():
    spec = _canonical_spec()
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    trigger = spec.layout.points["trigger_point"]
    points = {
        **spec.layout.points,
        "trigger_point": Point2D(conflict.x_m + 5.0, trigger.y_m),
    }
    return replace(spec, layout=replace(spec.layout, points=points))


def _trigger_too_close_to_conflict():
    spec = _canonical_spec()
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    trigger = spec.layout.points["trigger_point"]
    points = {
        **spec.layout.points,
        "trigger_point": Point2D(conflict.x_m - 0.5, trigger.y_m),
    }
    return replace(spec, layout=replace(spec.layout, points=points))


def _pedestrian_outside_sidewalk():
    spec = _canonical_spec()
    assert spec.layout is not None
    pose = spec.layout.actor_poses["pedestrian"]
    actor_poses = {
        **spec.layout.actor_poses,
        "pedestrian": Pose2D(pose.x_m, 0.0, pose.heading_rad),
    }
    return replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))


def _oversized_van_outside_parking_strip():
    spec = _van_outside_parking_strip()
    assert spec.layout is not None
    footprint = spec.layout.actor_footprints["parked_van"]
    footprints = {
        **spec.layout.actor_footprints,
        "parked_van": FootprintSpec(footprint.length_m, 10.0),
    }
    return replace(spec, layout=replace(spec.layout, actor_footprints=footprints))
