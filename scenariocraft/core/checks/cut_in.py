from __future__ import annotations

"""Family checks for adjacent-lane cut-in scenarios."""

from scenariocraft.core.schemas import CheckResult, ScenarioSpec


def run_cut_in_checks(spec: ScenarioSpec) -> tuple[CheckResult, ...]:
    if spec.scenario_type != "cut_in":
        return ()
    return (
        _starts_in_adjacent_lane_check(spec),
        _ends_in_ego_lane_check(spec),
        _path_crosses_into_ego_lane_check(spec),
        _trigger_timing_check(spec),
    )


def _starts_in_adjacent_lane_check(spec: ScenarioSpec) -> CheckResult:
    measured = _lane_membership_measured(spec, actor_id="cut_in_vehicle", band_id="adjacent_same_direction_lane")
    return _result(
        "cut_in_starts_in_adjacent_lane",
        bool(measured["inside_band"]),
        "Cut-in vehicle starts fully inside the adjacent same-direction lane.",
        "Cut-in vehicle must start fully inside the adjacent same-direction lane.",
        measured,
    )


def _ends_in_ego_lane_check(spec: ScenarioSpec) -> CheckResult:
    measured = _path_endpoint_measured(spec, path_id="cut_in_path", band_id="ego_driving_lane")
    return _result(
        "cut_in_ends_in_ego_lane",
        bool(measured["endpoint_inside_band"]),
        "Cut-in path ends inside the ego driving lane.",
        "Cut-in path must end inside the ego driving lane.",
        measured,
    )


def _path_crosses_into_ego_lane_check(spec: ScenarioSpec) -> CheckResult:
    measured = _path_crossing_measured(spec)
    return _result(
        "cut_in_path_crosses_into_ego_lane",
        bool(measured["starts_above_ego_lane"] and measured["ends_inside_ego_lane"]),
        "Cut-in path crosses from the adjacent lane into the ego driving lane.",
        "Cut-in path must cross from the adjacent lane into the ego driving lane.",
        measured,
    )


def _trigger_timing_check(spec: ScenarioSpec) -> CheckResult:
    trigger_time_s = _trigger_time_s(spec)
    stop_time_s = spec.timing.total_duration_s if spec.timing is not None else None
    passed = trigger_time_s is not None and stop_time_s is not None and 0.0 <= trigger_time_s < stop_time_s
    return _result(
        "cut_in_trigger_timing",
        passed,
        "Cut-in trigger is reachable before the scenario stop time.",
        "Cut-in trigger is not reachable before the scenario stop time.",
        {
            "trigger_distance_m": spec.trigger.distance_m,
            "trigger_time_s": trigger_time_s,
            "stop_time_s": stop_time_s,
        },
    )


def _lane_membership_measured(spec: ScenarioSpec, *, actor_id: str, band_id: str) -> dict[str, object]:
    if spec.layout is None:
        return {"actor_id": actor_id, "band_id": band_id, "inside_band": False}
    pose = spec.layout.actor_poses.get(actor_id)
    footprint = spec.layout.actor_footprints.get(actor_id)
    band = _band(spec, band_id)
    if pose is None or footprint is None or band is None:
        return {"actor_id": actor_id, "band_id": band_id, "inside_band": False}
    y_min = pose.y_m - footprint.width_m / 2.0
    y_max = pose.y_m + footprint.width_m / 2.0
    inside = band.y_min_m <= y_min <= y_max <= band.y_max_m
    return {
        "actor_id": actor_id,
        "band_id": band_id,
        "actor_y_min_m": y_min,
        "actor_y_max_m": y_max,
        "band_y_min_m": band.y_min_m,
        "band_y_max_m": band.y_max_m,
        "inside_band": inside,
    }


def _path_endpoint_measured(spec: ScenarioSpec, *, path_id: str, band_id: str) -> dict[str, object]:
    if spec.layout is None:
        return {"path_id": path_id, "band_id": band_id, "endpoint_inside_band": False}
    path = spec.layout.paths.get(path_id)
    band = _band(spec, band_id)
    if path is None or band is None:
        return {"path_id": path_id, "band_id": band_id, "endpoint_inside_band": False}
    endpoint = path.points[-1]
    inside = band.y_min_m <= endpoint.y_m <= band.y_max_m
    return {
        "path_id": path_id,
        "band_id": band_id,
        "endpoint_x_m": endpoint.x_m,
        "endpoint_y_m": endpoint.y_m,
        "band_y_min_m": band.y_min_m,
        "band_y_max_m": band.y_max_m,
        "endpoint_inside_band": inside,
    }


def _path_crossing_measured(spec: ScenarioSpec) -> dict[str, object]:
    if spec.layout is None:
        return {"starts_above_ego_lane": False, "ends_inside_ego_lane": False}
    path = spec.layout.paths.get("cut_in_path")
    band = _band(spec, "ego_driving_lane")
    if path is None or band is None:
        return {"starts_above_ego_lane": False, "ends_inside_ego_lane": False}
    start = path.points[0]
    end = path.points[-1]
    return {
        "start_y_m": start.y_m,
        "end_y_m": end.y_m,
        "ego_lane_y_min_m": band.y_min_m,
        "ego_lane_y_max_m": band.y_max_m,
        "starts_above_ego_lane": start.y_m > band.y_max_m,
        "ends_inside_ego_lane": band.y_min_m <= end.y_m <= band.y_max_m,
    }


def _trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    ego_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    ego = spec.actor_by_id(spec.trigger.source)
    if ego_pose is None or target_pose is None or ego is None or ego.initial_speed_kph is None:
        return None
    ego_speed_mps = ego.initial_speed_kph / 3.6
    if ego_speed_mps <= 0.0:
        return None
    distance_to_threshold = target_pose.x_m - ego_pose.x_m - spec.trigger.distance_m
    return max(distance_to_threshold, 0.0) / ego_speed_mps


def _band(spec: ScenarioSpec, band_id: str) -> object | None:
    if spec.layout is None:
        return None
    return next((band for band in spec.layout.road_bands if band.id == band_id), None)


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
