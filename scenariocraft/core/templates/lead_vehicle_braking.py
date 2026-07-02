from __future__ import annotations

"""Deterministic same-lane lead-vehicle-braking scenario template.

The template expands intent/parameters into ScenarioSpec semantics; it does not
encode runtime braking physics directly into OpenSCENARIO.
"""

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
    TriggerConditionSpec,
    TriggerSpec,
    WeatherSpec,
)


@dataclass(frozen=True)
class LeadVehicleBrakingParameters:
    ego_speed_kph: float = 50.0
    lead_vehicle_speed_kph: float = 45.0
    initial_gap_m: float = 28.0
    lead_deceleration_mps2: float = -4.0
    reaction_point_x_m: float = 10.0
    ego_length_m: float = 4.6
    ego_width_m: float = 1.9
    lead_vehicle_length_m: float = 4.8
    lead_vehicle_width_m: float = 1.9
    total_duration_s: float = 8.0
    preferred_trigger_earliest_s: float = 1.0
    preferred_trigger_latest_s: float = 3.0
    minimum_pre_trigger_context_s: float = 0.5
    minimum_post_trigger_buffer_s: float = 0.5
    target_min_ttc_s: float = 2.0
    weather: str = "clear_dry"


class LeadVehicleBrakingTemplate:
    template_id = "lead_vehicle_braking"
    description = "Urban same-lane following scenario where a lead vehicle brakes ahead of ego."
    required_actors = ("ego", "lead_vehicle")
    default_parameters: Mapping[str, object] = {
        "scenario_name": "lead_vehicle_braking",
        "source_text": "",
        "parameters": LeadVehicleBrakingParameters(),
    }
    supported_operations = ()

    def instantiate(self, **parameters: object) -> ScenarioSpec:
        scenario_name = str(parameters.get("scenario_name", self.default_parameters["scenario_name"]))
        source_text = str(parameters.get("source_text", self.default_parameters["source_text"]))
        intent = parameters.get("intent")
        template_parameters = _parameters_from_mapping(parameters, intent if isinstance(intent, ScenarioIntent) else None)
        metadata = {
            "generator": "template",
            "source_text": source_text,
            "lead_vehicle_braking": {
                "initial_gap_m": template_parameters.initial_gap_m,
                "lead_deceleration_mps2": template_parameters.lead_deceleration_mps2,
                "reaction_point_x_m": template_parameters.reaction_point_x_m,
            },
        }
        return ScenarioSpec(
            scenario_name=scenario_name,
            scenario_type=self.template_id,
            road=RoadSpec(type="urban_straight", lanes_per_direction=1, speed_limit_kph=50),
            weather=_weather(template_parameters),
            actors=[
                ActorSpec(
                    id="ego",
                    type="car",
                    role="ego",
                    initial_speed_kph=template_parameters.ego_speed_kph,
                ),
                ActorSpec(
                    id="lead_vehicle",
                    type="car",
                    role="lead_vehicle",
                    initial_speed_kph=template_parameters.lead_vehicle_speed_kph,
                    state="braking",
                ),
            ],
            trigger=TriggerSpec(
                type="relative_distance",
                source="ego",
                target="lead_vehicle",
                distance_m=template_parameters.initial_gap_m,
                condition=TriggerConditionSpec(
                    id="lead_vehicle_brake_relative_distance",
                    metric="relative_distance",
                    source="ego",
                    target="lead_vehicle",
                    rule="lessThan",
                    value=template_parameters.initial_gap_m,
                    unit="m",
                    coordinate_system="entity",
                    relative_distance_type="longitudinal",
                    freespace=False,
                    target_kind="entity",
                ),
            ),
            intended_criticality=CriticalitySpec(
                type="lead_vehicle_braking",
                target_min_ttc_s=template_parameters.target_min_ttc_s,
            ),
            metadata=metadata,
            layout=_layout(template_parameters),
            spatial_relations=_spatial_relations(template_parameters),
            timing=ScenarioTimingSpec(
                total_duration_s=template_parameters.total_duration_s,
                preferred_trigger_earliest_s=template_parameters.preferred_trigger_earliest_s,
                preferred_trigger_latest_s=template_parameters.preferred_trigger_latest_s,
                minimum_pre_trigger_context_s=template_parameters.minimum_pre_trigger_context_s,
                minimum_post_trigger_buffer_s=template_parameters.minimum_post_trigger_buffer_s,
            ),
        )


def _parameters_from_mapping(
    values: Mapping[str, object],
    intent: ScenarioIntent | None,
) -> LeadVehicleBrakingParameters:
    template_parameters = values.get("parameters", LeadVehicleBrakingParameters())
    if isinstance(template_parameters, LeadVehicleBrakingParameters):
        base = template_parameters
    elif isinstance(template_parameters, Mapping):
        base = LeadVehicleBrakingParameters(**template_parameters)
    else:
        raise TypeError("parameters must be a LeadVehicleBrakingParameters or mapping.")

    intent_overrides: dict[str, object] = {}
    if intent is not None:
        ego = intent.actor("ego")
        lead = intent.actor("lead_vehicle")
        if "speed_kph" in ego:
            intent_overrides["ego_speed_kph"] = ego["speed_kph"]
        if "speed_kph" in lead:
            intent_overrides["lead_vehicle_speed_kph"] = lead["speed_kph"]
        if "target_ttc_s" in intent.criticality:
            intent_overrides["target_min_ttc_s"] = intent.criticality["target_ttc_s"]
        if "condition" in intent.weather:
            intent_overrides["weather"] = intent.weather["condition"]

    direct_overrides = {
        field_name: values[field_name]
        for field_name in LeadVehicleBrakingParameters.__dataclass_fields__
        if field_name in values
    }
    return replace(base, **intent_overrides, **direct_overrides)


def _weather(parameters: LeadVehicleBrakingParameters) -> WeatherSpec:
    if parameters.weather == "rainy_wet":
        return WeatherSpec(rain=True, road_condition="wet")
    return WeatherSpec(rain=False, road_condition="dry")


def _layout(parameters: LeadVehicleBrakingParameters) -> LayoutSpec:
    ego_pose = Pose2D(x_m=0.0, y_m=0.0, heading_rad=0.0)
    lead_pose = Pose2D(x_m=parameters.initial_gap_m, y_m=0.0, heading_rad=0.0)
    path_end = Point2D(parameters.initial_gap_m + 45.0, 0.0)
    return LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={
            "ego": ego_pose,
            "lead_vehicle": lead_pose,
        },
        actor_footprints={
            "ego": FootprintSpec(length_m=parameters.ego_length_m, width_m=parameters.ego_width_m),
            "lead_vehicle": FootprintSpec(
                length_m=parameters.lead_vehicle_length_m,
                width_m=parameters.lead_vehicle_width_m,
            ),
        },
        paths={
            "ego_path": PathSpec(name="ego_path", points=(Point2D(0.0, 0.0), path_end)),
            "lead_vehicle_path": PathSpec(
                name="lead_vehicle_path",
                points=(Point2D(parameters.initial_gap_m, 0.0), path_end),
            ),
        },
        points={
            "reaction_point": Point2D(parameters.reaction_point_x_m, 0.0),
            "lead_brake_start_point": Point2D(parameters.initial_gap_m, 0.0),
        },
        road_bands=_road_bands(),
    )


def _road_bands() -> tuple[RoadBandSpec, ...]:
    return (
        RoadBandSpec(id="ego_side_sidewalk", kind="sidewalk", y_min_m=4.25, y_max_m=6.50),
        RoadBandSpec(id="ego_side_parking_strip", kind="parking_strip", y_min_m=1.75, y_max_m=4.25),
        RoadBandSpec(id="ego_driving_lane", kind="driving_lane", y_min_m=-1.75, y_max_m=1.75, travel_direction="+x"),
        RoadBandSpec(id="center_divider", kind="center_divider", y_min_m=-2.00, y_max_m=-1.75),
        RoadBandSpec(id="opposing_driving_lane", kind="driving_lane", y_min_m=-5.50, y_max_m=-2.00, travel_direction="-x"),
        RoadBandSpec(id="opposing_side_sidewalk", kind="sidewalk", y_min_m=-7.50, y_max_m=-5.50),
    )


def _spatial_relations(parameters: LeadVehicleBrakingParameters) -> tuple[SpatialRelationSpec, ...]:
    return (
        SpatialRelationSpec(
            relation_type="same_lane_as",
            subject="ego",
            object="lead_vehicle",
            metadata={"lane_band_id": "ego_driving_lane"},
        ),
        SpatialRelationSpec(
            relation_type="ahead_of",
            subject="lead_vehicle",
            object="ego",
            metadata={"axis": "+x", "initial_gap_m": parameters.initial_gap_m},
        ),
        SpatialRelationSpec(
            relation_type="brakes_before",
            subject="lead_vehicle",
            object="ego",
            metadata={
                "lead_deceleration_mps2": parameters.lead_deceleration_mps2,
                "reaction_point": "reaction_point",
            },
        ),
    )
