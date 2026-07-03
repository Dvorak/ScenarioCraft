from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
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
