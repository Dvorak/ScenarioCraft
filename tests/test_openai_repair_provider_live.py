from __future__ import annotations

import os

import pytest

from scenariocraft.core.generators import MockScenarioGenerator
from scenariocraft.integrations.openai_repair import OpenAIRepairProvider
from scenariocraft.core.repair.providers import RepairProposal, RepairRequest
from scenariocraft.core.schemas import ProbeResult


LIVE_ENABLED = (
    bool(os.environ.get("OPENAI_API_KEY"))
    and os.environ.get("SCENARIOCRAFT_RUN_OPENAI_LIVE_TEST") == "1"
)

pytestmark = pytest.mark.skipif(
    not LIVE_ENABLED,
    reason="Set OPENAI_API_KEY and SCENARIOCRAFT_RUN_OPENAI_LIVE_TEST=1 to run.",
)


def test_openai_repair_provider_live_returns_safe_proposal_metadata() -> None:
    pytest.importorskip("openai")
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    failed = ProbeResult(
        name="parked_van_footprint_in_parking_strip",
        passed=False,
        severity="failure",
        message="The parked van footprint is outside the parking strip.",
        measured={"actor_id": "parked_van", "band_id": "ego_side_parking_strip"},
    )
    request = RepairRequest(
        user_intent="Place the parked van in its designated parking strip.",
        scenario_spec=spec,
        failed_probe_results=(failed,),
        allowed_operation_types=("reposition_actor_to_band",),
    )
    model = os.environ.get("SCENARIOCRAFT_OPENAI_REPAIR_MODEL", "gpt-4o-mini")

    proposal = OpenAIRepairProvider(model=model).propose_patch(request)

    assert isinstance(proposal, RepairProposal)
    assert proposal.provider_name == "openai"
    assert proposal.rationale
    if proposal.patch is not None:
        assert all(
            operation.to_dict()["op"] in request.allowed_operation_types
            for operation in proposal.patch.operations
        )
