from scenariocraft.generators import MockScenarioGenerator


def test_mock_generator_returns_rainy_pedestrian_occlusion_spec() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    assert spec.scenario_name == "rainy_pedestrian_occlusion"
    assert spec.weather.rain is True
    assert spec.actor_by_role("ego") is not None
    assert spec.actor_by_role("occluder") is not None
    assert spec.actor_by_role("crossing_actor") is not None
