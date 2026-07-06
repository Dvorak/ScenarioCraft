from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.build import build_openscenario
from scenariocraft.core.checks import run_artifact_consistency_checks, run_crossing_vehicle_checks
from scenariocraft.core.roads import URBAN_FOUR_WAY_INTERSECTION_FILENAME
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import family_asset_readiness, get_template, resolve_scenario_intent


def test_crossing_vehicle_template_resolves_to_intersection_bound_spec() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="crossing_vehicle"))

    assert spec.scenario_type == "crossing_vehicle"
    assert spec.layout is not None
    assert spec.layout.actor_poses["ego"].y_m == 0.0
    assert spec.layout.actor_poses["crossing_vehicle"].x_m == spec.layout.points["conflict_point"].x_m
    assert spec.layout.paths["crossing_vehicle_path"].points[-1].y_m > 0.0
    assert spec.layout.points["conflict_point"].y_m == 0.0
    assert get_template("crossing_vehicle").capability.template_id == "crossing_vehicle"
    assert family_asset_readiness("crossing_vehicle").executable is True
    assert family_asset_readiness("crossing_vehicle").road_asset_ready is True


def test_crossing_vehicle_family_checks_pass_for_default_instance() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="crossing_vehicle"))

    by_name = {result.name: result for result in run_crossing_vehicle_checks(spec)}

    assert by_name["crossing_vehicle_path_crosses_ego_path"].passed is True
    assert by_name["crossing_vehicle_conflict_point_on_both_paths"].passed is True
    assert by_name["crossing_vehicle_arrival_time_alignment"].passed is True
    assert by_name["crossing_vehicle_trigger_timing"].passed is True


def test_crossing_vehicle_builder_binds_intersection_opendrive_and_follow_trajectory(tmp_path: Path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="crossing_vehicle"))

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")

    assert result.xodr_path == tmp_path / URBAN_FOUR_WAY_INTERSECTION_FILENAME
    assert result.xodr_path.exists()
    assert logic_file is not None
    assert logic_file.attrib["filepath"] == URBAN_FOUR_WAY_INTERSECTION_FILENAME
    assert root.find(".//ManeuverGroup[@name='crossing_vehicle_movement']") is not None
    assert root.find(".//Action[@name='crossing_vehicle_follow_crossing_path']//FollowTrajectoryAction") is not None
    xodr_root = ET.parse(result.xodr_path).getroot()
    roads = {road.attrib["name"]: road for road in xodr_root.findall("./road")}
    cross_geometry = roads["north_south_cross"].find("./planView/geometry")
    assert cross_geometry is not None
    assert float(cross_geometry.attrib["x"]) == spec.layout.points["conflict_point"].x_m
    assert xodr_root.find("./junction/connection[@id='south_to_north_straight']/laneLink") is not None


def test_crossing_vehicle_artifact_consistency_checks_pass(tmp_path: Path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="crossing_vehicle"))
    build_result = build_openscenario(spec, tmp_path)

    results = run_artifact_consistency_checks(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    by_name = {result.name: result for result in results}

    assert set(by_name) == {
        "xosc_crossing_vehicle_actor_poses_match_layout",
        "xosc_crossing_vehicle_trajectory_matches_layout_path",
        "xosc_logic_file_is_relative",
        "xodr_logic_file_target_exists",
        "xosc_logic_file_matches_canonical_road",
        "xodr_crossing_vehicle_layout_aligns_with_road",
    }
    assert all(result.passed for result in results)
