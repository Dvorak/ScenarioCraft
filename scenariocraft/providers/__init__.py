"""Optional provider adapters that propose structured intent or repair patches."""

from scenariocraft.providers.intent import IntentProposal, IntentProvider, IntentRequest
from scenariocraft.providers.openai_intent import (
    OpenAIIntentProvider,
    OpenAIIntentProviderConfigurationError,
)
from scenariocraft.providers.openai_repair import (
    OpenAIRepairProvider,
    OpenAIRepairProviderConfigurationError,
)

__all__ = [
    "IntentProposal",
    "IntentProvider",
    "IntentRequest",
    "OpenAIIntentProvider",
    "OpenAIIntentProviderConfigurationError",
    "OpenAIRepairProvider",
    "OpenAIRepairProviderConfigurationError",
]
