from __future__ import annotations

"""Deterministic adjacent-lane cut-in scenario family."""

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
class CutInParameters:
    ego_speed_kph: float = 50.0
    cut_in_vehicle_speed_kph: float = 45.0
    initial_gap_m: float = 22.0
    merge_point_x_m: float = 35.0
    lane_change_duration_s: float = 3.0
    trigger_distance_m: float = 18.0
    vehicle_length_m: float = 4.6
    vehicle_width_m: float = 1.9
    total_duration_s: float = 8.0
    target_min_ttc_s: float = 2.0
    weather: str = "clear_dry"


class CutInTemplate:
    template_id = "cut_in"
    description = "Adjacent same-direction vehicle changes into ego lane ahead of ego."
    required_actors = ("ego", "cut_in_vehicle")
    default_parameters: Mapping[str, object] = {
        "scenario_name": "cut_in",
        "source_text": "",
        "parameters": CutInParameters(),
    }
    supported_operations = ()
    capability = TemplateCapability(
        template_id=template_id,
        interaction_family="cut_in",
        description=description,
        actor_roles=required_actors,
        road_contexts=("urban", "urban_straight"),
        topologies=("multi_lane_same_direction",),
        aliases=(
            "vehicle cuts into ego lane",
            "adjacent lane cut-in",
            "lane change in front of ego",
            "merge into ego lane",
        ),
        semantic_slots=(
            "road_context",
            "ego",
            "cut_in_vehicle",
            "adjacent_lane_start",
            "lane_change_event",
            "initial_gap",
            "criticality",
            "weather",
        ),
        supported_variants=(
            "urban same-direction adjacent-lane cut-in",
            "variable speed, gap, lane-change duration, merge point, and target TTC",
            "rainy/wet or clear/dry weather",
        ),
        unsupported_boundary_examples=(
            "same-lane lead vehicle braking",
            "intersection crossing vehicle",
            "oncoming turn",
            "pedestrian crossing",
        ),
        parameter_domains=(
            ParameterDomain("ego_speed_kph", "float", 50.0, unit="km/h", min_value=35.0, max_value=60.0),
            ParameterDomain("cut_in_vehicle_speed_kph", "float", 45.0, unit="km/h", min_value=25.0, max_value=60.0),
            ParameterDomain("initial_gap_m", "float", 22.0, unit="m", min_value=14.0, max_value=35.0),
            ParameterDomain("merge_point_x_m", "float", 35.0, unit="m", min_value=25.0, max_value=55.0),
            ParameterDomain("lane_change_duration_s", "float", 3.0, unit="s", min_value=2.0, max_value=5.0),
            ParameterDomain("trigger_distance_m", "float", 18.0, unit="m", min_value=10.0, max_value=28.0),
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
        template_parameters = _parameters_from_mapping(parameters, intent if isinstance(intent, ScenarioIntent) else None)
        return ScenarioSpec(
            scenario_name=scenario_name,
            scenario_type=self.template_id,
            road=RoadSpec(type="urban_straight", lanes_per_direction=2, speed_limit_kph=50),
            weather=_weather(template_parameters),
            actors=[
                ActorSpec(id="ego", type="car", role="ego", initial_speed_kph=template_parameters.ego_speed_kph),
                ActorSpec(
                    id="cut_in_vehicle",
                    type="car",
                    role="cut_in_actor",
                    initial_speed_kph=template_parameters.cut_in_vehicle_speed_kph,
                    state="lane_changing",
                ),
            ],
            trigger=TriggerSpec(
                type="relative_distance",
                source="ego",
                target="cut_in_vehicle",
                distance_m=template_parameters.trigger_distance_m,
                condition=TriggerConditionSpec(
                    id="cut_in_relative_distance",
                    metric="relative_distance",
                    source="ego",
                    target="cut_in_vehicle",
                    rule="lessThan",
                    value=template_parameters.trigger_distance_m,
                    unit="m",
                    coordinate_system="entity",
                    relative_distance_type="longitudinal",
                    freespace=False,
                    target_kind="entity",
                ),
            ),
            intended_criticality=CriticalitySpec(type="cut_in", target_min_ttc_s=template_parameters.target_min_ttc_s),
            metadata={
                "generator": "template",
                "source_text": source_text,
                "road_asset_id": "multi_lane_same_direction",
                "cut_in": {
                    "initial_gap_m": template_parameters.initial_gap_m,
                    "merge_point_x_m": template_parameters.merge_point_x_m,
                    "lane_change_duration_s": template_parameters.lane_change_duration_s,
                    "trigger_distance_m": template_parameters.trigger_distance_m,
                },
            },
            layout=_layout(template_parameters),
            spatial_relations=_spatial_relations(template_parameters),
            storyboard=_storyboard(),
            timing=ScenarioTimingSpec(total_duration_s=template_parameters.total_duration_s),
        )


def _parameters_from_mapping(values: Mapping[str, object], intent: ScenarioIntent | None) -> CutInParameters:
    template_parameters = values.get("parameters", CutInParameters())
    if isinstance(template_parameters, CutInParameters):
        base = template_parameters
    elif isinstance(template_parameters, Mapping):
        base = CutInParameters(**template_parameters)
    else:
        raise TypeError("parameters must be a CutInParameters or mapping.")
    intent_overrides: dict[str, object] = {}
    if intent is not None:
        ego = intent.actor("ego")
        cut_in = intent.actor("cut_in_vehicle")
        if "speed_kph" in ego:
            intent_overrides["ego_speed_kph"] = ego["speed_kph"]
        if "speed_kph" in cut_in:
            intent_overrides["cut_in_vehicle_speed_kph"] = cut_in["speed_kph"]
        if "target_ttc_s" in intent.criticality:
            intent_overrides["target_min_ttc_s"] = intent.criticality["target_ttc_s"]
        if "condition" in intent.weather:
            intent_overrides["weather"] = intent.weather["condition"]
    direct_overrides = {
        field_name: values[field_name]
        for field_name in CutInParameters.__dataclass_fields__
        if field_name in values
    }
    parameters = replace(base, **{**intent_overrides, **direct_overrides})
    _validate_parameters(parameters)
    return parameters


def _validate_parameters(parameters: CutInParameters) -> None:
    if parameters.merge_point_x_m <= parameters.initial_gap_m:
        raise ValueError("merge_point_x_m must be greater than initial_gap_m.")
    if parameters.trigger_distance_m <= 0:
        raise ValueError("trigger_distance_m must be positive.")


def _weather(parameters: CutInParameters) -> WeatherSpec:
    if parameters.weather == "rainy_wet":
        return WeatherSpec(rain=True, road_condition="wet")
    return WeatherSpec(rain=False, road_condition="dry")


def _layout(parameters: CutInParameters) -> LayoutSpec:
    ego_pose = Pose2D(0.0, 0.0, 0.0)
    cut_in_pose = Pose2D(parameters.initial_gap_m, 3.5, 0.0)
    merge_point = Point2D(parameters.merge_point_x_m, 0.0)
    return LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={"ego": ego_pose, "cut_in_vehicle": cut_in_pose},
        actor_footprints={
            "ego": FootprintSpec(length_m=parameters.vehicle_length_m, width_m=parameters.vehicle_width_m),
            "cut_in_vehicle": FootprintSpec(length_m=parameters.vehicle_length_m, width_m=parameters.vehicle_width_m),
        },
        paths={
            "ego_path": PathSpec("ego_path", (Point2D(0.0, 0.0), Point2D(parameters.merge_point_x_m + 45.0, 0.0))),
            "cut_in_path": PathSpec("cut_in_path", (Point2D(parameters.initial_gap_m, 3.5), merge_point)),
        },
        points={
            "trigger_point": Point2D(parameters.initial_gap_m - parameters.trigger_distance_m, 0.0),
            "merge_point": merge_point,
        },
        road_bands=_road_bands(),
    )


def _road_bands() -> tuple[RoadBandSpec, ...]:
    return (
        RoadBandSpec("adjacent_same_direction_lane", "driving_lane", 1.75, 5.25, travel_direction="+x"),
        RoadBandSpec("ego_driving_lane", "driving_lane", -1.75, 1.75, travel_direction="+x"),
        RoadBandSpec("ego_side_shoulder", "shoulder", -3.75, -1.75),
    )


def _storyboard() -> StoryboardSpec:
    return StoryboardSpec(
        stories=(StoryboardStorySpec("cut_in_story", ("cut_in_act",)),),
        acts=(StoryboardActSpec("cut_in_act", ("ego_driving", "cut_in_vehicle_lane_change")),),
        maneuver_groups=(
            StoryboardManeuverGroupSpec("ego_driving", ("ego",), ("ego_drives_forward",)),
            StoryboardManeuverGroupSpec(
                "cut_in_vehicle_lane_change",
                ("cut_in_vehicle",),
                ("cut_in_vehicle_starts_lane_change",),
            ),
        ),
        events=(
            StoryboardEventSpec("ego_drives_forward", "override", "ego_starts_driving", ("ego_follow_ego_path",)),
            StoryboardEventSpec(
                "cut_in_vehicle_starts_lane_change",
                "override",
                "cut_in_relative_distance",
                ("cut_in_vehicle_follow_cut_in_path",),
            ),
        ),
        actions=(
            StoryboardActionSpec("ego_follow_ego_path", "follow_trajectory", actor_refs=("ego",), path_ref="ego_path"),
            StoryboardActionSpec(
                "cut_in_vehicle_follow_cut_in_path",
                "follow_trajectory",
                actor_refs=("cut_in_vehicle",),
                path_ref="cut_in_path",
            ),
        ),
    )


def _spatial_relations(parameters: CutInParameters) -> tuple[SpatialRelationSpec, ...]:
    return (
        SpatialRelationSpec("starts_in_adjacent_lane", "cut_in_vehicle", "adjacent_same_direction_lane"),
        SpatialRelationSpec("cuts_into", "cut_in_vehicle", "ego_driving_lane"),
        SpatialRelationSpec(
            "ahead_of",
            "cut_in_vehicle",
            "ego",
            metadata={"axis": "+x", "initial_gap_m": parameters.initial_gap_m},
        ),
    )
