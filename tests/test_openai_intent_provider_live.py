from scenariocraft.providers.intent import IntentRequest
from scenariocraft.providers.openai_intent import OpenAIIntentProvider
from scenariocraft.core.templates import registered_templates
from tests.local_llm import ensure_ollama_server


def test_live_openai_compatible_intent_provider_can_extract_lead_vehicle_braking_intent() -> None:
    ensure_ollama_server()
    provider = OpenAIIntentProvider.from_env()

    proposal = provider.propose_intent(
        IntentRequest(
            user_text=(
                "Create an urban same-lane scenario where the ego car follows a slower lead vehicle, "
                "and the lead vehicle brakes hard after about 30 meters."
            ),
            available_templates=tuple(sorted(registered_templates())),
            template_contract_summary={
                template_id: {
                    "description": template.description,
                    "capability": template.capability.to_dict(),
                }
                for template_id, template in sorted(registered_templates().items())
            },
        )
    )

    assert proposal.intent is not None, proposal.refusal_reason
    assert proposal.intent.template_id == "lead_vehicle_braking"
