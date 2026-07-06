from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec, resolve_scenario_intent
from scenariocraft.core.checks import run_artifact_consistency_checks
from scenariocraft.core.build import BuildResult, build_openscenario

EXPECTED_CHECK_NAMES = [
    "xosc_actor_poses_match_layout",
    "xosc_pedestrian_trajectory_matches_layout_path",
    "xosc_logic_file_is_relative",
    "xodr_logic_file_target_exists",
    "xosc_logic_file_matches_canonical_road",
]


@pytest.fixture
def canonical_artifacts(tmp_path: Path):
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    build_result = build_openscenario(spec, tmp_path / "canonical")
    return spec, build_result


def test_canonical_artifact_consistency_checks_all_pass(canonical_artifacts) -> None:
    spec, build_result = canonical_artifacts

    results = run_artifact_consistency_checks(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )

    assert [result.name for result in results] == EXPECTED_CHECK_NAMES
    assert len(results) == 5
    assert all(result.passed for result in results)
    assert {result.severity for result in results} == {"note"}
    assert {result.category for result in results} == {"artifact_consistency"}
    assert {result.intent_relation for result in results} == {"not_applicable"}


def test_mutated_actor_world_position_fails_pose_check(canonical_artifacts, tmp_path: Path) -> None:
    spec, build_result = canonical_artifacts
    copied = _copy_artifacts(build_result, tmp_path / "mutated_pose")
    root = ET.parse(copied.xosc_path).getroot()
    world_position = root.find(".//Init/Actions/Private[@entityRef='ego']//TeleportAction/Position/WorldPosition")
    assert world_position is not None
    world_position.attrib["x"] = str(float(world_position.attrib["x"]) + 1.0)
    ET.ElementTree(root).write(copied.xosc_path, encoding="utf-8", xml_declaration=True)

    result = _result(spec, copied, "xosc_actor_poses_match_layout")

    assert result.passed is False
    assert result.severity == "repairable"
    assert result.category == "artifact_consistency"
    assert result.intent_relation == "not_applicable"
    assert result.repair_action == "none"
    assert result.measured["actor_id"] == ["ego", "parked_van", "pedestrian"]
    assert result.measured["position_error_m"]["ego"] == 1.0
    assert result.suggested_operations[0]["op"] == "rebuild_artifacts"


def test_mutated_pedestrian_vertex_fails_trajectory_check(canonical_artifacts, tmp_path: Path) -> None:
    spec, build_result = canonical_artifacts
    copied = _copy_artifacts(build_result, tmp_path / "mutated_trajectory")
    root = ET.parse(copied.xosc_path).getroot()
    vertex = root.find(
        ".//Action[@name='pedestrian_follow_crossing_path']"
        "//FollowTrajectoryAction//Polyline/Vertex/Position/WorldPosition"
    )
    assert vertex is not None
    vertex.attrib["y"] = str(float(vertex.attrib["y"]) + 0.75)
    ET.ElementTree(root).write(copied.xosc_path, encoding="utf-8", xml_declaration=True)

    result = _result(spec, copied, "xosc_pedestrian_trajectory_matches_layout_path")

    assert result.passed is False
    assert result.measured["expected_vertex_count"] == 2
    assert result.measured["observed_vertex_count"] == 2
    assert result.measured["maximum_position_error_m"] == 0.75
    assert result.measured["time_attributes_parseable"] is True


def test_absolute_logic_file_path_fails_relative_check(canonical_artifacts, tmp_path: Path) -> None:
    spec, build_result = canonical_artifacts
    copied = _copy_artifacts(build_result, tmp_path / "absolute_logic_file")
    root = ET.parse(copied.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")
    assert logic_file is not None and copied.xodr_path is not None
    logic_file.attrib["filepath"] = str(copied.xodr_path.resolve())
    ET.ElementTree(root).write(copied.xosc_path, encoding="utf-8", xml_declaration=True)

    result = _result(spec, copied, "xosc_logic_file_is_relative")

    assert result.passed is False
    assert result.measured["is_relative"] is False
    assert Path(result.measured["logic_file_path"]).is_absolute()


def test_missing_logic_file_target_fails_exists_check(canonical_artifacts, tmp_path: Path) -> None:
    spec, build_result = canonical_artifacts
    copied = _copy_artifacts(build_result, tmp_path / "missing_logic_file")
    root = ET.parse(copied.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")
    assert logic_file is not None
    logic_file.attrib["filepath"] = "missing.xodr"
    ET.ElementTree(root).write(copied.xosc_path, encoding="utf-8", xml_declaration=True)

    result = _result(spec, copied, "xodr_logic_file_target_exists")

    assert result.passed is False
    assert result.measured["logic_file_path"] == "missing.xodr"
    assert result.measured["target_exists"] is False
    assert result.suggested_operations[0]["op"] == "materialize_canonical_road_asset"


def test_other_logic_file_basename_fails_canonical_road_check(canonical_artifacts, tmp_path: Path) -> None:
    spec, build_result = canonical_artifacts
    copied = _copy_artifacts(build_result, tmp_path / "other_logic_file")
    assert copied.xodr_path is not None
    other_xodr = copied.xodr_path.with_name("other_road.xodr")
    shutil.copy2(copied.xodr_path, other_xodr)
    root = ET.parse(copied.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")
    assert logic_file is not None
    logic_file.attrib["filepath"] = other_xodr.name
    ET.ElementTree(root).write(copied.xosc_path, encoding="utf-8", xml_declaration=True)
    other_build = replace(copied, xodr_path=other_xodr)

    result = _result(spec, other_build, "xosc_logic_file_matches_canonical_road")

    assert result.passed is False
    assert result.measured["expected_basename"] == "urban_two_way_parking.xodr"
    assert result.measured["observed_basename"] == "other_road.xodr"


def test_layout_free_spec_returns_no_artifact_consistency_checks(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    layout_free_spec = replace(spec, layout=None, spatial_relations=(), timing=None)

    results = run_artifact_consistency_checks(
        layout_free_spec,
        xosc_path=tmp_path / "not_built.xosc",
        xodr_path=None,
    )

    assert results == ()


def test_lead_vehicle_braking_artifact_consistency_checks_pass(tmp_path: Path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))
    build_result = build_openscenario(spec, tmp_path / "lead_braking")

    results = run_artifact_consistency_checks(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    by_name = {result.name: result for result in results}

    assert set(by_name) == {
        "xosc_lead_actor_poses_match_layout",
        "xosc_lead_braking_action_present",
        "xosc_lead_braking_trigger_matches_spec",
        "xosc_logic_file_is_relative",
        "xodr_logic_file_target_exists",
        "xosc_logic_file_matches_canonical_road",
    }
    assert all(result.passed for result in results)
    assert by_name["xosc_lead_braking_action_present"].measured["action_name"] == "lead_vehicle_brakes"
    assert by_name["xosc_lead_braking_trigger_matches_spec"].measured["trigger_distance_m"] == spec.trigger.distance_m


def _copy_artifacts(build_result: BuildResult, destination: Path) -> BuildResult:
    destination.mkdir(parents=True)
    xosc_path = destination / build_result.xosc_path.name
    shutil.copy2(build_result.xosc_path, xosc_path)
    xodr_path = None
    if build_result.xodr_path is not None:
        xodr_path = destination / build_result.xodr_path.name
        shutil.copy2(build_result.xodr_path, xodr_path)
    return BuildResult(xosc_path=xosc_path, xodr_path=xodr_path, builder=build_result.builder)


def _result(spec, build_result: BuildResult, name: str):
    results = run_artifact_consistency_checks(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    return next(result for result in results if result.name == name)
