import pytest

from scenariocraft.core.checks import run_pedestrian_occlusion_checks
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import get_template
from scenariocraft.core.templates.resolver import resolve_scenario_intent, resolve_template_parameters


def test_templates_expose_parameter_capability_manifests() -> None:
    pedestrian = get_template("pedestrian_occlusion")
    lead = get_template("lead_vehicle_braking")

    assert pedestrian.capability.template_id == "pedestrian_occlusion"
    assert pedestrian.capability.interaction_family == "pedestrian_occlusion"
    assert "child emerges from behind van" in pedestrian.capability.aliases
    assert "crossing_actor" in pedestrian.capability.semantic_slots
    assert "ego_speed_kph" in pedestrian.capability.domain_map()
    assert "trigger_offset_m" in pedestrian.capability.domain_map()
    assert lead.capability.template_id == "lead_vehicle_braking"
    assert lead.capability.interaction_family == "lead_vehicle_braking"
    assert "hard braking lead vehicle" in lead.capability.aliases
    assert "lead_vehicle" in lead.capability.semantic_slots
    assert "initial_gap_m" in lead.capability.domain_map()
    assert "lead_deceleration_mps2" in lead.capability.domain_map()


def test_resolver_preserves_canonical_defaults_without_seed() -> None:
    intent = ScenarioIntent(template_id="pedestrian_occlusion")

    resolved = resolve_template_parameters(intent)
    spec = resolve_scenario_intent(intent)

    assert resolved.sampled is False
    assert resolved.seed is None
    assert resolved.values["ego_speed_kph"] == 35.0
    assert resolved.values["trigger_offset_m"] == 18.0
    assert spec.actor_by_id("ego").initial_speed_kph == 35.0
    assert spec.trigger.distance_m == 18.0
    assert spec.metadata["template_resolution"]["sampled"] is False


def test_resolver_generates_deterministic_seeded_variants() -> None:
    intent = ScenarioIntent(template_id="lead_vehicle_braking", metadata={"seed": 41})

    first = resolve_scenario_intent(intent)
    second = resolve_scenario_intent(intent)
    different = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking", metadata={"seed": 42}))

    assert first.to_dict() == second.to_dict()
    assert first.metadata["template_resolution"]["sampled"] is True
    assert first.layout is not None
    assert different.layout is not None
    assert first.layout.actor_poses["lead_vehicle"].x_m != different.layout.actor_poses["lead_vehicle"].x_m


def test_explicit_intent_parameters_override_sampling() -> None:
    intent = ScenarioIntent(
        template_id="lead_vehicle_braking",
        metadata={"seed": 123},
        parameters={"initial_gap_m": 31.0, "lead_deceleration_mps2": -6.0},
    )

    resolved = resolve_template_parameters(intent)
    spec = resolve_scenario_intent(intent)

    sources = {parameter.name: parameter.source for parameter in resolved.parameters}
    assert resolved.values["initial_gap_m"] == 31.0
    assert sources["initial_gap_m"] == "user"
    assert sources["lead_deceleration_mps2"] == "user"
    assert spec.layout is not None
    assert spec.layout.actor_poses["lead_vehicle"].x_m == 31.0
    assert spec.metadata["lead_vehicle_braking"]["lead_deceleration_mps2"] == -6.0


def test_intent_actor_weather_and_criticality_fields_feed_resolution() -> None:
    intent = ScenarioIntent(
        template_id="pedestrian_occlusion",
        weather={"condition": "clear_dry"},
        actors={
            "ego": {"speed_kph": 40.0},
            "pedestrian": {"speed_mps": 1.7},
        },
        criticality={"target_ttc_s": 2.1},
    )

    resolved = resolve_template_parameters(intent)
    spec = resolve_scenario_intent(intent)

    sources = {parameter.name: parameter.source for parameter in resolved.parameters}
    assert sources["ego_speed_kph"] == "intent"
    assert sources["pedestrian_speed_mps"] == "intent"
    assert sources["target_min_ttc_s"] == "intent"
    assert spec.actor_by_id("ego").initial_speed_kph == 40.0
    assert spec.actor_by_id("pedestrian").speed_mps == 1.7
    assert spec.weather.rain is False
    assert spec.intended_criticality.target_min_ttc_s == 2.1


def test_seeded_pedestrian_variants_still_pass_template_checks() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="pedestrian_occlusion", metadata={"seed": 7}))

    results = run_pedestrian_occlusion_checks(spec)

    assert results
    assert all(result.passed for result in results)


def test_out_of_domain_parameter_is_rejected() -> None:
    intent = ScenarioIntent(template_id="lead_vehicle_braking", parameters={"initial_gap_m": 3.0})

    with pytest.raises(ValueError, match="initial_gap_m"):
        resolve_scenario_intent(intent)
