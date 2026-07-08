from __future__ import annotations

"""Family checks for intersection crossing-vehicle scenarios."""

import math

from scenariocraft.core.schemas import CheckResult, Point2D, ScenarioSpec


def run_crossing_vehicle_checks(spec: ScenarioSpec) -> tuple[CheckResult, ...]:
    if spec.scenario_type != "crossing_vehicle":
        return ()
    return (
        _path_crosses_ego_path_check(spec),
        _conflict_point_on_both_paths_check(spec),
        _arrival_time_alignment_check(spec),
        _trigger_timing_check(spec),
    )


def _path_crosses_ego_path_check(spec: ScenarioSpec) -> CheckResult:
    measured = _path_crossing_measured(spec)
    return _result(
        "crossing_vehicle_path_crosses_ego_path",
        bool(measured["crosses_ego_path"]),
        "Crossing vehicle path crosses the ego path.",
        "Crossing vehicle path does not cross the ego path.",
        measured,
    )


def _conflict_point_on_both_paths_check(spec: ScenarioSpec) -> CheckResult:
    measured = _conflict_point_measured(spec)
    return _result(
        "crossing_vehicle_conflict_point_on_both_paths",
        bool(measured["on_ego_path"] and measured["on_crossing_path"]),
        "Conflict point lies on both ego and crossing-vehicle paths.",
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
        "crossing_vehicle_arrival_time_alignment",
        passed,
        "Ego and crossing vehicle reach the conflict point within the intended timing tolerance.",
        "Ego and crossing vehicle do not reach the conflict point within the intended timing tolerance.",
        measured,
    )


def _trigger_timing_check(spec: ScenarioSpec) -> CheckResult:
    trigger_time_s = _trigger_time_s(spec)
    stop_time_s = spec.timing.total_duration_s if spec.timing is not None else None
    passed = trigger_time_s is not None and stop_time_s is not None and 0.0 <= trigger_time_s < stop_time_s
    return _result(
        "crossing_vehicle_trigger_timing",
        passed,
        "Crossing-vehicle trigger is reachable before scenario stop time.",
        "Crossing-vehicle trigger is not reachable before scenario stop time.",
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
    crossing_path = spec.layout.paths.get("crossing_vehicle_path")
    if ego_path is None or crossing_path is None:
        return {"crosses_ego_path": False}
    ego_y = ego_path.points[0].y_m
    x_min = min(point.x_m for point in ego_path.points)
    x_max = max(point.x_m for point in ego_path.points)
    crossing_x = crossing_path.points[0].x_m
    y_min = min(point.y_m for point in crossing_path.points)
    y_max = max(point.y_m for point in crossing_path.points)
    return {
        "ego_y_m": ego_y,
        "crossing_x_m": crossing_x,
        "ego_path_x_min_m": x_min,
        "ego_path_x_max_m": x_max,
        "crossing_path_y_min_m": y_min,
        "crossing_path_y_max_m": y_max,
        "crosses_ego_path": x_min <= crossing_x <= x_max and y_min <= ego_y <= y_max,
    }


def _conflict_point_measured(spec: ScenarioSpec) -> dict[str, object]:
    if spec.layout is None:
        return {"on_ego_path": False, "on_crossing_path": False}
    conflict = spec.layout.points.get("conflict_point")
    ego_path = spec.layout.paths.get("ego_path")
    crossing_path = spec.layout.paths.get("crossing_vehicle_path")
    if conflict is None or ego_path is None or crossing_path is None:
        return {"on_ego_path": False, "on_crossing_path": False}
    return {
        "conflict_x_m": conflict.x_m,
        "conflict_y_m": conflict.y_m,
        "on_ego_path": _point_on_axis_aligned_path(conflict, ego_path.points),
        "on_crossing_path": _point_on_axis_aligned_path(conflict, crossing_path.points),
    }


def _arrival_time_measured(spec: ScenarioSpec) -> dict[str, object]:
    unavailable = {"ego_arrival_time_s": None, "crossing_vehicle_arrival_time_s": None, "arrival_time_delta_s": None}
    if spec.layout is None:
        return unavailable
    conflict = spec.layout.points.get("conflict_point")
    ego_actor = spec.actor_by_id("ego")
    crossing_actor = spec.actor_by_id("crossing_vehicle")
    ego_pose = spec.layout.actor_poses.get("ego")
    crossing_pose = spec.layout.actor_poses.get("crossing_vehicle")
    if (
        conflict is None
        or ego_actor is None
        or crossing_actor is None
        or ego_actor.initial_speed_kph is None
        or crossing_actor.initial_speed_kph is None
        or ego_pose is None
        or crossing_pose is None
    ):
        return unavailable
    ego_time = _distance(ego_pose.x_m, ego_pose.y_m, conflict) / (ego_actor.initial_speed_kph / 3.6)
    crossing_time = _distance(crossing_pose.x_m, crossing_pose.y_m, conflict) / (
        crossing_actor.initial_speed_kph / 3.6
    )
    return {
        "ego_arrival_time_s": ego_time,
        "crossing_vehicle_arrival_time_s": crossing_time,
        "arrival_time_delta_s": crossing_time - ego_time,
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
    value = spec.metadata_float("crossing_vehicle", "arrival_time_tolerance_s", 0.35)
    return value if value is not None else 0.35


def _point_on_axis_aligned_path(point: Point2D, path: tuple[Point2D, ...]) -> bool:
    for start, end in zip(path, path[1:]):
        if abs(start.x_m - end.x_m) <= 1e-9 and abs(point.x_m - start.x_m) <= 1e-9:
            if min(start.y_m, end.y_m) <= point.y_m <= max(start.y_m, end.y_m):
                return True
        if abs(start.y_m - end.y_m) <= 1e-9 and abs(point.y_m - start.y_m) <= 1e-9:
            if min(start.x_m, end.x_m) <= point.x_m <= max(start.x_m, end.x_m):
                return True
    return False


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
