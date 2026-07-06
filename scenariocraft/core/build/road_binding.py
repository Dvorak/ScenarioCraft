"""Canonical OpenDRIVE road binding for ScenarioSpec builds."""

from pathlib import Path

from scenariocraft.core.roads import (
    MULTI_LANE_SAME_DIRECTION_FILENAME,
    URBAN_FOUR_WAY_INTERSECTION_FILENAME,
    URBAN_TWO_WAY_PARKING_FILENAME,
    write_multi_lane_same_direction_xodr,
    write_urban_four_way_intersection_xodr,
    write_urban_two_way_parking_xodr,
)
from scenariocraft.core.schemas import ScenarioSpec


def materialize_canonical_road_if_needed(spec: ScenarioSpec, output_dir: Path) -> Path | None:
    """Write the canonical OpenDRIVE asset required by this spec, if any."""

    filename = canonical_road_filename_for_spec(spec)
    if filename == URBAN_TWO_WAY_PARKING_FILENAME:
        return write_urban_two_way_parking_xodr(output_dir / URBAN_TWO_WAY_PARKING_FILENAME)
    if filename == MULTI_LANE_SAME_DIRECTION_FILENAME:
        return write_multi_lane_same_direction_xodr(output_dir / MULTI_LANE_SAME_DIRECTION_FILENAME)
    if filename == URBAN_FOUR_WAY_INTERSECTION_FILENAME:
        intersection_center = intersection_center_for_spec(spec)
        return write_urban_four_way_intersection_xodr(
            output_dir / URBAN_FOUR_WAY_INTERSECTION_FILENAME,
            intersection_center_x=intersection_center[0],
            intersection_center_y=intersection_center[1],
        )
    return None


def canonical_road_filename_for_spec(spec: ScenarioSpec) -> str | None:
    """Return the canonical road filename selected for a supported spec."""

    if uses_canonical_urban_two_way_parking_road(spec):
        return URBAN_TWO_WAY_PARKING_FILENAME
    if uses_canonical_multi_lane_same_direction_road(spec):
        return MULTI_LANE_SAME_DIRECTION_FILENAME
    if uses_canonical_urban_four_way_intersection_road(spec):
        return URBAN_FOUR_WAY_INTERSECTION_FILENAME
    return None


def uses_canonical_urban_two_way_parking_road(spec: ScenarioSpec) -> bool:
    return (
        spec.scenario_type in {"pedestrian_occlusion", "lead_vehicle_braking"}
        and spec.layout is not None
        and spec.layout.coordinate_frame == "ego_local"
        and spec.road.type == "urban_straight"
    )


def uses_canonical_multi_lane_same_direction_road(spec: ScenarioSpec) -> bool:
    return (
        spec.scenario_type == "cut_in"
        and spec.layout is not None
        and spec.layout.coordinate_frame == "ego_local"
        and spec.road.type == "urban_straight"
    )


def uses_canonical_urban_four_way_intersection_road(spec: ScenarioSpec) -> bool:
    return (
        spec.scenario_type in {"crossing_vehicle", "oncoming_turn_across_path"}
        and spec.layout is not None
        and spec.layout.coordinate_frame == "ego_local"
        and spec.road.type == "urban_intersection"
    )


def intersection_center_for_spec(spec: ScenarioSpec) -> tuple[float, float]:
    """Anchor intersection road geometry to the semantic conflict point."""

    if spec.layout is None:
        return (0.0, 0.0)
    conflict_point = spec.layout.points.get("conflict_point")
    if conflict_point is None:
        return (0.0, 0.0)
    return (conflict_point.x_m, conflict_point.y_m)
