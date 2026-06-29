import json

import pytest

from scenariocraft.core.schemas import (
    PatchSpec,
    PatchSpecError,
    Point2D,
    RepositionActorToBandOperation,
    SetActorPoseOperation,
    SetNamedPointOperation,
    SetPathPointsOperation,
    SetTriggerPointByLeadTimeOperation,
)


def test_patch_spec_parses_and_round_trips_typed_operations() -> None:
    raw = {
        "operations": [
            {
                "op": "set_actor_pose",
                "actor_id": "pedestrian",
                "x_m": 25.0,
                "y_m": 4.6,
                "heading_rad": 0.0,
            },
            {
                "op": "reposition_actor_to_band",
                "actor_id": "parked_van",
                "target_band_id": "ego_side_parking_strip",
            },
            {
                "op": "set_path_points",
                "path_id": "pedestrian_crossing_path",
                "points": [{"x_m": 25.0, "y_m": 4.6}, {"x_m": 25.0, "y_m": -1.0}],
            },
            {
                "op": "set_named_point",
                "point_id": "conflict_point",
                "x_m": 25.0,
                "y_m": 0.0,
            },
            {
                "op": "set_trigger_point_by_lead_time",
                "point_id": "trigger_point",
                "reference_point_id": "conflict_point",
                "speed_source_actor_id": "ego",
                "lead_time_s": 3.0,
            },
        ]
    }

    patch = PatchSpec.from_json(json.dumps(raw))
    loaded = PatchSpec.from_json(patch.to_json())

    assert loaded == patch
    assert isinstance(patch.operations[0], SetActorPoseOperation)
    assert isinstance(patch.operations[1], RepositionActorToBandOperation)
    assert isinstance(patch.operations[2], SetPathPointsOperation)
    assert isinstance(patch.operations[3], SetNamedPointOperation)
    assert isinstance(patch.operations[4], SetTriggerPointByLeadTimeOperation)
    assert patch.operations[2].points == (Point2D(25.0, 4.6), Point2D(25.0, -1.0))


def test_patch_spec_normalizes_reposition_actor_probe_suggestion() -> None:
    patch = PatchSpec.from_dict({
        "operations": [{
            "op": "reposition_actor",
            "actor_id": "parked_van",
            "target_band_id": "ego_side_parking_strip",
        }]
    })

    assert isinstance(patch.operations[0], RepositionActorToBandOperation)
    assert patch.to_dict()["operations"][0]["op"] == "reposition_actor_to_band"


def test_patch_spec_rejects_unknown_operation() -> None:
    with pytest.raises(PatchSpecError, match="Unknown patch operation"):
        PatchSpec.from_dict({"operations": [{"op": "rewrite_xosc"}]})


def test_patch_spec_rejects_missing_required_field() -> None:
    with pytest.raises(PatchSpecError, match="missing required fields: heading_rad"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_actor_pose",
                "actor_id": "ego",
                "x_m": 0.0,
                "y_m": 0.0,
            }]
        })


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_patch_spec_rejects_non_finite_numeric_values(value: float) -> None:
    with pytest.raises(PatchSpecError, match="x_m must be a finite number"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_named_point",
                "point_id": "conflict_point",
                "x_m": value,
                "y_m": 0.0,
            }]
        })


def test_patch_spec_rejects_exact_duplicate_operations() -> None:
    operation = SetNamedPointOperation("conflict_point", 25.0, 0.0)

    with pytest.raises(PatchSpecError, match="duplicates an earlier operation"):
        PatchSpec((operation, operation))


def test_patch_spec_rejects_malformed_extra_fields() -> None:
    with pytest.raises(PatchSpecError, match="unsupported fields: raw_xml"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_named_point",
                "point_id": "conflict_point",
                "x_m": 25.0,
                "y_m": 0.0,
                "raw_xml": "<Position/>",
            }]
        })


def test_set_trigger_point_by_lead_time_requires_positive_lead_time() -> None:
    with pytest.raises(PatchSpecError, match="lead_time_s must be positive"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_trigger_point_by_lead_time",
                "point_id": "trigger_point",
                "reference_point_id": "conflict_point",
                "speed_source_actor_id": "ego",
                "lead_time_s": 0.0,
            }]
        })


def test_set_path_points_requires_at_least_two_valid_points() -> None:
    with pytest.raises(PatchSpecError, match="at least two points"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_path_points",
                "path_id": "pedestrian_crossing_path",
                "points": [{"x_m": 25.0, "y_m": 4.6}],
            }]
        })

    with pytest.raises(PatchSpecError, match=r"points\[1\] is missing required fields: y_m"):
        PatchSpec.from_dict({
            "operations": [{
                "op": "set_path_points",
                "path_id": "pedestrian_crossing_path",
                "points": [{"x_m": 25.0, "y_m": 4.6}, {"x_m": 25.0}],
            }]
        })
