from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.providers.intent import IntentProposal
from scenariocraft.providers.intent_eval import IntentEvalCase, run_intent_eval


class _MappingIntentProvider:
    provider_name = "mapping-intent"

    def propose_intent(self, request):
        if "lead vehicle" in request.user_text:
            intent = ScenarioIntent(
                template_id="lead_vehicle_braking",
                actors={"ego": {"speed_kph": 50.0}, "lead_vehicle": {"speed_kph": 35.0}},
                parameters={"initial_gap_m": 30.0},
            )
        else:
            intent = ScenarioIntent(
                template_id="pedestrian_occlusion",
                weather={"condition": "rainy_wet"},
                actors={"ego": {"speed_kph": 35.0}, "pedestrian": {"speed_mps": 1.5}},
            )
        return IntentProposal(intent=intent, rationale="mapped", provider_name=self.provider_name)


class _RefusingIntentProvider:
    provider_name = "refusing-intent"

    def propose_intent(self, request):
        return IntentProposal(
            intent=None,
            rationale="unsupported",
            provider_name=self.provider_name,
            status="unsupported",
            refusal_reason="unsupported request",
            nearest_template_candidates=("lead_vehicle_braking",),
        )


class _ClarifyingIntentProvider:
    provider_name = "clarifying-intent"

    def propose_intent(self, request):
        return IntentProposal(
            intent=None,
            rationale="ambiguous",
            provider_name=self.provider_name,
            status="clarification_required",
            clarification_question="Which interaction family should be used?",
            nearest_template_candidates=("pedestrian_occlusion", "lead_vehicle_braking"),
        )


def test_intent_eval_verifies_template_selection_and_resolver_compatibility() -> None:
    cases = (
        IntentEvalCase(
            case_id="lead_braking",
            user_text="The ego follows a lead vehicle that brakes hard.",
            expected_template_id="lead_vehicle_braking",
            expected_parameters={"initial_gap_m": 30.0},
        ),
        IntentEvalCase(
            case_id="rainy_pedestrian",
            user_text="A rainy pedestrian crosses from behind a parked van.",
            expected_template_id="pedestrian_occlusion",
        ),
    )

    results = run_intent_eval(cases, provider=_MappingIntentProvider())

    assert [result.passed for result in results] == [True, True]
    assert results[0].resolved_scenario_type == "lead_vehicle_braking"
    assert results[1].resolved_scenario_type == "pedestrian_occlusion"


def test_intent_eval_accepts_expected_refusal() -> None:
    results = run_intent_eval(
        (
            IntentEvalCase(
                case_id="unsupported",
                user_text="Generate a complex highway cut-in with three lanes.",
                expected_refusal=True,
            ),
        ),
        provider=_RefusingIntentProvider(),
    )

    assert results[0].passed is True
    assert results[0].refusal_reason == "unsupported request"
    assert results[0].status == "unsupported"
    assert results[0].nearest_template_candidates == ("lead_vehicle_braking",)


def test_intent_eval_accepts_expected_clarification_required() -> None:
    results = run_intent_eval(
        (
            IntentEvalCase(
                case_id="ambiguous",
                user_text="Generate a dangerous urban scenario with another actor.",
                expected_status="clarification_required",
                expected_nearest_template_candidates=("pedestrian_occlusion", "lead_vehicle_braking"),
            ),
        ),
        provider=_ClarifyingIntentProvider(),
    )

    assert results[0].passed is True
    assert results[0].status == "clarification_required"
    assert results[0].clarification_question == "Which interaction family should be used?"


def test_default_eval_cases_include_supported_unsupported_and_clarification() -> None:
    from scenariocraft.providers.intent_eval import default_intent_eval_cases

    cases = default_intent_eval_cases()
    statuses = {case.expected_status for case in cases}

    assert len(cases) >= 20
    assert {"supported", "unsupported", "clarification_required"} <= statuses
    assert any("highway cut-in" in case.user_text.lower() for case in cases)
    assert any("child" in case.user_text.lower() and "delivery van" in case.user_text.lower() for case in cases)
    assert any("前车" in case.user_text for case in cases)
