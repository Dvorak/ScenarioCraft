from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.validation import validate_semantics


def test_semantic_validator_passes_mock_spec() -> None:
    spec = generate_default_pedestrian_occlusion_spec("scenario")

    result = validate_semantics(spec)

    assert result.passed is True
    assert {check.name for check in result.checks} >= {
        "ego_vehicle_exists",
        "occluding_vehicle_exists",
        "pedestrian_exists",
    }
