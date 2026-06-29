from dataclasses import replace

import pytest

from scenariocraft.core.generators import MockScenarioGenerator
from scenariocraft.core.repair import PatchApplicationError, apply_patch
from scenariocraft.core.schemas import (
    FootprintSpec,
    PatchSpec,
    Point2D,
    RepositionActorToBandOperation,
    SetActorPoseOperation,
    SetNamedPointOperation,
    SetPathPointsOperation,
    SetTriggerPointByLeadTimeOperation,
)


def test_set_actor_pose_returns_new_spec_and_updates_only_target_pose() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    original_json = spec.to_json()
    original_path = spec.layout.paths["pedestrian_crossing_path"]
    original_ego_pose = spec.layout.actor_poses["ego"]
    patch = PatchSpec((SetActorPoseOperation("pedestrian", 40.0, 5.0, 0.25),))

    patched = apply_patch(spec, patch)

    assert patched is not spec
    assert patched.layout is not spec.layout
    assert patched.layout.actor_poses["pedestrian"].x_m == 40.0
    assert patched.layout.actor_poses["pedestrian"].y_m == 5.0
    assert patched.layout.actor_poses["pedestrian"].heading_rad == 0.25
    assert patched.layout.actor_poses["ego"] == original_ego_pose
    assert patched.layout.paths["pedestrian_crossing_path"] == original_path
    assert spec.to_json() == original_json


def test_reposition_actor_to_band_centers_full_footprint_and_preserves_longitudinal_pose() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    original_pose = spec.layout.actor_poses["parked_van"]
    patch = PatchSpec((RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),))

    patched = apply_patch(spec, patch)
    pose = patched.layout.actor_poses["parked_van"]

    assert pose.x_m == original_pose.x_m
    assert pose.heading_rad == original_pose.heading_rad
    assert pose.y_m == 3.0
    footprint = patched.layout.actor_footprints["parked_van"]
    assert pose.y_m - footprint.width_m / 2.0 >= 1.75
    assert pose.y_m + footprint.width_m / 2.0 <= 4.25


def test_reposition_actor_to_band_rejects_footprint_wider_than_band() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    footprints = {
        **spec.layout.actor_footprints,
        "parked_van": FootprintSpec(length_m=5.3, width_m=3.0),
    }
    wide_spec = replace(spec, layout=replace(spec.layout, actor_footprints=footprints))
    patch = PatchSpec((RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),))

    with pytest.raises(PatchApplicationError, match="wider than road band"):
        apply_patch(wide_spec, patch)


def test_set_path_points_replaces_only_named_path() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    ego_path = spec.layout.paths["ego_path"]
    pedestrian_pose = spec.layout.actor_poses["pedestrian"]
    points = (Point2D(60.0, 4.6), Point2D(60.0, 1.0), Point2D(60.0, -1.0))
    patch = PatchSpec((SetPathPointsOperation("pedestrian_crossing_path", points),))

    patched = apply_patch(spec, patch)

    assert patched.layout.paths["pedestrian_crossing_path"].points == points
    assert patched.layout.paths["ego_path"] == ego_path
    assert patched.layout.actor_poses["pedestrian"] == pedestrian_pose


def test_set_named_point_replaces_only_target_point() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    trigger_point = spec.layout.points["trigger_point"]
    pedestrian_path = spec.layout.paths["pedestrian_crossing_path"]
    patch = PatchSpec((SetNamedPointOperation("conflict_point", 55.0, 0.25),))

    patched = apply_patch(spec, patch)

    assert patched.layout.points["conflict_point"] == Point2D(55.0, 0.25)
    assert patched.layout.points["trigger_point"] == trigger_point
    assert patched.layout.paths["pedestrian_crossing_path"] == pedestrian_path


def test_set_trigger_point_by_lead_time_computes_x_and_preserves_y() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    original_trigger = spec.layout.points["trigger_point"]
    conflict = spec.layout.points["conflict_point"]
    patch = PatchSpec((SetTriggerPointByLeadTimeOperation("trigger_point", "conflict_point", "ego", 3.0),))

    patched = apply_patch(spec, patch)

    trigger = patched.layout.points["trigger_point"]
    assert trigger.x_m == pytest.approx(conflict.x_m - (35.0 / 3.6) * 3.0)
    assert trigger.y_m == original_trigger.y_m
    assert spec.layout.points["trigger_point"] == original_trigger


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (SetActorPoseOperation("missing_actor", 0.0, 0.0, 0.0), "Actor not found: missing_actor"),
        (
            RepositionActorToBandOperation("parked_van", "missing_band"),
            "Road band not found: missing_band",
        ),
        (
            SetPathPointsOperation("missing_path", (Point2D(0.0, 0.0), Point2D(1.0, 1.0))),
            "Path not found: missing_path",
        ),
        (SetNamedPointOperation("missing_point", 0.0, 0.0), "Named point not found: missing_point"),
        (
            SetTriggerPointByLeadTimeOperation("missing_point", "conflict_point", "ego", 2.0),
            "Named point not found: missing_point",
        ),
        (
            SetTriggerPointByLeadTimeOperation("trigger_point", "missing_point", "ego", 2.0),
            "Named point not found: missing_point",
        ),
        (
            SetTriggerPointByLeadTimeOperation("trigger_point", "conflict_point", "missing_actor", 2.0),
            "Actor not found: missing_actor",
        ),
    ],
)
def test_unknown_patch_references_are_rejected(operation, message: str) -> None:
    with pytest.raises(PatchApplicationError, match=message):
        apply_patch(_canonical_spec(), PatchSpec((operation,)))


def test_set_trigger_point_by_lead_time_rejects_nonpositive_speed() -> None:
    spec = _canonical_spec()
    actors = tuple(
        replace(actor, initial_speed_kph=0.0) if actor.id == "ego" else actor
        for actor in spec.actors
    )
    stopped_ego = replace(spec, actors=actors)
    patch = PatchSpec((SetTriggerPointByLeadTimeOperation("trigger_point", "conflict_point", "ego", 2.0),))

    with pytest.raises(PatchApplicationError, match="Actor speed must be positive"):
        apply_patch(stopped_ego, patch)


def test_missing_actor_footprint_is_rejected() -> None:
    spec = _canonical_spec()
    assert spec.layout is not None
    footprints = dict(spec.layout.actor_footprints)
    del footprints["parked_van"]
    missing_footprint_spec = replace(spec, layout=replace(spec.layout, actor_footprints=footprints))
    patch = PatchSpec((RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),))

    with pytest.raises(PatchApplicationError, match="Actor footprint not found: parked_van"):
        apply_patch(missing_footprint_spec, patch)


def test_multiple_operations_apply_in_listed_order() -> None:
    patch = PatchSpec((
        SetActorPoseOperation("parked_van", 12.0, 20.0, 0.5),
        RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),
    ))

    patched = apply_patch(_canonical_spec(), patch)
    pose = patched.layout.actor_poses["parked_van"]

    assert pose.x_m == 12.0
    assert pose.y_m == 3.0
    assert pose.heading_rad == 0.5


def test_layout_free_spec_rejects_patch_application() -> None:
    spec = _canonical_spec()
    layout_free = replace(spec, layout=None, spatial_relations=())
    patch = PatchSpec((SetNamedPointOperation("conflict_point", 1.0, 0.0),))

    with pytest.raises(PatchApplicationError, match="ScenarioSpec.layout is required"):
        apply_patch(layout_free, patch)


def _canonical_spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
