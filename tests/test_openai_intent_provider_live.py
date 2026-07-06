import os

import pytest

from scenariocraft.providers.intent import IntentRequest
from scenariocraft.providers.openai_intent import OpenAIIntentProvider


@pytest.mark.skipif(
    os.environ.get("SCENARIOCRAFT_RUN_LIVE_INTENT_PROVIDER") != "1",
    reason="Set SCENARIOCRAFT_RUN_LIVE_INTENT_PROVIDER=1 to run against a real local/hosted model.",
)
def test_live_openai_compatible_intent_provider_can_extract_lead_vehicle_braking_intent() -> None:
    provider = OpenAIIntentProvider.from_env()

    proposal = provider.propose_intent(
        IntentRequest(
            user_text=(
                "Create an urban same-lane scenario where the ego car follows a slower lead vehicle, "
                "and the lead vehicle brakes hard after about 30 meters."
            ),
            available_templates=("pedestrian_occlusion", "lead_vehicle_braking"),
            template_contract_summary={
                "pedestrian_occlusion": {"description": "Occluded crossing pedestrian near a parked van."},
                "lead_vehicle_braking": {"description": "Same-lane lead vehicle braking ahead of ego."},
            },
        )
    )

    assert proposal.intent is not None, proposal.refusal_reason
    assert proposal.intent.template_id == "lead_vehicle_braking"
