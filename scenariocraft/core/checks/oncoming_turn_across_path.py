from __future__ import annotations

"""Family checks for oncoming-turn-across-path scenarios."""

import math

from scenariocraft.core.schemas import CheckResult, Point2D, ScenarioSpec


def run_oncoming_turn_across_path_checks(spec: ScenarioSpec) -> tuple[CheckResult, ...]:
    if spec.scenario_type != "oncoming_turn_across_path":
        return ()
    return (
        _starts_opposite_ego_check(spec),
        _path_crosses_ego_path_check(spec),
        _conflict_point_on_paths_check(spec),
        _arrival_time_alignment_check(spec),
        _trigger_timing_check(spec),
    )


def _starts_opposite_ego_check(spec: ScenarioSpec) -> CheckResult:
    if spec.layout is None:
        measured = {"starts_opposite_ego": False}
    else:
        pose = spec.layout.actor_poses.get("oncoming_vehicle")
        measured = {
            "oncoming_y_m": pose.y_m if pose is not None else None,
            "oncoming_heading_rad": pose.heading_rad if pose is not None else None,
            "starts_opposite_ego": bool(pose is not None and pose.y_m > 1.75 and pose.heading_rad > 3.0),
        }
    return _result(
        "oncoming_turn_starts_opposite_ego",
        bool(measured["starts_opposite_ego"]),
        "Oncoming vehicle starts in the opposing direction before turning.",
        "Oncoming vehicle does not start in the expected opposing approach.",
        measured,
    )


def _path_crosses_ego_path_check(spec: ScenarioSpec) -> CheckResult:
    measured = _path_crossing_measured(spec)
    return _result(
        "oncoming_turn_path_crosses_ego_path",
        bool(measured["crosses_ego_path"]),
        "Oncoming turn path crosses the ego path.",
        "Oncoming turn path does not cross the ego path.",
        measured,
    )


def _conflict_point_on_paths_check(spec: ScenarioSpec) -> CheckResult:
    measured = _conflict_point_measured(spec)
    return _result(
        "oncoming_turn_conflict_point_on_paths",
        bool(measured["on_ego_path"] and measured["on_turn_path"]),
        "Conflict point lies on both ego and oncoming-turn paths.",
        "Conflict point does not lie on both relevant paths.",
        measured,
    )


def _arrival_time_alignment_check(spec: ScenarioSpec) -> CheckResult:
    measured = _arrival_time_measured(spec)
    tolerance_s = _arrival_time_tolerance_s(spec)
    delta_s = measured["arrival_time_delta_s"]
    passed = delta_s is not None and abs(float(delta_s)) <= tolerance_s
    measured["arrival_time_tolerance_s"] = tolerance_s
    return _result(
        "oncoming_turn_arrival_time_alignment",
        passed,
        "Ego and oncoming vehicle reach the conflict point within the intended timing tolerance.",
        "Ego and oncoming vehicle do not reach the conflict point within the intended timing tolerance.",
        measured,
    )


def _trigger_timing_check(spec: ScenarioSpec) -> CheckResult:
    trigger_time_s = _trigger_time_s(spec)
    stop_time_s = spec.timing.total_duration_s if spec.timing is not None else None
    passed = trigger_time_s is not None and stop_time_s is not None and 0.0 <= trigger_time_s < stop_time_s
    return _result(
        "oncoming_turn_trigger_timing",
        passed,
        "Oncoming-turn trigger is reachable before scenario stop time.",
        "Oncoming-turn trigger is not reachable before scenario stop time.",
        {
            "trigger_distance_m": spec.trigger.distance_m,
            "trigger_time_s": trigger_time_s,
            "stop_time_s": stop_time_s,
        },
    )


def _path_crossing_measured(spec: ScenarioSpec) -> dict[str, object]:
    if spec.layout is None:
        return {"crosses_ego_path": False}
    ego_path = spec.layout.paths.get("ego_path")
    turn_path = spec.layout.paths.get("oncoming_turn_path")
    if ego_path is None or turn_path is None:
        return {"crosses_ego_path": False}
    ego_y = ego_path.points[0].y_m
    x_min = min(point.x_m for point in ego_path.points)
    x_max = max(point.x_m for point in ego_path.points)
    y_values = [point.y_m for point in turn_path.points]
    return {
        "ego_y_m": ego_y,
        "ego_path_x_min_m": x_min,
        "ego_path_x_max_m": x_max,
        "turn_path_y_min_m": min(y_values),
        "turn_path_y_max_m": max(y_values),
        "crosses_ego_path": min(y_values) <= ego_y <= max(y_values),
    }


def _conflict_point_measured(spec: ScenarioSpec) -> dict[str, object]:
    if spec.layout is None:
        return {"on_ego_path": False, "on_turn_path": False}
    conflict = spec.layout.points.get("conflict_point")
    ego_path = spec.layout.paths.get("ego_path")
    turn_path = spec.layout.paths.get("oncoming_turn_path")
    if conflict is None or ego_path is None or turn_path is None:
        return {"on_ego_path": False, "on_turn_path": False}
    return {
        "conflict_x_m": conflict.x_m,
        "conflict_y_m": conflict.y_m,
        "on_ego_path": _point_on_axis_aligned_path(conflict, ego_path.points),
        "on_turn_path": any(_same_point(conflict, point) for point in turn_path.points),
    }


def _arrival_time_measured(spec: ScenarioSpec) -> dict[str, object]:
    unavailable = {"ego_arrival_time_s": None, "oncoming_vehicle_arrival_time_s": None, "arrival_time_delta_s": None}
    if spec.layout is None:
        return unavailable
    conflict = spec.layout.points.get("conflict_point")
    ego_actor = spec.actor_by_id("ego")
    oncoming_actor = spec.actor_by_id("oncoming_vehicle")
    ego_pose = spec.layout.actor_poses.get("ego")
    oncoming_pose = spec.layout.actor_poses.get("oncoming_vehicle")
    if (
        conflict is None
        or ego_actor is None
        or oncoming_actor is None
        or ego_actor.initial_speed_kph is None
        or oncoming_actor.initial_speed_kph is None
        or ego_pose is None
        or oncoming_pose is None
    ):
        return unavailable
    ego_time = _distance(ego_pose.x_m, ego_pose.y_m, conflict) / (ego_actor.initial_speed_kph / 3.6)
    oncoming_time = _distance(oncoming_pose.x_m, oncoming_pose.y_m, conflict) / (
        oncoming_actor.initial_speed_kph / 3.6
    )
    return {
        "ego_arrival_time_s": ego_time,
        "oncoming_vehicle_arrival_time_s": oncoming_time,
        "arrival_time_delta_s": oncoming_time - ego_time,
    }


def _trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    source_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    source_actor = spec.actor_by_id(spec.trigger.source)
    if source_pose is None or target_pose is None or source_actor is None or source_actor.initial_speed_kph is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0.0:
        return None
    distance_to_threshold = target_pose.x_m - source_pose.x_m - spec.trigger.distance_m
    return max(distance_to_threshold, 0.0) / speed_mps


def _arrival_time_tolerance_s(spec: ScenarioSpec) -> float:
    value = spec.metadata_float("oncoming_turn_across_path", "arrival_time_tolerance_s", 0.45)
    return value if value is not None else 0.45


def _point_on_axis_aligned_path(point: Point2D, path: tuple[Point2D, ...]) -> bool:
    for start, end in zip(path, path[1:]):
        if abs(start.y_m - end.y_m) <= 1e-9 and abs(point.y_m - start.y_m) <= 1e-9:
            if min(start.x_m, end.x_m) <= point.x_m <= max(start.x_m, end.x_m):
                return True
        if abs(start.x_m - end.x_m) <= 1e-9 and abs(point.x_m - start.x_m) <= 1e-9:
            if min(start.y_m, end.y_m) <= point.y_m <= max(start.y_m, end.y_m):
                return True
    return False


def _same_point(left: Point2D, right: Point2D) -> bool:
    return abs(left.x_m - right.x_m) <= 1e-9 and abs(left.y_m - right.y_m) <= 1e-9


def _distance(x_m: float, y_m: float, point: Point2D) -> float:
    return math.hypot(point.x_m - x_m, point.y_m - y_m)


def _result(
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
) -> CheckResult:
    return CheckResult(
        name=name,
        passed=passed,
        severity="note" if passed else "warning",
        message=pass_message if passed else failure_message,
        category="intent_alignment",
        intent_relation="matches_intent" if passed else "mismatches_intent",
        repair_action=None if passed else "none",
        measured=measured,
    )
