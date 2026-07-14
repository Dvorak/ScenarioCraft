import json

import pytest

from scenariocraft.providers.intent import IntentRequest
import scenariocraft.providers.openai_intent as openai_intent_module
from scenariocraft.providers.openai_intent import (
    OpenAIIntentProvider,
    OpenAIIntentProviderConfigurationError,
    OpenAIIntentProviderExecutionError,
    local_llm_configuration_hint,
)


class _FakeResponses:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return type("Response", (), {"output_text": self.payload})()


class _FakeClient:
    def __init__(self, payload: object) -> None:
        self.responses = _FakeResponses(payload)


class _FailingResponses:
    def create(self, **kwargs):
        raise RuntimeError("responses endpoint unavailable")


class _FakeChatCompletions:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = type("Message", (), {"content": self.payload})()
        choice = type("Choice", (), {"message": message})()
        return type("ChatResponse", (), {"choices": [choice]})()


class _FakeChatClient:
    def __init__(self, payload: str) -> None:
        self.responses = _FailingResponses()
        self.chat = type("Chat", (), {"completions": _FakeChatCompletions(payload)})()


class _UnavailableClient:
    def __init__(self) -> None:
        self.responses = _FailingResponses()


def _request() -> IntentRequest:
    return IntentRequest(
        user_text="The ego car follows a lead vehicle that brakes hard after about 30 meters.",
        available_templates=("pedestrian_occlusion", "lead_vehicle_braking"),
        template_contract_summary={
            "pedestrian_occlusion": {"description": "Occluded crossing pedestrian near a parked van."},
            "lead_vehicle_braking": {"description": "Same-lane lead vehicle braking ahead of ego."},
        },
    )


def test_openai_intent_provider_returns_valid_scenario_intent() -> None:
    payload = json.dumps(
        {
            "intent": {
                "template_id": "lead_vehicle_braking",
                "actors": {
                    "ego": {"type": "car", "speed_kph": 50.0},
                    "lead_vehicle": {"type": "car", "speed_kph": 35.0},
                },
                "parameters": {"initial_gap_m": 30.0},
                "criticality": {"target_ttc_s": 2.0},
            },
            "rationale": "The request describes same-lane following and hard braking.",
        }
    )
    client = _FakeClient(payload)
    provider = OpenAIIntentProvider(model="local-qwen", client=client)

    proposal = provider.propose_intent(_request())

    assert proposal.intent is not None
    assert proposal.intent.template_id == "lead_vehicle_braking"
    assert proposal.intent.parameters["initial_gap_m"] == 30.0


def test_openai_intent_provider_sends_revision_context_to_model() -> None:
    payload = json.dumps(
        {
            "intent": {"template_id": "lead_vehicle_braking"},
            "rationale": "The revision remains a same-lane lead vehicle braking variant.",
        }
    )
    client = _FakeClient(payload)
    provider = OpenAIIntentProvider(model="local-qwen", client=client)
    request = IntentRequest(
        user_text="Lead vehicle braking scenario.\n\nRevision request: Make the gap shorter.",
        available_templates=("lead_vehicle_braking",),
        template_contract_summary={
            "lead_vehicle_braking": {"description": "Same-lane lead vehicle braking ahead of ego."},
        },
        metadata={
            "revision_request": "Make the gap shorter.",
            "base_scenario_type": "lead_vehicle_braking",
        },
    )

    proposal = provider.propose_intent(request)

    assert proposal.status == "supported"
    messages = client.responses.calls[0]["input"]
    assert "Scenario Revision Loop" in messages[0]["content"]
    assert "base_scenario_type" in messages[0]["content"]
    assert '"revision_request": "Make the gap shorter."' in messages[1]["content"]
    assert proposal.status == "supported"
    assert proposal.provider_name == "openai_compatible"
    assert proposal.refusal_reason is None
    call = client.responses.calls[0]
    assert call["model"] == "local-qwen"
    assert "json_schema" in str(call["text"])
    assert call["temperature"] == 0


def test_openai_intent_provider_refuses_unknown_template() -> None:
    payload = json.dumps(
        {
            "intent": {"template_id": "cut_in"},
            "rationale": "The request sounds like a cut-in.",
        }
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(_request())

    assert proposal.intent is None
    assert proposal.status == "unsupported"
    assert "unknown template_id" in proposal.refusal_reason


def test_openai_intent_provider_coerces_semantic_template_alias() -> None:
    payload = json.dumps(
        {
            "intent": {"template_id": "same_lane_following_lead_brake"},
            "rationale": "The request describes following a lead vehicle that brakes.",
        }
    )
    request = IntentRequest(
        user_text="Ego follows a lead vehicle that brakes.",
        available_templates=("pedestrian_occlusion", "lead_vehicle_braking"),
        template_contract_summary={
            "pedestrian_occlusion": {
                "description": "Occluded crossing pedestrian near a parked van.",
                "capability": {
                    "aliases": ["pedestrian crosses from behind parked vehicle"],
                    "semantic_slots": ["pedestrian", "occluder"],
                    "supported_variants": [],
                },
            },
            "lead_vehicle_braking": {
                "description": "Same-lane lead vehicle braking ahead of ego.",
                "capability": {
                    "aliases": ["ego follows lead vehicle that brakes", "same lane emergency braking"],
                    "semantic_slots": ["lead_vehicle", "following_relation", "braking_event"],
                    "supported_variants": ["urban same-lane following"],
                },
            },
        },
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(request)

    assert proposal.intent is not None
    assert proposal.intent.template_id == "lead_vehicle_braking"
    assert proposal.intent.metadata["provider_template_id"] == "same_lane_following_lead_brake"


def test_openai_intent_provider_preserves_unsupported_with_nearest_candidates() -> None:
    payload = json.dumps(
        {
            "status": "unsupported",
            "intent": None,
            "rationale": "The request describes a highway cut-in.",
            "refusal_reason": "No registered cut-in template is available.",
            "nearest_template_candidates": ["lead_vehicle_braking"],
        }
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(_request())

    assert proposal.intent is None
    assert proposal.status == "unsupported"
    assert proposal.refusal_reason == "No registered cut-in template is available."
    assert proposal.nearest_template_candidates == ("lead_vehicle_braking",)


def test_openai_intent_provider_preserves_clarification_required() -> None:
    payload = json.dumps(
        {
            "status": "clarification_required",
            "intent": None,
            "rationale": "The request names an obstacle but not the interaction.",
            "clarification_question": "Should the scenario involve a pedestrian or a braking lead vehicle?",
            "nearest_template_candidates": ["pedestrian_occlusion", "lead_vehicle_braking"],
        }
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(_request())

    assert proposal.intent is None
    assert proposal.status == "clarification_required"
    assert proposal.refusal_reason is None
    assert "pedestrian" in proposal.clarification_question
    assert proposal.nearest_template_candidates == ("pedestrian_occlusion", "lead_vehicle_braking")


def test_openai_intent_provider_preserves_valid_refinement_suggestions() -> None:
    payload = json.dumps(
        {
            "status": "clarification_required",
            "intent": None,
            "rationale": "The request only says urban scenario.",
            "clarification_question": "Which interaction should the urban scenario focus on?",
            "nearest_template_candidates": ["pedestrian_occlusion", "lead_vehicle_braking"],
            "refinement_suggestions": [
                {
                    "template_id": "pedestrian_occlusion",
                    "label": "Pedestrian occlusion",
                    "suggested_request": (
                        "An urban scenario where ego approaches a parked van and a pedestrian crosses from behind it."
                    ),
                    "reason": "Adds the missing pedestrian crossing interaction.",
                },
                {
                    "template_id": "cut_in",
                    "label": "Cut-in",
                    "suggested_request": "A highway cut-in scenario.",
                    "reason": "Invalid because no cut-in template is registered.",
                },
            ],
        }
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(_request())

    assert proposal.status == "clarification_required"
    assert len(proposal.refinement_suggestions) == 1
    suggestion = proposal.refinement_suggestions[0]
    assert suggestion.template_id == "pedestrian_occlusion"
    assert suggestion.label == "Pedestrian occlusion"
    assert "parked van" in suggestion.suggested_request


def test_openai_intent_provider_routes_clear_semantic_match_as_supported() -> None:
    payload = json.dumps(
        {
            "status": "supported",
            "intent": {
                "template_id": "pedestrian_occlusion",
                "road_context": {"type": "urban"},
                "actors": {
                    "pedestrian": {"type": "pedestrian", "age_group": "child"},
                    "occluder": {"type": "delivery_van"},
                },
                "parameters": {"lighting": "night", "seed": 42},
            },
            "rationale": "Child emerging from behind a delivery van is pedestrian occlusion.",
            "refinement_suggestions": [],
        }
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(_request())

    assert proposal.status == "supported"
    assert proposal.intent is not None
    assert proposal.intent.template_id == "pedestrian_occlusion"
    assert proposal.intent.parameters["lighting"] == "night"


def test_openai_intent_provider_falls_back_to_chat_completions_for_local_models() -> None:
    payload = json.dumps(
        {
            "intent": {"template_id": "pedestrian_occlusion"},
            "rationale": "The prompt describes an occluded pedestrian.",
            "refusal_reason": None,
        }
    )
    client = _FakeChatClient(payload)
    provider = OpenAIIntentProvider(model="qwen2.5:7b", client=client)

    proposal = provider.propose_intent(_request())

    assert proposal.intent is not None
    assert proposal.intent.template_id == "pedestrian_occlusion"
    assert client.chat.completions.calls
    assert client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    assert client.chat.completions.calls[0]["temperature"] == 0


def test_openai_intent_provider_raises_execution_error_when_endpoint_fails() -> None:
    provider = OpenAIIntentProvider(model="local-qwen", client=_UnavailableClient())

    with pytest.raises(OpenAIIntentProviderExecutionError, match="RuntimeError"):
        provider.propose_intent(_request())


def test_openai_intent_provider_corrects_clear_template_mismatch_against_capability_tree() -> None:
    payload = json.dumps(
        {
            "intent": {"template_id": "cut_in"},
            "rationale": "The model selected a lane-change family by mistake.",
        }
    )
    request = IntentRequest(
        user_text=(
            "Create an urban same-lane scenario where the ego car follows a lead vehicle "
            "and the lead vehicle suddenly brakes."
        ),
        available_templates=("lead_vehicle_braking", "cut_in"),
        template_contract_summary={
            "lead_vehicle_braking": {
                "description": "Urban same-lane following scenario where a lead vehicle brakes ahead of ego.",
                "capability": {
                    "interaction_family": "lead_vehicle_braking",
                    "aliases": ["ego follows lead vehicle that brakes", "same lane emergency braking"],
                    "semantic_slots": ["lead_vehicle", "following_relation", "braking_event"],
                    "supported_variants": ["urban same-lane following"],
                },
            },
            "cut_in": {
                "description": "Adjacent-lane vehicle cuts into the ego lane.",
                "capability": {
                    "interaction_family": "cut_in",
                    "aliases": ["adjacent lane cut-in", "vehicle merges into ego lane"],
                    "semantic_slots": ["adjacent_lane", "lane_change", "merge_point"],
                    "supported_variants": ["multi-lane same-direction cut-in"],
                },
            },
        },
    )
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient(payload))

    proposal = provider.propose_intent(request)

    assert proposal.intent is not None
    assert proposal.intent.template_id == "lead_vehicle_braking"
    assert proposal.intent.metadata["provider_template_id"] == "cut_in"


def test_openai_intent_provider_refuses_invalid_json() -> None:
    provider = OpenAIIntentProvider(model="local-qwen", client=_FakeClient("not json"))

    proposal = provider.propose_intent(_request())

    assert proposal.intent is None
    assert "valid JSON" in proposal.refusal_reason


def test_openai_intent_provider_reads_local_openai_compatible_env(monkeypatch) -> None:
    monkeypatch.setenv("SCENARIOCRAFT_OPENAI_API_KEY", "local")
    monkeypatch.setenv("SCENARIOCRAFT_OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("SCENARIOCRAFT_INTENT_MODEL", "qwen2.5:7b")

    provider = OpenAIIntentProvider.from_env(client=_FakeClient("{}"))

    assert provider.model == "qwen2.5:7b"
    assert provider.base_url == "http://localhost:11434/v1"


def test_openai_intent_provider_reads_local_llm_env_aliases(monkeypatch) -> None:
    monkeypatch.setenv("SCENARIOCRAFT_LOCAL_LLM_API_KEY", "local")
    monkeypatch.setenv("SCENARIOCRAFT_LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("SCENARIOCRAFT_LOCAL_LLM_MODEL", "qwen2.5:7b")
    monkeypatch.setenv("SCENARIOCRAFT_LOCAL_LLM_TIMEOUT_S", "7.5")

    provider = OpenAIIntentProvider.from_env(client=_FakeClient("{}"))

    assert provider.model == "qwen2.5:7b"
    assert provider.base_url == "http://localhost:11434/v1"
    assert provider.timeout_s == 7.5


def test_openai_intent_provider_auto_discovers_ollama_model(monkeypatch) -> None:
    monkeypatch.delenv("SCENARIOCRAFT_LOCAL_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_LOCAL_LLM_MODEL", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_INTENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(openai_intent_module, "_ollama_model_names", lambda base_url, timeout_s: ("qwen2.5:7b",))

    provider = OpenAIIntentProvider.from_env(client=_FakeClient("{}"))

    assert provider.model == "qwen2.5:7b"
    assert provider.base_url == "http://localhost:11434/v1"


def test_local_llm_configuration_hint_detects_running_ollama(monkeypatch) -> None:
    monkeypatch.delenv("SCENARIOCRAFT_LOCAL_LLM_MODEL", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_INTENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(openai_intent_module, "_ollama_model_names", lambda base_url, timeout_s: ("qwen2.5:7b",))

    hint = local_llm_configuration_hint()

    assert hint.reachable is True
    assert hint.model_names == ("qwen2.5:7b",)
    assert "Ollama appears to be running locally" in hint.message
    assert "SCENARIOCRAFT_LOCAL_LLM_MODEL=qwen2.5:7b" in hint.message


def test_local_llm_configuration_hint_explains_missing_ollama(monkeypatch) -> None:
    monkeypatch.delenv("SCENARIOCRAFT_LOCAL_LLM_MODEL", raising=False)
    monkeypatch.delenv("SCENARIOCRAFT_INTENT_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.setattr(openai_intent_module, "_ollama_model_names", lambda base_url, timeout_s: ())

    hint = local_llm_configuration_hint()

    assert hint.reachable is False
    assert "ollama pull qwen2.5:7b" in hint.message
    assert "README.md -> Tool Setup Details -> Local LLM" in hint.message


def test_openai_intent_provider_requires_model() -> None:
    with pytest.raises(OpenAIIntentProviderConfigurationError, match="model"):
        OpenAIIntentProvider(model="", client=_FakeClient("{}"))
