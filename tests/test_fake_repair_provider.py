from dataclasses import replace

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.probes import run_pedestrian_occlusion_probes, run_pedestrian_occlusion_timing_probes
from scenariocraft.core.repair import apply_patch
from scenariocraft.core.repair.providers import FakeRepairProvider, RepairRequest
from scenariocraft.core.schemas import (
    PatchSpec,
    Point2D,
    Pose2D,
    ProbeResult,
    RepositionActorToBandOperation,
    SetNamedPointOperation,
    SetTriggerPointByLeadTimeOperation,
)


def test_fake_provider_proposes_parking_strip_patch_and_manual_revalidation_passes() -> None:
    invalid = _van_outside_parking_strip()
    failed = _failed_probe(invalid, "parked_van_footprint_in_parking_strip")
    request = RepairRequest(
        user_intent="Repair the parked van placement.",
        scenario_spec=invalid,
        failed_probe_results=(failed,),
        allowed_operation_types=("reposition_actor_to_band",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert isinstance(proposal.patch, PatchSpec)
    assert len(proposal.patch.operations) == 1
    operation = proposal.patch.operations[0]
    assert isinstance(operation, RepositionActorToBandOperation)
    assert operation.actor_id == "parked_van"
    assert operation.target_band_id == "ego_side_parking_strip"
    repaired = apply_patch(invalid, proposal.patch)
    assert _probe(repaired, "parked_van_footprint_in_parking_strip").passed is True


def test_fake_provider_proposes_trigger_patch_and_manual_revalidation_passes() -> None:
    invalid = _trigger_after_conflict()
    assert invalid.layout is not None
    original_trigger_y = invalid.layout.points["trigger_point"].y_m
    conflict_x = invalid.layout.points["conflict_point"].x_m
    failed = _failed_probe(invalid, "trigger_point_before_conflict_and_in_ego_lane")
    request = RepairRequest(
        user_intent=None,
        scenario_spec=invalid,
        failed_probe_results=(failed,),
        allowed_operation_types=("set_named_point",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert isinstance(proposal.patch, PatchSpec)
    operation = proposal.patch.operations[0]
    assert isinstance(operation, SetNamedPointOperation)
    assert operation.point_id == "trigger_point"
    assert operation.x_m == conflict_x - 1.0
    assert operation.y_m == original_trigger_y
    repaired = apply_patch(invalid, proposal.patch)
    assert _probe(repaired, "trigger_point_before_conflict_and_in_ego_lane").passed is True


def test_fake_provider_proposes_timing_lead_time_patch_and_revalidation_passes() -> None:
    invalid = _trigger_too_close_to_conflict()
    failed = _failed_timing_probe(invalid, "ego_lead_time_within_timing_policy")
    request = RepairRequest(
        user_intent="Repair trigger timing.",
        scenario_spec=invalid,
        failed_probe_results=(failed,),
        allowed_operation_types=("set_trigger_point_by_lead_time",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert isinstance(proposal.patch, PatchSpec)
    assert len(proposal.patch.operations) == 1
    operation = proposal.patch.operations[0]
    assert isinstance(operation, SetTriggerPointByLeadTimeOperation)
    assert operation.point_id == "trigger_point"
    assert operation.reference_point_id == "conflict_point"
    assert operation.speed_source_actor_id == "ego"
    assert operation.lead_time_s > failed.measured["required_minimum_lead_time_s"]
    repaired = apply_patch(invalid, proposal.patch)
    timing_results = run_pedestrian_occlusion_timing_probes(repaired)
    assert all(result.passed for result in timing_results)


def test_fake_provider_declines_disallowed_operation_type() -> None:
    invalid = _van_outside_parking_strip()
    failed = _failed_probe(invalid, "parked_van_footprint_in_parking_strip")
    request = RepairRequest(
        user_intent=None,
        scenario_spec=invalid,
        failed_probe_results=(failed,),
        allowed_operation_types=("set_named_point",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert proposal.patch is None
    assert "reposition_actor_to_band" in proposal.rationale
    assert "not allowed" in proposal.rationale


def test_fake_provider_declines_unsupported_failed_probe() -> None:
    spec = _canonical_spec()
    unsupported = ProbeResult(
        name="xosc_logic_file_is_relative",
        passed=False,
        severity="failure",
        message="LogicFile is absolute.",
        measured={"is_relative": False},
    )
    request = RepairRequest(
        user_intent="Repair the scenario.",
        scenario_spec=spec,
        failed_probe_results=(unsupported,),
        allowed_operation_types=("set_named_point", "reposition_actor_to_band"),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert proposal.patch is None
    assert "No supported deterministic repair" in proposal.rationale
    assert unsupported.name in proposal.rationale


def test_fake_provider_does_not_mutate_original_scenario_spec() -> None:
    invalid = _van_outside_parking_strip()
    original_json = invalid.to_json()
    failed = _failed_probe(invalid, "parked_van_footprint_in_parking_strip")
    request = RepairRequest(
        None,
        invalid,
        (failed,),
        ("reposition_actor_to_band",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert proposal.patch is not None
    assert invalid.to_json() == original_json
    assert invalid.layout.actor_poses["parked_van"].y_m == 0.0


def test_fake_provider_does_not_call_patch_build_runtime_or_artifact_tools(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Provider crossed its proposal-only boundary.")

    monkeypatch.setattr("scenariocraft.core.repair.apply_patch", forbidden)
    monkeypatch.setattr("scenariocraft.core.build.build_openscenario", forbidden)
    monkeypatch.setattr("scenariocraft.external_tools.run_esmini", forbidden)
    monkeypatch.setattr("scenariocraft.core.probes.run_artifact_consistency_probes", forbidden)
    invalid = _van_outside_parking_strip()
    request = RepairRequest(
        None,
        invalid,
        (_failed_probe(invalid, "parked_van_footprint_in_parking_strip"),),
        ("reposition_actor_to_band",),
    )

    proposal = FakeRepairProvider().propose_patch(request)

    assert proposal.patch is not None


def _canonical_spec():
    return generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")


def _van_outside_parking_strip():
    spec = _canonical_spec()
    assert spec.layout is not None
    original = spec.layout.actor_poses["parked_van"]
    actor_poses = {
        **spec.layout.actor_poses,
        "parked_van": Pose2D(original.x_m, 0.0, original.heading_rad),
    }
    return replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))


def _trigger_after_conflict():
    spec = _canonical_spec()
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    points = {
        **spec.layout.points,
        "trigger_point": Point2D(conflict.x_m + 5.0, spec.layout.points["trigger_point"].y_m),
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


def _failed_probe(spec, name: str) -> ProbeResult:
    result = _probe(spec, name)
    assert result.passed is False
    return result


def _probe(spec, name: str) -> ProbeResult:
    return next(result for result in run_pedestrian_occlusion_probes(spec) if result.name == name)


def _failed_timing_probe(spec, name: str) -> ProbeResult:
    result = next(result for result in run_pedestrian_occlusion_timing_probes(spec) if result.name == name)
    assert result.passed is False
    return result
