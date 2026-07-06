from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.build import build_openscenario
from scenariocraft.core.checks import run_artifact_consistency_checks, run_cut_in_checks
from scenariocraft.core.roads import MULTI_LANE_SAME_DIRECTION_FILENAME
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import family_asset_readiness, get_template, resolve_scenario_intent


def test_cut_in_template_resolves_to_road_bound_scenario_spec() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="cut_in"))

    assert spec.scenario_type == "cut_in"
    assert spec.layout is not None
    assert spec.layout.actor_poses["ego"].y_m == 0.0
    assert spec.layout.actor_poses["cut_in_vehicle"].y_m == 3.5
    assert spec.layout.paths["cut_in_path"].points[-1].y_m == 0.0
    assert {band.id for band in spec.layout.road_bands} >= {
        "ego_driving_lane",
        "adjacent_same_direction_lane",
    }
    assert get_template("cut_in").capability.template_id == "cut_in"
    assert family_asset_readiness("cut_in").executable is True
    assert family_asset_readiness("cut_in").road_asset_ready is True


def test_cut_in_family_checks_pass_for_default_instance() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="cut_in"))

    by_name = {result.name: result for result in run_cut_in_checks(spec)}

    assert by_name["cut_in_starts_in_adjacent_lane"].passed is True
    assert by_name["cut_in_ends_in_ego_lane"].passed is True
    assert by_name["cut_in_path_crosses_into_ego_lane"].passed is True
    assert by_name["cut_in_trigger_timing"].passed is True


def test_cut_in_builder_binds_multilane_opendrive_and_follow_trajectory(tmp_path: Path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="cut_in"))

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")

    assert result.xodr_path == tmp_path / MULTI_LANE_SAME_DIRECTION_FILENAME
    assert result.xodr_path.exists()
    assert logic_file is not None
    assert logic_file.attrib["filepath"] == MULTI_LANE_SAME_DIRECTION_FILENAME
    assert root.find(".//ManeuverGroup[@name='cut_in_vehicle_lane_change']") is not None
    assert root.find(".//Action[@name='cut_in_vehicle_follow_cut_in_path']//FollowTrajectoryAction") is not None


def test_cut_in_artifact_consistency_checks_pass(tmp_path: Path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="cut_in"))
    build_result = build_openscenario(spec, tmp_path)

    results = run_artifact_consistency_checks(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    by_name = {result.name: result for result in results}

    assert set(by_name) == {
        "xosc_cut_in_actor_poses_match_layout",
        "xosc_cut_in_trajectory_matches_layout_path",
        "xosc_logic_file_is_relative",
        "xodr_logic_file_target_exists",
        "xosc_logic_file_matches_canonical_road",
    }
    assert all(result.passed for result in results)
