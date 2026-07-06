import pytest

from scenariocraft.core.schemas import ScenarioIntent, ScenarioIntentError, ScenarioSpec
from scenariocraft.core.templates.resolver import resolve_scenario_intent


def test_scenario_intent_round_trips_structured_payload() -> None:
    intent = ScenarioIntent.from_dict(
        {
            "template_id": "pedestrian_occlusion",
            "road_context": {"road_type": "urban_straight"},
            "weather": {"condition": "rainy_wet"},
            "actors": {
                "ego": {"type": "car", "speed_kph": 35.0},
                "pedestrian": {"type": "pedestrian", "speed_mps": 1.5},
            },
            "criticality": {"target_ttc_s": 1.5},
            "parameters": {"scenario_name": "round_trip_pedestrian_occlusion"},
        }
    )

    assert intent.template_id == "pedestrian_occlusion"
    assert intent.actor("ego")["speed_kph"] == 35.0
    assert ScenarioIntent.from_json(intent.to_json()) == intent


def test_scenario_intent_rejects_invalid_required_fields() -> None:
    with pytest.raises(ScenarioIntentError, match="template_id"):
        ScenarioIntent.from_dict({"actors": {}})

    with pytest.raises(ScenarioIntentError, match="actors must be an object"):
        ScenarioIntent.from_dict({"template_id": "pedestrian_occlusion", "actors": []})


def test_resolver_maps_pedestrian_occlusion_intent_to_existing_template() -> None:
    intent = ScenarioIntent(
        template_id="pedestrian_occlusion",
        actors={"ego": {"speed_kph": 35.0}},
        parameters={"scenario_name": "resolved_pedestrian_occlusion"},
    )

    spec = resolve_scenario_intent(intent)

    assert isinstance(spec, ScenarioSpec)
    assert spec.scenario_name == "resolved_pedestrian_occlusion"
    assert spec.scenario_type == "pedestrian_occlusion"
    assert spec.layout is not None
    assert spec.layout.actor_poses["parked_van"].y_m == 3.25


def test_resolver_rejects_unknown_template_id() -> None:
    intent = ScenarioIntent(template_id="unknown_template")

    with pytest.raises(ValueError, match="Unknown scenario template"):
        resolve_scenario_intent(intent)


def test_resolver_maps_lead_vehicle_braking_intent_to_scenario_spec() -> None:
    intent = ScenarioIntent(
        template_id="lead_vehicle_braking",
        actors={
            "ego": {"type": "car", "speed_kph": 50.0},
            "lead_vehicle": {"type": "car", "speed_kph": 45.0},
        },
        criticality={"target_ttc_s": 2.0},
        parameters={
            "scenario_name": "lead_vehicle_braking_eval",
            "initial_gap_m": 28.0,
            "lead_deceleration_mps2": -4.0,
        },
    )

    spec = resolve_scenario_intent(intent)

    assert spec.scenario_name == "lead_vehicle_braking_eval"
    assert spec.scenario_type == "lead_vehicle_braking"
    assert {actor.id for actor in spec.actors} == {"ego", "lead_vehicle"}
    assert spec.layout is not None
    assert spec.layout.coordinate_frame == "ego_local"
    assert spec.layout.actor_poses["ego"].x_m == 0.0
    assert spec.layout.actor_poses["lead_vehicle"].x_m == 28.0
    assert spec.layout.actor_poses["ego"].y_m == spec.layout.actor_poses["lead_vehicle"].y_m == 0.0
    assert spec.intended_criticality.target_min_ttc_s == 2.0
    assert spec.trigger.distance_m == 18.0
    assert spec.metadata["lead_vehicle_braking"]["lead_deceleration_mps2"] == -4.0


def test_lead_vehicle_braking_template_emits_same_lane_layout_and_timing_semantics() -> None:
    spec = resolve_scenario_intent(
        ScenarioIntent(
            template_id="lead_vehicle_braking",
            parameters={
                "ego_speed_kph": 54.0,
                "lead_vehicle_speed_kph": 42.0,
                "initial_gap_m": 30.0,
                "reaction_point_x_m": 12.0,
            },
        )
    )

    assert spec.layout is not None
    assert spec.timing is not None
    assert spec.actor_by_id("ego").initial_speed_kph == 54.0
    assert spec.actor_by_id("lead_vehicle").initial_speed_kph == 42.0
    assert spec.layout.points["reaction_point"].x_m == 12.0
    assert spec.layout.points["lead_brake_start_point"].x_m == 30.0
    assert spec.layout.paths["ego_path"].points[-1].x_m > spec.layout.actor_poses["lead_vehicle"].x_m
    assert spec.trigger.source == "ego"
    assert spec.trigger.target == "lead_vehicle"
    assert spec.trigger.distance_m == 18.0
    relations = {(relation.relation_type, relation.subject, relation.object) for relation in spec.spatial_relations}
    assert ("same_lane_as", "ego", "lead_vehicle") in relations
    assert ("ahead_of", "lead_vehicle", "ego") in relations
    assert ("brakes_before", "lead_vehicle", "ego") in relations


def test_lead_vehicle_braking_template_emits_storyboard_semantics() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))

    assert spec.storyboard is not None
    assert {group.id for group in spec.storyboard.maneuver_groups} == {
        "ego_driving",
        "lead_vehicle_braking",
    }
    lead_group = next(group for group in spec.storyboard.maneuver_groups if group.id == "lead_vehicle_braking")
    assert lead_group.actor_refs == ("lead_vehicle",)
    lead_event = next(event for event in spec.storyboard.events if event.id == "lead_vehicle_starts_braking")
    assert lead_event.start_trigger_ref == "lead_vehicle_brake_relative_distance"
    lead_action = next(action for action in spec.storyboard.actions if action.id == "lead_vehicle_brakes")
    assert lead_action.type == "absolute_speed"
    assert lead_action.actor_refs == ("lead_vehicle",)
    assert lead_action.metadata["target_speed_mps"] == 0.0
    assert lead_action.metadata["dynamics_dimension"] == "rate"
