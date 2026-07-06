"""Layout-backed actor pose and trajectory compilation helpers."""

from scenariocraft.core.build.layout_adapter import (
    BuilderInitialPose,
    BuilderTrajectory,
    layout_path_to_builder_trajectory,
    layout_pose_to_builder_initial_pose,
)
from scenariocraft.core.schemas import ActorSpec, ScenarioSpec


def ego_driving_trajectory(spec: ScenarioSpec, ego: ActorSpec | None) -> BuilderTrajectory | None:
    if ego is None or spec.layout is None:
        return None
    path = spec.layout.paths.get("ego_path")
    if path is None or ego.initial_speed_kph is None:
        return None
    return layout_path_to_builder_trajectory(
        path,
        traversal_speed_mps=ego.initial_speed_kph / 3.6,
        coordinate_frame=spec.layout.coordinate_frame,
        road_context=spec.road,
    )


def actor_trajectory(spec: ScenarioSpec, actor: ActorSpec | None, path_id: str | None) -> BuilderTrajectory | None:
    if actor is None or spec.layout is None or path_id is None:
        return None
    path = spec.layout.paths.get(path_id)
    if path is None:
        return None
    speed_mps = (
        actor.initial_speed_kph / 3.6
        if actor.initial_speed_kph is not None
        else pedestrian_traversal_speed_mps(actor)
    )
    return layout_path_to_builder_trajectory(
        path,
        traversal_speed_mps=speed_mps,
        coordinate_frame=spec.layout.coordinate_frame,
        road_context=spec.road,
    )


def pedestrian_traversal_speed_mps(pedestrian: ActorSpec | None) -> float:
    return pedestrian.speed_mps if pedestrian and pedestrian.speed_mps else 1.5


def lead_deceleration_mps2(spec: ScenarioSpec) -> float:
    template_metadata = spec.metadata.get("lead_vehicle_braking", {})
    if isinstance(template_metadata, dict) and template_metadata.get("lead_deceleration_mps2") is not None:
        return float(template_metadata["lead_deceleration_mps2"])
    return -4.0


def layout_initial_poses(spec: ScenarioSpec) -> dict[str, BuilderInitialPose] | None:
    if spec.layout is None:
        return None
    if any(actor.id not in spec.layout.actor_poses for actor in spec.actors):
        return None
    return {
        actor.id: layout_pose_to_builder_initial_pose(
            spec.layout.actor_poses[actor.id],
            coordinate_frame=spec.layout.coordinate_frame,
            road_context=spec.road,
        )
        for actor in spec.actors
    }


def initial_pose(actor_id: str, layout_initial_poses: dict[str, BuilderInitialPose] | None = None) -> BuilderInitialPose:
    if layout_initial_poses is not None:
        return layout_initial_poses[actor_id]
    positions = {
        "ego": (0.0, 0.0, 0.0),
        "parked_van": (32.0, -3.5, 0.0),
        "pedestrian": (34.0, -5.5, 0.0),
    }
    x, y, h = positions.get(actor_id, (0.0, 0.0, 0.0))
    return BuilderInitialPose(x=x, y=y, h=h)
