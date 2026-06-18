from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.roads import URBAN_TWO_WAY_PARKING_FILENAME
from scenariocraft.schemas import PathSpec, Point2D, Pose2D, TriggerSpec
from scenariocraft.tools import FallbackXmlScenarioBuilder, build_openscenario


def test_scenario_builder_creates_xosc_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path)

    assert result.xosc_path.exists()
    assert result.builder == "scenariogeneration"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"
    assert root.find(".//ScenarioObject[@name='ego']") is not None
    assert root.find(".//ScenarioObject[@name='pedestrian']") is not None


def test_canonical_layout_backed_builder_binds_portable_opendrive_logic_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")

    assert result.xodr_path == tmp_path / URBAN_TWO_WAY_PARKING_FILENAME
    assert result.xodr_path.exists()
    assert logic_file is not None
    assert logic_file.attrib["filepath"] == URBAN_TWO_WAY_PARKING_FILENAME
    assert not Path(logic_file.attrib["filepath"]).is_absolute()
    xosc_text = result.xosc_path.read_text(encoding="utf-8")
    assert str(tmp_path) not in xosc_text
    assert "/Users/" not in xosc_text


def test_fallback_xml_builder_binds_same_portable_opendrive_logic_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    root = ET.parse(result.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")

    assert result.xodr_path == tmp_path / URBAN_TWO_WAY_PARKING_FILENAME
    assert result.xodr_path.exists()
    assert logic_file is not None
    assert logic_file.attrib["filepath"] == URBAN_TWO_WAY_PARKING_FILENAME
    assert not Path(logic_file.attrib["filepath"]).is_absolute()
    assert str(tmp_path) not in result.xosc_path.read_text(encoding="utf-8")


def test_layout_backed_builder_uses_layout_initial_poses(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"] == (0.0, 0.0, 0.0)
    assert poses["parked_van"] == (20.0, 3.25, 0.0)
    assert poses["pedestrian"] == (25.0, 4.6, 0.0)
    assert poses["parked_van"] != (32.0, -3.5, 0.0)
    assert poses["pedestrian"] != (34.0, -5.5, 0.0)


def test_changing_layout_pose_changes_generated_xosc_pose(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None
    layout = replace(
        spec.layout,
        actor_poses={
            **spec.layout.actor_poses,
            "parked_van": Pose2D(18.5, 3.0, 0.25),
        },
    )
    changed_spec = replace(spec, layout=layout)

    result = build_openscenario(changed_spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["parked_van"] == (18.5, 3.0, 0.25)


def test_layout_backed_builder_preserves_relative_arrangement(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"][0] < poses["parked_van"][0] < spec.layout.points["conflict_point"].x_m
    assert poses["pedestrian"][0] == spec.layout.points["conflict_point"].x_m
    assert poses["pedestrian"][1] > poses["parked_van"][1] > poses["ego"][1]


def test_layout_free_builder_keeps_legacy_initial_pose_fallback(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    legacy_spec = replace(spec, layout=None, spatial_relations=())

    result = build_openscenario(legacy_spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"] == (0.0, 0.0, 0.0)
    assert poses["parked_van"] == (32.0, -3.5, 0.0)
    assert poses["pedestrian"] == (34.0, -5.5, 0.0)
    root = ET.parse(result.xosc_path).getroot()
    assert root.find(".//Action[@name='ego_follow_ego_path']") is None
    assert root.find(".//Action[@name='pedestrian_speed_action']") is not None
    assert result.xodr_path is None
    logic_file = root.find("./RoadNetwork/LogicFile")
    if logic_file is not None:
        assert logic_file.attrib["filepath"] == ""


def test_fallback_scenario_builder_creates_xosc_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())

    assert result.xosc_path.exists()
    assert result.builder == "fallback_xml"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"


def test_fallback_xml_builder_uses_layout_initial_poses(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"] == (0.0, 0.0, 0.0)
    assert poses["parked_van"] == (20.0, 3.25, 0.0)
    assert poses["pedestrian"] == (25.0, 4.6, 0.0)


def test_layout_backed_builder_serializes_pedestrian_crossing_trajectory(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    crossing_points = spec.layout.paths["pedestrian_crossing_path"].points
    assert poses["pedestrian"][:2] == (crossing_points[0].x_m, crossing_points[0].y_m)
    assert [(x, y) for _, x, y, _ in vertices] == [(point.x_m, point.y_m) for point in crossing_points]
    assert vertices[-1][1:] == (25.0, -1.0, 0.0)
    assert [time for time, _, _, _ in vertices] == [0.0, 3.733333333333333]
    root = ET.parse(result.xosc_path).getroot()
    assert root.find(".//Action[@name='pedestrian_follow_crossing_path']") is not None
    assert root.find(".//Action[@name='pedestrian_speed_action']") is None
    timing = root.find(".//Action[@name='pedestrian_follow_crossing_path']//TimeReference/Timing")
    assert timing is not None
    assert timing.attrib == {"domainAbsoluteRelative": "relative", "scale": "1.0", "offset": "0.0"}


def test_layout_backed_builder_serializes_ego_driving_trajectory(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    vertices = _trajectory_vertices(result.xosc_path, "ego_follow_ego_path")

    assert root.find(".//ManeuverGroup[@name='ego_driving']") is not None
    assert root.find(".//Event[@name='ego_drives_forward']") is not None
    assert root.find(".//Action[@name='ego_follow_ego_path']") is not None
    assert [(x, y) for _, x, y, _ in vertices] == [(0.0, 0.0), (60.0, 0.0)]
    assert vertices[-1][0] == 60.0 / (35.0 / 3.6)
    start_condition = root.find(".//Event[@name='ego_drives_forward']/StartTrigger//SimulationTimeCondition")
    assert start_condition is not None
    assert start_condition.attrib == {"value": "0.0", "rule": "greaterThan"}


def test_canonical_pedestrian_event_start_trigger_references_expected_actors_and_distance(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    condition = _pedestrian_relative_distance_condition(result.xosc_path)
    triggering_entity = root.find(
        ".//Event[@name='pedestrian_starts_crossing']/StartTrigger//TriggeringEntities/EntityRef"
    )

    assert triggering_entity is not None
    assert triggering_entity.attrib["entityRef"] == "ego"
    assert condition.attrib["entityRef"] == "parked_van"
    assert condition.attrib["relativeDistanceType"] == "longitudinal"
    assert condition.attrib["rule"] == "lessThan"
    assert float(condition.attrib["value"]) == 18.0
    time_condition = root.find(
        ".//Event[@name='pedestrian_starts_crossing']/StartTrigger"
        "//Condition[@name='relative_distance_time_alignment']/ByValueCondition/SimulationTimeCondition"
    )
    assert time_condition is not None
    assert float(time_condition.attrib["value"]) == (20.0 - 18.0) / (35.0 / 3.6)


def test_canonical_pedestrian_event_start_condition_is_reachable_before_stop(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    stop_condition = root.find(".//Storyboard/StopTrigger//SimulationTimeCondition")
    assert stop_condition is not None
    stop_time_s = float(stop_condition.attrib["value"])
    ego = spec.actor_by_role("ego")
    assert ego is not None and ego.initial_speed_kph is not None
    ego_speed_mps = ego.initial_speed_kph / 3.6
    trigger_x_m = spec.layout.actor_poses["parked_van"].x_m - spec.trigger.distance_m
    trigger_time_s = trigger_x_m / ego_speed_mps
    pedestrian_duration_s = _pedestrian_trajectory_vertices(result.xosc_path)[-1][0]

    assert 0.0 < trigger_time_s < stop_time_s
    assert trigger_time_s + pedestrian_duration_s < stop_time_s


def test_changing_trigger_distance_changes_generated_xosc_trigger_condition(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    changed_spec = replace(
        spec,
        trigger=TriggerSpec(
            type=spec.trigger.type,
            source=spec.trigger.source,
            target=spec.trigger.target,
            distance_m=12.5,
        ),
    )

    result = build_openscenario(changed_spec, tmp_path)
    condition = _pedestrian_relative_distance_condition(result.xosc_path)
    root = ET.parse(result.xosc_path).getroot()
    time_condition = root.find(
        ".//Event[@name='pedestrian_starts_crossing']/StartTrigger"
        "//Condition[@name='relative_distance_time_alignment']/ByValueCondition/SimulationTimeCondition"
    )

    assert float(condition.attrib["value"]) == 12.5
    assert time_condition is not None
    assert float(time_condition.attrib["value"]) == (20.0 - 12.5) / (35.0 / 3.6)


def test_changing_layout_path_endpoint_changes_generated_trajectory_endpoint(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None
    original_path = spec.layout.paths["pedestrian_crossing_path"]
    changed_path = PathSpec(
        original_path.name,
        (original_path.points[0], Point2D(25.0, -0.25)),
    )
    changed_layout = replace(
        spec.layout,
        paths={**spec.layout.paths, "pedestrian_crossing_path": changed_path},
    )
    changed_spec = replace(spec, layout=changed_layout)

    result = build_openscenario(changed_spec, tmp_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert vertices[-1][1:] == (25.0, -0.25, 0.0)


def test_layout_path_point_order_is_preserved_in_generated_trajectory(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None
    path = PathSpec(
        "pedestrian_crossing_path",
        (
            Point2D(25.0, 4.6),
            Point2D(25.5, 2.0),
            Point2D(25.0, -1.0),
        ),
    )
    layout = replace(spec.layout, paths={**spec.layout.paths, "pedestrian_crossing_path": path})

    result = build_openscenario(replace(spec, layout=layout), tmp_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert [(x, y) for _, x, y, _ in vertices] == [(25.0, 4.6), (25.5, 2.0), (25.0, -1.0)]
    assert [time for time, _, _, _ in vertices] == sorted(time for time, _, _, _ in vertices)


def test_path_free_builder_keeps_speed_action_only_fallback(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")
    assert spec.layout is not None
    path_free_layout = replace(
        spec.layout,
        paths={name: path for name, path in spec.layout.paths.items() if name != "pedestrian_crossing_path"},
    )

    result = build_openscenario(replace(spec, layout=path_free_layout), tmp_path)
    root = ET.parse(result.xosc_path).getroot()

    assert root.find(".//Action[@name='pedestrian_speed_action']") is not None
    assert root.find(".//Action[@name='pedestrian_follow_crossing_path']") is None


def test_fallback_xml_builder_serializes_pedestrian_crossing_trajectory(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert [(x, y) for _, x, y, _ in vertices] == [(25.0, 4.6), (25.0, -1.0)]


def test_fallback_xml_builder_serializes_ego_driving_trajectory(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    vertices = _trajectory_vertices(result.xosc_path, "ego_follow_ego_path")

    assert [(x, y) for _, x, y, _ in vertices] == [(0.0, 0.0), (60.0, 0.0)]


def _world_positions_by_entity(xosc_path) -> dict[str, tuple[float, float, float]]:
    root = ET.parse(xosc_path).getroot()
    poses: dict[str, tuple[float, float, float]] = {}
    for private in root.findall(".//Init/Actions/Private"):
        entity_ref = private.attrib["entityRef"]
        world_position = private.find(".//TeleportAction/Position/WorldPosition")
        assert world_position is not None
        poses[entity_ref] = (
            float(world_position.attrib["x"]),
            float(world_position.attrib["y"]),
            float(world_position.attrib["h"]),
        )
    return poses


def _pedestrian_trajectory_vertices(xosc_path) -> list[tuple[float, float, float, float]]:
    return _trajectory_vertices(xosc_path, "pedestrian_follow_crossing_path")


def _trajectory_vertices(xosc_path, action_name: str) -> list[tuple[float, float, float, float]]:
    root = ET.parse(xosc_path).getroot()
    vertices = []
    for vertex in root.findall(f".//Action[@name='{action_name}']//Polyline/Vertex"):
        world_position = vertex.find("./Position/WorldPosition")
        assert world_position is not None
        vertices.append((
            float(vertex.attrib["time"]),
            float(world_position.attrib["x"]),
            float(world_position.attrib["y"]),
            float(world_position.attrib["h"]),
        ))
    return vertices


def _pedestrian_relative_distance_condition(xosc_path) -> ET.Element:
    root = ET.parse(xosc_path).getroot()
    condition = root.find(".//Event[@name='pedestrian_starts_crossing']/StartTrigger//RelativeDistanceCondition")
    assert condition is not None
    return condition
