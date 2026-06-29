from dataclasses import replace

from scenariocraft_core.generators import MockScenarioGenerator
from scenariocraft_core.probes import run_pedestrian_occlusion_probes, run_pedestrian_occlusion_timing_probes
from scenariocraft_core.schemas import PathSpec, Point2D, Pose2D

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

EXPECTED_TIMING_PROBE_NAMES = [
    "ego_lead_time_to_conflict_positive",
    "ego_lead_time_within_timing_policy",
    "pedestrian_time_to_conflict_computable",
    "pedestrian_conflict_timing_alignment",
    "trigger_threshold_time_not_ttc",
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


def test_layout_free_spec_returns_timing_unavailable_evidence_without_crashing() -> None:
    spec = replace(_canonical_spec(), layout=None, spatial_relations=())

    results = run_pedestrian_occlusion_timing_probes(spec)

    assert [result.name for result in results] == EXPECTED_TIMING_PROBE_NAMES
    assert not next(result for result in results if result.name == "ego_lead_time_to_conflict_positive").passed
    assert not next(result for result in results if result.name == "pedestrian_time_to_conflict_computable").passed
    threshold = next(result for result in results if result.name == "trigger_threshold_time_not_ttc")
    assert threshold.passed is True
    assert threshold.measured["ego_lead_time_to_conflict_s"] is None
    assert threshold.measured["pedestrian_time_to_conflict_s"] is None


def test_unsupported_scenario_type_returns_no_template_aware_probes() -> None:
    spec = replace(_canonical_spec(), scenario_type="cut_in")

    assert run_pedestrian_occlusion_probes(spec) == ()
    assert run_pedestrian_occlusion_timing_probes(spec) == ()


def test_canonical_pedestrian_occlusion_timing_probes_all_pass() -> None:
    spec = _canonical_spec()

    results = run_pedestrian_occlusion_timing_probes(spec)

    assert [result.name for result in results] == EXPECTED_TIMING_PROBE_NAMES
    assert all(result.passed for result in results)
    lead_probe = next(result for result in results if result.name == "ego_lead_time_within_timing_policy")
    assert lead_probe.measured["target_ttc_s"] == 1.5
    assert lead_probe.measured["trigger_threshold_time_s"] > 0
    assert lead_probe.measured["ego_lead_time_to_conflict_s"] > 0
    assert lead_probe.measured["pedestrian_time_to_conflict_s"] > 0
    assert lead_probe.suggested_operations == ()


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


def test_trigger_after_conflict_fails_timing_probes_with_patch_hints() -> None:
    canonical = _canonical_spec()
    assert canonical.layout is not None
    conflict_x = canonical.layout.points["conflict_point"].x_m
    spec = _with_point("trigger_point", Point2D(conflict_x + 5.0, 0.0))

    results = run_pedestrian_occlusion_timing_probes(spec)
    failures = {result.name: result for result in results if not result.passed}

    assert "ego_lead_time_to_conflict_positive" in failures
    assert "ego_lead_time_within_timing_policy" in failures
    assert "pedestrian_conflict_timing_alignment" in failures
    assert failures["ego_lead_time_to_conflict_positive"].measured["ego_lead_time_to_conflict_s"] < 0
    operation = failures["ego_lead_time_to_conflict_positive"].suggested_operations[0]
    assert operation["op"] == "set_named_point"
    assert operation["point_id"] == "trigger_point"
    assert operation["x_m"] < conflict_x


def test_too_short_positive_lead_time_fails_timing_policy_and_alignment() -> None:
    canonical = _canonical_spec()
    assert canonical.layout is not None
    conflict = canonical.layout.points["conflict_point"]
    spec = _with_point("trigger_point", Point2D(conflict.x_m - 0.5, conflict.y_m))

    results = run_pedestrian_occlusion_timing_probes(spec)
    by_name = {result.name: result for result in results}

    assert by_name["ego_lead_time_to_conflict_positive"].passed is True
    assert by_name["ego_lead_time_within_timing_policy"].passed is False
    assert by_name["pedestrian_conflict_timing_alignment"].passed is False
    assert by_name["ego_lead_time_within_timing_policy"].measured["lead_time_margin_s"] < 0
    assert by_name["ego_lead_time_within_timing_policy"].suggested_operations[0]["op"] == "set_named_point"


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
