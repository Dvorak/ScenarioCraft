from __future__ import annotations

"""ScenarioSpec to OpenSCENARIO/OpenDRIVE artifact builders.

Builders serialize deterministic ScenarioSpec semantics. They do not choose
templates, call providers, or decide validation/repair success.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from scenariocraft.core.roads import URBAN_TWO_WAY_PARKING_FILENAME, write_urban_two_way_parking_xodr
from scenariocraft.core.schemas import ActorSpec, ScenarioSpec
from scenariocraft.core.build.layout_adapter import (
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


@dataclass(frozen=True)
class _StoryboardBuildPlan:
    story_name: str
    act_name: str
    stop_trigger_name: str | None
    ego_group_name: str
    ego_maneuver_name: str
    ego_event_name: str
    ego_event_priority: str
    ego_action_name: str
    ego_path_ref: str | None
    ego_start_trigger_name: str
    pedestrian_group_name: str
    pedestrian_maneuver_name: str
    pedestrian_event_name: str
    pedestrian_event_priority: str
    pedestrian_action_name: str
    pedestrian_path_ref: str | None
    pedestrian_start_trigger_name: str


class ScenarioBuilder(ABC):
    @abstractmethod
    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        """Build scenario artifacts from a structured ScenarioSpec."""


class ScenariogenerationBuilder(ScenarioBuilder):
    """Default builder backed by pyoscx/scenariogeneration."""

    def __init__(
        self,
        fallback_builder: ScenarioBuilder | None = None,
        *,
        include_timing_alignment_trigger: bool = True,
    ) -> None:
        self._include_timing_alignment_trigger = include_timing_alignment_trigger
        self._fallback_builder = fallback_builder or FallbackXmlScenarioBuilder(
            include_timing_alignment_trigger=include_timing_alignment_trigger
        )

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

        plan = _storyboard_build_plan(spec)
        pedestrian = spec.actor_by_role("crossing_actor")
        ego = spec.actor_by_role("ego")
        act = xosc.Act(plan.act_name)
        ego_trajectory = _actor_trajectory(spec, ego, plan.ego_path_ref)
        if ego_trajectory is not None:
            ego_event = xosc.Event(plan.ego_event_name, _xosc_priority(plan.ego_event_priority, xosc))
            ego_event.add_action(plan.ego_action_name, _xosc_follow_trajectory_action(ego_trajectory, xosc))
            ego_event.add_trigger(_xosc_simulation_time_trigger(plan.ego_start_trigger_name, 0.0, xosc))
            ego_maneuver = xosc.Maneuver(plan.ego_maneuver_name)
            ego_maneuver.add_event(ego_event)
            ego_group = xosc.ManeuverGroup(plan.ego_group_name, maxexecution=1, selecttriggeringentities=False)
            ego_group.add_actor(ego.id)
            ego_group.add_maneuver(ego_maneuver)
            act.add_maneuver_group(ego_group)
        event = xosc.Event(plan.pedestrian_event_name, _xosc_priority(plan.pedestrian_event_priority, xosc))
        trajectory = _actor_trajectory(spec, pedestrian, plan.pedestrian_path_ref)
        if trajectory is not None:
            event.add_action(plan.pedestrian_action_name, _xosc_follow_trajectory_action(trajectory, xosc))
        else:
            event.add_action(
                "pedestrian_speed_action",
                _xosc_speed_action(_pedestrian_traversal_speed_mps(pedestrian), xosc),
            )
        event.add_trigger(
            _xosc_pedestrian_start_trigger(
                spec,
                xosc,
                trigger_name=plan.pedestrian_start_trigger_name,
                include_timing_alignment_trigger=self._include_timing_alignment_trigger,
            )
        )
        maneuver = xosc.Maneuver(plan.pedestrian_maneuver_name)
        maneuver.add_event(event)
        maneuver_group = xosc.ManeuverGroup(plan.pedestrian_group_name, maxexecution=1, selecttriggeringentities=False)
        if pedestrian is not None:
            maneuver_group.add_actor(pedestrian.id)
        maneuver_group.add_maneuver(maneuver)
        act.add_maneuver_group(maneuver_group)
        story = xosc.Story(plan.story_name)
        story.add_act(act)
        stop_time_s = _scenario_stop_time_s(spec)
        stop_trigger = xosc.ValueTrigger(
            plan.stop_trigger_name or _stop_trigger_name(stop_time_s),
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

    def __init__(self, *, include_timing_alignment_trigger: bool = True) -> None:
        self._include_timing_alignment_trigger = include_timing_alignment_trigger

    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        xosc_path = output_dir / "scenario.xosc"
        xodr_path = _materialize_canonical_road_if_needed(spec, output_dir)
        root = _build_xml_tree(
            spec,
            road_logic_file=URBAN_TWO_WAY_PARKING_FILENAME if xodr_path is not None else None,
            include_timing_alignment_trigger=self._include_timing_alignment_trigger,
        )
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


def _xosc_rule(rule: str, xosc: object) -> object:
    return getattr(xosc.Rule, rule, xosc.Rule.lessThan)


def _xosc_priority(priority: str, xosc: object) -> object:
    normalized = "override" if priority in {"overwrite", "override"} else priority
    return getattr(xosc.Priority, normalized, xosc.Priority.override)


def _normalized_priority(priority: str) -> str:
    return "override" if priority in {"overwrite", "override"} else priority


def _xosc_pedestrian_start_trigger(
    spec: ScenarioSpec,
    xosc: object,
    *,
    trigger_name: str | None = None,
    include_timing_alignment_trigger: bool = True,
) -> object:
    trigger = xosc.Trigger("start")
    relative_group = xosc.ConditionGroup("start")
    relative_group.add_condition(
        _xosc_pedestrian_start_condition(spec, xosc, trigger_name=trigger_name)
    )
    trigger.add_conditiongroup(relative_group)
    trigger_time_s = _derived_trigger_time_s(spec)
    if _uses_relative_distance_start_condition(spec) and include_timing_alignment_trigger and trigger_time_s is not None:
        time_group = xosc.ConditionGroup("start")
        time_group.add_condition(_xosc_simulation_time_trigger("relative_distance_time_alignment", trigger_time_s, xosc))
        trigger.add_conditiongroup(time_group)
    return trigger


def _xosc_pedestrian_start_condition(spec: ScenarioSpec, xosc: object, *, trigger_name: str | None) -> object:
    condition = spec.trigger.condition
    if condition is not None and condition.metric == "time_to_collision":
        return xosc.EntityTrigger(
            condition.id,
            0,
            xosc.ConditionEdge.rising,
            _xosc_time_to_collision_condition(spec, xosc),
            condition.source or spec.trigger.source,
            xosc.TriggeringEntitiesRule.any,
        )
    return xosc.EntityTrigger(
        trigger_name or spec.trigger.type,
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


def _xosc_time_to_collision_condition(spec: ScenarioSpec, xosc: object) -> object:
    condition = spec.trigger.condition
    if condition is None or condition.metric != "time_to_collision":
        raise ValueError("trigger.condition.metric must be time_to_collision.")
    kwargs: dict[str, object] = {
        "alongroute": True,
        "freespace": condition.freespace if condition.freespace is not None else True,
        "distance_type": getattr(
            xosc.RelativeDistanceType,
            condition.relative_distance_type or "longitudinal",
            xosc.RelativeDistanceType.longitudinal,
        ),
        "coordinate_system": getattr(
            xosc.CoordinateSystem,
            condition.coordinate_system or "road",
            xosc.CoordinateSystem.road,
        ),
    }
    if condition.target_kind == "named_point":
        point = spec.layout.points.get(condition.target) if spec.layout is not None and condition.target is not None else None
        if point is None:
            raise ValueError("time_to_collision named-point target requires a layout point.")
        kwargs["position"] = xosc.WorldPosition(point.x_m, point.y_m, 0.0, 0.0)
    else:
        kwargs["entity"] = condition.target or spec.trigger.target
    return xosc.TimeToCollisionCondition(
        condition.value,
        _xosc_rule(condition.rule, xosc),
        **kwargs,
    )


def _uses_relative_distance_start_condition(spec: ScenarioSpec) -> bool:
    return spec.trigger.condition is None or spec.trigger.condition.metric == "relative_distance"


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


def _storyboard_build_plan(spec: ScenarioSpec) -> _StoryboardBuildPlan:
    default = _StoryboardBuildPlan(
        story_name=spec.scenario_name,
        act_name="pedestrian_occlusion_act",
        stop_trigger_name=None,
        ego_group_name="ego_driving",
        ego_maneuver_name="ego_drive_maneuver",
        ego_event_name="ego_drives_forward",
        ego_event_priority="override",
        ego_action_name="ego_follow_ego_path",
        ego_path_ref="ego_path",
        ego_start_trigger_name="ego_starts_driving",
        pedestrian_group_name="pedestrian_crossing",
        pedestrian_maneuver_name="crossing_maneuver",
        pedestrian_event_name="pedestrian_starts_crossing",
        pedestrian_event_priority="override",
        pedestrian_action_name="pedestrian_follow_crossing_path",
        pedestrian_path_ref="pedestrian_crossing_path",
        pedestrian_start_trigger_name=spec.trigger.type,
    )
    storyboard = spec.storyboard
    if storyboard is None:
        return default

    stories = {story.id: story for story in storyboard.stories}
    acts = {act.id: act for act in storyboard.acts}
    groups = {group.id: group for group in storyboard.maneuver_groups}
    events = {event.id: event for event in storyboard.events}
    actions = {action.id: action for action in storyboard.actions}

    story = next(iter(stories.values()), None)
    act = acts.get(story.act_refs[0]) if story is not None and story.act_refs else next(iter(acts.values()), None)
    ego_group = _storyboard_group_for_actor(groups.values(), "ego")
    pedestrian_group = _storyboard_group_for_actor(groups.values(), "pedestrian")
    ego_event = _storyboard_first_event(ego_group, events)
    pedestrian_event = _storyboard_first_event(pedestrian_group, events)
    ego_action = _storyboard_first_action(ego_event, actions)
    pedestrian_action = _storyboard_first_action(pedestrian_event, actions)

    return _StoryboardBuildPlan(
        story_name=story.id if story is not None else default.story_name,
        act_name=act.id if act is not None else default.act_name,
        stop_trigger_name=act.stop_trigger_ref if act is not None else default.stop_trigger_name,
        ego_group_name=ego_group.id if ego_group is not None else default.ego_group_name,
        ego_maneuver_name=f"{ego_group.id}_maneuver" if ego_group is not None else default.ego_maneuver_name,
        ego_event_name=ego_event.id if ego_event is not None else default.ego_event_name,
        ego_event_priority=ego_event.priority if ego_event is not None else default.ego_event_priority,
        ego_action_name=ego_action.id if ego_action is not None else default.ego_action_name,
        ego_path_ref=ego_action.path_ref if ego_action is not None else default.ego_path_ref,
        ego_start_trigger_name=ego_event.start_trigger_ref if ego_event is not None else default.ego_start_trigger_name,
        pedestrian_group_name=(
            pedestrian_group.id if pedestrian_group is not None else default.pedestrian_group_name
        ),
        pedestrian_maneuver_name=(
            f"{pedestrian_group.id}_maneuver"
            if pedestrian_group is not None
            else default.pedestrian_maneuver_name
        ),
        pedestrian_event_name=(
            pedestrian_event.id if pedestrian_event is not None else default.pedestrian_event_name
        ),
        pedestrian_event_priority=(
            pedestrian_event.priority if pedestrian_event is not None else default.pedestrian_event_priority
        ),
        pedestrian_action_name=(
            pedestrian_action.id if pedestrian_action is not None else default.pedestrian_action_name
        ),
        pedestrian_path_ref=(
            pedestrian_action.path_ref if pedestrian_action is not None else default.pedestrian_path_ref
        ),
        pedestrian_start_trigger_name=(
            pedestrian_event.start_trigger_ref
            if pedestrian_event is not None
            else default.pedestrian_start_trigger_name
        ),
    )


def _storyboard_group_for_actor(groups: object, actor_id: str) -> object | None:
    return next((group for group in groups if actor_id in group.actor_refs), None)


def _storyboard_first_event(group: object | None, events: dict[str, object]) -> object | None:
    if group is None:
        return None
    return events.get(group.event_refs[0]) if group.event_refs else None


def _storyboard_first_action(event: object | None, actions: dict[str, object]) -> object | None:
    if event is None:
        return None
    return actions.get(event.action_refs[0]) if event.action_refs else None


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


def _actor_trajectory(spec: ScenarioSpec, actor: ActorSpec | None, path_id: str | None) -> BuilderTrajectory | None:
    if actor is None or spec.layout is None or path_id is None:
        return None
    path = spec.layout.paths.get(path_id)
    if path is None:
        return None
    speed_mps = (
        actor.initial_speed_kph / 3.6
        if actor.initial_speed_kph is not None
        else _pedestrian_traversal_speed_mps(actor)
    )
    return layout_path_to_builder_trajectory(
        path,
        traversal_speed_mps=speed_mps,
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


def _build_xml_tree(
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
    plan = _storyboard_build_plan(spec)
    storyboard = ET.SubElement(root, "Storyboard")
    init = ET.SubElement(storyboard, "Init")
    actions = ET.SubElement(init, "Actions")
    _append_initial_actions(actions, spec)
    story = ET.SubElement(storyboard, "Story", {"name": plan.story_name})
    act = ET.SubElement(story, "Act", {"name": plan.act_name})
    _append_ego_driving_maneuver_group(act, spec, plan)
    maneuver_group = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": plan.pedestrian_group_name})
    ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    event = ET.SubElement(ET.SubElement(maneuver_group, "Maneuver", {"name": plan.pedestrian_maneuver_name}), "Event", {
        "name": plan.pedestrian_event_name,
        "priority": _normalized_priority(plan.pedestrian_event_priority),
    })
    pedestrian = spec.actor_by_role("crossing_actor")
    trajectory = _actor_trajectory(spec, pedestrian, plan.pedestrian_path_ref)
    if trajectory is not None:
        _append_follow_trajectory_action(event, trajectory, action_name=plan.pedestrian_action_name)
    else:
        _append_speed_action(event, _pedestrian_traversal_speed_mps(pedestrian))
    _append_trigger(
        event,
        spec,
        trigger_name=plan.pedestrian_start_trigger_name,
        include_timing_alignment_trigger=include_timing_alignment_trigger,
    )
    ET.SubElement(act, "StopTrigger")
    _append_stop_trigger(storyboard, spec, trigger_name=plan.stop_trigger_name)
    return root


def _append_ego_driving_maneuver_group(
    parent: ET.Element,
    spec: ScenarioSpec,
    plan: _StoryboardBuildPlan,
) -> None:
    ego = spec.actor_by_role("ego")
    trajectory = _actor_trajectory(spec, ego, plan.ego_path_ref)
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
    trigger_time_s = _derived_trigger_time_s(spec)
    if _uses_relative_distance_start_condition(spec) and include_timing_alignment_trigger and trigger_time_s is not None:
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
    stop_time_s = _scenario_stop_time_s(spec)
    stop_trigger = ET.SubElement(parent, "StopTrigger")
    condition_group = ET.SubElement(stop_trigger, "ConditionGroup")
    condition = ET.SubElement(condition_group, "Condition", {
        "name": trigger_name or _stop_trigger_name(stop_time_s),
        "delay": "0",
        "conditionEdge": "rising",
    })
    by_value = ET.SubElement(condition, "ByValueCondition")
    ET.SubElement(by_value, "SimulationTimeCondition", {"value": str(stop_time_s), "rule": "greaterThan"})
