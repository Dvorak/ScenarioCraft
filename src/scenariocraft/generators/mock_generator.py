from __future__ import annotations

from scenariocraft.generators.base import ScenarioGenerator
from scenariocraft.schemas import ActorSpec, CriticalitySpec, RoadSpec, ScenarioSpec, TriggerSpec, WeatherSpec


class MockScenarioGenerator(ScenarioGenerator):
    """Deterministic generator for the pedestrian occlusion scenario."""

    def generate_spec(self, scenario_text: str) -> ScenarioSpec:
        return ScenarioSpec(
            scenario_name="rainy_pedestrian_occlusion",
            scenario_type="pedestrian_occlusion",
            road=RoadSpec(type="urban_straight", lanes_per_direction=1, speed_limit_kph=50),
            weather=WeatherSpec(rain=True, road_condition="wet"),
            actors=[
                ActorSpec(id="ego", type="car", role="ego", initial_speed_kph=35),
                ActorSpec(id="parked_van", type="van", role="occluder", state="parked"),
                ActorSpec(id="pedestrian", type="pedestrian", role="crossing_actor", speed_mps=1.5),
            ],
            trigger=TriggerSpec(type="relative_distance", source="ego", target="parked_van", distance_m=18),
            intended_criticality=CriticalitySpec(type="near_miss", target_min_ttc_s=1.5),
            metadata={"generator": "mock", "source_text": scenario_text},
        )
