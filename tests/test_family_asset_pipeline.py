from scenariocraft.core.roads import supported_road_preview_capabilities
from scenariocraft.core.templates import family_asset_readiness, family_asset_readiness_report, get_template


def test_family_asset_readiness_report_covers_taxonomy_order() -> None:
    report = family_asset_readiness_report()

    assert tuple(report) == (
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    )
    assert report["pedestrian_occlusion"].status == "mature"
    assert report["lead_vehicle_braking"].status == "early"
    assert report["cut_in"].status == "early"


def test_mature_pedestrian_family_is_executable_and_asset_ready() -> None:
    readiness = family_asset_readiness("pedestrian_occlusion")

    assert readiness.executable is True
    assert readiness.template_registered is True
    assert readiness.capability_ready is True
    assert readiness.road_asset_ready is True
    assert readiness.builder_ready is True
    assert readiness.family_checks_ready is True
    assert readiness.artifact_checks_ready is True
    assert readiness.required_road_assets == ("urban_two_way_parking",)
    assert readiness.missing_assets == ()
    assert readiness.automatable_scaffold == ()
    assert readiness.manual_dirty_work == ()


def test_lead_braking_is_executable_and_bound_to_current_owned_road_asset() -> None:
    readiness = family_asset_readiness("lead_vehicle_braking")

    assert readiness.executable is True
    assert readiness.template_registered is True
    assert readiness.capability_ready is True
    assert readiness.builder_ready is True
    assert readiness.family_checks_ready is True
    assert readiness.artifact_checks_ready is True
    assert readiness.road_asset_ready is True
    assert readiness.required_road_assets == ("urban_two_way_parking",)
    assert readiness.missing_assets == ()
    assert readiness.manual_dirty_work == ()


def test_cut_in_family_is_executable_and_bound_to_multilane_road_asset() -> None:
    readiness = family_asset_readiness("cut_in")

    assert readiness.executable is True
    assert readiness.template_registered is True
    assert readiness.capability_ready is True
    assert readiness.road_asset_ready is True
    assert readiness.builder_ready is True
    assert readiness.family_checks_ready is True
    assert readiness.artifact_checks_ready is True
    assert readiness.required_road_assets == ("multi_lane_same_direction",)
    assert readiness.missing_assets == ()
    assert readiness.automatable_scaffold == ()
    assert readiness.manual_dirty_work == ()


def test_readiness_exports_machine_readable_payload() -> None:
    payload = family_asset_readiness("crossing_vehicle").to_dict()

    assert payload["template_id"] == "crossing_vehicle"
    assert payload["status"] == "early"
    assert payload["executable"] is True
    assert payload["required_road_assets"] == ["urban_four_way_intersection"]
    assert payload["missing_assets"] == []


def test_golden_family_specs_declare_supported_road_asset_id() -> None:
    supported_roads = set(supported_road_preview_capabilities())

    for template_id, expected_road in {
        "pedestrian_occlusion": "urban_two_way_parking",
        "lead_vehicle_braking": "urban_two_way_parking",
        "cut_in": "multi_lane_same_direction",
        "crossing_vehicle": "urban_four_way_intersection",
        "oncoming_turn_across_path": "urban_four_way_intersection",
    }.items():
        spec = get_template(template_id).instantiate()

        assert spec.metadata["road_asset_id"] == expected_road
        assert spec.metadata["road_asset_id"] in supported_roads
