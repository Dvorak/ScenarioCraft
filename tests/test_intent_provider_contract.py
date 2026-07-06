from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.providers.intent import IntentProposal, IntentRequest, RefinementSuggestion
from scenariocraft.providers.intent import IntentProposalStatus


def test_intent_provider_contract_is_json_friendly() -> None:
    request = IntentRequest(
        user_text="A lead vehicle brakes ahead of ego on an urban road.",
        available_templates=("pedestrian_occlusion", "lead_vehicle_braking"),
        template_contract_summary={
            "lead_vehicle_braking": {
                "required_actors": ["ego", "lead_vehicle"],
                "parameters": ["initial_gap_m", "ego_speed_kph"],
            }
        },
        metadata={"source": "unit"},
    )
    proposal = IntentProposal(
        intent=ScenarioIntent(
            template_id="lead_vehicle_braking",
            actors={"ego": {"speed_kph": 50.0}, "lead_vehicle": {"speed_kph": 35.0}},
        ),
        rationale="The user described same-lane following with lead-vehicle braking.",
        provider_name="test-provider",
    )

    assert request.to_dict()["available_templates"] == ["pedestrian_occlusion", "lead_vehicle_braking"]
    assert proposal.to_dict()["intent"]["template_id"] == "lead_vehicle_braking"
    assert proposal.status == "supported"
    assert proposal.refusal_reason is None


def test_intent_proposal_supports_explicit_unsupported_result() -> None:
    proposal = IntentProposal(
        intent=None,
        rationale="The request asks for an unsupported highway merge scenario.",
        provider_name="test-provider",
        status="unsupported",
        refusal_reason="No available template supports this request.",
        nearest_template_candidates=("lead_vehicle_braking",),
    )

    payload = proposal.to_dict()

    assert payload["intent"] is None
    assert payload["status"] == "unsupported"
    assert payload["refusal_reason"] == "No available template supports this request."
    assert payload["nearest_template_candidates"] == ["lead_vehicle_braking"]


def test_intent_proposal_supports_clarification_required_result() -> None:
    proposal = IntentProposal(
        intent=None,
        rationale="The road context is unclear.",
        provider_name="test-provider",
        status="clarification_required",
        clarification_question="Is this a pedestrian crossing or a lead-vehicle braking scenario?",
        nearest_template_candidates=("pedestrian_occlusion", "lead_vehicle_braking"),
    )

    payload = proposal.to_dict()

    assert proposal.status == "clarification_required"
    assert payload["clarification_question"] == (
        "Is this a pedestrian crossing or a lead-vehicle braking scenario?"
    )
    assert payload["nearest_template_candidates"] == ["pedestrian_occlusion", "lead_vehicle_braking"]


def test_intent_proposal_serializes_refinement_suggestions() -> None:
    proposal = IntentProposal(
        intent=None,
        rationale="The request is broad.",
        provider_name="test-provider",
        status="clarification_required",
        clarification_question="Which scenario family should be used?",
        refinement_suggestions=(
            RefinementSuggestion(
                template_id="pedestrian_occlusion",
                label="Pedestrian occlusion",
                suggested_request=(
                    "An urban scenario where ego approaches a parked van and a pedestrian crosses from behind it."
                ),
                reason="Adds the missing interaction family.",
            ),
        ),
    )

    payload = proposal.to_dict()

    assert payload["refinement_suggestions"] == [
        {
            "template_id": "pedestrian_occlusion",
            "label": "Pedestrian occlusion",
            "suggested_request": (
                "An urban scenario where ego approaches a parked van and a pedestrian crosses from behind it."
            ),
            "reason": "Adds the missing interaction family.",
        }
    ]


def test_intent_proposal_rejects_invalid_status() -> None:
    try:
        IntentProposal(intent=None, rationale="bad", provider_name="test", status="maybe")
    except ValueError as exc:
        assert "status" in str(exc)
    else:
        raise AssertionError("invalid IntentProposal status should fail")

    assert IntentProposalStatus.__args__ == ("supported", "clarification_required", "unsupported")
