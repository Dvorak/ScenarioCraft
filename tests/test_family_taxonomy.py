import pytest

from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.templates import get_template, registered_templates
from scenariocraft.core.templates.family_taxonomy import (
    FamilyStatus,
    executable_family_ids,
    family_declaration,
    family_declarations,
    planned_family_ids,
)
from scenariocraft.core.templates.resolver import resolve_scenario_intent


def test_family_taxonomy_declares_five_golden_families_with_status() -> None:
    declarations = family_declarations()

    assert tuple(declarations) == (
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    )
    assert declarations["pedestrian_occlusion"].status == "mature"
    assert declarations["lead_vehicle_braking"].status == "early"
    assert declarations["cut_in"].status == "planned"
    assert declarations["crossing_vehicle"].status == "planned"
    assert declarations["oncoming_turn_across_path"].status == "planned"
    assert set(FamilyStatus.__args__) == {"mature", "early", "planned"}


def test_planned_families_are_recognized_but_not_executable() -> None:
    assert planned_family_ids() == ("cut_in", "crossing_vehicle", "oncoming_turn_across_path")
    assert executable_family_ids() == ("pedestrian_occlusion", "lead_vehicle_braking")
    assert set(registered_templates()) == set(executable_family_ids())

    with pytest.raises(ValueError, match="Unknown scenario template"):
        resolve_scenario_intent(ScenarioIntent(template_id="cut_in"))


def test_implemented_template_capabilities_align_with_family_taxonomy() -> None:
    for template_id in executable_family_ids():
        declaration = family_declaration(template_id)
        capability = get_template(template_id).capability
        domain_names = set(capability.domain_map())

        assert capability.template_id == declaration.template_id
        assert capability.interaction_family == declaration.template_id
        assert set(capability.actor_roles) == set(declaration.actors)
        assert set(capability.road_contexts) == set(declaration.odd)
        assert set(capability.topologies) == set(declaration.topologies)
        assert set(declaration.capability_parameter_names) <= domain_names
        for boundary in declaration.boundaries:
            assert boundary in capability.unsupported_boundary_examples


def test_family_declaration_exports_machine_readable_payload() -> None:
    declaration = family_declaration("lead_vehicle_braking")
    payload = declaration.to_dict()

    assert payload == {
        "template_id": "lead_vehicle_braking",
        "interaction": "ego follows a lead vehicle that brakes suddenly",
        "actors": ["ego", "lead_vehicle"],
        "odd": ["urban", "urban_straight"],
        "topologies": ["straight_same_lane"],
        "parameters": [
            "ego_speed",
            "lead_speed",
            "initial_gap",
            "lead_deceleration",
            "brake_start",
            "target_ttc",
            "target_thw",
            "seed",
        ],
        "capability_parameter_names": [
            "ego_speed_kph",
            "lead_vehicle_speed_kph",
            "initial_gap_m",
            "lead_deceleration_mps2",
            "reaction_point_x_m",
            "target_min_ttc_s",
            "weather",
        ],
        "boundaries": ["adjacent lane cut-in", "crossing vehicle", "oncoming turn"],
        "status": "early",
        "implemented": True,
    }
