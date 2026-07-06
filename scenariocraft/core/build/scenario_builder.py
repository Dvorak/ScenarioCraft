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

from scenariocraft.core.build.fallback_xml_writer import build_fallback_xml_tree
from scenariocraft.core.build.layout_adapter import BuilderTrajectory
from scenariocraft.core.build.road_binding import (
    materialize_canonical_road_if_needed as _materialize_canonical_road_if_needed,
)
from scenariocraft.core.build.storyboard_compiler import (
    ActorEventBuildPlan as _ActorEventBuildPlan,
    StoryboardBuildPlan as _StoryboardBuildPlan,
    actor_event_build_plan as _actor_event_build_plan,
    storyboard_build_plan as _storyboard_build_plan,
)
from scenariocraft.core.build.trajectory_compiler import (
    actor_trajectory as _actor_trajectory,
    initial_pose as _initial_pose,
    layout_initial_poses as _layout_initial_poses,
    lead_deceleration_mps2 as _lead_deceleration_mps2,
    pedestrian_traversal_speed_mps as _pedestrian_traversal_speed_mps,
)
from scenariocraft.core.build.trigger_compiler import (
    scenario_stop_time_s as _scenario_stop_time_s,
    stop_trigger_name as _stop_trigger_name,
    xosc_pedestrian_start_trigger as _xosc_pedestrian_start_trigger,
    xosc_simulation_time_trigger as _xosc_simulation_time_trigger,
    xosc_start_trigger as _xosc_start_trigger,
)
from scenariocraft.core.schemas import ActorSpec, ScenarioSpec


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
        road_logic_file = xodr_path.name if xodr_path is not None else None
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
        if spec.scenario_type == "lead_vehicle_braking":
            _add_xosc_lead_braking_group(act, spec, xosc)
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
                xosc.RoadNetwork(road_logic_file) if road_logic_file is not None else xosc.RoadNetwork(),
                xosc.Catalog(),
                osc_minor_version=3,
            )
            scenario.write_xml(str(xosc_path))
            return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="scenariogeneration")
        if spec.scenario_type == "cut_in":
            _add_xosc_cut_in_group(act, spec, xosc)
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
                xosc.RoadNetwork(road_logic_file) if road_logic_file is not None else xosc.RoadNetwork(),
                xosc.Catalog(),
                osc_minor_version=3,
            )
            scenario.write_xml(str(xosc_path))
            return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="scenariogeneration")
        if spec.scenario_type == "crossing_vehicle":
            _add_xosc_crossing_vehicle_group(act, spec, xosc)
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
                xosc.RoadNetwork(road_logic_file) if road_logic_file is not None else xosc.RoadNetwork(),
                xosc.Catalog(),
                osc_minor_version=3,
            )
            scenario.write_xml(str(xosc_path))
            return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="scenariogeneration")
        if spec.scenario_type == "oncoming_turn_across_path":
            _add_xosc_oncoming_turn_group(act, spec, xosc)
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
                xosc.RoadNetwork(road_logic_file) if road_logic_file is not None else xosc.RoadNetwork(),
                xosc.Catalog(),
                osc_minor_version=3,
            )
            scenario.write_xml(str(xosc_path))
            return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder="scenariogeneration")
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
            xosc.RoadNetwork(road_logic_file) if road_logic_file is not None else xosc.RoadNetwork(),
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
        road_logic_file = xodr_path.name if xodr_path is not None else None
        root = build_fallback_xml_tree(
            spec,
            road_logic_file=road_logic_file,
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


def _xosc_braking_speed_action(spec: ScenarioSpec, plan: _ActorEventBuildPlan, xosc: object) -> object:
    metadata = plan.action_metadata or {}
    target_speed_mps = float(metadata.get("target_speed_mps", 0.0))
    dynamics_shape = str(metadata.get("dynamics_shape", "linear"))
    dynamics_dimension = str(metadata.get("dynamics_dimension", "rate"))
    dynamics_value = float(metadata.get("dynamics_value", abs(_lead_deceleration_mps2(spec))))
    return xosc.AbsoluteSpeedAction(
        target_speed_mps,
        xosc.TransitionDynamics(
            getattr(xosc.DynamicsShapes, dynamics_shape, xosc.DynamicsShapes.linear),
            getattr(xosc.DynamicsDimension, dynamics_dimension, xosc.DynamicsDimension.rate),
            dynamics_value,
        ),
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


def _xosc_priority(priority: str, xosc: object) -> object:
    normalized = "override" if priority in {"overwrite", "override"} else priority
    return getattr(xosc.Priority, normalized, xosc.Priority.override)


def _normalized_priority(priority: str) -> str:
    return "override" if priority in {"overwrite", "override"} else priority


def _add_xosc_lead_braking_group(act: object, spec: ScenarioSpec, xosc: object) -> None:
    lead = spec.actor_by_id("lead_vehicle")
    if lead is None:
        return
    plan = _actor_event_build_plan(
        spec,
        "lead_vehicle",
        _ActorEventBuildPlan(
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
                "dynamics_value": abs(_lead_deceleration_mps2(spec)),
            },
        ),
    )
    event = xosc.Event(plan.event_name, _xosc_priority(plan.event_priority, xosc))
    event.add_action(plan.action_name, _xosc_braking_speed_action(spec, plan, xosc))
    event.add_trigger(_xosc_start_trigger(spec, xosc, trigger_name=plan.start_trigger_name))
    maneuver = xosc.Maneuver(plan.maneuver_name)
    maneuver.add_event(event)
    maneuver_group = xosc.ManeuverGroup(plan.group_name, maxexecution=1, selecttriggeringentities=False)
    maneuver_group.add_actor(lead.id)
    maneuver_group.add_maneuver(maneuver)
    act.add_maneuver_group(maneuver_group)


def _add_xosc_cut_in_group(act: object, spec: ScenarioSpec, xosc: object) -> None:
    actor = spec.actor_by_id("cut_in_vehicle")
    if actor is None:
        return
    plan = _actor_event_build_plan(
        spec,
        "cut_in_vehicle",
        _ActorEventBuildPlan(
            group_name="cut_in_vehicle_lane_change",
            maneuver_name="cut_in_vehicle_lane_change_maneuver",
            event_name="cut_in_vehicle_starts_lane_change",
            event_priority="override",
            action_name="cut_in_vehicle_follow_cut_in_path",
            start_trigger_name="cut_in_relative_distance",
            path_ref="cut_in_path",
            action_type="follow_trajectory",
        ),
    )
    trajectory = _actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    event = xosc.Event(plan.event_name, _xosc_priority(plan.event_priority, xosc))
    event.add_action(plan.action_name, _xosc_follow_trajectory_action(trajectory, xosc))
    event.add_trigger(_xosc_start_trigger(spec, xosc, trigger_name=plan.start_trigger_name))
    maneuver = xosc.Maneuver(plan.maneuver_name)
    maneuver.add_event(event)
    maneuver_group = xosc.ManeuverGroup(plan.group_name, maxexecution=1, selecttriggeringentities=False)
    maneuver_group.add_actor(actor.id)
    maneuver_group.add_maneuver(maneuver)
    act.add_maneuver_group(maneuver_group)


def _add_xosc_crossing_vehicle_group(act: object, spec: ScenarioSpec, xosc: object) -> None:
    actor = spec.actor_by_id("crossing_vehicle")
    if actor is None:
        return
    plan = _actor_event_build_plan(
        spec,
        "crossing_vehicle",
        _ActorEventBuildPlan(
            group_name="crossing_vehicle_movement",
            maneuver_name="crossing_vehicle_movement_maneuver",
            event_name="crossing_vehicle_enters_intersection",
            event_priority="override",
            action_name="crossing_vehicle_follow_crossing_path",
            start_trigger_name="crossing_vehicle_relative_distance",
            path_ref="crossing_vehicle_path",
            action_type="follow_trajectory",
        ),
    )
    trajectory = _actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    event = xosc.Event(plan.event_name, _xosc_priority(plan.event_priority, xosc))
    event.add_action(plan.action_name, _xosc_follow_trajectory_action(trajectory, xosc))
    event.add_trigger(_xosc_start_trigger(spec, xosc, trigger_name=plan.start_trigger_name))
    maneuver = xosc.Maneuver(plan.maneuver_name)
    maneuver.add_event(event)
    maneuver_group = xosc.ManeuverGroup(plan.group_name, maxexecution=1, selecttriggeringentities=False)
    maneuver_group.add_actor(actor.id)
    maneuver_group.add_maneuver(maneuver)
    act.add_maneuver_group(maneuver_group)


def _add_xosc_oncoming_turn_group(act: object, spec: ScenarioSpec, xosc: object) -> None:
    actor = spec.actor_by_id("oncoming_vehicle")
    if actor is None:
        return
    plan = _actor_event_build_plan(
        spec,
        "oncoming_vehicle",
        _ActorEventBuildPlan(
            group_name="oncoming_vehicle_turn",
            maneuver_name="oncoming_vehicle_turn_maneuver",
            event_name="oncoming_vehicle_starts_turning",
            event_priority="override",
            action_name="oncoming_vehicle_follow_turn_path",
            start_trigger_name="oncoming_turn_relative_distance",
            path_ref="oncoming_turn_path",
            action_type="follow_trajectory",
        ),
    )
    trajectory = _actor_trajectory(spec, actor, plan.path_ref)
    if trajectory is None:
        return
    event = xosc.Event(plan.event_name, _xosc_priority(plan.event_priority, xosc))
    event.add_action(plan.action_name, _xosc_follow_trajectory_action(trajectory, xosc))
    event.add_trigger(_xosc_start_trigger(spec, xosc, trigger_name=plan.start_trigger_name))
    maneuver = xosc.Maneuver(plan.maneuver_name)
    maneuver.add_event(event)
    maneuver_group = xosc.ManeuverGroup(plan.group_name, maxexecution=1, selecttriggeringentities=False)
    maneuver_group.add_actor(actor.id)
    maneuver_group.add_maneuver(maneuver)
    act.add_maneuver_group(maneuver_group)
