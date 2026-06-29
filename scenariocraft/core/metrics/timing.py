from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from scenariocraft.core.schemas import ScenarioSpec


@dataclass(frozen=True)
class ScenarioTimingMetrics:
    target_ttc_s: float | None
    trigger_threshold_time_s: float | None
    ego_lead_time_to_conflict_s: float | None
    pedestrian_time_to_conflict_s: float | None
    runtime_min_ttc_s: float | None = None
    time_headway_s: float | None = None


def compute_timing_metrics(spec: ScenarioSpec) -> ScenarioTimingMetrics:
    return ScenarioTimingMetrics(
        target_ttc_s=spec.intended_criticality.target_min_ttc_s,
        trigger_threshold_time_s=trigger_threshold_time_s(spec),
        ego_lead_time_to_conflict_s=ego_lead_time_to_conflict_s(spec),
        pedestrian_time_to_conflict_s=pedestrian_time_to_conflict_s(spec),
        time_headway_s=time_headway_s(spec),
    )


def trigger_threshold_time_s(spec: ScenarioSpec) -> float | None:
    condition = spec.trigger.condition
    if condition is not None and condition.metric != "relative_distance":
        return None
    ego = spec.actor_by_id(spec.trigger.source)
    if ego is None or ego.initial_speed_kph is None:
        return None
    speed_mps = ego.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    return spec.trigger.distance_m / speed_mps


def ego_lead_time_to_conflict_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    ego = spec.actor_by_id(spec.trigger.source)
    trigger_point = spec.layout.points.get("trigger_point")
    conflict_point = spec.layout.points.get("conflict_point")
    if ego is None or ego.initial_speed_kph is None or trigger_point is None or conflict_point is None:
        return None
    speed_mps = ego.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    return (conflict_point.x_m - trigger_point.x_m) / speed_mps


def pedestrian_time_to_conflict_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    pedestrian = spec.actor_by_role("crossing_actor")
    path = spec.layout.paths.get("pedestrian_crossing_path")
    conflict_point = spec.layout.points.get("conflict_point")
    if pedestrian is None or pedestrian.speed_mps is None or pedestrian.speed_mps <= 0:
        return None
    if path is None or conflict_point is None:
        return None
    if len(path.points) < 2:
        return None

    distance_m = 0.0
    previous = path.points[0]
    if previous == conflict_point:
        return 0.0
    for current in path.points[1:]:
        if _point_on_segment(conflict_point, previous, current):
            distance_m += hypot(conflict_point.x_m - previous.x_m, conflict_point.y_m - previous.y_m)
            return distance_m / pedestrian.speed_mps
        distance_m += hypot(current.x_m - previous.x_m, current.y_m - previous.y_m)
        previous = current
    return None


def time_headway_s(
    spec: ScenarioSpec,
    *,
    source_actor_id: str | None = None,
    target_actor_id: str | None = None,
    max_lateral_offset_m: float = 1.0,
) -> float | None:
    if spec.layout is None:
        return None
    condition = spec.trigger.condition
    source_id = source_actor_id or (condition.source if condition is not None else spec.trigger.source)
    target_id = target_actor_id or (condition.target if condition is not None else spec.trigger.target)
    if source_id is None or target_id is None:
        return None
    source_actor = spec.actor_by_id(source_id)
    source_pose = spec.layout.actor_poses.get(source_id)
    target_pose = spec.layout.actor_poses.get(target_id)
    if source_actor is None or source_actor.initial_speed_kph is None or source_pose is None or target_pose is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    if abs(target_pose.y_m - source_pose.y_m) > max_lateral_offset_m:
        return None
    longitudinal_gap_m = target_pose.x_m - source_pose.x_m
    if longitudinal_gap_m <= 0:
        return None
    return longitudinal_gap_m / speed_mps


def _point_on_segment(point: object, start: object, end: object) -> bool:
    cross = (point.y_m - start.y_m) * (end.x_m - start.x_m) - (point.x_m - start.x_m) * (end.y_m - start.y_m)
    if abs(cross) > 1e-6:
        return False
    min_x, max_x = sorted((start.x_m, end.x_m))
    min_y, max_y = sorted((start.y_m, end.y_m))
    return min_x - 1e-6 <= point.x_m <= max_x + 1e-6 and min_y - 1e-6 <= point.y_m <= max_y + 1e-6
