from __future__ import annotations

"""Deterministic intersection crossing-vehicle scenario family."""

from dataclasses import dataclass, replace
from typing import Mapping

from scenariocraft.core.schemas import (
    ActorSpec,
    CriticalitySpec,
    FootprintSpec,
    LayoutSpec,
    PathSpec,
    Point2D,
    Pose2D,
    RoadBandSpec,
    RoadSpec,
    ScenarioIntent,
    ScenarioSpec,
    ScenarioTimingSpec,
    SpatialRelationSpec,
    StoryboardActionSpec,
    StoryboardActSpec,
    StoryboardEventSpec,
    StoryboardManeuverGroupSpec,
    StoryboardSpec,
    StoryboardStorySpec,
    TriggerConditionSpec,
    TriggerSpec,
    WeatherSpec,
)
from scenariocraft.core.templates.capability import ParameterDomain, TemplateCapability


@dataclass(frozen=True)
class CrossingVehicleParameters:
    ego_speed_kph: float = 50.0
    crossing_vehicle_speed_kph: float = 40.0
    conflict_point_x_m: float = 25.0
    crossing_start_y_m: float = -20.0
    crossing_end_y_m: float = 20.0
    trigger_distance_m: float = 18.0
    arrival_time_tolerance_s: float = 0.35
    vehicle_length_m: float = 4.6
    vehicle_width_m: float = 1.9
    total_duration_s: float = 8.0
    target_min_ttc_s: float = 2.0
    weather: str = "clear_dry"


class CrossingVehicleTemplate:
    template_id = "crossing_vehicle"
    description = "Side vehicle crosses ego path at an urban intersection."
    required_actors = ("ego", "crossing_vehicle")
    default_parameters: Mapping[str, object] = {
        "scenario_name": "crossing_vehicle",
        "source_text": "",
        "parameters": CrossingVehicleParameters(),
    }
    supported_operations = ()
    capability = TemplateCapability(
        template_id=template_id,
        interaction_family="crossing_vehicle",
        description=description,
        actor_roles=required_actors,
        road_contexts=("urban", "urban_intersection"),
        topologies=("urban_four_way_intersection",),
        aliases=(
            "vehicle crosses ego path at intersection",
            "side vehicle crossing",
            "cross traffic conflict",
            "intersection crossing vehicle",
        ),
        semantic_slots=(
            "road_context",
            "ego",
            "crossing_vehicle",
            "intersection",
            "conflict_point",
            "arrival_time_alignment",
            "criticality",
            "weather",
        ),
        supported_variants=(
            "urban four-way intersection crossing conflict",
            "variable speed, conflict point, trigger distance, and arrival-time tolerance",
            "rainy/wet or clear/dry weather",
        ),
        unsupported_boundary_examples=(
            "oncoming turn across ego path",
            "oncoming vehicle turns across ego path",
            "same-lane lead vehicle braking",
            "adjacent lane cut-in",
            "highway cut-in",
            "pedestrian crossing",
        ),
        parameter_domains=(
            ParameterDomain("ego_speed_kph", "float", 50.0, unit="km/h", min_value=30.0, max_value=60.0),
            ParameterDomain("crossing_vehicle_speed_kph", "float", 40.0, unit="km/h", min_value=25.0, max_value=55.0),
            ParameterDomain("conflict_point_x_m", "float", 25.0, unit="m", min_value=18.0, max_value=38.0),
            ParameterDomain("crossing_start_y_m", "float", -20.0, unit="m", min_value=-28.0, max_value=-14.0),
            ParameterDomain("crossing_end_y_m", "float", 20.0, unit="m", min_value=14.0, max_value=28.0),
            ParameterDomain("trigger_distance_m", "float", 18.0, unit="m", min_value=10.0, max_value=28.0),
            ParameterDomain("arrival_time_tolerance_s", "float", 0.35, unit="s", min_value=0.2, max_value=0.8),
            ParameterDomain("target_min_ttc_s", "float", 2.0, unit="s", min_value=1.2, max_value=3.0),
            ParameterDomain(
                "weather",
                "str",
                "clear_dry",
                allowed_values=("clear_dry", "rainy_wet"),
                sampleable=False,
            ),
        ),
    )

    def instantiate(self, **parameters: object) -> ScenarioSpec:
        scenario_name = str(parameters.get("scenario_name", self.default_parameters["scenario_name"]))
        source_text = str(parameters.get("source_text", self.default_parameters["source_text"]))
        intent = parameters.get("intent")
        template_parameters = _parameters_from_mapping(
            parameters,
            intent if isinstance(intent, ScenarioIntent) else None,
        )
        return ScenarioSpec(
            scenario_name=scenario_name,
            scenario_type=self.template_id,
            road=RoadSpec(type="urban_intersection", lanes_per_direction=1, speed_limit_kph=50),
            weather=_weather(template_parameters),
            actors=[
                ActorSpec(id="ego", type="car", role="ego", initial_speed_kph=template_parameters.ego_speed_kph),
                ActorSpec(
                    id="crossing_vehicle",
                    type="car",
                    role="crossing_vehicle",
                    initial_speed_kph=template_parameters.crossing_vehicle_speed_kph,
                    state="crossing",
                ),
            ],
            trigger=TriggerSpec(
                type="relative_distance",
                source="ego",
                target="crossing_vehicle",
                distance_m=template_parameters.trigger_distance_m,
                condition=TriggerConditionSpec(
                    id="crossing_vehicle_relative_distance",
                    metric="relative_distance",
                    source="ego",
                    target="crossing_vehicle",
                    rule="lessThan",
                    value=template_parameters.trigger_distance_m,
                    unit="m",
                    coordinate_system="entity",
                    relative_distance_type="longitudinal",
                    freespace=False,
                    target_kind="entity",
                ),
            ),
            intended_criticality=CriticalitySpec(
                type="crossing_vehicle",
                target_min_ttc_s=template_parameters.target_min_ttc_s,
            ),
            metadata={
                "generator": "template",
                "source_text": source_text,
                "road_asset_id": "urban_four_way_intersection",
                "crossing_vehicle": {
                    "conflict_point_x_m": template_parameters.conflict_point_x_m,
                    "arrival_time_tolerance_s": template_parameters.arrival_time_tolerance_s,
                    "trigger_distance_m": template_parameters.trigger_distance_m,
                },
            },
            layout=_layout(template_parameters),
            spatial_relations=_spatial_relations(),
            storyboard=_storyboard(),
            timing=ScenarioTimingSpec(total_duration_s=template_parameters.total_duration_s),
        )


def _parameters_from_mapping(
    values: Mapping[str, object],
    intent: ScenarioIntent | None,
) -> CrossingVehicleParameters:
    template_parameters = values.get("parameters", CrossingVehicleParameters())
    if isinstance(template_parameters, CrossingVehicleParameters):
        base = template_parameters
    elif isinstance(template_parameters, Mapping):
        base = CrossingVehicleParameters(**template_parameters)
    else:
        raise TypeError("parameters must be a CrossingVehicleParameters or mapping.")

    intent_overrides: dict[str, object] = {}
    if intent is not None:
        ego = intent.actor("ego")
        crossing = intent.actor("crossing_vehicle")
        if "speed_kph" in ego:
            intent_overrides["ego_speed_kph"] = ego["speed_kph"]
        if "speed_kph" in crossing:
            intent_overrides["crossing_vehicle_speed_kph"] = crossing["speed_kph"]
        if "target_ttc_s" in intent.criticality:
            intent_overrides["target_min_ttc_s"] = intent.criticality["target_ttc_s"]
        if "condition" in intent.weather:
            intent_overrides["weather"] = intent.weather["condition"]
    direct_overrides = {
        field_name: values[field_name]
        for field_name in CrossingVehicleParameters.__dataclass_fields__
        if field_name in values
    }
    parameters = replace(base, **{**intent_overrides, **direct_overrides})
    _validate_parameters(parameters)
    return parameters


def _validate_parameters(parameters: CrossingVehicleParameters) -> None:
    if parameters.crossing_start_y_m >= 0.0:
        raise ValueError("crossing_start_y_m must be below the ego path.")
    if parameters.crossing_end_y_m <= 0.0:
        raise ValueError("crossing_end_y_m must be above the ego path.")
    if parameters.trigger_distance_m >= parameters.conflict_point_x_m:
        raise ValueError("trigger_distance_m must be less than conflict_point_x_m.")


def _weather(parameters: CrossingVehicleParameters) -> WeatherSpec:
    if parameters.weather == "rainy_wet":
        return WeatherSpec(rain=True, road_condition="wet")
    return WeatherSpec(rain=False, road_condition="dry")


def _layout(parameters: CrossingVehicleParameters) -> LayoutSpec:
    conflict = Point2D(parameters.conflict_point_x_m, 0.0)
    return LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={
            "ego": Pose2D(0.0, 0.0, 0.0),
            "crossing_vehicle": Pose2D(parameters.conflict_point_x_m, parameters.crossing_start_y_m, 1.57079632679),
        },
        actor_footprints={
            "ego": FootprintSpec(length_m=parameters.vehicle_length_m, width_m=parameters.vehicle_width_m),
            "crossing_vehicle": FootprintSpec(
                length_m=parameters.vehicle_length_m,
                width_m=parameters.vehicle_width_m,
            ),
        },
        paths={
            "ego_path": PathSpec("ego_path", (Point2D(0.0, 0.0), Point2D(parameters.conflict_point_x_m + 35.0, 0.0))),
            "crossing_vehicle_path": PathSpec(
                "crossing_vehicle_path",
                (
                    Point2D(parameters.conflict_point_x_m, parameters.crossing_start_y_m),
                    conflict,
                    Point2D(parameters.conflict_point_x_m, parameters.crossing_end_y_m),
                ),
            ),
        },
        points={
            "trigger_point": Point2D(parameters.conflict_point_x_m - parameters.trigger_distance_m, 0.0),
            "conflict_point": conflict,
        },
        road_bands=(
            RoadBandSpec("ego_driving_lane", "driving_lane", -1.75, 1.75, travel_direction="+x"),
            RoadBandSpec("opposing_driving_lane", "driving_lane", 1.75, 5.25, travel_direction="-x"),
        ),
    )


def _storyboard() -> StoryboardSpec:
    return StoryboardSpec(
        stories=(StoryboardStorySpec("crossing_vehicle_story", ("crossing_vehicle_act",)),),
        acts=(StoryboardActSpec("crossing_vehicle_act", ("ego_driving", "crossing_vehicle_movement")),),
        maneuver_groups=(
            StoryboardManeuverGroupSpec("ego_driving", ("ego",), ("ego_drives_forward",)),
            StoryboardManeuverGroupSpec(
                "crossing_vehicle_movement",
                ("crossing_vehicle",),
                ("crossing_vehicle_enters_intersection",),
            ),
        ),
        events=(
            StoryboardEventSpec("ego_drives_forward", "override", "ego_starts_driving", ("ego_follow_ego_path",)),
            StoryboardEventSpec(
                "crossing_vehicle_enters_intersection",
                "override",
                "crossing_vehicle_relative_distance",
                ("crossing_vehicle_follow_crossing_path",),
            ),
        ),
        actions=(
            StoryboardActionSpec("ego_follow_ego_path", "follow_trajectory", actor_refs=("ego",), path_ref="ego_path"),
            StoryboardActionSpec(
                "crossing_vehicle_follow_crossing_path",
                "follow_trajectory",
                actor_refs=("crossing_vehicle",),
                path_ref="crossing_vehicle_path",
            ),
        ),
    )


def _spatial_relations() -> tuple[SpatialRelationSpec, ...]:
    return (
        SpatialRelationSpec("crosses_path_of", "crossing_vehicle", "ego"),
        SpatialRelationSpec("conflicts_at", "crossing_vehicle", "conflict_point"),
    )
