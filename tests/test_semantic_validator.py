from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.templates import get_template
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.core.checks import run_structural_validity_checks, validate_semantics


def test_semantic_validator_passes_mock_spec() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = validate_semantics(spec)

    assert result.passed is True
    assert {check.name for check in result.checks} >= {
        "ego_vehicle_exists",
        "occluding_vehicle_exists",
        "pedestrian_exists",
    }


def test_semantic_validator_emits_structural_validity_check_evidence() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    results = run_structural_validity_checks(spec)

    assert results
    assert {result.category for result in results} == {"structural_validity"}
    assert {result.intent_relation for result in results} == {"not_applicable"}
    assert {result.repair_action for result in results} == {"none"}


def test_semantic_validator_is_family_aware_for_lead_vehicle_braking() -> None:
    spec = get_template("lead_vehicle_braking").instantiate(
        intent=ScenarioIntent(template_id="lead_vehicle_braking")
    )

    result = validate_semantics(spec)

    assert result.passed is True
    names = {check.name for check in result.checks}
    assert "occluding_vehicle_exists" not in names
    assert "pedestrian_exists" not in names
    assert "pedestrian_speed_plausible" not in names


def test_semantic_validator_accepts_all_golden_families_without_pedestrian_specific_requirements() -> None:
    for family_id in (
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    ):
        spec = get_template(family_id).instantiate(intent=ScenarioIntent(template_id=family_id))

        result = validate_semantics(spec)

        assert result.passed is True, family_id
        names = {check.name for check in result.checks}
        assert "occluding_vehicle_exists" not in names
        assert "pedestrian_exists" not in names
        assert "pedestrian_speed_plausible" not in names
