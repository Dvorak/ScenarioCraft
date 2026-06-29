from __future__ import annotations

from dataclasses import dataclass
import math

from scenariocraft_core.schemas import PathSpec, Pose2D, RoadSpec


@dataclass(frozen=True)
class BuilderInitialPose:
    x: float
    y: float
    h: float


@dataclass(frozen=True)
class BuilderTrajectoryPoint:
    x: float
    y: float
    h: float
    time_s: float


@dataclass(frozen=True)
class BuilderTrajectory:
    name: str
    points: tuple[BuilderTrajectoryPoint, ...]


def layout_pose_to_builder_initial_pose(
    pose: Pose2D,
    *,
    coordinate_frame: str,
    road_context: RoadSpec,
) -> BuilderInitialPose:
    """Map ScenarioSpec layout poses into OpenSCENARIO builder initial poses.

    The current builder writes OpenSCENARIO WorldPosition values through both
    scenariogeneration and the deterministic XML fallback. It does not use
    OpenDRIVE s/t coordinates, lane-relative positions, or road-relative
    positions. For the existing straight urban mock road, the template's
    ego-local frame is therefore mapped directly into builder world x/y/h.
    """
    if coordinate_frame != "ego_local":
        raise ValueError(f"Unsupported layout coordinate frame: {coordinate_frame}")
    if road_context.type != "urban_straight":
        raise ValueError(f"Unsupported layout road context: {road_context.type}")
    return BuilderInitialPose(x=pose.x_m, y=pose.y_m, h=pose.heading_rad)


def layout_path_to_builder_trajectory(
    path: PathSpec,
    *,
    traversal_speed_mps: float,
    coordinate_frame: str,
    road_context: RoadSpec,
) -> BuilderTrajectory:
    """Map a layout polyline into a timed OpenSCENARIO world-position trajectory.

    The mapping matches layout_pose_to_builder_initial_pose: the current straight
    road builder uses WorldPosition, so ego-local x/y points become world x/y
    vertices. Vertex times are deterministic cumulative travel times derived
    from segment length and the pedestrian traversal speed.
    """
    if coordinate_frame != "ego_local":
        raise ValueError(f"Unsupported layout coordinate frame: {coordinate_frame}")
    if road_context.type != "urban_straight":
        raise ValueError(f"Unsupported layout road context: {road_context.type}")
    if traversal_speed_mps <= 0:
        raise ValueError("traversal_speed_mps must be greater than zero.")
    if len(path.points) < 2:
        raise ValueError("builder trajectory path must contain at least two points.")

    elapsed_s = 0.0
    trajectory_points: list[BuilderTrajectoryPoint] = []
    previous = path.points[0]
    trajectory_points.append(BuilderTrajectoryPoint(x=previous.x_m, y=previous.y_m, h=0.0, time_s=elapsed_s))
    for point in path.points[1:]:
        elapsed_s += math.hypot(point.x_m - previous.x_m, point.y_m - previous.y_m) / traversal_speed_mps
        trajectory_points.append(BuilderTrajectoryPoint(x=point.x_m, y=point.y_m, h=0.0, time_s=elapsed_s))
        previous = point
    return BuilderTrajectory(name=path.name, points=tuple(trajectory_points))
