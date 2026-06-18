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
    SpatialRelationSpec,
    TriggerSpec,
    WeatherSpec,
)
from scenariocraft.schemas.scenario_spec import ScenarioSpecError


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
