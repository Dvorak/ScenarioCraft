from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.roads import (
    MULTI_LANE_SAME_DIRECTION_FILENAME,
    URBAN_FOUR_WAY_INTERSECTION_FILENAME,
    URBAN_TWO_WAY_PARKING_FILENAME,
)
from scenariocraft.core.schemas import CheckResult, ScenarioSpec
from scenariocraft.core.checks.xosc_artifact_reader import (
    float_attr,
    initial_world_positions,
    logic_file_path,
    parse_xosc,
    trajectory_vertices,
)

POSITION_TOLERANCE_M = 1e-6
HEADING_TOLERANCE_RAD = 1e-6
PATH_TOLERANCE_M = 1e-6
CANONICAL_ACTOR_IDS = ("ego", "parked_van", "pedestrian")
LEAD_BRAKING_ACTOR_IDS = ("ego", "lead_vehicle")
CUT_IN_ACTOR_IDS = ("ego", "cut_in_vehicle")
CROSSING_VEHICLE_ACTOR_IDS = ("ego", "crossing_vehicle")
ONCOMING_TURN_ACTOR_IDS = ("ego", "oncoming_vehicle")


def run_artifact_consistency_checks(
    spec: ScenarioSpec,
    *,
    xosc_path: Path,
    xodr_path: Path | None,
) -> tuple[CheckResult, ...]:
    if spec.layout is None:
        return ()

    root, parse_error = parse_xosc(xosc_path)
    logic_file_path_value = logic_file_path(root)
    if spec.scenario_type == "lead_vehicle_braking":
        return (
            _lead_actor_poses_check(spec, root, parse_error),
            _lead_braking_action_check(spec, root, parse_error),
            _lead_braking_trigger_check(spec, root, parse_error),
            _logic_file_relative_check(logic_file_path_value, parse_error),
            _logic_file_target_exists_check(xosc_path, xodr_path, logic_file_path_value, parse_error),
            _logic_file_canonical_check(spec, logic_file_path_value, parse_error),
        )
    if spec.scenario_type == "cut_in":
        return (
            _cut_in_actor_poses_check(spec, root, parse_error),
            _cut_in_trajectory_check(spec, root, parse_error),
            _logic_file_relative_check(logic_file_path_value, parse_error),
            _logic_file_target_exists_check(xosc_path, xodr_path, logic_file_path_value, parse_error),
            _logic_file_canonical_check(spec, logic_file_path_value, parse_error),
        )
    if spec.scenario_type == "crossing_vehicle":
        return (
            _crossing_vehicle_actor_poses_check(spec, root, parse_error),
            _crossing_vehicle_trajectory_check(spec, root, parse_error),
            _logic_file_relative_check(logic_file_path_value, parse_error),
            _logic_file_target_exists_check(xosc_path, xodr_path, logic_file_path_value, parse_error),
            _logic_file_canonical_check(spec, logic_file_path_value, parse_error),
            _intersection_layout_alignment_check(
                spec,
                xodr_path,
                name="xodr_crossing_vehicle_layout_aligns_with_road",
                path_id="crossing_vehicle_path",
            ),
        )
    if spec.scenario_type == "oncoming_turn_across_path":
        return (
            _oncoming_turn_actor_poses_check(spec, root, parse_error),
            _oncoming_turn_trajectory_check(spec, root, parse_error),
            _logic_file_relative_check(logic_file_path_value, parse_error),
            _logic_file_target_exists_check(xosc_path, xodr_path, logic_file_path_value, parse_error),
            _logic_file_canonical_check(spec, logic_file_path_value, parse_error),
            _intersection_layout_alignment_check(
                spec,
                xodr_path,
                name="xodr_oncoming_turn_layout_aligns_with_road",
                path_id="oncoming_turn_path",
            ),
        )
    if spec.scenario_type != "pedestrian_occlusion":
        return ()
    return (
        _actor_poses_check(spec, root, parse_error),
        _pedestrian_trajectory_check(spec, root, parse_error),
        _logic_file_relative_check(logic_file_path_value, parse_error),
        _logic_file_target_exists_check(xosc_path, xodr_path, logic_file_path_value, parse_error),
        _logic_file_canonical_check(spec, logic_file_path_value, parse_error),
    )


def _actor_poses_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    observed = initial_world_positions(root)
    actor_ids = list(CANONICAL_ACTOR_IDS)
    expected_x: dict[str, float] = {}
    expected_y: dict[str, float] = {}
    expected_heading: dict[str, float] = {}
    observed_x: dict[str, float | None] = {}
    observed_y: dict[str, float | None] = {}
    observed_heading: dict[str, float | None] = {}
    position_error: dict[str, float | None] = {}
    heading_error: dict[str, float | None] = {}

    for actor_id in actor_ids:
        pose = spec.layout.actor_poses[actor_id]
        expected_x[actor_id] = pose.x_m
        expected_y[actor_id] = pose.y_m
        expected_heading[actor_id] = pose.heading_rad
        world_position = observed.get(actor_id)
        if world_position is None:
            observed_x[actor_id] = None
            observed_y[actor_id] = None
            observed_heading[actor_id] = None
            position_error[actor_id] = None
            heading_error[actor_id] = None
            continue
        x_m, y_m, heading_rad = world_position
        observed_x[actor_id] = x_m
        observed_y[actor_id] = y_m
        observed_heading[actor_id] = heading_rad
        position_error[actor_id] = math.hypot(x_m - pose.x_m, y_m - pose.y_m)
        heading_error[actor_id] = abs(heading_rad - pose.heading_rad)

    passed = parse_error is None and all(
        position_error[actor_id] is not None
        and position_error[actor_id] <= POSITION_TOLERANCE_M
        and heading_error[actor_id] is not None
        and heading_error[actor_id] <= HEADING_TOLERANCE_RAD
        for actor_id in actor_ids
    )
    measured: dict[str, object] = {
        "actor_id": actor_ids,
        "expected_x_m": expected_x,
        "expected_y_m": expected_y,
        "expected_heading_rad": expected_heading,
        "observed_x_m": observed_x,
        "observed_y_m": observed_y,
        "observed_heading_rad": observed_heading,
        "position_error_m": position_error,
        "heading_error_rad": heading_error,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_actor_poses_match_layout",
        passed=passed,
        pass_message="XOSC initial actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC initial actor WorldPosition values diverge from ScenarioSpec layout poses.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC actor initial pose diverges from ScenarioSpec layout.",
        },),
    )


def _lead_actor_poses_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _actor_pose_match_result(
        spec,
        root,
        parse_error,
        actor_ids=LEAD_BRAKING_ACTOR_IDS,
        name="xosc_lead_actor_poses_match_layout",
        pass_message="XOSC lead-braking actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC lead-braking actor WorldPosition values diverge from ScenarioSpec layout poses.",
    )


def _cut_in_actor_poses_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _actor_pose_match_result(
        spec,
        root,
        parse_error,
        actor_ids=CUT_IN_ACTOR_IDS,
        name="xosc_cut_in_actor_poses_match_layout",
        pass_message="XOSC cut-in actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC cut-in actor WorldPosition values diverge from ScenarioSpec layout poses.",
    )


def _crossing_vehicle_actor_poses_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _actor_pose_match_result(
        spec,
        root,
        parse_error,
        actor_ids=CROSSING_VEHICLE_ACTOR_IDS,
        name="xosc_crossing_vehicle_actor_poses_match_layout",
        pass_message="XOSC crossing-vehicle actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC crossing-vehicle actor WorldPosition values diverge from ScenarioSpec layout poses.",
    )


def _oncoming_turn_actor_poses_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _actor_pose_match_result(
        spec,
        root,
        parse_error,
        actor_ids=ONCOMING_TURN_ACTOR_IDS,
        name="xosc_oncoming_turn_actor_poses_match_layout",
        pass_message="XOSC oncoming-turn actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC oncoming-turn actor WorldPosition values diverge from ScenarioSpec layout poses.",
    )


def _actor_pose_match_result(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
    *,
    actor_ids: tuple[str, ...],
    name: str,
    pass_message: str,
    failure_message: str,
) -> CheckResult:
    observed = initial_world_positions(root)
    expected_x: dict[str, float] = {}
    expected_y: dict[str, float] = {}
    observed_x: dict[str, float | None] = {}
    observed_y: dict[str, float | None] = {}
    position_error: dict[str, float | None] = {}
    for actor_id in actor_ids:
        pose = spec.layout.actor_poses[actor_id]
        expected_x[actor_id] = pose.x_m
        expected_y[actor_id] = pose.y_m
        world_position = observed.get(actor_id)
        if world_position is None:
            observed_x[actor_id] = None
            observed_y[actor_id] = None
            position_error[actor_id] = None
            continue
        x_m, y_m, _heading_rad = world_position
        observed_x[actor_id] = x_m
        observed_y[actor_id] = y_m
        position_error[actor_id] = math.hypot(x_m - pose.x_m, y_m - pose.y_m)
    passed = parse_error is None and all(
        position_error[actor_id] is not None and position_error[actor_id] <= POSITION_TOLERANCE_M
        for actor_id in actor_ids
    )
    measured: dict[str, object] = {
        "actor_id": list(actor_ids),
        "expected_x_m": expected_x,
        "expected_y_m": expected_y,
        "observed_x_m": observed_x,
        "observed_y_m": observed_y,
        "position_error_m": position_error,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name=name,
        passed=passed,
        pass_message=pass_message,
        failure_message=failure_message,
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC actor initial pose diverges from ScenarioSpec layout.",
        },),
    )


def _lead_braking_action_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    action = root.find(".//Action[@name='lead_vehicle_brakes']") if root is not None else None
    dynamics = action.find(".//SpeedActionDynamics") if action is not None else None
    target_speed = action.find(".//AbsoluteTargetSpeed") if action is not None else None
    expected_deceleration = _lead_deceleration_mps2(spec)
    observed_target_speed = float_attr(target_speed, "value")
    observed_dynamics_value = float_attr(dynamics, "value")
    observed_dimension = dynamics.attrib.get("dynamicsDimension") if dynamics is not None else None
    observed_shape = dynamics.attrib.get("dynamicsShape") if dynamics is not None else None
    passed = (
        parse_error is None
        and action is not None
        and observed_target_speed == 0.0
        and observed_shape == "linear"
        and observed_dimension == "rate"
        and observed_dynamics_value == abs(expected_deceleration)
    )
    measured: dict[str, object] = {
        "action_name": "lead_vehicle_brakes",
        "observed_target_speed_mps": observed_target_speed,
        "observed_dynamics_shape": observed_shape,
        "observed_dynamics_dimension": observed_dimension,
        "observed_dynamics_value": observed_dynamics_value,
        "expected_deceleration_mps2": expected_deceleration,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_lead_braking_action_present",
        passed=passed,
        pass_message="XOSC contains the lead vehicle braking SpeedAction.",
        failure_message="XOSC lead vehicle braking SpeedAction is missing or inconsistent.",
        measured=measured,
        suggested_operations=({"op": "rebuild_artifacts", "reason": "Lead braking action is inconsistent."},),
    )


def _lead_braking_trigger_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    event = root.find(".//Event[@name='lead_vehicle_starts_braking']") if root is not None else None
    trigger_source = event.find(".//TriggeringEntities/EntityRef") if event is not None else None
    condition = event.find(".//RelativeDistanceCondition") if event is not None else None
    observed_distance = float_attr(condition, "value")
    observed_target = condition.attrib.get("entityRef") if condition is not None else None
    observed_source = trigger_source.attrib.get("entityRef") if trigger_source is not None else None
    passed = (
        parse_error is None
        and observed_source == spec.trigger.source
        and observed_target == spec.trigger.target
        and observed_distance == spec.trigger.distance_m
    )
    measured: dict[str, object] = {
        "trigger_source": observed_source,
        "trigger_target": observed_target,
        "trigger_distance_m": observed_distance,
        "expected_source": spec.trigger.source,
        "expected_target": spec.trigger.target,
        "expected_distance_m": spec.trigger.distance_m,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_lead_braking_trigger_matches_spec",
        passed=passed,
        pass_message="XOSC lead braking trigger matches ScenarioSpec trigger semantics.",
        failure_message="XOSC lead braking trigger diverges from ScenarioSpec trigger semantics.",
        measured=measured,
        suggested_operations=({"op": "rebuild_artifacts", "reason": "Lead braking trigger is inconsistent."},),
    )


def _pedestrian_trajectory_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    path_id = "pedestrian_crossing_path"
    expected_points = spec.layout.paths[path_id].points
    expected_vertices = [{"x_m": point.x_m, "y_m": point.y_m} for point in expected_points]
    observed_vertices, times_parseable = trajectory_vertices(
        root,
        action_name="pedestrian_follow_crossing_path",
    )
    comparable_count = min(len(expected_vertices), len(observed_vertices))
    errors = [
        math.hypot(
            float(observed_vertices[index]["x_m"]) - expected_vertices[index]["x_m"],
            float(observed_vertices[index]["y_m"]) - expected_vertices[index]["y_m"],
        )
        for index in range(comparable_count)
        if observed_vertices[index]["x_m"] is not None and observed_vertices[index]["y_m"] is not None
    ]
    maximum_error = max(errors) if len(errors) == comparable_count and errors else None
    passed = (
        parse_error is None
        and len(expected_vertices) == len(observed_vertices)
        and maximum_error is not None
        and maximum_error <= PATH_TOLERANCE_M
        and times_parseable
    )
    measured: dict[str, object] = {
        "path_id": path_id,
        "expected_vertex_count": len(expected_vertices),
        "observed_vertex_count": len(observed_vertices),
        "expected_vertices": expected_vertices,
        "observed_vertices": observed_vertices,
        "maximum_position_error_m": maximum_error,
        "time_attributes_parseable": times_parseable,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_pedestrian_trajectory_matches_layout_path",
        passed=passed,
        pass_message="XOSC pedestrian FollowTrajectoryAction vertices match ScenarioSpec layout path.",
        failure_message="XOSC pedestrian FollowTrajectoryAction vertices diverge from ScenarioSpec layout path.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC pedestrian trajectory diverges from ScenarioSpec layout path.",
        },),
    )


def _cut_in_trajectory_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _layout_path_trajectory_check(
        spec,
        root,
        parse_error,
        path_id="cut_in_path",
        action_name="cut_in_vehicle_follow_cut_in_path",
        name="xosc_cut_in_trajectory_matches_layout_path",
        pass_message="XOSC cut-in FollowTrajectoryAction vertices match ScenarioSpec layout path.",
        failure_message="XOSC cut-in FollowTrajectoryAction vertices diverge from ScenarioSpec layout path.",
    )


def _crossing_vehicle_trajectory_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _layout_path_trajectory_check(
        spec,
        root,
        parse_error,
        path_id="crossing_vehicle_path",
        action_name="crossing_vehicle_follow_crossing_path",
        name="xosc_crossing_vehicle_trajectory_matches_layout_path",
        pass_message="XOSC crossing-vehicle FollowTrajectoryAction vertices match ScenarioSpec layout path.",
        failure_message="XOSC crossing-vehicle FollowTrajectoryAction vertices diverge from ScenarioSpec layout path.",
    )


def _oncoming_turn_trajectory_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> CheckResult:
    return _layout_path_trajectory_check(
        spec,
        root,
        parse_error,
        path_id="oncoming_turn_path",
        action_name="oncoming_vehicle_follow_turn_path",
        name="xosc_oncoming_turn_trajectory_matches_layout_path",
        pass_message="XOSC oncoming-turn FollowTrajectoryAction vertices match ScenarioSpec layout path.",
        failure_message="XOSC oncoming-turn FollowTrajectoryAction vertices diverge from ScenarioSpec layout path.",
    )


def _layout_path_trajectory_check(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
    *,
    path_id: str,
    action_name: str,
    name: str,
    pass_message: str,
    failure_message: str,
) -> CheckResult:
    expected_points = spec.layout.paths[path_id].points
    expected_vertices = [{"x_m": point.x_m, "y_m": point.y_m} for point in expected_points]
    observed_vertices, times_parseable = trajectory_vertices(root, action_name=action_name)
    comparable_count = min(len(expected_vertices), len(observed_vertices))
    errors = [
        math.hypot(
            float(observed_vertices[index]["x_m"]) - expected_vertices[index]["x_m"],
            float(observed_vertices[index]["y_m"]) - expected_vertices[index]["y_m"],
        )
        for index in range(comparable_count)
        if observed_vertices[index]["x_m"] is not None and observed_vertices[index]["y_m"] is not None
    ]
    maximum_error = max(errors) if len(errors) == comparable_count and errors else None
    passed = (
        parse_error is None
        and len(expected_vertices) == len(observed_vertices)
        and maximum_error is not None
        and maximum_error <= PATH_TOLERANCE_M
        and times_parseable
    )
    measured: dict[str, object] = {
        "path_id": path_id,
        "action_name": action_name,
        "expected_vertex_count": len(expected_vertices),
        "observed_vertex_count": len(observed_vertices),
        "expected_vertices": expected_vertices,
        "observed_vertices": observed_vertices,
        "maximum_position_error_m": maximum_error,
        "time_attributes_parseable": times_parseable,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name=name,
        passed=passed,
        pass_message=pass_message,
        failure_message=failure_message,
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC trajectory diverges from ScenarioSpec layout path.",
        },),
    )


def _logic_file_relative_check(logic_file_path: str | None, parse_error: str | None) -> CheckResult:
    user_home = str(Path.home())
    is_relative = bool(
        logic_file_path
        and not Path(logic_file_path).is_absolute()
        and user_home not in logic_file_path
    )
    measured: dict[str, object] = {
        "logic_file_path": logic_file_path,
        "is_relative": is_relative,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_logic_file_is_relative",
        passed=parse_error is None and is_relative,
        pass_message="XOSC RoadNetwork LogicFile uses a portable relative path.",
        failure_message="XOSC RoadNetwork LogicFile is missing or is not portable and relative.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC LogicFile must use a portable relative path.",
        },),
    )


def _logic_file_target_exists_check(
    xosc_path: Path,
    xodr_path: Path | None,
    logic_file_path: str | None,
    parse_error: str | None,
) -> CheckResult:
    xosc_directory = xosc_path.parent.resolve()
    relative = bool(logic_file_path and not Path(logic_file_path).is_absolute())
    resolved = (xosc_directory / logic_file_path).resolve() if relative and logic_file_path else None
    supplied_xodr = xodr_path.resolve() if xodr_path is not None else None
    matches_build_result = bool(resolved is not None and supplied_xodr is not None and resolved == supplied_xodr)
    target_exists = bool(resolved is not None and resolved.is_file() and matches_build_result)
    measured: dict[str, object] = {
        "xosc_directory": str(xosc_directory),
        "logic_file_path": logic_file_path,
        "resolved_xodr_path": str(resolved) if resolved is not None else None,
        "target_exists": target_exists,
        "build_result_xodr_path": str(supplied_xodr) if supplied_xodr is not None else None,
        "matches_build_result_xodr_path": matches_build_result,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xodr_logic_file_target_exists",
        passed=parse_error is None and target_exists,
        pass_message="XOSC LogicFile resolves to the generated OpenDRIVE file beside the XOSC artifact.",
        failure_message="XOSC LogicFile does not resolve to the generated OpenDRIVE file.",
        measured=measured,
        suggested_operations=({
            "op": "materialize_canonical_road_asset",
            "road_asset": URBAN_TWO_WAY_PARKING_FILENAME,
        },),
    )


def _logic_file_canonical_check(spec: ScenarioSpec, logic_file_path: str | None, parse_error: str | None) -> CheckResult:
    expected_basename = _expected_canonical_road_filename(spec)
    observed_basename = Path(logic_file_path).name if logic_file_path else None
    passed = parse_error is None and observed_basename == expected_basename
    measured: dict[str, object] = {
        "expected_basename": expected_basename,
        "observed_basename": observed_basename,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_logic_file_matches_canonical_road",
        passed=passed,
        pass_message="XOSC LogicFile references the canonical urban two-way parking road.",
        failure_message="XOSC LogicFile does not reference the canonical urban two-way parking road.",
        measured=measured,
        suggested_operations=({
            "op": "materialize_canonical_road_asset",
            "road_asset": expected_basename,
        },),
    )


def _intersection_layout_alignment_check(
    spec: ScenarioSpec,
    xodr_path: Path | None,
    *,
    name: str,
    path_id: str,
) -> CheckResult:
    assert spec.layout is not None
    conflict_point = spec.layout.points.get("conflict_point")
    path = spec.layout.paths.get(path_id)
    road_data, parse_error = _intersection_road_data(xodr_path)
    crossing_x_error = None
    conflict_on_ego_corridor = False
    path_uses_crossing_corridor = False
    junction_has_lane_links = False
    if conflict_point is not None and road_data is not None:
        crossing_x_error = abs(road_data["north_south_cross_x_m"] - conflict_point.x_m)
        conflict_on_ego_corridor = -1.75 <= conflict_point.y_m <= 1.75
        if path is not None and path.points:
            path_uses_crossing_corridor = all(
                abs(point.x_m - conflict_point.x_m) <= 1e-6
                for point in path.points
                if point is not conflict_point
            ) or path_id == "oncoming_turn_path"
        junction_has_lane_links = bool(road_data["junction_lane_link_count"] > 0)
    passed = (
        parse_error is None
        and crossing_x_error is not None
        and crossing_x_error <= POSITION_TOLERANCE_M
        and conflict_on_ego_corridor
        and path_uses_crossing_corridor
        and junction_has_lane_links
    )
    measured: dict[str, object] = {
        "road_asset_id": spec.road_asset_id(),
        "path_id": path_id,
        "conflict_point_x_m": conflict_point.x_m if conflict_point is not None else None,
        "conflict_point_y_m": conflict_point.y_m if conflict_point is not None else None,
        "north_south_cross_x_m": road_data["north_south_cross_x_m"] if road_data is not None else None,
        "crossing_x_error_m": crossing_x_error,
        "conflict_on_ego_corridor": conflict_on_ego_corridor,
        "path_uses_crossing_corridor": path_uses_crossing_corridor,
        "junction_lane_link_count": road_data["junction_lane_link_count"] if road_data is not None else 0,
    }
    if parse_error is not None:
        measured["xodr_parse_error"] = parse_error
    return _result(
        name=name,
        passed=passed,
        pass_message="Intersection XODR road geometry and junction links align with ScenarioSpec layout.",
        failure_message="Intersection XODR road geometry or junction links do not align with ScenarioSpec layout.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "Generated OpenDRIVE intersection does not align with ScenarioSpec layout.",
        },),
    )


def _intersection_road_data(xodr_path: Path | None) -> tuple[dict[str, float | int] | None, str | None]:
    if xodr_path is None:
        return None, "missing xodr_path"
    try:
        root = ET.parse(xodr_path).getroot()
    except (OSError, ET.ParseError) as exc:
        return None, str(exc)
    roads = {road.attrib.get("name", ""): road for road in root.findall("./road")}
    cross_geometry = roads.get("north_south_cross").find("./planView/geometry") if "north_south_cross" in roads else None
    if cross_geometry is None:
        return None, "north_south_cross geometry missing"
    try:
        cross_x = float(cross_geometry.attrib["x"])
    except (KeyError, ValueError) as exc:
        return None, f"north_south_cross x parse error: {exc}"
    return {
        "north_south_cross_x_m": cross_x,
        "junction_lane_link_count": len(root.findall("./junction/connection/laneLink")),
    }, None


def _expected_canonical_road_filename(spec: ScenarioSpec) -> str:
    if spec.scenario_type in {"crossing_vehicle", "oncoming_turn_across_path"}:
        return URBAN_FOUR_WAY_INTERSECTION_FILENAME
    if spec.scenario_type == "cut_in":
        return MULTI_LANE_SAME_DIRECTION_FILENAME
    return URBAN_TWO_WAY_PARKING_FILENAME


def _lead_deceleration_mps2(spec: ScenarioSpec) -> float:
    value = spec.metadata_float("lead_vehicle_braking", "lead_deceleration_mps2", -4.0)
    return value if value is not None else -4.0


def _result(
    *,
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
    suggested_operations: tuple[dict[str, object], ...],
) -> CheckResult:
    return CheckResult(
        name=name,
        passed=passed,
        severity="note" if passed else "repairable",
        message=pass_message if passed else failure_message,
        category="artifact_consistency",
        intent_relation="not_applicable",
        repair_action="none",
        measured=measured,
        suggested_operations=() if passed else suggested_operations,
    )
