from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.repair.providers import (
    OpenAIRepairProvider,
    OpenAIRepairProviderConfigurationError,
    RepairProvider,
    RepairRequest,
)
from scenariocraft.schemas import PatchSpec, ProbeResult, RepositionActorToBandOperation


class FakeResponses:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: object) -> None:
        self.responses = FakeResponses(response)


def test_openai_provider_satisfies_runtime_protocol() -> None:
    provider = OpenAIRepairProvider(model="test-model", client=FakeOpenAIClient(_response(None)))

    assert isinstance(provider, RepairProvider)


def test_request_contains_only_structured_repair_context_and_guardrails() -> None:
    client = FakeOpenAIClient(_response(None))
    request = _request()

    OpenAIRepairProvider(model="test-model", client=client).propose_patch(request)

    call = client.responses.calls[0]
    assert call["model"] == "test-model"
    messages = call["input"]
    system_prompt = messages[0]["content"]
    payload = json.loads(messages[1]["content"])
    assert payload["user_intent"] == request.user_intent
    assert payload["scenario_spec"] == request.scenario_spec.to_dict()
    assert payload["failed_probe_results"] == [request.failed_probe_results[0].to_dict()]
    assert payload["allowed_operation_types"] == ["reposition_actor_to_band"]
    assert set(payload["allowed_operation_contract"]) == {"reposition_actor_to_band"}
    assert payload["repair_authority"] == {
        "provider_role": "proposal_only",
        "output_contract": "PatchSpec JSON or refusal",
        "success_authority": "deterministic probes/build/runtime evidence",
        "may_mutate_xml": False,
        "may_claim_repair_success": False,
    }
    assert "raw OpenSCENARIO XML" in system_prompt
    assert "raw OpenDRIVE XML" in system_prompt
    assert "claims that the repair is successful" in system_prompt
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True


def test_valid_structured_response_becomes_validated_patch_spec() -> None:
    provider = OpenAIRepairProvider(
        model="test-model",
        client=FakeOpenAIClient(
            _response(
                {
                    "operations": [
                        {
                            "op": "reposition_actor_to_band",
                            "actor_id": "parked_van",
                            "target_band_id": "ego_side_parking_strip",
                        }
                    ]
                }
            )
        ),
    )

    proposal = provider.propose_patch(_request())

    assert isinstance(proposal.patch, PatchSpec)
    operation = proposal.patch.operations[0]
    assert isinstance(operation, RepositionActorToBandOperation)
    assert operation.actor_id == "parked_van"
    assert operation.target_band_id == "ego_side_parking_strip"


def test_disallowed_operation_is_declined_after_patch_validation() -> None:
    response = _response(
        {
            "operations": [
                {
                    "op": "set_named_point",
                    "point_id": "trigger_point",
                    "x_m": 20.0,
                    "y_m": 0.0,
                }
            ]
        }
    )

    proposal = OpenAIRepairProvider(
        model="test-model", client=FakeOpenAIClient(response)
    ).propose_patch(_request())

    assert proposal.patch is None
    assert "disallowed operation types: set_named_point" in proposal.rationale


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (SimpleNamespace(output_text="not json"), "not valid JSON"),
        (SimpleNamespace(), "did not contain a structured JSON payload"),
        (SimpleNamespace(output_text="[]"), "was not an object"),
        (
            SimpleNamespace(output_text='{"rationale": "Missing patch."}'),
            "did not match the repair proposal structure",
        ),
    ],
)
def test_malformed_response_is_an_explicit_refusal(response: object, reason: str) -> None:
    proposal = OpenAIRepairProvider(
        model="test-model", client=FakeOpenAIClient(response)
    ).propose_patch(_request())

    assert proposal.patch is None
    assert reason in proposal.rationale


def test_patch_spec_validation_failure_is_an_explicit_refusal() -> None:
    proposal = OpenAIRepairProvider(
        model="test-model",
        client=FakeOpenAIClient(_response({"operations": []})),
    ).propose_patch(_request())

    assert proposal.patch is None
    assert "failed PatchSpec validation" in proposal.rationale


def test_model_refusal_is_preserved_as_no_patch() -> None:
    proposal = OpenAIRepairProvider(
        model="test-model",
        client=FakeOpenAIClient(_response(None, "Evidence is insufficient.")),
    ).propose_patch(_request())

    assert proposal.patch is None
    assert proposal.rationale == "Evidence is insufficient."


def test_sdk_safety_refusal_is_preserved_as_no_patch() -> None:
    response = SimpleNamespace(
        output=[SimpleNamespace(content=[SimpleNamespace(refusal="Cannot comply.")])]
    )

    proposal = OpenAIRepairProvider(
        model="test-model", client=FakeOpenAIClient(response)
    ).propose_patch(_request())

    assert proposal.patch is None
    assert proposal.rationale == "OpenAI refused the repair request: Cannot comply."


def test_transport_failure_is_an_explicit_refusal_without_retry() -> None:
    client = FakeOpenAIClient(ConnectionError("offline"))

    proposal = OpenAIRepairProvider(model="test-model", client=client).propose_patch(_request())

    assert proposal.patch is None
    assert proposal.rationale == "OpenAI request failed with ConnectionError."
    assert len(client.responses.calls) == 1


def test_missing_api_key_without_injected_client_fails_clearly(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(OpenAIRepairProviderConfigurationError, match="OPENAI_API_KEY is required"):
        OpenAIRepairProvider(model="test-model")


def test_provider_does_not_mutate_or_call_repair_build_probe_runtime_or_web(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("OpenAI provider crossed its proposal-only boundary.")

    monkeypatch.setattr("scenariocraft.repair.apply_patch", forbidden)
    monkeypatch.setattr("scenariocraft.build.build_openscenario", forbidden)
    monkeypatch.setattr("scenariocraft.runtime.run_esmini", forbidden)
    monkeypatch.setattr("scenariocraft.probes.run_artifact_consistency_probes", forbidden)
    request = _request()
    original = request.scenario_spec.to_json()

    proposal = OpenAIRepairProvider(
        model="test-model",
        client=FakeOpenAIClient(
            _response(
                {
                    "operations": [
                        {
                            "op": "reposition_actor_to_band",
                            "actor_id": "parked_van",
                            "target_band_id": "ego_side_parking_strip",
                        }
                    ]
                }
            )
        ),
    ).propose_patch(request)

    assert proposal.patch is not None
    assert request.scenario_spec.to_json() == original


def _request() -> RepairRequest:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    failed = ProbeResult(
        name="parked_van_footprint_in_parking_strip",
        passed=False,
        severity="failure",
        message="The parked van footprint is outside the parking strip.",
        measured={"actor_id": "parked_van", "band_id": "ego_side_parking_strip"},
        suggested_operations=(
            {
                "op": "reposition_actor_to_band",
                "actor_id": "parked_van",
                "target_band_id": "ego_side_parking_strip",
            },
        ),
    )
    return RepairRequest(
        user_intent="Keep the parked van inside the parking strip.",
        scenario_spec=spec,
        failed_probe_results=(failed,),
        allowed_operation_types=("reposition_actor_to_band",),
    )


def _response(patch: object, rationale: str = "Use the canonical parking strip.") -> object:
    return SimpleNamespace(output_text=json.dumps({"patch": patch, "rationale": rationale}))
