import pytest

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.repair.providers import (
    FakeRepairProvider,
    RepairProposal,
    RepairProvider,
    RepairProviderContractError,
    RepairRequest,
)
from scenariocraft.core.schemas import (
    PatchSpec,
    CheckResult,
    RepositionActorToBandOperation,
)


def test_repair_request_stores_structured_spec_and_failed_check_results() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    failed = CheckResult(
        name="parked_van_footprint_in_parking_strip",
        passed=False,
        severity="failure",
        message="Van is outside the parking strip.",
        measured={"actor_id": "parked_van"},
    )

    request = RepairRequest(
        user_intent="Keep the parked van inside the parking strip.",
        scenario_spec=spec,
        failed_check_results=(failed,),
        allowed_operation_types=("reposition_actor_to_band",),
    )

    assert request.user_intent == "Keep the parked van inside the parking strip."
    assert request.scenario_spec is spec
    assert request.failed_check_results == (failed,)
    assert request.allowed_operation_types == ("reposition_actor_to_band",)


def test_repair_proposal_stores_patch_or_explicit_no_patch() -> None:
    patch = PatchSpec((RepositionActorToBandOperation("parked_van", "ego_side_parking_strip"),))

    proposal = RepairProposal(
        patch=patch,
        rationale="Use the canonical parking strip.",
        provider_name="test_provider",
    )
    refusal = RepairProposal(
        patch=None,
        rationale="No supported operation is allowed.",
        provider_name="test_provider",
    )

    assert proposal.patch is patch
    assert refusal.patch is None
    assert refusal.rationale


def test_fake_provider_satisfies_runtime_protocol() -> None:
    provider = FakeRepairProvider()

    assert isinstance(provider, RepairProvider)


def test_repair_request_rejects_passed_results_and_duplicate_allowed_operations() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    passed = CheckResult(name="already_valid", passed=True, severity="note", message="Already valid.")

    with pytest.raises(RepairProviderContractError, match="must be a failed result"):
        RepairRequest(None, spec, (passed,), ("set_named_point",))

    with pytest.raises(RepairProviderContractError, match="must be unique"):
        RepairRequest(None, spec, (), ("set_named_point", "set_named_point"))


def test_repair_proposal_rejects_empty_rationale_and_provider_name() -> None:
    with pytest.raises(RepairProviderContractError, match="rationale"):
        RepairProposal(None, "", "provider")
    with pytest.raises(RepairProviderContractError, match="provider_name"):
        RepairProposal(None, "No patch.", "")
