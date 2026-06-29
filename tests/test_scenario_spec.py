import json

import pytest

from scenariocraft.schemas import (
    ActorSpec,
    CriticalitySpec,
    FootprintSpec,
    LayoutSpec,
    PathSpec,
    Point2D,
    Pose2D,
    RoadBandSpec,
    RoadSpec,
    ScenarioSpec,
    ScenarioTimingSpec,
    SpatialRelationSpec,
    StoryboardActionSpec,
    StoryboardActSpec,
    StoryboardEventSpec,
    StoryboardManeuverGroupSpec,
    StoryboardSpec,
    StoryboardStorySpec,
    TriggerConditionSpec,
    TriggerSpec,
    WeatherSpec,
)
from scenariocraft.schemas.common import ScenarioSpecError


def test_scenario_spec_round_trip_json() -> None:
    spec = ScenarioSpec(
        scenario_name="rainy_pedestrian_occlusion",
        scenario_type="pedestrian_occlusion",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(True, "wet"),
        actors=[ActorSpec("ego", "car", "ego", initial_speed_kph=35)],
        trigger=TriggerSpec("relative_distance", "ego", "ego", 18),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
    )

    loaded = ScenarioSpec.from_json(spec.to_json())

    assert loaded.to_dict() == spec.to_dict()
    assert json.loads(spec.to_json())["scenario_name"] == "rainy_pedestrian_occlusion"
    assert loaded.layout is None
    assert loaded.spatial_relations == ()
    assert loaded.timing is None
    assert loaded.storyboard is None


def test_scenario_spec_loads_legacy_json_without_layout_or_spatial_relations() -> None:
    raw = json.dumps({
        "scenario_name": "legacy",
        "scenario_type": "pedestrian_occlusion",
        "road": {"type": "urban_straight", "lanes_per_direction": 1, "speed_limit_kph": 50},
        "weather": {"rain": True, "road_condition": "wet"},
        "actors": [{"id": "ego", "type": "car", "role": "ego"}],
        "trigger": {"type": "relative_distance", "source": "ego", "target": "ego", "distance_m": 18},
        "intended_criticality": {"type": "near_miss", "target_min_ttc_s": 1.5},
    })

    spec = ScenarioSpec.from_json(raw)

    assert spec.layout is None
    assert spec.spatial_relations == ()
    assert spec.timing is None
    assert spec.storyboard is None


def test_trigger_condition_round_trips_with_legacy_trigger_fields() -> None:
    spec = ScenarioSpec(
        scenario_name="semantic_trigger_demo",
        scenario_type="pedestrian_occlusion",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(True, "wet"),
        actors=[ActorSpec("ego", "car", "ego", initial_speed_kph=35)],
        trigger=TriggerSpec(
            "relative_distance",
            "ego",
            "parked_van",
            18,
            condition=TriggerConditionSpec(
                id="pedestrian_start_relative_distance",
                metric="relative_distance",
                source="ego",
                target="parked_van",
                rule="lessThan",
                value=18,
                unit="m",
                coordinate_system="entity",
                relative_distance_type="longitudinal",
                freespace=False,
                target_kind="entity",
            ),
        ),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
    )

    loaded = ScenarioSpec.from_json(spec.to_json())

    assert loaded == spec
    assert loaded.trigger.condition is not None
    assert loaded.trigger.condition.metric == "relative_distance"
    assert loaded.trigger.condition.value == 18


def test_ttc_and_thw_trigger_metrics_are_representable() -> None:
    ttc = TriggerConditionSpec(
        id="ego_ttc_to_conflict",
        metric="time_to_collision",
        source="ego",
        target="conflict_point",
        rule="lessThan",
        value=2.5,
        unit="s",
        target_kind="named_point",
        freespace=True,
    )
    thw = TriggerConditionSpec(
        id="ego_time_headway_to_lead_vehicle",
        metric="time_headway",
        source="ego",
        target="lead_vehicle",
        rule="lessThan",
        value=1.2,
        unit="s",
        target_kind="entity",
    )

    assert TriggerConditionSpec.from_dict(ttc.to_dict()) == ttc
    assert TriggerConditionSpec.from_dict(thw.to_dict()) == thw


def test_scenario_spec_round_trips_layout_and_spatial_relations() -> None:
    spec = ScenarioSpec(
        scenario_name="layout_demo",
        scenario_type="pedestrian_occlusion",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(True, "wet"),
        actors=[
            ActorSpec("ego", "car", "ego", initial_speed_kph=35),
            ActorSpec("parked_van", "van", "occluder", state="parked"),
            ActorSpec("pedestrian", "pedestrian", "crossing_actor", speed_mps=1.5),
        ],
        trigger=TriggerSpec("relative_distance", "ego", "parked_van", 18),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
        layout=LayoutSpec(
            coordinate_frame="ego_local",
            actor_poses={
                "ego": Pose2D(0.0, 0.0, 0.0),
                "parked_van": Pose2D(25.0, 2.8, 0.0),
            },
            actor_footprints={
                "ego": FootprintSpec(4.6, 1.9),
                "parked_van": FootprintSpec(5.3, 2.0),
            },
            paths={
                "pedestrian_crossing": PathSpec(
                    "pedestrian_crossing",
                    (Point2D(25.0, 5.5), Point2D(25.0, -1.0)),
                ),
            },
            points={
                "conflict_point": Point2D(25.0, 0.0),
                "trigger_point": Point2D(7.0, 0.0),
            },
            road_bands=(
                RoadBandSpec("ego_driving_lane", "driving_lane", -1.75, 1.75, "+x"),
                RoadBandSpec("ego_side_parking_strip", "parking_strip", 1.75, 4.25),
            ),
        ),
        spatial_relations=(
            SpatialRelationSpec(
                relation_type="occludes",
                subject="parked_van",
                object="pedestrian",
                metadata={"phase": "before_emergence"},
            ),
        ),
    )

    loaded = ScenarioSpec.from_json(spec.to_json())

    assert loaded == spec
    assert loaded.layout is not None
    assert loaded.layout.coordinate_frame == "ego_local"
    assert loaded.layout.actor_poses["parked_van"].x_m == 25.0
    assert loaded.layout.actor_poses["parked_van"].y_m == 2.8
    assert loaded.layout.actor_poses["parked_van"].heading_rad == 0.0
    assert loaded.layout.actor_footprints["parked_van"] == FootprintSpec(5.3, 2.0)
    assert loaded.layout.points["conflict_point"] == Point2D(25.0, 0.0)
    assert loaded.layout.paths["pedestrian_crossing"].points == (Point2D(25.0, 5.5), Point2D(25.0, -1.0))
    assert loaded.layout.road_bands == (
        RoadBandSpec("ego_driving_lane", "driving_lane", -1.75, 1.75, "+x"),
        RoadBandSpec("ego_side_parking_strip", "parking_strip", 1.75, 4.25),
    )
    assert loaded.spatial_relations[0].metadata == {"phase": "before_emergence"}


def test_scenario_spec_round_trips_timing_policy() -> None:
    spec = ScenarioSpec(
        scenario_name="timing_demo",
        scenario_type="pedestrian_occlusion",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(True, "wet"),
        actors=[ActorSpec("ego", "car", "ego", initial_speed_kph=35)],
        trigger=TriggerSpec("relative_distance", "ego", "ego", 18),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
        timing=ScenarioTimingSpec(
            total_duration_s=10.0,
            preferred_trigger_earliest_s=2.0,
            preferred_trigger_latest_s=4.0,
            minimum_pre_trigger_context_s=0.75,
            minimum_post_trigger_buffer_s=1.0,
        ),
    )

    loaded = ScenarioSpec.from_json(spec.to_json())

    assert loaded.timing == spec.timing
    assert loaded.to_dict()["timing"] == {
        "total_duration_s": 10.0,
        "preferred_trigger_earliest_s": 2.0,
        "preferred_trigger_latest_s": 4.0,
        "minimum_pre_trigger_context_s": 0.75,
        "minimum_post_trigger_buffer_s": 1.0,
    }


def test_scenario_spec_round_trips_lightweight_storyboard_semantics() -> None:
    storyboard = StoryboardSpec(
        stories=(StoryboardStorySpec("story", ("act",)),),
        acts=(StoryboardActSpec("act", ("group",), stop_trigger_ref="stop_after_8s"),),
        maneuver_groups=(StoryboardManeuverGroupSpec("group", ("pedestrian",), ("event",)),),
        events=(StoryboardEventSpec("event", "overwrite", "pedestrian_start_relative_distance", ("action",)),),
        actions=(
            StoryboardActionSpec(
                "action",
                "follow_trajectory",
                actor_refs=("pedestrian",),
                path_ref="pedestrian_crossing_path",
            ),
        ),
    )
    spec = ScenarioSpec(
        scenario_name="storyboard_demo",
        scenario_type="pedestrian_occlusion",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(True, "wet"),
        actors=[ActorSpec("pedestrian", "pedestrian", "crossing_actor", speed_mps=1.5)],
        trigger=TriggerSpec("relative_distance", "ego", "parked_van", 18),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
        storyboard=storyboard,
    )

    loaded = ScenarioSpec.from_json(spec.to_json())

    assert loaded.storyboard == storyboard
    assert loaded.to_dict()["storyboard"]["events"][0]["start_trigger_ref"] == "pedestrian_start_relative_distance"


def test_storyboard_rejects_dangling_references() -> None:
    with pytest.raises(ScenarioSpecError, match="unknown action"):
        StoryboardSpec(
            stories=(StoryboardStorySpec("story", ("act",)),),
            acts=(StoryboardActSpec("act", ("group",)),),
            maneuver_groups=(StoryboardManeuverGroupSpec("group", ("ego",), ("event",)),),
            events=(StoryboardEventSpec("event", "overwrite", "trigger", ("missing_action",)),),
            actions=(),
        )


def test_scenario_timing_rejects_invalid_values() -> None:
    with pytest.raises(ScenarioSpecError):
        ScenarioTimingSpec(total_duration_s=0.0)
    with pytest.raises(ScenarioSpecError):
        ScenarioTimingSpec(preferred_trigger_earliest_s=-0.1)
    with pytest.raises(ScenarioSpecError):
        ScenarioTimingSpec(preferred_trigger_earliest_s=3.0, preferred_trigger_latest_s=2.0)
    with pytest.raises(ScenarioSpecError):
        ScenarioTimingSpec(total_duration_s=3.0, preferred_trigger_latest_s=3.0)
    with pytest.raises(ScenarioSpecError):
        ScenarioTimingSpec(total_duration_s=float("nan"))


def test_layout_without_actor_footprints_remains_valid() -> None:
    layout = LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={"ego": Pose2D(0.0, 0.0)},
        paths={},
        points={},
    )

    assert layout.actor_footprints == {}
    assert LayoutSpec.from_dict(layout.to_dict()) == layout


def test_layout_without_road_bands_remains_valid() -> None:
    layout = LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={"ego": Pose2D(0.0, 0.0)},
        paths={},
        points={},
    )

    loaded = LayoutSpec.from_dict(layout.to_dict())

    assert layout.road_bands == ()
    assert loaded.road_bands == ()


def test_road_band_rejects_invalid_values() -> None:
    with pytest.raises(ScenarioSpecError):
        RoadBandSpec("", "driving_lane", -1.0, 1.0, "+x")
    with pytest.raises(ScenarioSpecError):
        RoadBandSpec("lane", "not_a_band", -1.0, 1.0)
    with pytest.raises(ScenarioSpecError):
        RoadBandSpec("lane", "driving_lane", 1.0, 1.0)
    with pytest.raises(ScenarioSpecError):
        RoadBandSpec("lane", "driving_lane", -1.0, 1.0, "north")


def test_footprint_rejects_invalid_dimensions() -> None:
    with pytest.raises(ScenarioSpecError):
        FootprintSpec(0.0, 1.0)
    with pytest.raises(ScenarioSpecError):
        FootprintSpec(1.0, -1.0)
    with pytest.raises(ScenarioSpecError):
        FootprintSpec(float("nan"), 1.0)
    with pytest.raises(ScenarioSpecError):
        FootprintSpec(1.0, 1.0, reference_point="front_axle")


def test_layout_rejects_empty_coordinate_frame() -> None:
    with pytest.raises(ScenarioSpecError):
        LayoutSpec(coordinate_frame="", actor_poses={}, paths={}, points={})


def test_spatial_relation_rejects_empty_relation_values() -> None:
    with pytest.raises(ScenarioSpecError):
        SpatialRelationSpec(relation_type="", subject="ego", object="pedestrian")


def test_scenario_spec_rejects_implausible_speed_limit() -> None:
    with pytest.raises(ScenarioSpecError):
        RoadSpec("urban_straight", 1, 500)
