from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from scenariocraft.roads import URBAN_TWO_WAY_PARKING_FILENAME, write_urban_two_way_parking_xodr
from scenariocraft.schemas import ActorSpec, ScenarioSpec
from scenariocraft.tools.layout_adapter import (
    BuilderInitialPose,
    BuilderTrajectory,
    layout_path_to_builder_trajectory,
    layout_pose_to_builder_initial_pose,
)


@dataclass(frozen=True)
class BuildResult:
    xosc_path: Path
    xodr_path: Path | None = None
    builder: str = "unknown"
    fallback_reason: str | None = None

    def artifact_paths(self) -> list[Path]:
        return [path for path in [self.xosc_path, self.xodr_path] if path is not None]


class ScenarioBuilder(ABC):
    @abstractmethod
    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        """Build scenario artifacts from a structured ScenarioSpec."""


class ScenariogenerationBuilder(ScenarioBuilder):
    """Default builder backed by pyoscx/scenariogeneration."""

    def __init__(self, fallback_builder: ScenarioBuilder | None = None) -> None:
        self._fallback_builder = fallback_builder or FallbackXmlScenarioBuilder()

    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        try:
            return self._build_with_scenariogeneration(spec, output_dir)
        except Exception as exc:
            fallback = self._fallback_builder.build(spec, output_dir)
            return BuildResult(
                xosc_path=fallback.xosc_path,
                xodr_path=fallback.xodr_path,
                builder=fallback.builder,
                fallback_reason=f"scenariogeneration failed: {exc}",
            )

    def _build_with_scenariogeneration(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        from scenariogeneration import xosc

        output_dir.mkdir(parents=True, exist_ok=True)
        xosc_path = output_dir / "scenario.xosc"
        xodr_path = _materialize_canonical_road_if_needed(spec, output_dir)
        entities = xosc.Entities()
        for actor in spec.actors:
            entities.add_scenario_object(actor.id, _xosc_entity(actor, xosc))

        init = xosc.Init()
        layout_initial_poses = _layout_initial_poses(spec)
        for actor in spec.actors:
            pose = _initial_pose(actor.id, layout_initial_poses)
            init.add_init_action(actor.id, xosc.TeleportAction(xosc.WorldPosition(pose.x, pose.y, 0, pose.h)))
            if actor.initial_speed_kph is not None:
                init.add_init_action(actor.id, _xosc_speed_action(actor.initial_speed_kph / 3.6, xosc))

        pedestrian = spec.actor_by_role("crossing_actor")
        ego = spec.actor_by_role("ego")
        act = xosc.Act("pedestrian_occlusion_act")
        ego_trajectory = _ego_driving_trajectory(spec, ego)
        if ego_trajectory is not None:
            ego_event = xosc.Event("ego_drives_forward", xosc.Priority.override)
            ego_event.add_action("ego_follow_ego_path", _xosc_follow_trajectory_action(ego_trajectory, xosc))
            ego_event.add_trigger(_xosc_simulation_time_trigger("ego_starts_driving", 0.0, xosc))
            ego_maneuver = xosc.Maneuver("ego_drive_maneuver")
            ego_maneuver.add_event(ego_event)
            ego_group = xosc.ManeuverGroup("ego_driving", maxexecution=1, selecttriggeringentities=False)
            ego_group.add_actor(ego.id)
            ego_group.add_maneuver(ego_maneuver)
            act.add_maneuver_group(ego_group)
        event = xosc.Event("pedestrian_starts_crossing", xosc.Priority.override)
        trajectory = _pedestrian_crossing_trajectory(spec, pedestrian)
        if trajectory is not None:
            event.add_action("pedestrian_follow_crossing_path", _xosc_follow_trajectory_action(trajectory, xosc))
        else:
            event.add_action(
                "pedestrian_speed_action",
                _xosc_speed_action(_pedestrian_traversal_speed_mps(pedestrian), xosc),
            )
        event.add_trigger(_xosc_pedestrian_start_trigger(spec, xosc))
        maneuver = xosc.Maneuver("crossing_maneuver")
        maneuver.add_event(event)
        maneuver_group = xosc.ManeuverGroup("pedestrian_crossing", maxexecution=1, selecttriggeringentities=False)
        if pedestrian is not None:
            maneuver_group.add_actor(pedestrian.id)
        maneuver_group.add_maneuver(maneuver)
        act.add_maneuver_group(maneuver_group)
        story = xosc.Story(spec.scenario_name)
        story.add_act(act)
        stop_time_s = _scenario_stop_time_s(spec)
        stop_trigger = xosc.ValueTrigger(
            _stop_trigger_name(stop_time_s),
            0,
            xosc.ConditionEdge.rising,
            xosc.SimulationTimeCondition(stop_time_s, xosc.Rule.greaterThan),
            triggeringpoint="stop",
        )
        storyboard = xosc.StoryBoard(init, stop_trigger)
        storyboard.add_story(story)

        scenario = xosc.Scenario(
            spec.scenario_name,
            "scenarioCraft",
            xosc.ParameterDeclarations(),
            entities,
            storyboard,
            xosc.RoadNetwork(URBAN_TWO_WAY_PARKING_FILENAME) if xodr_path is not None else xosc.RoadNetwork(),
            xosc.Catalog(),
            osc_minor_version=3,
        )
        scenario.write_xml(str(xosc_path))
        return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="scenariogeneration")


class FallbackXmlScenarioBuilder(ScenarioBuilder):
    """Small deterministic XML fallback kept for inspectability and testability."""

    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        xosc_path = output_dir / "scenario.xosc"
        xodr_path = _materialize_canonical_road_if_needed(spec, output_dir)
        root = _build_xml_tree(spec, road_logic_file=URBAN_TWO_WAY_PARKING_FILENAME if xodr_path is not None else None)
        rough = ET.tostring(root, encoding="utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        xosc_path.write_text(pretty, encoding="utf-8")
        return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="fallback_xml")


def build_openscenario(spec: ScenarioSpec, output_dir: Path, builder: ScenarioBuilder | None = None) -> BuildResult:
    return (builder or ScenariogenerationBuilder()).build(spec, output_dir)


def _xosc_entity(actor: ActorSpec, xosc: object) -> object:
    if actor.type == "pedestrian":
        return xosc.Pedestrian(
            actor.id,
            80,
            xosc.PedestrianCategory.pedestrian,
            xosc.BoundingBox(0.6, 0.6, 1.8, 0, 0, 0.9),
            model="adult",
        )
    vehicle_category = xosc.VehicleCategory.van if actor.type == "van" else xosc.VehicleCategory.car
    return xosc.Vehicle(
        actor.id,
        vehicle_category,
        xosc.BoundingBox(2.0, 4.8 if actor.type == "van" else 4.5, 1.8, 0, 0, 0.9),
        xosc.Axle(0.5, 0.6, 1.8, 2.8, 0.3),
        xosc.Axle(0.5, 0.6, 1.8, 0.0, 0.3),
        69.4,
        10,
        10,
    )


def _xosc_speed_action(speed_mps: float, xosc: object) -> object:
    return xosc.AbsoluteSpeedAction(
        speed_mps,
        xosc.TransitionDynamics(xosc.DynamicsShapes.step, xosc.DynamicsDimension.time, 0),
    )


def _xosc_follow_trajectory_action(trajectory: BuilderTrajectory, xosc: object) -> object:
    xosc_trajectory = xosc.Trajectory(trajectory.name, False)
    positions = [
        xosc.WorldPosition(point.x, point.y, 0.0, point.h)
        for point in trajectory.points
    ]
    times = [point.time_s for point in trajectory.points]
    xosc_trajectory.add_shape(xosc.Polyline(times, positions))
    return xosc.FollowTrajectoryAction(
        xosc_trajectory,
        xosc.FollowingMode.position,
        xosc.ReferenceContext.relative,
        1.0,
        0.0,
    )


def _xosc_simulation_time_trigger(name: str, value_s: float, xosc: object) -> object:
    return xosc.ValueTrigger(
        name,
        0,
        xosc.ConditionEdge.rising,
        xosc.SimulationTimeCondition(value_s, xosc.Rule.greaterThan),
    )


def _xosc_pedestrian_start_trigger(spec: ScenarioSpec, xosc: object) -> object:
    trigger = xosc.Trigger("start")
    relative_group = xosc.ConditionGroup("start")
    relative_group.add_condition(
        xosc.EntityTrigger(
            spec.trigger.type,
            0,
            xosc.ConditionEdge.rising,
            xosc.RelativeDistanceCondition(
                spec.trigger.distance_m,
                xosc.Rule.lessThan,
                xosc.RelativeDistanceType.longitudinal,
                spec.trigger.target,
                freespace=False,
            ),
            spec.trigger.source,
            xosc.TriggeringEntitiesRule.any,
        )
    )
    trigger.add_conditiongroup(relative_group)
    trigger_time_s = _derived_trigger_time_s(spec)
    if trigger_time_s is not None:
        time_group = xosc.ConditionGroup("start")
        time_group.add_condition(_xosc_simulation_time_trigger("relative_distance_time_alignment", trigger_time_s, xosc))
        trigger.add_conditiongroup(time_group)
    return trigger


def _derived_trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    source_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    source_actor = spec.actor_by_id(spec.trigger.source)
    if source_pose is None or target_pose is None or source_actor is None or source_actor.initial_speed_kph is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    trigger_distance_along_x = target_pose.x_m - source_pose.x_m - spec.trigger.distance_m
    if trigger_distance_along_x < 0:
        return 0.0
    return trigger_distance_along_x / speed_mps


def _scenario_stop_time_s(spec: ScenarioSpec) -> float:
    return spec.timing.total_duration_s if spec.timing is not None else 8.0


def _stop_trigger_name(stop_time_s: float) -> str:
    return f"stop_after_{stop_time_s:g}s"


def _ego_driving_trajectory(spec: ScenarioSpec, ego: ActorSpec | None) -> BuilderTrajectory | None:
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


def _pedestrian_crossing_trajectory(spec: ScenarioSpec, pedestrian: ActorSpec | None) -> BuilderTrajectory | None:
    if pedestrian is None or spec.layout is None:
        return None
    path = spec.layout.paths.get("pedestrian_crossing_path")
    if path is None:
        return None
    return layout_path_to_builder_trajectory(
        path,
        traversal_speed_mps=_pedestrian_traversal_speed_mps(pedestrian),
        coordinate_frame=spec.layout.coordinate_frame,
        road_context=spec.road,
    )


def _pedestrian_traversal_speed_mps(pedestrian: ActorSpec | None) -> float:
    return pedestrian.speed_mps if pedestrian and pedestrian.speed_mps else 1.5


def _layout_initial_poses(spec: ScenarioSpec) -> dict[str, BuilderInitialPose] | None:
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


def _initial_pose(actor_id: str, layout_initial_poses: dict[str, BuilderInitialPose] | None = None) -> BuilderInitialPose:
    if layout_initial_poses is not None:
        return layout_initial_poses[actor_id]
    positions = {
        "ego": (0.0, 0.0, 0.0),
        "parked_van": (32.0, -3.5, 0.0),
        "pedestrian": (34.0, -5.5, 0.0),
    }
    x, y, h = positions.get(actor_id, (0.0, 0.0, 0.0))
    return BuilderInitialPose(x=x, y=y, h=h)


def _materialize_canonical_road_if_needed(spec: ScenarioSpec, output_dir: Path) -> Path | None:
    if not _uses_canonical_urban_two_way_parking_road(spec):
        return None
    return write_urban_two_way_parking_xodr(output_dir / URBAN_TWO_WAY_PARKING_FILENAME)


def _uses_canonical_urban_two_way_parking_road(spec: ScenarioSpec) -> bool:
    return (
        spec.scenario_type == "pedestrian_occlusion"
        and spec.layout is not None
        and spec.layout.coordinate_frame == "ego_local"
        and bool(spec.layout.road_bands)
        and spec.road.type == "urban_straight"
    )


def _build_xml_tree(spec: ScenarioSpec, road_logic_file: str | None = None) -> ET.Element:
    root = ET.Element("OpenSCENARIO")
    ET.SubElement(root, "FileHeader", {
        "description": spec.scenario_name,
        "author": "scenarioCraft",
        "revMajor": "1",
        "revMinor": "0",
        "date": "2026-06-15T00:00:00",
    })
    ET.SubElement(root, "CatalogLocations")
    road_network = ET.SubElement(root, "RoadNetwork")
    if road_logic_file is not None:
        ET.SubElement(road_network, "LogicFile", {"filepath": road_logic_file})
    else:
        ET.SubElement(road_network, "LogicFile", {"filepath": ""})
    entities = ET.SubElement(root, "Entities")
    for actor in spec.actors:
        _append_entity(entities, actor)
    storyboard = ET.SubElement(root, "Storyboard")
    init = ET.SubElement(storyboard, "Init")
    actions = ET.SubElement(init, "Actions")
    _append_initial_actions(actions, spec)
    story = ET.SubElement(storyboard, "Story", {"name": spec.scenario_name})
    act = ET.SubElement(story, "Act", {"name": "pedestrian_occlusion_act"})
    _append_ego_driving_maneuver_group(act, spec)
    maneuver_group = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": "pedestrian_crossing"})
    ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    event = ET.SubElement(ET.SubElement(maneuver_group, "Maneuver", {"name": "crossing_maneuver"}), "Event", {
        "name": "pedestrian_starts_crossing",
        "priority": "override",
    })
    pedestrian = spec.actor_by_role("crossing_actor")
    trajectory = _pedestrian_crossing_trajectory(spec, pedestrian)
    if trajectory is not None:
        _append_follow_trajectory_action(event, trajectory)
    else:
        _append_speed_action(event, _pedestrian_traversal_speed_mps(pedestrian))
    _append_trigger(event, spec)
    ET.SubElement(act, "StopTrigger")
    _append_stop_trigger(storyboard, spec)
    return root


def _append_ego_driving_maneuver_group(parent: ET.Element, spec: ScenarioSpec) -> None:
    ego = spec.actor_by_role("ego")
    trajectory = _ego_driving_trajectory(spec, ego)
    if ego is None or trajectory is None:
        return
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": "ego_driving"})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": ego.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": "ego_drive_maneuver"})
    event = ET.SubElement(maneuver, "Event", {
        "name": "ego_drives_forward",
        "priority": "override",
    })
    _append_follow_trajectory_action(event, trajectory, action_name="ego_follow_ego_path")
    _append_simulation_time_start_trigger(event, "ego_starts_driving", 0.0)


def _append_entity(parent: ET.Element, actor: ActorSpec) -> None:
    scenario_object = ET.SubElement(parent, "ScenarioObject", {"name": actor.id})
    if actor.type == "pedestrian":
        ET.SubElement(scenario_object, "Pedestrian", {
            "model": "adult",
            "mass": "80",
            "name": actor.id,
            "pedestrianCategory": "pedestrian",
        })
        return
    vehicle_category = "van" if actor.type == "van" else "car"
    vehicle = ET.SubElement(scenario_object, "Vehicle", {"name": actor.id, "vehicleCategory": vehicle_category})
    ET.SubElement(vehicle, "Performance", {"maxSpeed": "69.4", "maxAcceleration": "10", "maxDeceleration": "10"})
    ET.SubElement(vehicle, "BoundingBox")
    ET.SubElement(vehicle, "Properties")


def _append_initial_actions(parent: ET.Element, spec: ScenarioSpec) -> None:
    layout_initial_poses = _layout_initial_poses(spec)
    for actor in spec.actors:
        private = ET.SubElement(parent, "Private", {"entityRef": actor.id})
        teleport = ET.SubElement(ET.SubElement(private, "PrivateAction"), "TeleportAction")
        position = ET.SubElement(teleport, "Position")
        pose = _initial_pose(actor.id, layout_initial_poses)
        ET.SubElement(position, "WorldPosition", {"x": str(pose.x), "y": str(pose.y), "z": "0", "h": str(pose.h)})
        if actor.initial_speed_kph is not None:
            speed = actor.initial_speed_kph / 3.6
            speed_action = ET.SubElement(ET.SubElement(private, "PrivateAction"), "LongitudinalAction")
            speed_action = ET.SubElement(speed_action, "SpeedAction")
            ET.SubElement(speed_action, "SpeedActionDynamics", {
                "dynamicsShape": "step",
                "value": "0",
                "dynamicsDimension": "time",
            })
            target = ET.SubElement(speed_action, "SpeedActionTarget")
            ET.SubElement(target, "AbsoluteTargetSpeed", {"value": f"{speed:.3f}"})


def _append_speed_action(parent: ET.Element, speed_mps: float) -> None:
    action = ET.SubElement(parent, "Action", {"name": "pedestrian_speed_action"})
    private_action = ET.SubElement(action, "PrivateAction")
    longitudinal = ET.SubElement(private_action, "LongitudinalAction")
    speed_action = ET.SubElement(longitudinal, "SpeedAction")
    ET.SubElement(speed_action, "SpeedActionDynamics", {
        "dynamicsShape": "step",
        "value": "0",
        "dynamicsDimension": "time",
    })
    target = ET.SubElement(speed_action, "SpeedActionTarget")
    ET.SubElement(target, "AbsoluteTargetSpeed", {"value": str(speed_mps)})


def _append_follow_trajectory_action(
    parent: ET.Element,
    trajectory: BuilderTrajectory,
    action_name: str = "pedestrian_follow_crossing_path",
) -> None:
    action = ET.SubElement(parent, "Action", {"name": action_name})
    private_action = ET.SubElement(action, "PrivateAction")
    routing_action = ET.SubElement(private_action, "RoutingAction")
    follow_action = ET.SubElement(routing_action, "FollowTrajectoryAction")
    trajectory_ref = ET.SubElement(follow_action, "TrajectoryRef")
    trajectory_element = ET.SubElement(trajectory_ref, "Trajectory", {
        "name": trajectory.name,
        "closed": "false",
    })
    shape = ET.SubElement(trajectory_element, "Shape")
    polyline = ET.SubElement(shape, "Polyline")
    for point in trajectory.points:
        vertex = ET.SubElement(polyline, "Vertex", {"time": str(point.time_s)})
        position = ET.SubElement(vertex, "Position")
        ET.SubElement(position, "WorldPosition", {
            "x": str(point.x),
            "y": str(point.y),
            "z": "0.0",
            "h": str(point.h),
        })
    time_reference = ET.SubElement(follow_action, "TimeReference")
    ET.SubElement(time_reference, "Timing", {
        "domainAbsoluteRelative": "relative",
        "scale": "1.0",
        "offset": "0.0",
    })
    ET.SubElement(follow_action, "TrajectoryFollowingMode", {"followingMode": "position"})


def _append_trigger(parent: ET.Element, spec: ScenarioSpec) -> None:
    start_trigger = ET.SubElement(parent, "StartTrigger")
    relative_group = ET.SubElement(start_trigger, "ConditionGroup")
    condition = ET.SubElement(relative_group, "Condition", {
        "name": spec.trigger.type,
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_entity = ET.SubElement(condition, "ByEntityCondition")
    triggering = ET.SubElement(by_entity, "TriggeringEntities", {"triggeringEntitiesRule": "any"})
    ET.SubElement(triggering, "EntityRef", {"entityRef": spec.trigger.source})
    entity_condition = ET.SubElement(by_entity, "EntityCondition")
    relative = ET.SubElement(entity_condition, "RelativeDistanceCondition", {
        "entityRef": spec.trigger.target,
        "relativeDistanceType": "longitudinal",
        "value": str(spec.trigger.distance_m),
        "freespace": "false",
        "rule": "lessThan",
    })
    relative.text = ""
    trigger_time_s = _derived_trigger_time_s(spec)
    if trigger_time_s is not None:
        time_group = ET.SubElement(start_trigger, "ConditionGroup")
        time_condition = ET.SubElement(time_group, "Condition", {
            "name": "relative_distance_time_alignment",
            "delay": "0",
            "conditionEdge": "rising",
        })
        by_value = ET.SubElement(time_condition, "ByValueCondition")
        ET.SubElement(by_value, "SimulationTimeCondition", {
            "value": str(trigger_time_s),
            "rule": "greaterThan",
        })


def _append_simulation_time_start_trigger(parent: ET.Element, name: str, value_s: float) -> None:
    start_trigger = ET.SubElement(parent, "StartTrigger")
    condition_group = ET.SubElement(start_trigger, "ConditionGroup")
    condition = ET.SubElement(condition_group, "Condition", {
        "name": name,
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_value = ET.SubElement(condition, "ByValueCondition")
    ET.SubElement(by_value, "SimulationTimeCondition", {"value": str(value_s), "rule": "greaterThan"})


def _append_stop_trigger(parent: ET.Element, spec: ScenarioSpec) -> None:
    stop_time_s = _scenario_stop_time_s(spec)
    stop_trigger = ET.SubElement(parent, "StopTrigger")
    condition_group = ET.SubElement(stop_trigger, "ConditionGroup")
    condition = ET.SubElement(condition_group, "Condition", {
        "name": _stop_trigger_name(stop_time_s),
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_value = ET.SubElement(condition, "ByValueCondition")
    ET.SubElement(by_value, "SimulationTimeCondition", {"value": str(stop_time_s), "rule": "greaterThan"})
