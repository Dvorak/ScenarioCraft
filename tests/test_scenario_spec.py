import json

import pytest

from scenariocraft.schemas import ActorSpec, CriticalitySpec, RoadSpec, ScenarioSpec, TriggerSpec, WeatherSpec
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


def test_scenario_spec_rejects_implausible_speed_limit() -> None:
    with pytest.raises(ScenarioSpecError):
        RoadSpec("urban_straight", 1, 500)
