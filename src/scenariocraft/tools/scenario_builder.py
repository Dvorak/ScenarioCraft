from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET

from scenariocraft.schemas import ActorSpec, ScenarioSpec


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
        entities = xosc.Entities()
        for actor in spec.actors:
            entities.add_scenario_object(actor.id, _xosc_entity(actor, xosc))

        init = xosc.Init()
        for actor in spec.actors:
            x, y, h = _initial_pose(actor.id)
            init.add_init_action(actor.id, xosc.TeleportAction(xosc.WorldPosition(x, y, 0, h)))
            if actor.initial_speed_kph is not None:
                init.add_init_action(actor.id, _xosc_speed_action(actor.initial_speed_kph / 3.6, xosc))

        pedestrian = spec.actor_by_role("crossing_actor")
        trigger = xosc.EntityTrigger(
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
        event = xosc.Event("pedestrian_starts_crossing", xosc.Priority.override)
        event.add_action(
            "pedestrian_speed_action",
            _xosc_speed_action(pedestrian.speed_mps if pedestrian and pedestrian.speed_mps else 1.5, xosc),
        )
        event.add_trigger(trigger)
        maneuver = xosc.Maneuver("crossing_maneuver")
        maneuver.add_event(event)
        maneuver_group = xosc.ManeuverGroup("pedestrian_crossing", maxexecution=1, selecttriggeringentities=False)
        if pedestrian is not None:
            maneuver_group.add_actor(pedestrian.id)
        maneuver_group.add_maneuver(maneuver)
        act = xosc.Act("pedestrian_occlusion_act")
        act.add_maneuver_group(maneuver_group)
        story = xosc.Story(spec.scenario_name)
        story.add_act(act)
        storyboard = xosc.StoryBoard(init)
        storyboard.add_story(story)

        scenario = xosc.Scenario(
            spec.scenario_name,
            "scenarioCraft",
            xosc.ParameterDeclarations(),
            entities,
            storyboard,
            xosc.RoadNetwork(),
            xosc.Catalog(),
            osc_minor_version=3,
        )
        scenario.write_xml(str(xosc_path))
        return BuildResult(xosc_path=xosc_path, builder="scenariogeneration")


class FallbackXmlScenarioBuilder(ScenarioBuilder):
    """Small deterministic XML fallback kept for inspectability and testability."""

    def build(self, spec: ScenarioSpec, output_dir: Path) -> BuildResult:
        output_dir.mkdir(parents=True, exist_ok=True)
        xosc_path = output_dir / "scenario.xosc"
        root = _build_xml_tree(spec)
        rough = ET.tostring(root, encoding="utf-8")
        pretty = minidom.parseString(rough).toprettyxml(indent="  ")
        xosc_path.write_text(pretty, encoding="utf-8")
        return BuildResult(xosc_path=xosc_path, builder="fallback_xml")


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


def _initial_pose(actor_id: str) -> tuple[float, float, float]:
    positions = {
        "ego": (0.0, 0.0, 0.0),
        "parked_van": (32.0, -3.5, 0.0),
        "pedestrian": (34.0, -5.5, 0.0),
    }
    return positions.get(actor_id, (0.0, 0.0, 0.0))


def _build_xml_tree(spec: ScenarioSpec) -> ET.Element:
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
    maneuver_group = ET.SubElement(act, "ManeuverGroup", {"maximumExecutionCount": "1", "name": "pedestrian_crossing"})
    ET.SubElement(maneuver_group, "Actors", {"selectTriggeringEntities": "false"})
    event = ET.SubElement(ET.SubElement(maneuver_group, "Maneuver", {"name": "crossing_maneuver"}), "Event", {
        "name": "pedestrian_starts_crossing",
        "priority": "override",
    })
    action = ET.SubElement(event, "Action", {"name": "pedestrian_speed_action"})
    private_action = ET.SubElement(action, "PrivateAction")
    longitudinal = ET.SubElement(private_action, "LongitudinalAction")
    speed_action = ET.SubElement(longitudinal, "SpeedAction")
    ET.SubElement(speed_action, "SpeedActionDynamics", {"dynamicsShape": "step", "value": "0", "dynamicsDimension": "time"})
    target = ET.SubElement(speed_action, "SpeedActionTarget")
    pedestrian = spec.actor_by_role("crossing_actor")
    ET.SubElement(target, "AbsoluteTargetSpeed", {"value": str(pedestrian.speed_mps if pedestrian else 1.5)})
    _append_trigger(event, spec)
    ET.SubElement(act, "StopTrigger")
    ET.SubElement(storyboard, "StopTrigger")
    return root


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
    for actor in spec.actors:
        private = ET.SubElement(parent, "Private", {"entityRef": actor.id})
        teleport = ET.SubElement(ET.SubElement(private, "PrivateAction"), "TeleportAction")
        position = ET.SubElement(teleport, "Position")
        x, y, h = _initial_pose(actor.id)
        ET.SubElement(position, "WorldPosition", {"x": str(x), "y": str(y), "z": "0", "h": str(h)})
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


def _append_trigger(parent: ET.Element, spec: ScenarioSpec) -> None:
    start_trigger = ET.SubElement(parent, "StartTrigger")
    condition_group = ET.SubElement(start_trigger, "ConditionGroup")
    condition = ET.SubElement(condition_group, "Condition", {
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
