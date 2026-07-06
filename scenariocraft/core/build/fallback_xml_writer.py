"""Deterministic fallback OpenSCENARIO XML writer."""

from xml.etree import ElementTree as ET

from scenariocraft.core.build.layout_adapter import BuilderTrajectory
from scenariocraft.core.build.storyboard_compiler import (
    ActorEventBuildPlan,
    StoryboardBuildPlan,
    actor_event_build_plan,
    storyboard_build_plan,
)
from scenariocraft.core.build.trajectory_compiler import (
    actor_trajectory,
    initial_pose,
    layout_initial_poses,
    lead_deceleration_mps2,
    pedestrian_traversal_speed_mps,
)
from scenariocraft.core.build.trigger_compiler import (
    derived_trigger_time_s,
    scenario_stop_time_s,
    stop_trigger_name,
    uses_relative_distance_start_condition,
)
from scenariocraft.core.schemas import ActorSpec, ScenarioSpec


def build_fallback_xml_tree(
    spec: ScenarioSpec,
    road_logic_file: str | None = None,
    *,
    include_timing_alignment_trigger: bool = True,
) -> ET.Element:
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
    plan = storyboard_build_plan(spec)
    storyboard = ET.SubElement(root, "Storyboard")
    init = ET.SubElement(storyboard, "Init")
    actions = ET.SubElement(init, "Actions")
    _append_initial_actions(actions, spec)
    story = ET.SubElement(storyboard, "Story", {"name": plan.story_name})
    act = ET.SubElement(story, "Act", {"name": plan.act_name})
    _append_ego_driving_maneuver_group(act, spec, plan)
    if spec.scenario_type == "lead_vehicle_braking":
        _append_lead_vehicle_braking_maneuver_group(act, spec)
        ET.SubElement(act, "StopTrigger")
        _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
        return root
    if spec.scenario_type == "cut_in":
        _append_cut_in_maneuver_group(act, spec)
        ET.SubElement(act, "StopTrigger")
        _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
        return root
    if spec.scenario_type == "crossing_vehicle":
        _append_crossing_vehicle_maneuver_group(act, spec)
        ET.SubElement(act, "StopTrigger")
        _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
        return root
    if spec.scenario_type == "oncoming_turn_across_path":
        _append_oncoming_turn_maneuver_group(act, spec)
        ET.SubElement(act, "StopTrigger")
        _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
        return root
    maneuver_group = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.pedestrian_group_name})
    ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    event = ET.SubElement(ET.SubElement(maneuver_group, "Maneuver", {"name": plan.pedestrian_maneuver_name}), "Event", {
        "name": plan.pedestrian_event_name,
        "priority": _normalized_priority(plan.pedestrian_event_priority),
    })
    pedestrian = spec.actor_by_role("crossing_actor")
    trajectory = actor_trajectory(spec, pedestrian, plan.pedestrian_path_ref)
    if trajectory is not None:
        _append_follow_trajectory_action(event, trajectory, action_name=plan.pedestrian_action_name)
    else:
        _append_speed_action(event, pedestrian_traversal_speed_mps(pedestrian))
    _append_trigger(
        event,
        spec,
        trigger_name=plan.pedestrian_start_trigger_name,
        include_timing_alignment_trigger=include_timing_alignment_trigger,
    )
    ET.SubElement(act, "StopTrigger")
    _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
    return root


def _normalized_priority(priority: str) -> str:
    return "override" if priority in {"overwrite", "override"} else priority


def _append_ego_driving_maneuver_group(
    parent: ET.Element,
    spec: ScenarioSpec,
    plan: StoryboardBuildPlan,
) -> None:
    ego = spec.actor_by_role("ego")
    trajectory = actor_trajectory(spec, ego, plan.ego_path_ref)
    if ego is None or trajectory is None:
        return
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.ego_group_name})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": ego.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": plan.ego_maneuver_name})
    event = ET.SubElement(maneuver, "Event", {
        "name": plan.ego_event_name,
        "priority": _normalized_priority(plan.ego_event_priority),
    })
    _append_follow_trajectory_action(event, trajectory, action_name=plan.ego_action_name)
    _append_simulation_time_start_trigger(event, plan.ego_start_trigger_name, 0.0)


def _append_lead_vehicle_braking_maneuver_group(parent: ET.Element, spec: ScenarioSpec) -> None:
    lead = spec.actor_by_id("lead_vehicle")
    if lead is None:
        return
    plan = actor_event_build_plan(
        spec,
        "lead_vehicle",
        ActorEventBuildPlan(
            group_name="lead_vehicle_braking",
            maneuver_name="lead_vehicle_braking_maneuver",
            event_name="lead_vehicle_starts_braking",
            event_priority="override",
            action_name="lead_vehicle_brakes",
            start_trigger_name="lead_vehicle_brake_relative_distance",
            action_type="absolute_speed",
            action_metadata={
                "target_speed_mps": 0.0,
                "dynamics_shape": "linear",
                "dynamics_dimension": "rate",
                "dynamics_value": abs(lead_deceleration_mps2(spec)),
            },
        ),
    )
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.group_name})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": lead.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": plan.maneuver_name})
    event = ET.SubElement(maneuver, "Event", {
        "name": plan.event_name,
        "priority": _normalized_priority(plan.event_priority),
    })
    _append_braking_speed_action(event, spec, plan)
    _append_trigger(event, spec, trigger_name=plan.start_trigger_name)


def _append_cut_in_maneuver_group(parent: ET.Element, spec: ScenarioSpec) -> None:
    actor = spec.actor_by_id("cut_in_vehicle")
    if actor is None:
        return
    plan = actor_event_build_plan(
        spec,
        "cut_in_vehicle",
        ActorEventBuildPlan(
            group_name="cut_in_vehicle_lane_change",
            maneuver_name="cut_in_vehicle_lane_change_maneuver",
            event_name="cut_in_vehicle_starts_lane_change",
            event_priority="override",
            action_name="cut_in_vehicle_follow_cut_in_path",
            start_trigger_name="cut_in_relative_distance",
            path_ref="cut_in_path",
        ),
    )
    trajectory = actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.group_name})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": actor.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": plan.maneuver_name})
    event = ET.SubElement(maneuver, "Event", {
        "name": plan.event_name,
        "priority": _normalized_priority(plan.event_priority),
    })
    _append_follow_trajectory_action(event, trajectory, action_name=plan.action_name)
    _append_trigger(event, spec, trigger_name=plan.start_trigger_name)


def _append_crossing_vehicle_maneuver_group(parent: ET.Element, spec: ScenarioSpec) -> None:
    actor = spec.actor_by_id("crossing_vehicle")
    if actor is None:
        return
    plan = actor_event_build_plan(
        spec,
        "crossing_vehicle",
        ActorEventBuildPlan(
            group_name="crossing_vehicle_movement",
            maneuver_name="crossing_vehicle_movement_maneuver",
            event_name="crossing_vehicle_enters_intersection",
            event_priority="override",
            action_name="crossing_vehicle_follow_crossing_path",
            start_trigger_name="crossing_vehicle_relative_distance",
            path_ref="crossing_vehicle_path",
        ),
    )
    trajectory = actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.group_name})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": actor.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": plan.maneuver_name})
    event = ET.SubElement(maneuver, "Event", {
        "name": plan.event_name,
        "priority": _normalized_priority(plan.event_priority),
    })
    _append_follow_trajectory_action(event, trajectory, action_name=plan.action_name)
    _append_trigger(event, spec, trigger_name=plan.start_trigger_name)


def _append_oncoming_turn_maneuver_group(parent: ET.Element, spec: ScenarioSpec) -> None:
    actor = spec.actor_by_id("oncoming_vehicle")
    if actor is None:
        return
    plan = actor_event_build_plan(
        spec,
        "oncoming_vehicle",
        ActorEventBuildPlan(
            group_name="oncoming_vehicle_turn",
            maneuver_name="oncoming_vehicle_turn_maneuver",
            event_name="oncoming_vehicle_starts_turning",
            event_priority="override",
            action_name="oncoming_vehicle_follow_turn_path",
            start_trigger_name="oncoming_turn_relative_distance",
            path_ref="oncoming_turn_path",
        ),
    )
    trajectory = actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    maneuver_group = ET.SubElement(parent, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.group_name})
    actors = ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    ET.SubElement(actors, "EntityRef", {"entityRef": actor.id})
    maneuver = ET.SubElement(maneuver_group, "Maneuver", {"name": plan.maneuver_name})
    event = ET.SubElement(maneuver, "Event", {
        "name": plan.event_name,
        "priority": _normalized_priority(plan.event_priority),
    })
    _append_follow_trajectory_action(event, trajectory, action_name=plan.action_name)
    _append_trigger(event, spec, trigger_name=plan.start_trigger_name)


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
    poses = layout_initial_poses(spec)
    for actor in spec.actors:
        private = ET.SubElement(parent, "Private", {"entityRef": actor.id})
        teleport = ET.SubElement(ET.SubElement(private, "PrivateAction"), "TeleportAction")
        position = ET.SubElement(teleport, "Position")
        pose = initial_pose(actor.id, poses)
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


def _append_braking_speed_action(parent: ET.Element, spec: ScenarioSpec, plan: ActorEventBuildPlan) -> None:
    metadata = plan.action_metadata or {}
    action = ET.SubElement(parent, "Action", {"name": plan.action_name})
    private_action = ET.SubElement(action, "PrivateAction")
    longitudinal = ET.SubElement(private_action, "LongitudinalAction")
    speed_action = ET.SubElement(longitudinal, "SpeedAction")
    dynamics_value = float(metadata.get("dynamics_value", abs(lead_deceleration_mps2(spec))))
    ET.SubElement(speed_action, "SpeedActionDynamics", {
        "dynamicsShape": str(metadata.get("dynamics_shape", "linear")),
        "value": str(dynamics_value),
        "dynamicsDimension": str(metadata.get("dynamics_dimension", "rate")),
    })
    target = ET.SubElement(speed_action, "SpeedActionTarget")
    ET.SubElement(target, "AbsoluteTargetSpeed", {"value": str(float(metadata.get("target_speed_mps", 0.0)))})


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


def _append_trigger(
    parent: ET.Element,
    spec: ScenarioSpec,
    *,
    trigger_name: str | None = None,
    include_timing_alignment_trigger: bool = True,
) -> None:
    start_trigger = ET.SubElement(parent, "StartTrigger")
    relative_group = ET.SubElement(start_trigger, "ConditionGroup")
    condition_name = (
        spec.trigger.condition.id
        if spec.trigger.condition is not None and spec.trigger.condition.metric == "time_to_collision"
        else trigger_name or spec.trigger.type
    )
    condition = ET.SubElement(relative_group, "Condition", {
        "name": condition_name,
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_entity = ET.SubElement(condition, "ByEntityCondition")
    triggering = ET.SubElement(by_entity, "TriggeringEntities", {"triggeringEntitiesRule": "any"})
    trigger_source = (
        spec.trigger.condition.source
        if spec.trigger.condition is not None and spec.trigger.condition.source is not None
        else spec.trigger.source
    )
    ET.SubElement(triggering, "EntityRef", {"entityRef": trigger_source})
    entity_condition = ET.SubElement(by_entity, "EntityCondition")
    if spec.trigger.condition is not None and spec.trigger.condition.metric == "time_to_collision":
        _append_time_to_collision_condition(entity_condition, spec)
    else:
        relative = ET.SubElement(entity_condition, "RelativeDistanceCondition", {
            "entityRef": spec.trigger.target,
            "relativeDistanceType": "longitudinal",
            "value": str(spec.trigger.distance_m),
            "freespace": "false",
            "rule": "lessThan",
        })
        relative.text = ""
    trigger_time_s = derived_trigger_time_s(spec)
    if uses_relative_distance_start_condition(spec) and include_timing_alignment_trigger and trigger_time_s is not None:
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


def _append_time_to_collision_condition(parent: ET.Element, spec: ScenarioSpec) -> None:
    condition = spec.trigger.condition
    if condition is None or condition.metric != "time_to_collision":
        raise ValueError("trigger.condition.metric must be time_to_collision.")
    ttc = ET.SubElement(parent, "TimeToCollisionCondition", {
        "value": str(condition.value),
        "relativeDistanceType": condition.relative_distance_type or "longitudinal",
        "coordinateSystem": condition.coordinate_system or "road",
        "freespace": str(condition.freespace if condition.freespace is not None else True).lower(),
        "rule": condition.rule,
    })
    target = ET.SubElement(ttc, "TimeToCollisionConditionTarget")
    if condition.target_kind == "named_point":
        point = spec.layout.points.get(condition.target) if spec.layout is not None and condition.target is not None else None
        if point is None:
            raise ValueError("time_to_collision named-point target requires a layout point.")
        position = ET.SubElement(target, "Position")
        ET.SubElement(position, "WorldPosition", {
            "x": str(point.x_m),
            "y": str(point.y_m),
            "z": "0.0",
            "h": "0.0",
        })
        return
    ET.SubElement(target, "EntityRef", {"entityRef": condition.target or spec.trigger.target})


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


def _append_stop_trigger(parent: ET.Element, spec: ScenarioSpec, trigger_name: str | None = None) -> None:
    stop_time_s = scenario_stop_time_s(spec)
    stop_trigger = ET.SubElement(parent, "StopTrigger")
    condition_group = ET.SubElement(stop_trigger, "ConditionGroup")
    condition = ET.SubElement(condition_group, "Condition", {
        "name": trigger_name or stop_trigger_name(stop_time_s),
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_value = ET.SubElement(condition, "ByValueCondition")
    ET.SubElement(by_value, "SimulationTimeCondition", {"value": str(stop_time_s), "rule": "greaterThan"})
