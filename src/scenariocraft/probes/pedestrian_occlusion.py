from __future__ import annotations

import math
from collections.abc import Callable

from scenariocraft.probes.base import run_probes
from scenariocraft.schemas import (
    FootprintSpec,
    LayoutSpec,
    Point2D,
    Pose2D,
    ProbeResult,
    RoadBandSpec,
    ScenarioSpec,
)
from scenariocraft.templates.pedestrian_occlusion import PedestrianOcclusionParameters

POSITION_TOLERANCE_M = 1e-6
PATH_TOLERANCE_M = 1e-6
REQUIRED_PATH_CLEARANCE_M = PedestrianOcclusionParameters().minimum_path_clearance_m


class _PedestrianOcclusionProbe:
    def __init__(self, name: str, check: Callable[[ScenarioSpec], ProbeResult]) -> None:
        self.name = name
        self._check = check

    def run(self, spec: ScenarioSpec) -> ProbeResult:
        return self._check(spec)


def run_pedestrian_occlusion_probes(spec: ScenarioSpec) -> tuple[ProbeResult, ...]:
    probes = (
        _PedestrianOcclusionProbe("ego_footprint_in_ego_lane", _ego_footprint_in_ego_lane),
        _PedestrianOcclusionProbe("parked_van_footprint_in_parking_strip", _parked_van_footprint_in_parking_strip),
        _PedestrianOcclusionProbe("pedestrian_initial_footprint_in_sidewalk", _pedestrian_initial_footprint_in_sidewalk),
        _PedestrianOcclusionProbe("pedestrian_path_starts_at_pedestrian_pose", _pedestrian_path_starts_at_pedestrian_pose),
        _PedestrianOcclusionProbe("pedestrian_path_crosses_ego_lane", _pedestrian_path_crosses_ego_lane),
        _PedestrianOcclusionProbe("pedestrian_path_clear_of_occluder", _pedestrian_path_clear_of_occluder),
        _PedestrianOcclusionProbe("pedestrian_line_of_sight_occluded_by_van", _pedestrian_line_of_sight_occluded_by_van),
        _PedestrianOcclusionProbe("conflict_point_on_path_and_in_ego_lane", _conflict_point_on_path_and_in_ego_lane),
        _PedestrianOcclusionProbe("trigger_point_before_conflict_and_in_ego_lane", _trigger_point_before_conflict_and_in_ego_lane),
    )
    return run_probes(spec, probes)


def _ego_footprint_in_ego_lane(spec: ScenarioSpec) -> ProbeResult:
    return _footprint_in_band_probe(
        spec,
        name="ego_footprint_in_ego_lane",
        actor_id="ego",
        band_id="ego_driving_lane",
        failure_message="Ego footprint is not fully inside the ego driving lane.",
    )


def _parked_van_footprint_in_parking_strip(spec: ScenarioSpec) -> ProbeResult:
    return _footprint_in_band_probe(
        spec,
        name="parked_van_footprint_in_parking_strip",
        actor_id="parked_van",
        band_id="ego_side_parking_strip",
        failure_message="Parked van footprint is not fully inside the ego-side parking strip.",
        suggested_operations=(
            {"op": "reposition_actor", "actor_id": "parked_van", "target_band_id": "ego_side_parking_strip"},
        ),
    )


def _pedestrian_initial_footprint_in_sidewalk(spec: ScenarioSpec) -> ProbeResult:
    return _footprint_in_band_probe(
        spec,
        name="pedestrian_initial_footprint_in_sidewalk",
        actor_id="pedestrian",
        band_id="ego_side_sidewalk",
        failure_message="Pedestrian initial footprint is not fully inside the ego-side sidewalk.",
        suggested_operations=(
            {"op": "reposition_actor", "actor_id": "pedestrian", "target_band_id": "ego_side_sidewalk"},
        ),
    )


def _pedestrian_path_starts_at_pedestrian_pose(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    path = _path_points(layout, "pedestrian_crossing_path")
    pose = _pose(layout, "pedestrian")
    start = path[0]
    position_error_m = _distance(start, Point2D(pose.x_m, pose.y_m))
    passed = position_error_m <= POSITION_TOLERANCE_M
    return _result(
        name="pedestrian_path_starts_at_pedestrian_pose",
        passed=passed,
        pass_message="Pedestrian crossing path starts at the pedestrian initial pose.",
        failure_message="Pedestrian crossing path does not start at the pedestrian initial pose.",
        measured={
            "path_start_x_m": start.x_m,
            "path_start_y_m": start.y_m,
            "pedestrian_x_m": pose.x_m,
            "pedestrian_y_m": pose.y_m,
            "position_error_m": position_error_m,
            "tolerance_m": POSITION_TOLERANCE_M,
        },
    )


def _pedestrian_path_crosses_ego_lane(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    path = _path_points(layout, "pedestrian_crossing_path")
    lane = _band(layout, "ego_driving_lane")
    path_y_min = min(point.y_m for point in path)
    path_y_max = max(point.y_m for point in path)
    passed = any(_segment_intersects_band(start, end, lane) for start, end in _segments(path))
    return _result(
        name="pedestrian_path_crosses_ego_lane",
        passed=passed,
        pass_message="Pedestrian crossing path intersects the ego driving lane.",
        failure_message="Pedestrian crossing path does not intersect the ego driving lane.",
        measured={
            "path_y_min_m": path_y_min,
            "path_y_max_m": path_y_max,
            "ego_lane_y_min_m": lane.y_min_m,
            "ego_lane_y_max_m": lane.y_max_m,
        },
    )


def _pedestrian_path_clear_of_occluder(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    path = _path_points(layout, "pedestrian_crossing_path")
    van_rect = _actor_rect(layout, "parked_van")
    intersects = any(_segment_intersects_rect(start, end, van_rect) for start, end in _segments(path))
    clearance = _polyline_rect_clearance(path, van_rect)
    passed = not intersects and clearance + PATH_TOLERANCE_M >= REQUIRED_PATH_CLEARANCE_M
    return _result(
        name="pedestrian_path_clear_of_occluder",
        passed=passed,
        pass_message="Pedestrian crossing path stays clear of the parked van footprint.",
        failure_message="Pedestrian crossing path intersects or is too close to the parked van footprint.",
        measured={
            "minimum_clearance_m": clearance,
            "required_clearance_m": REQUIRED_PATH_CLEARANCE_M,
            "path_intersects_van_footprint": intersects,
        },
        suggested_operations=({"op": "reposition_path_or_actor", "actor_id": "parked_van", "path_id": "pedestrian_crossing_path"},),
    )


def _pedestrian_line_of_sight_occluded_by_van(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    ego = _pose(layout, "ego")
    pedestrian = _pose(layout, "pedestrian")
    start = Point2D(ego.x_m, ego.y_m)
    end = Point2D(pedestrian.x_m, pedestrian.y_m)
    intersects = _segment_intersects_rect(start, end, _actor_rect(layout, "parked_van"))
    return _result(
        name="pedestrian_line_of_sight_occluded_by_van",
        passed=intersects,
        pass_message="Ego-to-pedestrian initial line of sight intersects the parked van footprint.",
        failure_message="Ego-to-pedestrian initial line of sight does not intersect the parked van footprint.",
        measured={
            "ego_position": {"x_m": start.x_m, "y_m": start.y_m},
            "pedestrian_initial_position": {"x_m": end.x_m, "y_m": end.y_m},
            "occluder_id": "parked_van",
            "line_of_sight_intersects_footprint": intersects,
        },
        suggested_operations=({"op": "reposition_occluder_or_pedestrian", "occluder_id": "parked_van", "actor_id": "pedestrian"},),
    )


def _conflict_point_on_path_and_in_ego_lane(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    conflict = _point(layout, "conflict_point")
    path = _path_points(layout, "pedestrian_crossing_path")
    lane = _band(layout, "ego_driving_lane")
    distance = _point_to_polyline_distance(conflict, path)
    point_on_path = distance <= PATH_TOLERANCE_M
    inside_lane = _point_inside_band(conflict, lane)
    passed = point_on_path and inside_lane
    return _result(
        name="conflict_point_on_path_and_in_ego_lane",
        passed=passed,
        pass_message="Conflict point lies on the pedestrian path and inside the ego driving lane.",
        failure_message="Conflict point is not on the pedestrian path or not inside the ego driving lane.",
        measured={
            "conflict_point": {"x_m": conflict.x_m, "y_m": conflict.y_m},
            "point_on_path": point_on_path,
            "point_to_path_distance_m": distance,
            "path_tolerance_m": PATH_TOLERANCE_M,
            "ego_lane_y_min_m": lane.y_min_m,
            "ego_lane_y_max_m": lane.y_max_m,
        },
    )


def _trigger_point_before_conflict_and_in_ego_lane(spec: ScenarioSpec) -> ProbeResult:
    layout = _require_layout(spec)
    trigger = _point(layout, "trigger_point")
    conflict = _point(layout, "conflict_point")
    lane = _band(layout, "ego_driving_lane")
    inside_lane = _point_inside_band(trigger, lane)
    gap = conflict.x_m - trigger.x_m
    passed = inside_lane and trigger.x_m < conflict.x_m
    return _result(
        name="trigger_point_before_conflict_and_in_ego_lane",
        passed=passed,
        pass_message="Trigger point is inside the ego lane and before the conflict point.",
        failure_message="Trigger point is not inside the ego lane or not before the conflict point.",
        measured={
            "trigger_x_m": trigger.x_m,
            "conflict_x_m": conflict.x_m,
            "longitudinal_gap_m": gap,
            "trigger_inside_ego_lane": inside_lane,
        },
    )


def _footprint_in_band_probe(
    spec: ScenarioSpec,
    *,
    name: str,
    actor_id: str,
    band_id: str,
    failure_message: str,
    suggested_operations: tuple[dict[str, object], ...] = (),
) -> ProbeResult:
    layout = _require_layout(spec)
    rect = _actor_rect(layout, actor_id)
    band = _band(layout, band_id)
    passed = _rect_inside_band(rect, band)
    _, _, actor_y_min, actor_y_max = rect
    return _result(
        name=name,
        passed=passed,
        pass_message=f"{actor_id} footprint is fully inside {band_id}.",
        failure_message=failure_message,
        measured={
            "actor_id": actor_id,
            "actor_y_min_m": actor_y_min,
            "actor_y_max_m": actor_y_max,
            "band_id": band.id,
            "band_y_min_m": band.y_min_m,
            "band_y_max_m": band.y_max_m,
        },
        suggested_operations=suggested_operations,
    )


def _result(
    *,
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
    suggested_operations: tuple[dict[str, object], ...] = (),
) -> ProbeResult:
    return ProbeResult(
        name=name,
        passed=passed,
        severity="note" if passed else "failure",
        message=pass_message if passed else failure_message,
        measured=measured,
        suggested_operations=() if passed else suggested_operations,
    )


def _require_layout(spec: ScenarioSpec) -> LayoutSpec:
    if spec.layout is None:
        raise ValueError("pedestrian_occlusion probes require ScenarioSpec.layout.")
    return spec.layout


def _pose(layout: LayoutSpec, actor_id: str) -> Pose2D:
    return layout.actor_poses[actor_id]


def _footprint(layout: LayoutSpec, actor_id: str) -> FootprintSpec:
    return layout.actor_footprints[actor_id]


def _point(layout: LayoutSpec, point_id: str) -> Point2D:
    return layout.points[point_id]


def _band(layout: LayoutSpec, band_id: str) -> RoadBandSpec:
    return next(band for band in layout.road_bands if band.id == band_id)


def _path_points(layout: LayoutSpec, path_id: str) -> tuple[Point2D, ...]:
    return layout.paths[path_id].points


def _actor_rect(layout: LayoutSpec, actor_id: str) -> tuple[float, float, float, float]:
    pose = _pose(layout, actor_id)
    footprint = _footprint(layout, actor_id)
    return (
        pose.x_m - footprint.length_m / 2.0,
        pose.x_m + footprint.length_m / 2.0,
        pose.y_m - footprint.width_m / 2.0,
        pose.y_m + footprint.width_m / 2.0,
    )


def _rect_inside_band(rect: tuple[float, float, float, float], band: RoadBandSpec) -> bool:
    _, _, y_min, y_max = rect
    return band.y_min_m <= y_min <= y_max <= band.y_max_m


def _point_inside_band(point: Point2D, band: RoadBandSpec) -> bool:
    return band.y_min_m <= point.y_m <= band.y_max_m


def _segment_intersects_band(start: Point2D, end: Point2D, band: RoadBandSpec) -> bool:
    y_min, y_max = sorted((start.y_m, end.y_m))
    return max(y_min, band.y_min_m) <= min(y_max, band.y_max_m)


def _segments(points: tuple[Point2D, ...]) -> tuple[tuple[Point2D, Point2D], ...]:
    return tuple((points[index], points[index + 1]) for index in range(len(points) - 1))


def _segment_intersects_rect(start: Point2D, end: Point2D, rect: tuple[float, float, float, float]) -> bool:
    if _point_in_rect(start, rect) or _point_in_rect(end, rect):
        return True
    min_x, max_x, min_y, max_y = rect
    corners = (
        Point2D(min_x, min_y),
        Point2D(max_x, min_y),
        Point2D(max_x, max_y),
        Point2D(min_x, max_y),
    )
    edges = (
        (corners[0], corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    )
    return any(_segments_intersect(start, end, edge_start, edge_end) for edge_start, edge_end in edges)


def _point_in_rect(point: Point2D, rect: tuple[float, float, float, float]) -> bool:
    min_x, max_x, min_y, max_y = rect
    return min_x <= point.x_m <= max_x and min_y <= point.y_m <= max_y


def _segments_intersect(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    def orientation(p: Point2D, q: Point2D, r: Point2D) -> float:
        return (q.y_m - p.y_m) * (r.x_m - q.x_m) - (q.x_m - p.x_m) * (r.y_m - q.y_m)

    def on_segment(p: Point2D, q: Point2D, r: Point2D) -> bool:
        return (
            min(p.x_m, r.x_m) - PATH_TOLERANCE_M <= q.x_m <= max(p.x_m, r.x_m) + PATH_TOLERANCE_M
            and min(p.y_m, r.y_m) - PATH_TOLERANCE_M <= q.y_m <= max(p.y_m, r.y_m) + PATH_TOLERANCE_M
        )

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    if abs(o1) <= PATH_TOLERANCE_M and on_segment(a, c, b):
        return True
    if abs(o2) <= PATH_TOLERANCE_M and on_segment(a, d, b):
        return True
    if abs(o3) <= PATH_TOLERANCE_M and on_segment(c, a, d):
        return True
    if abs(o4) <= PATH_TOLERANCE_M and on_segment(c, b, d):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _polyline_rect_clearance(points: tuple[Point2D, ...], rect: tuple[float, float, float, float]) -> float:
    return min(_segment_rect_clearance(start, end, rect) for start, end in _segments(points))


def _segment_rect_clearance(start: Point2D, end: Point2D, rect: tuple[float, float, float, float]) -> float:
    if _segment_intersects_rect(start, end, rect):
        return 0.0
    min_x, max_x, min_y, max_y = rect
    corners = (
        Point2D(min_x, min_y),
        Point2D(max_x, min_y),
        Point2D(max_x, max_y),
        Point2D(min_x, max_y),
    )
    edges = (
        (corners[0], corners[1]),
        (corners[1], corners[2]),
        (corners[2], corners[3]),
        (corners[3], corners[0]),
    )
    distances = [_point_to_segment_distance(start, edge_start, edge_end) for edge_start, edge_end in edges]
    distances.extend(_point_to_segment_distance(end, edge_start, edge_end) for edge_start, edge_end in edges)
    distances.extend(_point_to_segment_distance(corner, start, end) for corner in corners)
    return min(distances)


def _point_to_polyline_distance(point: Point2D, points: tuple[Point2D, ...]) -> float:
    return min(_point_to_segment_distance(point, start, end) for start, end in _segments(points))


def _point_to_segment_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    dx = end.x_m - start.x_m
    dy = end.y_m - start.y_m
    if dx == 0 and dy == 0:
        return _distance(point, start)
    t = ((point.x_m - start.x_m) * dx + (point.y_m - start.y_m) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    projection = Point2D(start.x_m + t * dx, start.y_m + t * dy)
    return _distance(point, projection)


def _distance(a: Point2D, b: Point2D) -> float:
    return math.hypot(a.x_m - b.x_m, a.y_m - b.y_m)
