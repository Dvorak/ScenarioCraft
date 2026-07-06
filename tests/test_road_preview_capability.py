from scenariocraft.core.roads import (
    canonical_road_asset_definition,
    road_preview_surface_kind,
    supported_road_preview_capabilities,
)


def test_supported_canonical_roads_declare_preview_surface_kind() -> None:
    capabilities = supported_road_preview_capabilities()

    assert capabilities["urban_two_way_parking"].preview_surface_kind == "road_bands"
    assert capabilities["multi_lane_same_direction"].preview_surface_kind == "road_bands"
    assert capabilities["urban_four_way_intersection"].preview_surface_kind == "intersection_cross"


def test_unknown_road_has_no_preview_surface_kind() -> None:
    assert road_preview_surface_kind("future_imported_city_map") is None


def test_canonical_road_assets_declare_supported_families_and_corridors() -> None:
    two_way = canonical_road_asset_definition("urban_two_way_parking")
    multi_lane = canonical_road_asset_definition("multi_lane_same_direction")
    intersection = canonical_road_asset_definition("urban_four_way_intersection")

    assert two_way is not None
    assert set(two_way.supported_families) == {"pedestrian_occlusion", "lead_vehicle_braking"}
    assert {"ego_driving_lane", "ego_side_parking_strip", "ego_side_sidewalk"}.issubset(two_way.corridors)
    assert two_way.topology == "straight_two_way_with_parking"

    assert multi_lane is not None
    assert multi_lane.supported_families == ("cut_in",)
    assert {"ego_driving_lane", "adjacent_same_direction_lane"}.issubset(multi_lane.corridors)
    assert multi_lane.topology == "straight_multi_lane_same_direction"

    assert intersection is not None
    assert set(intersection.supported_families) == {"crossing_vehicle", "oncoming_turn_across_path"}
    assert intersection.topology == "four_way_intersection"
    assert {"ego_straight", "crossing_straight", "oncoming_straight", "turn_across_path"}.issubset(
        intersection.corridors
    )
