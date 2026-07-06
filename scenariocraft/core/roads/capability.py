from __future__ import annotations

"""Road capabilities consumed by deterministic renderers and builders."""

from dataclasses import dataclass
from typing import Literal, Mapping

RoadPreviewSurfaceKind = Literal["road_bands", "intersection_cross"]


@dataclass(frozen=True)
class RoadPreviewCapability:
    """Minimal preview contract for a project-owned canonical road asset."""

    road_asset_id: str
    preview_surface_kind: RoadPreviewSurfaceKind


@dataclass(frozen=True)
class RoadCorridorDefinition:
    """Named world-coordinate corridor used by canonical templates and checks."""

    corridor_id: str
    kind: str
    x_min_m: float | None = None
    x_max_m: float | None = None
    y_min_m: float | None = None
    y_max_m: float | None = None
    travel_direction: str | None = None


@dataclass(frozen=True)
class RoadAssetDefinition:
    """Human- and machine-readable contract for a canonical road asset."""

    road_asset_id: str
    display_name: str
    topology: str
    preview_surface_kind: RoadPreviewSurfaceKind
    supported_families: tuple[str, ...]
    corridors: Mapping[str, RoadCorridorDefinition]
    anchor_points: Mapping[str, tuple[float, float]]


_ROAD_PREVIEW_CAPABILITIES: Mapping[str, RoadPreviewCapability] = {
    "urban_two_way_parking": RoadPreviewCapability(
        road_asset_id="urban_two_way_parking",
        preview_surface_kind="road_bands",
    ),
    "multi_lane_same_direction": RoadPreviewCapability(
        road_asset_id="multi_lane_same_direction",
        preview_surface_kind="road_bands",
    ),
    "urban_four_way_intersection": RoadPreviewCapability(
        road_asset_id="urban_four_way_intersection",
        preview_surface_kind="intersection_cross",
    ),
}

_ROAD_ASSET_DEFINITIONS: Mapping[str, RoadAssetDefinition] = {
    "urban_two_way_parking": RoadAssetDefinition(
        road_asset_id="urban_two_way_parking",
        display_name="Urban two-way road with ego-side parking",
        topology="straight_two_way_with_parking",
        preview_surface_kind="road_bands",
        supported_families=("pedestrian_occlusion", "lead_vehicle_braking"),
        corridors={
            "ego_side_sidewalk": RoadCorridorDefinition("ego_side_sidewalk", "sidewalk", y_min_m=4.25, y_max_m=6.50),
            "ego_side_parking_strip": RoadCorridorDefinition(
                "ego_side_parking_strip",
                "parking_strip",
                y_min_m=1.75,
                y_max_m=4.25,
            ),
            "ego_driving_lane": RoadCorridorDefinition(
                "ego_driving_lane",
                "driving_lane",
                y_min_m=-1.75,
                y_max_m=1.75,
                travel_direction="+x",
            ),
            "center_divider": RoadCorridorDefinition("center_divider", "center_divider", y_min_m=-2.00, y_max_m=-1.75),
            "opposing_driving_lane": RoadCorridorDefinition(
                "opposing_driving_lane",
                "driving_lane",
                y_min_m=-5.50,
                y_max_m=-2.00,
                travel_direction="-x",
            ),
            "opposing_side_sidewalk": RoadCorridorDefinition(
                "opposing_side_sidewalk",
                "sidewalk",
                y_min_m=-7.50,
                y_max_m=-5.50,
            ),
        },
        anchor_points={"origin": (0.0, 0.0)},
    ),
    "multi_lane_same_direction": RoadAssetDefinition(
        road_asset_id="multi_lane_same_direction",
        display_name="Straight multi-lane same-direction road",
        topology="straight_multi_lane_same_direction",
        preview_surface_kind="road_bands",
        supported_families=("cut_in",),
        corridors={
            "adjacent_same_direction_lane": RoadCorridorDefinition(
                "adjacent_same_direction_lane",
                "driving_lane",
                y_min_m=1.75,
                y_max_m=5.25,
                travel_direction="+x",
            ),
            "ego_driving_lane": RoadCorridorDefinition(
                "ego_driving_lane",
                "driving_lane",
                y_min_m=-1.75,
                y_max_m=1.75,
                travel_direction="+x",
            ),
            "ego_side_shoulder": RoadCorridorDefinition("ego_side_shoulder", "shoulder", y_min_m=-3.75, y_max_m=-1.75),
        },
        anchor_points={"origin": (0.0, 0.0)},
    ),
    "urban_four_way_intersection": RoadAssetDefinition(
        road_asset_id="urban_four_way_intersection",
        display_name="Urban four-way intersection",
        topology="four_way_intersection",
        preview_surface_kind="intersection_cross",
        supported_families=("crossing_vehicle", "oncoming_turn_across_path"),
        corridors={
            "ego_straight": RoadCorridorDefinition(
                "ego_straight",
                "driving_lane",
                y_min_m=-1.75,
                y_max_m=1.75,
                travel_direction="+x",
            ),
            "oncoming_straight": RoadCorridorDefinition(
                "oncoming_straight",
                "driving_lane",
                y_min_m=1.75,
                y_max_m=5.25,
                travel_direction="-x",
            ),
            "crossing_straight": RoadCorridorDefinition(
                "crossing_straight",
                "driving_lane",
                x_min_m=-1.75,
                x_max_m=1.75,
                travel_direction="+y",
            ),
            "turn_across_path": RoadCorridorDefinition("turn_across_path", "turn_connector", travel_direction="turn"),
        },
        anchor_points={"intersection_center": (0.0, 0.0)},
    ),
}


def supported_road_preview_capabilities() -> dict[str, RoadPreviewCapability]:
    """Return canonical road preview capabilities keyed by road asset id."""

    return dict(_ROAD_PREVIEW_CAPABILITIES)


def supported_canonical_road_assets() -> dict[str, RoadAssetDefinition]:
    """Return canonical road asset definitions keyed by road asset id."""

    return dict(_ROAD_ASSET_DEFINITIONS)


def canonical_road_asset_definition(road_asset_id: str | None) -> RoadAssetDefinition | None:
    """Return the canonical road definition for a road asset id if known."""

    if road_asset_id is None:
        return None
    return _ROAD_ASSET_DEFINITIONS.get(road_asset_id)


def road_preview_surface_kind(road_asset_id: str | None) -> RoadPreviewSurfaceKind | None:
    """Return the preview surface kind for a canonical road asset if known."""

    if road_asset_id is None:
        return None
    capability = _ROAD_PREVIEW_CAPABILITIES.get(road_asset_id)
    if capability is None:
        return None
    return capability.preview_surface_kind
