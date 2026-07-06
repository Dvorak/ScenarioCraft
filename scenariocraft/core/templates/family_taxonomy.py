from __future__ import annotations

"""Interaction-first scenario-family taxonomy.

The taxonomy is a lightweight code contract for routing, capability alignment,
and future scaffolding. It does not make planned families executable.
"""

from dataclasses import dataclass
from typing import Literal

FamilyStatus = Literal["mature", "early", "planned"]


@dataclass(frozen=True)
class FamilyDeclaration:
    template_id: str
    interaction: str
    actors: tuple[str, ...]
    odd: tuple[str, ...]
    topologies: tuple[str, ...]
    parameters: tuple[str, ...]
    capability_parameter_names: tuple[str, ...]
    boundaries: tuple[str, ...]
    status: FamilyStatus

    @property
    def implemented(self) -> bool:
        return self.status in {"mature", "early"}

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "interaction": self.interaction,
            "actors": list(self.actors),
            "odd": list(self.odd),
            "topologies": list(self.topologies),
            "parameters": list(self.parameters),
            "capability_parameter_names": list(self.capability_parameter_names),
            "boundaries": list(self.boundaries),
            "status": self.status,
            "implemented": self.implemented,
        }


_FAMILIES: tuple[FamilyDeclaration, ...] = (
    FamilyDeclaration(
        template_id="pedestrian_occlusion",
        interaction="pedestrian emerges from behind an occluder and crosses ego path",
        actors=("ego", "occluder", "crossing_actor"),
        odd=("urban", "urban_straight"),
        topologies=("urban_two_way_parking", "straight_two_way"),
        parameters=(
            "ego_speed",
            "pedestrian_speed",
            "occluder_position",
            "trigger_distance",
            "conflict_point",
            "target_ttc",
            "seed",
        ),
        capability_parameter_names=(
            "ego_speed_kph",
            "pedestrian_speed_mps",
            "trigger_offset_m",
            "van_to_conflict_offset_m",
            "total_duration_s",
            "preferred_trigger_earliest_s",
            "preferred_trigger_latest_s",
            "target_min_ttc_s",
            "weather",
        ),
        boundaries=(
            "cyclist occlusion",
            "intersection vehicle crossing",
            "freeway pedestrian",
        ),
        status="mature",
    ),
    FamilyDeclaration(
        template_id="lead_vehicle_braking",
        interaction="ego follows a lead vehicle that brakes suddenly",
        actors=("ego", "lead_vehicle"),
        odd=("urban", "urban_straight"),
        topologies=("straight_same_lane",),
        parameters=(
            "ego_speed",
            "lead_speed",
            "initial_gap",
            "lead_deceleration",
            "brake_start",
            "target_ttc",
            "target_thw",
            "seed",
        ),
        capability_parameter_names=(
            "ego_speed_kph",
            "lead_vehicle_speed_kph",
            "initial_gap_m",
            "lead_deceleration_mps2",
            "reaction_point_x_m",
            "target_min_ttc_s",
            "weather",
        ),
        boundaries=(
            "adjacent lane cut-in",
            "crossing vehicle",
            "oncoming turn",
        ),
        status="early",
    ),
    FamilyDeclaration(
        template_id="cut_in",
        interaction="adjacent vehicle changes into ego lane ahead of ego",
        actors=("ego", "cut_in_vehicle"),
        odd=("urban", "highway"),
        topologies=("multi_lane_same_direction",),
        parameters=(
            "ego_speed",
            "cut_in_speed",
            "initial_gap",
            "lane_change_duration",
            "cut_in_side",
            "target_ttc",
            "target_thw",
            "seed",
        ),
        capability_parameter_names=(),
        boundaries=(
            "lead vehicle braking without lane change",
            "intersection crossing",
            "pedestrian crossing",
        ),
        status="planned",
    ),
    FamilyDeclaration(
        template_id="crossing_vehicle",
        interaction="side vehicle crosses ego path at an intersection",
        actors=("ego", "crossing_vehicle"),
        odd=("urban",),
        topologies=("intersection",),
        parameters=(
            "ego_speed",
            "crossing_speed",
            "conflict_point",
            "arrival_time_difference",
            "right_of_way",
            "target_ttc",
            "seed",
        ),
        capability_parameter_names=(),
        boundaries=(
            "oncoming turn across ego path",
            "pedestrian crossing",
            "highway cut-in",
        ),
        status="planned",
    ),
    FamilyDeclaration(
        template_id="oncoming_turn_across_path",
        interaction="oncoming vehicle turns across ego path",
        actors=("ego", "oncoming_vehicle"),
        odd=("urban",),
        topologies=("intersection",),
        parameters=(
            "ego_speed",
            "oncoming_speed",
            "turn_start",
            "turn_radius",
            "conflict_point",
            "arrival_time_difference",
            "target_ttc",
            "seed",
        ),
        capability_parameter_names=(),
        boundaries=(
            "perpendicular crossing vehicle",
            "same-lane lead braking",
            "pedestrian crossing",
        ),
        status="planned",
    ),
)


def family_declarations() -> dict[str, FamilyDeclaration]:
    return {family.template_id: family for family in _FAMILIES}


def family_declaration(template_id: str) -> FamilyDeclaration:
    try:
        return family_declarations()[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario family: {template_id}") from exc


def executable_family_ids() -> tuple[str, ...]:
    return tuple(family.template_id for family in _FAMILIES if family.implemented)


def planned_family_ids() -> tuple[str, ...]:
    return tuple(family.template_id for family in _FAMILIES if family.status == "planned")
