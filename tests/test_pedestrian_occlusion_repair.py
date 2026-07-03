from dataclasses import replace

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.checks import run_pedestrian_occlusion_checks
from scenariocraft.core.repair import apply_patch
from scenariocraft.core.schemas import (
    PatchSpec,
    Point2D,
    Pose2D,
    RepositionActorToBandOperation,
    SetNamedPointOperation,
)


def test_reposition_actor_patch_repairs_parking_strip_check_failure() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    actor_poses = {
        **spec.layout.actor_poses,
        "parked_van": Pose2D(spec.layout.actor_poses["parked_van"].x_m, 0.0, 0.0),
    }
    invalid = replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))

    before = _check(invalid, "parked_van_footprint_in_parking_strip")
    patch = PatchSpec((RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),))
    repaired = apply_patch(invalid, patch)
    after = _check(repaired, "parked_van_footprint_in_parking_strip")

    assert before.passed is False
    assert before.suggested_operations[0]["op"] == "reposition_actor"
    assert after.passed is True
    assert invalid.layout.actor_poses["parked_van"].y_m == 0.0
    assert repaired.layout.actor_poses["parked_van"].y_m == 3.0


def test_set_named_point_patch_repairs_trigger_point_check_failure() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    invalid_points = {
        **spec.layout.points,
        "trigger_point": Point2D(conflict.x_m + 5.0, 0.0),
    }
    invalid = replace(spec, layout=replace(spec.layout, points=invalid_points))

    before = _check(invalid, "trigger_point_before_conflict_and_in_ego_lane")
    patch = PatchSpec((SetNamedPointOperation("trigger_point", conflict.x_m - 1.0, 0.0),))
    repaired = apply_patch(invalid, patch)
    after = _check(repaired, "trigger_point_before_conflict_and_in_ego_lane")

    assert before.passed is False
    assert after.passed is True
    assert invalid.layout.points["trigger_point"].x_m == conflict.x_m + 5.0
    assert repaired.layout.points["trigger_point"].x_m == conflict.x_m - 1.0


def _check(spec, name: str):
    return next(result for result in run_pedestrian_occlusion_checks(spec) if result.name == name)
