from __future__ import annotations

"""Deterministic oncoming-turn-across-path scenario family."""

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
class OncomingTurnAcrossPathParameters:
    ego_speed_kph: float = 50.0
    oncoming_vehicle_speed_kph: float = 39.0
    conflict_point_x_m: float = 25.0
    oncoming_start_x_m: float = 45.0
    oncoming_start_y_m: float = 3.5
    turn_end_y_m: float = -20.0
    trigger_distance_m: float = 25.0
    arrival_time_tolerance_s: float = 0.45
    vehicle_length_m: float = 4.6
    vehicle_width_m: float = 1.9
    total_duration_s: float = 8.0
    target_min_ttc_s: float = 2.0
    weather: str = "clear_dry"


class OncomingTurnAcrossPathTemplate:
    template_id = "oncoming_turn_across_path"
    description = "Oncoming vehicle turns across the ego path at an urban intersection."
    required_actors = ("ego", "oncoming_vehicle")
    default_parameters: Mapping[str, object] = {
        "scenario_name": "oncoming_turn_across_path",
        "source_text": "",
        "parameters": OncomingTurnAcrossPathParameters(),
    }
    supported_operations = ()
    capability = TemplateCapability(
        template_id=template_id,
        interaction_family=template_id,
        description=description,
        actor_roles=required_actors,
        road_contexts=("urban", "urban_intersection"),
        topologies=("urban_four_way_intersection",),
        aliases=(
            "oncoming vehicle turns across ego path",
            "left turn across path",
            "oncoming turn conflict",
            "opposing vehicle turns in front of ego",
        ),
        semantic_slots=(
            "road_context",
            "ego",
            "oncoming_vehicle",
            "intersection",
            "turn_path",
            "conflict_point",
            "arrival_time_alignment",
            "criticality",
            "weather",
        ),
        supported_variants=(
            "urban four-way intersection oncoming-turn conflict",
            "variable speed, start point, conflict point, trigger distance, and arrival-time tolerance",
            "rainy/wet or clear/dry weather",
        ),
        unsupported_boundary_examples=(
            "perpendicular crossing vehicle",
            "same-lane lead braking",
            "adjacent lane cut-in",
            "pedestrian crossing",
        ),
        parameter_domains=(
            ParameterDomain("ego_speed_kph", "float", 50.0, unit="km/h", min_value=30.0, max_value=60.0),
            ParameterDomain("oncoming_vehicle_speed_kph", "float", 39.0, unit="km/h", min_value=25.0, max_value=55.0),
            ParameterDomain("conflict_point_x_m", "float", 25.0, unit="m", min_value=18.0, max_value=38.0),
            ParameterDomain("oncoming_start_x_m", "float", 45.0, unit="m", min_value=34.0, max_value=58.0),
            ParameterDomain("oncoming_start_y_m", "float", 3.5, unit="m", min_value=2.5, max_value=5.0),
            ParameterDomain("turn_end_y_m", "float", -20.0, unit="m", min_value=-28.0, max_value=-14.0),
            ParameterDomain("trigger_distance_m", "float", 25.0, unit="m", min_value=14.0, max_value=32.0),
            ParameterDomain("arrival_time_tolerance_s", "float", 0.45, unit="s", min_value=0.2, max_value=0.8),
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
                    id="oncoming_vehicle",
                    type="car",
                    role="oncoming_vehicle",
                    initial_speed_kph=template_parameters.oncoming_vehicle_speed_kph,
                    state="turning",
                ),
            ],
            trigger=TriggerSpec(
                type="relative_distance",
                source="ego",
                target="oncoming_vehicle",
                distance_m=template_parameters.trigger_distance_m,
                condition=TriggerConditionSpec(
                    id="oncoming_turn_relative_distance",
                    metric="relative_distance",
                    source="ego",
                    target="oncoming_vehicle",
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
                type="oncoming_turn_across_path",
                target_min_ttc_s=template_parameters.target_min_ttc_s,
            ),
            metadata={
                "generator": "template",
                "source_text": source_text,
                "road_asset_id": "urban_four_way_intersection",
                "oncoming_turn_across_path": {
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
) -> OncomingTurnAcrossPathParameters:
    template_parameters = values.get("parameters", OncomingTurnAcrossPathParameters())
    if isinstance(template_parameters, OncomingTurnAcrossPathParameters):
        base = template_parameters
    elif isinstance(template_parameters, Mapping):
        base = OncomingTurnAcrossPathParameters(**template_parameters)
    else:
        raise TypeError("parameters must be an OncomingTurnAcrossPathParameters or mapping.")
    intent_overrides: dict[str, object] = {}
    if intent is not None:
        ego = intent.actor("ego")
        oncoming = intent.actor("oncoming_vehicle")
        if "speed_kph" in ego:
            intent_overrides["ego_speed_kph"] = ego["speed_kph"]
        if "speed_kph" in oncoming:
            intent_overrides["oncoming_vehicle_speed_kph"] = oncoming["speed_kph"]
        if "target_ttc_s" in intent.criticality:
            intent_overrides["target_min_ttc_s"] = intent.criticality["target_ttc_s"]
        if "condition" in intent.weather:
            intent_overrides["weather"] = intent.weather["condition"]
    direct_overrides = {
        field_name: values[field_name]
        for field_name in OncomingTurnAcrossPathParameters.__dataclass_fields__
        if field_name in values
    }
    parameters = replace(base, **{**intent_overrides, **direct_overrides})
    _validate_parameters(parameters)
    return parameters


def _validate_parameters(parameters: OncomingTurnAcrossPathParameters) -> None:
    if parameters.oncoming_start_x_m <= parameters.conflict_point_x_m:
        raise ValueError("oncoming_start_x_m must be greater than conflict_point_x_m.")
    if parameters.oncoming_start_y_m <= 0.0:
        raise ValueError("oncoming_start_y_m must be above the ego path.")
    if parameters.turn_end_y_m >= 0.0:
        raise ValueError("turn_end_y_m must be below the ego path.")
    if parameters.trigger_distance_m >= parameters.oncoming_start_x_m:
        raise ValueError("trigger_distance_m must be less than oncoming_start_x_m.")


def _weather(parameters: OncomingTurnAcrossPathParameters) -> WeatherSpec:
    if parameters.weather == "rainy_wet":
        return WeatherSpec(rain=True, road_condition="wet")
    return WeatherSpec(rain=False, road_condition="dry")


def _layout(parameters: OncomingTurnAcrossPathParameters) -> LayoutSpec:
    conflict = Point2D(parameters.conflict_point_x_m, 0.0)
    return LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={
            "ego": Pose2D(0.0, 0.0, 0.0),
            "oncoming_vehicle": Pose2D(parameters.oncoming_start_x_m, parameters.oncoming_start_y_m, 3.14159265359),
        },
        actor_footprints={
            "ego": FootprintSpec(length_m=parameters.vehicle_length_m, width_m=parameters.vehicle_width_m),
            "oncoming_vehicle": FootprintSpec(
                length_m=parameters.vehicle_length_m,
                width_m=parameters.vehicle_width_m,
            ),
        },
        paths={
            "ego_path": PathSpec("ego_path", (Point2D(0.0, 0.0), Point2D(parameters.conflict_point_x_m + 35.0, 0.0))),
            "oncoming_turn_path": PathSpec(
                "oncoming_turn_path",
                (
                    Point2D(parameters.oncoming_start_x_m, parameters.oncoming_start_y_m),
                    conflict,
                    Point2D(parameters.conflict_point_x_m, parameters.turn_end_y_m),
                ),
            ),
        },
        points={
            "trigger_point": Point2D(parameters.oncoming_start_x_m - parameters.trigger_distance_m, 0.0),
            "conflict_point": conflict,
        },
        road_bands=(
            RoadBandSpec("ego_driving_lane", "driving_lane", -1.75, 1.75, travel_direction="+x"),
            RoadBandSpec("opposing_driving_lane", "driving_lane", 1.75, 5.25, travel_direction="-x"),
        ),
    )


def _storyboard() -> StoryboardSpec:
    return StoryboardSpec(
        stories=(StoryboardStorySpec("oncoming_turn_story", ("oncoming_turn_act",)),),
        acts=(StoryboardActSpec("oncoming_turn_act", ("ego_driving", "oncoming_vehicle_turn")),),
        maneuver_groups=(
            StoryboardManeuverGroupSpec("ego_driving", ("ego",), ("ego_drives_forward",)),
            StoryboardManeuverGroupSpec(
                "oncoming_vehicle_turn",
                ("oncoming_vehicle",),
                ("oncoming_vehicle_starts_turning",),
            ),
        ),
        events=(
            StoryboardEventSpec("ego_drives_forward", "override", "ego_starts_driving", ("ego_follow_ego_path",)),
            StoryboardEventSpec(
                "oncoming_vehicle_starts_turning",
                "override",
                "oncoming_turn_relative_distance",
                ("oncoming_vehicle_follow_turn_path",),
            ),
        ),
        actions=(
            StoryboardActionSpec("ego_follow_ego_path", "follow_trajectory", actor_refs=("ego",), path_ref="ego_path"),
            StoryboardActionSpec(
                "oncoming_vehicle_follow_turn_path",
                "follow_trajectory",
                actor_refs=("oncoming_vehicle",),
                path_ref="oncoming_turn_path",
            ),
        ),
    )


def _spatial_relations() -> tuple[SpatialRelationSpec, ...]:
    return (
        SpatialRelationSpec("turns_across_path_of", "oncoming_vehicle", "ego"),
        SpatialRelationSpec("conflicts_at", "oncoming_vehicle", "conflict_point"),
    )
