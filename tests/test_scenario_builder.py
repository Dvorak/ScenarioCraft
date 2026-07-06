from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import resolve_scenario_intent
from scenariocraft.core.roads import URBAN_TWO_WAY_PARKING_FILENAME
from scenariocraft.core.schemas import (
    PathSpec,
    Point2D,
    Pose2D,
    StoryboardActionSpec,
    StoryboardActSpec,
    StoryboardEventSpec,
    StoryboardManeuverGroupSpec,
    StoryboardSpec,
    StoryboardStorySpec,
    TriggerConditionSpec,
    TriggerSpec,
)
from scenariocraft.core.build import FallbackXmlScenarioBuilder, ScenariogenerationBuilder, build_openscenario


DEFAULT_EGO_SPEED_MPS = 35.0 / 3.6
DEFAULT_TRIGGER_DISTANCE_M = 18.0
DEFAULT_TRIGGER_TIME_S = 3.0
DEFAULT_VAN_X_M = DEFAULT_EGO_SPEED_MPS * DEFAULT_TRIGGER_TIME_S + DEFAULT_TRIGGER_DISTANCE_M
DEFAULT_CONFLICT_X_M = DEFAULT_VAN_X_M + 5.0


def test_scenario_builder_creates_xosc_file(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path)

    assert result.xosc_path.exists()
    assert result.builder == "scenariogeneration"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"
    assert root.find(".//ScenarioObject[@name='ego']") is not None
    assert root.find(".//ScenarioObject[@name='pedestrian']") is not None


def test_canonical_layout_backed_builder_binds_portable_opendrive_logic_file(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

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
    spec = generate_default_pedestrian_occlusion_spec("scenario")

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
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"] == (0.0, 0.0, 0.0)
    assert poses["parked_van"] == (DEFAULT_VAN_X_M, 3.25, 0.0)
    assert poses["pedestrian"] == (DEFAULT_CONFLICT_X_M, 4.6, 0.0)
    assert poses["parked_van"] != (32.0, -3.5, 0.0)
    assert poses["pedestrian"] != (34.0, -5.5, 0.0)


def test_changing_layout_pose_changes_generated_xosc_pose(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
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
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"][0] < poses["parked_van"][0] < spec.layout.points["conflict_point"].x_m
    assert poses["pedestrian"][0] == spec.layout.points["conflict_point"].x_m
    assert poses["pedestrian"][1] > poses["parked_van"][1] > poses["ego"][1]


def test_layout_free_builder_keeps_legacy_initial_pose_fallback(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    legacy_spec = replace(spec, layout=None, spatial_relations=(), timing=None)

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
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())

    assert result.xosc_path.exists()
    assert result.builder == "fallback_xml"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"


def test_fallback_xml_builder_uses_layout_initial_poses(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    poses = _world_positions_by_entity(result.xosc_path)

    assert poses["ego"] == (0.0, 0.0, 0.0)
    assert poses["parked_van"] == (DEFAULT_VAN_X_M, 3.25, 0.0)
    assert poses["pedestrian"] == (DEFAULT_CONFLICT_X_M, 4.6, 0.0)


def test_layout_backed_builder_serializes_pedestrian_crossing_trajectory(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    crossing_points = spec.layout.paths["pedestrian_crossing_path"].points
    assert poses["pedestrian"][:2] == (crossing_points[0].x_m, crossing_points[0].y_m)
    assert [(x, y) for _, x, y, _ in vertices] == [(point.x_m, point.y_m) for point in crossing_points]
    assert vertices[-1][1:] == (DEFAULT_CONFLICT_X_M, -1.0, 0.0)
    assert [time for time, _, _, _ in vertices] == [0.0, 3.733333333333333]
    root = ET.parse(result.xosc_path).getroot()
    assert root.find(".//Action[@name='pedestrian_follow_crossing_path']") is not None
    assert root.find(".//Action[@name='pedestrian_speed_action']") is None
    timing = root.find(".//Action[@name='pedestrian_follow_crossing_path']//TimeReference/Timing")
    assert timing is not None
    assert timing.attrib == {"domainAbsoluteRelative": "relative", "scale": "1.0", "offset": "0.0"}


def test_layout_backed_builder_serializes_ego_driving_trajectory(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    vertices = _trajectory_vertices(result.xosc_path, "ego_follow_ego_path")

    assert root.find(".//ManeuverGroup[@name='ego_driving']") is not None
    assert root.find(".//Event[@name='ego_drives_forward']") is not None
    assert root.find(".//Action[@name='ego_follow_ego_path']") is not None
    assert [(x, y) for _, x, y, _ in vertices] == [(0.0, 0.0), (DEFAULT_CONFLICT_X_M + 35.0, 0.0)]
    assert vertices[-1][0] == (DEFAULT_CONFLICT_X_M + 35.0) / (35.0 / 3.6)
    start_condition = root.find(".//Event[@name='ego_drives_forward']/StartTrigger//SimulationTimeCondition")
    assert start_condition is not None
    assert start_condition.attrib == {"value": "0.0", "rule": "greaterThan"}


def test_canonical_pedestrian_event_start_trigger_references_expected_actors_and_distance(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

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
    assert float(time_condition.attrib["value"]) == DEFAULT_TRIGGER_TIME_S


def test_canonical_pedestrian_start_trigger_uses_separate_or_condition_groups(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    start_trigger = root.find(".//Event[@name='pedestrian_starts_crossing']/StartTrigger")
    assert start_trigger is not None
    condition_groups = start_trigger.findall("./ConditionGroup")

    assert len(condition_groups) == 2
    assert condition_groups[0].find(".//RelativeDistanceCondition") is not None
    assert condition_groups[0].find(".//SimulationTimeCondition") is None
    assert condition_groups[1].find(".//RelativeDistanceCondition") is None
    assert condition_groups[1].find(".//SimulationTimeCondition") is not None


def test_physical_trigger_diagnostic_variant_omits_timing_alignment_condition(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(
        spec,
        tmp_path,
        builder=ScenariogenerationBuilder(include_timing_alignment_trigger=False),
    )
    root = ET.parse(result.xosc_path).getroot()
    start_trigger = root.find(".//Event[@name='pedestrian_starts_crossing']/StartTrigger")
    assert start_trigger is not None
    condition_groups = start_trigger.findall("./ConditionGroup")

    assert len(condition_groups) == 1
    assert condition_groups[0].find(".//RelativeDistanceCondition") is not None
    assert start_trigger.find(".//Condition[@name='relative_distance_time_alignment']") is None


def test_expected_physical_relative_distance_crossing_time_uses_actual_geometry(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None
    ego = spec.actor_by_id(spec.trigger.source)
    assert ego is not None and ego.initial_speed_kph is not None

    result = build_openscenario(spec, tmp_path)
    poses = _world_positions_by_entity(result.xosc_path)
    initial_longitudinal_distance_m = poses[spec.trigger.target][0] - poses[spec.trigger.source][0]
    ego_speed_mps = ego.initial_speed_kph / 3.6
    predicted_crossing_time_s = (initial_longitudinal_distance_m - spec.trigger.distance_m) / ego_speed_mps

    assert initial_longitudinal_distance_m == DEFAULT_VAN_X_M
    assert predicted_crossing_time_s == DEFAULT_TRIGGER_TIME_S


def test_canonical_pedestrian_event_start_condition_is_reachable_before_stop(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None
    assert spec.timing is not None

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    stop_condition = root.find(".//Storyboard/StopTrigger//SimulationTimeCondition")
    assert stop_condition is not None
    stop_time_s = float(stop_condition.attrib["value"])
    trigger_x_m = spec.layout.actor_poses["parked_van"].x_m - spec.trigger.distance_m
    trigger_time_s = trigger_x_m / DEFAULT_EGO_SPEED_MPS
    pedestrian_duration_s = _pedestrian_trajectory_vertices(result.xosc_path)[-1][0]

    assert 0.0 < trigger_time_s < stop_time_s
    assert trigger_time_s + pedestrian_duration_s < stop_time_s


def test_changing_trigger_distance_changes_generated_xosc_trigger_condition(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
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
    assert float(time_condition.attrib["value"]) == (DEFAULT_VAN_X_M - 12.5) / DEFAULT_EGO_SPEED_MPS


def test_ttc_trigger_condition_builds_xosc_time_to_collision_condition(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    changed_spec = replace(
        spec,
        trigger=TriggerSpec(
            type=spec.trigger.type,
            source=spec.trigger.source,
            target=spec.trigger.target,
            distance_m=spec.trigger.distance_m,
            condition=TriggerConditionSpec(
                id="ego_ttc_to_conflict",
                metric="time_to_collision",
                source="ego",
                target="conflict_point",
                rule="lessThan",
                value=2.5,
                unit="s",
                target_kind="named_point",
                freespace=True,
            ),
        ),
    )

    result = build_openscenario(changed_spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    condition = root.find(
        ".//Event[@name='pedestrian_starts_crossing']/StartTrigger"
        "//Condition[@name='ego_ttc_to_conflict']/ByEntityCondition/EntityCondition/TimeToCollisionCondition"
    )

    assert condition is not None
    world_position = condition.find("./TimeToCollisionConditionTarget/Position/WorldPosition")
    assert condition.attrib["value"] == "2.5"
    assert condition.attrib["rule"] == "lessThan"
    assert condition.attrib["freespace"] == "true"
    assert world_position is not None
    assert float(world_position.attrib["x"]) == DEFAULT_CONFLICT_X_M
    assert float(world_position.attrib["y"]) == 0.0
    assert root.find(".//Event[@name='pedestrian_starts_crossing']/StartTrigger//RelativeDistanceCondition") is None
    assert root.find(".//Condition[@name='relative_distance_time_alignment']") is None


def test_fallback_builder_builds_ttc_condition_with_entity_target(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    changed_spec = replace(
        spec,
        trigger=TriggerSpec(
            type=spec.trigger.type,
            source=spec.trigger.source,
            target=spec.trigger.target,
            distance_m=spec.trigger.distance_m,
            condition=TriggerConditionSpec(
                id="ego_ttc_to_van",
                metric="time_to_collision",
                source="ego",
                target="parked_van",
                rule="lessThan",
                value=1.25,
                unit="s",
                target_kind="entity",
                freespace=True,
            ),
        ),
    )

    result = build_openscenario(changed_spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    root = ET.parse(result.xosc_path).getroot()
    condition = root.find(".//Condition[@name='ego_ttc_to_van']//TimeToCollisionCondition")

    assert condition is not None
    entity_ref = condition.find("./TimeToCollisionConditionTarget/EntityRef")
    assert condition.attrib["value"] == "1.25"
    assert entity_ref is not None
    assert entity_ref.attrib["entityRef"] == "parked_van"


def test_timing_policy_changes_generated_stop_and_nominal_alignment_condition(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec(
        "scenario",
        total_duration_s=10.0,
        preferred_trigger_earliest_s=2.0,
        preferred_trigger_latest_s=4.0,
    )

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    poses = _world_positions_by_entity(result.xosc_path)
    stop_condition = root.find(".//Storyboard/StopTrigger//SimulationTimeCondition")
    time_condition = root.find(
        ".//Event[@name='pedestrian_starts_crossing']/StartTrigger"
        "//Condition[@name='relative_distance_time_alignment']/ByValueCondition/SimulationTimeCondition"
    )

    assert stop_condition is not None
    assert float(stop_condition.attrib["value"]) == 10.0
    assert poses["parked_van"][0] == DEFAULT_EGO_SPEED_MPS * 4.0 + DEFAULT_TRIGGER_DISTANCE_M
    assert time_condition is not None
    assert float(time_condition.attrib["value"]) == 4.0


def test_changing_layout_path_endpoint_changes_generated_trajectory_endpoint(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None
    original_path = spec.layout.paths["pedestrian_crossing_path"]
    changed_path = PathSpec(
        original_path.name,
        (original_path.points[0], Point2D(original_path.points[0].x_m, -0.25)),
    )
    changed_layout = replace(
        spec.layout,
        paths={**spec.layout.paths, "pedestrian_crossing_path": changed_path},
    )
    changed_spec = replace(spec, layout=changed_layout)

    result = build_openscenario(changed_spec, tmp_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert vertices[-1][1:] == (DEFAULT_CONFLICT_X_M, -0.25, 0.0)


def test_layout_path_point_order_is_preserved_in_generated_trajectory(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None
    path = PathSpec(
        "pedestrian_crossing_path",
        (
            Point2D(DEFAULT_CONFLICT_X_M, 4.6),
            Point2D(DEFAULT_CONFLICT_X_M + 0.5, 2.0),
            Point2D(DEFAULT_CONFLICT_X_M, -1.0),
        ),
    )
    layout = replace(spec.layout, paths={**spec.layout.paths, "pedestrian_crossing_path": path})

    result = build_openscenario(replace(spec, layout=layout), tmp_path)
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert [(x, y) for _, x, y, _ in vertices] == [
        (DEFAULT_CONFLICT_X_M, 4.6),
        (DEFAULT_CONFLICT_X_M + 0.5, 2.0),
        (DEFAULT_CONFLICT_X_M, -1.0),
    ]
    assert [time for time, _, _, _ in vertices] == sorted(time for time, _, _, _ in vertices)


def test_path_free_builder_keeps_speed_action_only_fallback(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
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
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    vertices = _pedestrian_trajectory_vertices(result.xosc_path)

    assert [(x, y) for _, x, y, _ in vertices] == [(DEFAULT_CONFLICT_X_M, 4.6), (DEFAULT_CONFLICT_X_M, -1.0)]


def test_fallback_xml_builder_serializes_ego_driving_trajectory(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    vertices = _trajectory_vertices(result.xosc_path, "ego_follow_ego_path")

    assert [(x, y) for _, x, y, _ in vertices] == [(0.0, 0.0), (DEFAULT_CONFLICT_X_M + 35.0, 0.0)]


def test_builder_serializes_lead_vehicle_braking_speed_action(tmp_path) -> None:
    spec = resolve_scenario_intent(
        ScenarioIntent(
            template_id="lead_vehicle_braking",
            parameters={
                "initial_gap_m": 30.0,
                "reaction_point_x_m": 12.0,
                "lead_deceleration_mps2": -6.0,
            },
        )
    )

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()

    event = root.find(".//Event[@name='lead_vehicle_starts_braking']")
    assert event is not None
    assert root.find(".//ManeuverGroup[@name='lead_vehicle_braking']/Actors/EntityRef[@entityRef='lead_vehicle']") is not None
    speed_action = root.find(".//Action[@name='lead_vehicle_brakes']//SpeedAction")
    assert speed_action is not None
    dynamics = speed_action.find("./SpeedActionDynamics")
    assert dynamics is not None
    assert dynamics.attrib["dynamicsShape"] == "linear"
    assert dynamics.attrib["dynamicsDimension"] == "rate"
    assert dynamics.attrib["value"] == "6.0"
    target_speed = speed_action.find("./SpeedActionTarget/AbsoluteTargetSpeed")
    assert target_speed is not None
    assert target_speed.attrib["value"] == "0.0"
    condition = root.find(".//Event[@name='lead_vehicle_starts_braking']/StartTrigger//RelativeDistanceCondition")
    assert condition is not None
    assert condition.attrib["entityRef"] == "lead_vehicle"
    assert condition.attrib["value"] == "18.0"


def test_builder_binds_lead_vehicle_braking_to_opendrive_logic_file(tmp_path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()
    logic_file = root.find("./RoadNetwork/LogicFile")

    assert result.xodr_path == tmp_path / URBAN_TWO_WAY_PARKING_FILENAME
    assert result.xodr_path.exists()
    assert logic_file is not None
    assert logic_file.attrib["filepath"] == URBAN_TWO_WAY_PARKING_FILENAME
    assert not Path(logic_file.attrib["filepath"]).is_absolute()


def test_fallback_builder_serializes_lead_vehicle_braking_speed_action(tmp_path) -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    root = ET.parse(result.xosc_path).getroot()

    assert root.find(".//Event[@name='lead_vehicle_starts_braking']") is not None
    assert root.find(".//Action[@name='lead_vehicle_brakes']//SpeedAction") is not None
    assert root.find(".//Action[@name='pedestrian_speed_action']") is None


def test_builder_consumes_storyboard_ids_for_xosc_hierarchy(tmp_path) -> None:
    spec = _storyboard_renamed_spec()

    result = build_openscenario(spec, tmp_path)
    root = ET.parse(result.xosc_path).getroot()

    assert root.find(".//Story[@name='story_from_spec']") is not None
    assert root.find(".//Act[@name='act_from_spec']") is not None
    assert root.find(".//ManeuverGroup[@name='ego_group_from_spec']") is not None
    assert root.find(".//Event[@name='ego_event_from_spec']") is not None
    assert root.find(".//Action[@name='ego_action_from_spec']") is not None
    assert root.find(".//ManeuverGroup[@name='ped_group_from_spec']") is not None
    assert root.find(".//Event[@name='ped_event_from_spec']") is not None
    assert root.find(".//Action[@name='ped_action_from_spec']") is not None
    assert root.find(".//Condition[@name='ped_trigger_from_spec']") is not None
    assert root.find(".//Storyboard/StopTrigger//Condition[@name='stop_from_spec']") is not None


def test_builder_consumes_storyboard_action_path_ref(tmp_path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    assert spec.layout is not None
    alt_path = PathSpec(
        "alternate_crossing_path",
        (
            Point2D(DEFAULT_CONFLICT_X_M + 2.0, 4.6),
            Point2D(DEFAULT_CONFLICT_X_M + 2.0, -1.0),
        ),
    )
    layout = replace(spec.layout, paths={**spec.layout.paths, "alternate_crossing_path": alt_path})
    storyboard = StoryboardSpec(
        stories=(StoryboardStorySpec("story_from_spec", ("act_from_spec",)),),
        acts=(StoryboardActSpec("act_from_spec", ("ped_group_from_spec",)),),
        maneuver_groups=(
            StoryboardManeuverGroupSpec("ped_group_from_spec", ("pedestrian",), ("ped_event_from_spec",)),
        ),
        events=(
            StoryboardEventSpec(
                "ped_event_from_spec",
                "overwrite",
                "ped_trigger_from_spec",
                ("ped_action_from_spec",),
            ),
        ),
        actions=(
            StoryboardActionSpec(
                "ped_action_from_spec",
                "follow_trajectory",
                actor_refs=("pedestrian",),
                path_ref="alternate_crossing_path",
            ),
        ),
    )

    result = build_openscenario(replace(spec, layout=layout, storyboard=storyboard), tmp_path)
    vertices = _trajectory_vertices(result.xosc_path, "ped_action_from_spec")

    assert [(x, y) for _, x, y, _ in vertices] == [
        (DEFAULT_CONFLICT_X_M + 2.0, 4.6),
        (DEFAULT_CONFLICT_X_M + 2.0, -1.0),
    ]
    assert _trajectory_vertices(result.xosc_path, "pedestrian_follow_crossing_path") == []


def test_fallback_builder_consumes_storyboard_ids_for_xosc_hierarchy(tmp_path) -> None:
    spec = _storyboard_renamed_spec()

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())
    root = ET.parse(result.xosc_path).getroot()

    assert root.find(".//Story[@name='story_from_spec']") is not None
    assert root.find(".//Act[@name='act_from_spec']") is not None
    assert root.find(".//Event[@name='ped_event_from_spec']") is not None
    assert root.find(".//Action[@name='ped_action_from_spec']") is not None
    assert root.find(".//Condition[@name='ped_trigger_from_spec']") is not None


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


def _storyboard_renamed_spec():
    spec = generate_default_pedestrian_occlusion_spec("scenario")
    storyboard = StoryboardSpec(
        stories=(StoryboardStorySpec("story_from_spec", ("act_from_spec",)),),
        acts=(StoryboardActSpec("act_from_spec", ("ego_group_from_spec", "ped_group_from_spec"), "stop_from_spec"),),
        maneuver_groups=(
            StoryboardManeuverGroupSpec("ego_group_from_spec", ("ego",), ("ego_event_from_spec",)),
            StoryboardManeuverGroupSpec("ped_group_from_spec", ("pedestrian",), ("ped_event_from_spec",)),
        ),
        events=(
            StoryboardEventSpec("ego_event_from_spec", "overwrite", "ego_trigger_from_spec", ("ego_action_from_spec",)),
            StoryboardEventSpec("ped_event_from_spec", "overwrite", "ped_trigger_from_spec", ("ped_action_from_spec",)),
        ),
        actions=(
            StoryboardActionSpec(
                "ego_action_from_spec",
                "follow_trajectory",
                actor_refs=("ego",),
                path_ref="ego_path",
            ),
            StoryboardActionSpec(
                "ped_action_from_spec",
                "follow_trajectory",
                actor_refs=("pedestrian",),
                path_ref="pedestrian_crossing_path",
            ),
        ),
    )
    return replace(spec, storyboard=storyboard)
