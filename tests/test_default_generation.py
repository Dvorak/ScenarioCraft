from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec


def test_default_generation_returns_rainy_pedestrian_occlusion_spec() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    assert spec.scenario_name == "rainy_pedestrian_occlusion"
    assert spec.weather.rain is True
    assert spec.actor_by_role("ego") is not None
    assert spec.actor_by_role("occluder") is not None
    assert spec.actor_by_role("crossing_actor") is not None
    assert spec.timing is not None
    assert spec.timing.total_duration_s == 8.0
    assert spec.timing.preferred_trigger_earliest_s == 1.5
    assert spec.timing.preferred_trigger_latest_s == 3.0


def test_default_generation_passes_timing_window_overrides_to_template() -> None:
    spec = generate_default_pedestrian_occlusion_spec(
        "rainy pedestrian occlusion",
        total_duration_s=10.0,
        preferred_trigger_earliest_s=2.0,
        preferred_trigger_latest_s=4.0,
    )

    assert spec.timing is not None
    assert spec.timing.total_duration_s == 10.0
    assert spec.timing.preferred_trigger_earliest_s == 2.0
    assert spec.timing.preferred_trigger_latest_s == 4.0
