from dataclasses import replace

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.probes import run_pedestrian_occlusion_probes
from scenariocraft.schemas import PathSpec, Point2D, Pose2D

EXPECTED_PROBE_NAMES = [
    "ego_footprint_in_ego_lane",
    "parked_van_footprint_in_parking_strip",
    "pedestrian_initial_footprint_in_sidewalk",
    "pedestrian_path_starts_at_pedestrian_pose",
    "pedestrian_path_crosses_ego_lane",
    "pedestrian_path_clear_of_occluder",
    "pedestrian_line_of_sight_occluded_by_van",
    "conflict_point_on_path_and_in_ego_lane",
    "trigger_point_before_conflict_and_in_ego_lane",
]


def test_canonical_pedestrian_occlusion_probes_all_pass() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    results = run_pedestrian_occlusion_probes(spec)

    assert [result.name for result in results] == EXPECTED_PROBE_NAMES
    assert all(result.passed for result in results)
    assert {result.severity for result in results} == {"note"}


def test_layout_free_spec_returns_no_template_aware_probes() -> None:
    spec = replace(_canonical_spec(), layout=None, spatial_relations=())

    assert run_pedestrian_occlusion_probes(spec) == ()


def test_unsupported_scenario_type_returns_no_template_aware_probes() -> None:
    spec = replace(_canonical_spec(), scenario_type="cut_in")

    assert run_pedestrian_occlusion_probes(spec) == ()


def test_van_shifted_outside_parking_strip_fails_parking_probe() -> None:
    spec = _with_pose("parked_van", Pose2D(20.0, 0.0, 0.0))

    result = _probe_result(spec, "parked_van_footprint_in_parking_strip")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["actor_id"] == "parked_van"
    assert result.measured["band_id"] == "ego_side_parking_strip"
    assert "actor_y_min_m" in result.measured
    assert "band_y_max_m" in result.measured
    assert result.suggested_operations[0]["op"] == "reposition_actor"


def test_pedestrian_shifted_outside_sidewalk_fails_sidewalk_probe() -> None:
    spec = _with_pose("pedestrian", Pose2D(25.0, 3.0, 0.0))

    result = _probe_result(spec, "pedestrian_initial_footprint_in_sidewalk")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["actor_id"] == "pedestrian"
    assert result.measured["band_id"] == "ego_side_sidewalk"
    assert result.suggested_operations[0]["target_band_id"] == "ego_side_sidewalk"


def test_path_moved_through_van_footprint_fails_clearance_probe() -> None:
    canonical = _canonical_spec()
    assert canonical.layout is not None
    van_x = canonical.layout.actor_poses["parked_van"].x_m
    spec = _with_pose("pedestrian", Pose2D(van_x, 4.6, 0.0))
    spec = _with_crossing_path(spec, (Point2D(van_x, 4.6), Point2D(van_x, -1.0)))

    result = _probe_result(spec, "pedestrian_path_clear_of_occluder")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["path_intersects_van_footprint"] is True
    assert result.measured["minimum_clearance_m"] == 0.0
    assert result.measured["required_clearance_m"] == 0.5
    assert result.suggested_operations[0]["op"] == "reposition_path_or_actor"


def test_path_that_misses_ego_lane_fails_crosses_ego_lane_probe() -> None:
    spec = _with_crossing_path(_canonical_spec(), (Point2D(25.0, 4.6), Point2D(25.0, 3.0)))

    result = _probe_result(spec, "pedestrian_path_crosses_ego_lane")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["path_y_min_m"] == 3.0
    assert result.measured["ego_lane_y_max_m"] == 1.75
    assert result.suggested_operations[0]["target_band_id"] == "ego_driving_lane"


def test_pedestrian_start_without_van_occlusion_fails_line_of_sight_probe() -> None:
    spec = _with_pose("pedestrian", Pose2D(25.0, 8.0, 0.0))
    spec = _with_crossing_path(spec, (Point2D(25.0, 8.0), Point2D(25.0, -1.0)))

    result = _probe_result(spec, "pedestrian_line_of_sight_occluded_by_van")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["line_of_sight_intersects_footprint"] is False
    assert result.measured["occluder_id"] == "parked_van"
    assert "ego_position" in result.measured
    assert "pedestrian_initial_position" in result.measured
    assert result.suggested_operations[0]["op"] == "reposition_occluder_or_pedestrian"


def test_conflict_point_off_path_fails_conflict_probe() -> None:
    spec = _with_point("conflict_point", Point2D(24.0, 0.0))

    result = _probe_result(spec, "conflict_point_on_path_and_in_ego_lane")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["point_on_path"] is False
    assert result.measured["point_to_path_distance_m"] > result.measured["path_tolerance_m"]
    assert result.suggested_operations[0]["point_id"] == "conflict_point"


def test_trigger_after_conflict_fails_trigger_probe() -> None:
    canonical = _canonical_spec()
    assert canonical.layout is not None
    conflict_x = canonical.layout.points["conflict_point"].x_m
    spec = _with_point("trigger_point", Point2D(conflict_x + 5.0, 0.0))

    result = _probe_result(spec, "trigger_point_before_conflict_and_in_ego_lane")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["trigger_x_m"] == conflict_x + 5.0
    assert result.measured["conflict_x_m"] == conflict_x
    assert result.measured["longitudinal_gap_m"] == -5.0
    assert result.measured["trigger_inside_ego_lane"] is True
    assert result.suggested_operations[0]["point_id"] == "trigger_point"


def test_path_start_mismatch_fails_start_probe() -> None:
    spec = _with_crossing_path(_canonical_spec(), (Point2D(26.0, 4.6), Point2D(25.0, -1.0)))

    result = _probe_result(spec, "pedestrian_path_starts_at_pedestrian_pose")

    assert result.passed is False
    assert result.severity == "failure"
    assert result.measured["position_error_m"] > result.measured["tolerance_m"]
    assert result.suggested_operations[0]["op"] == "align_path_start_to_actor"


def _canonical_spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")


def _probe_result(spec, name: str):
    results = run_pedestrian_occlusion_probes(spec)
    return next(result for result in results if result.name == name)


def _with_pose(actor_id: str, pose: Pose2D):
    spec = _canonical_spec()
    assert spec.layout is not None
    layout = replace(spec.layout, actor_poses={**spec.layout.actor_poses, actor_id: pose})
    return replace(spec, layout=layout)


def _with_point(point_id: str, point: Point2D):
    spec = _canonical_spec()
    assert spec.layout is not None
    layout = replace(spec.layout, points={**spec.layout.points, point_id: point})
    return replace(spec, layout=layout)


def _with_crossing_path(spec, points: tuple[Point2D, ...]):
    assert spec.layout is not None
    path = PathSpec("pedestrian_crossing_path", points)
    layout = replace(spec.layout, paths={**spec.layout.paths, "pedestrian_crossing_path": path})
    return replace(spec, layout=layout)
