from __future__ import annotations

"""Small NL-to-ScenarioIntent evaluation harness."""

from dataclasses import dataclass, field
from typing import Any

from scenariocraft.core.templates import family_declarations, registered_templates, resolve_scenario_intent
from scenariocraft.providers.intent import IntentProvider, IntentProposalStatus, IntentRequest


@dataclass(frozen=True)
class IntentEvalCase:
    case_id: str
    user_text: str
    expected_template_id: str | None = None
    expected_parameters: dict[str, object] = field(default_factory=dict)
    expected_refusal: bool = False
    expected_status: IntentProposalStatus = "supported"
    expected_nearest_template_candidates: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntentEvalResult:
    case_id: str
    passed: bool
    provider_name: str
    template_id: str | None
    resolved_scenario_type: str | None
    refusal_reason: str | None
    status: IntentProposalStatus
    clarification_question: str | None = None
    nearest_template_candidates: tuple[str, ...] = ()
    failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "provider_name": self.provider_name,
            "template_id": self.template_id,
            "resolved_scenario_type": self.resolved_scenario_type,
            "refusal_reason": self.refusal_reason,
            "status": self.status,
            "clarification_question": self.clarification_question,
            "nearest_template_candidates": list(self.nearest_template_candidates),
            "failures": list(self.failures),
        }


def run_intent_eval(
    cases: tuple[IntentEvalCase, ...],
    *,
    provider: IntentProvider,
) -> tuple[IntentEvalResult, ...]:
    return tuple(_run_case(case, provider=provider) for case in cases)


def _run_case(case: IntentEvalCase, *, provider: IntentProvider) -> IntentEvalResult:
    proposal = provider.propose_intent(_request(case))
    provider_name = proposal.provider_name
    expected_status = "unsupported" if case.expected_refusal else case.expected_status
    if expected_status != "supported":
        failures = _status_failures(
            expected_status=expected_status,
            actual_status=proposal.status,
            expected_candidates=case.expected_nearest_template_candidates,
            actual_candidates=proposal.nearest_template_candidates,
        )
        if proposal.intent is not None:
            failures.append("non-supported proposal must not include ScenarioIntent")
        if expected_status == "unsupported" and not proposal.refusal_reason:
            failures.append("unsupported proposal must include refusal_reason")
        if expected_status == "clarification_required" and not proposal.clarification_question:
            failures.append("clarification_required proposal must include clarification_question")
        passed = not failures
        return IntentEvalResult(
            case_id=case.case_id,
            passed=passed,
            provider_name=provider_name,
            template_id=None,
            resolved_scenario_type=None,
            refusal_reason=proposal.refusal_reason,
            status=proposal.status,
            clarification_question=proposal.clarification_question,
            nearest_template_candidates=proposal.nearest_template_candidates,
            failures=tuple(failures),
        )
    if proposal.intent is None:
        return IntentEvalResult(
            case_id=case.case_id,
            passed=False,
            provider_name=provider_name,
            template_id=None,
            resolved_scenario_type=None,
            refusal_reason=proposal.refusal_reason,
            status=proposal.status,
            clarification_question=proposal.clarification_question,
            nearest_template_candidates=proposal.nearest_template_candidates,
            failures=("provider refused unexpectedly",),
        )

    failures: list[str] = []
    if proposal.status != "supported":
        failures.append(f"expected status=supported, got {proposal.status}")
    if case.expected_template_id and proposal.intent.template_id != case.expected_template_id:
        failures.append(
            f"expected template_id={case.expected_template_id}, got {proposal.intent.template_id}"
        )
    for key, expected in case.expected_parameters.items():
        actual = proposal.intent.parameters.get(key)
        if actual != expected:
            failures.append(f"expected parameter {key}={expected!r}, got {actual!r}")
    resolved_scenario_type = None
    try:
        spec = resolve_scenario_intent(proposal.intent)
        resolved_scenario_type = spec.scenario_type
    except Exception as exc:
        failures.append(f"resolver failed with {type(exc).__name__}: {exc}")
    return IntentEvalResult(
        case_id=case.case_id,
        passed=not failures,
        provider_name=provider_name,
        template_id=proposal.intent.template_id,
        resolved_scenario_type=resolved_scenario_type,
        refusal_reason=None,
        status=proposal.status,
        clarification_question=proposal.clarification_question,
        nearest_template_candidates=proposal.nearest_template_candidates,
        failures=tuple(failures),
    )


def default_intent_eval_cases() -> tuple[IntentEvalCase, ...]:
    return (
        IntentEvalCase("en_pedestrian_occlusion", "A rainy pedestrian crosses from behind a parked van.", "pedestrian_occlusion"),
        IntentEvalCase("zh_pedestrian_occlusion", "生成一个雨天城市道路行人从停着的货车后方突然横穿的场景。", "pedestrian_occlusion"),
        IntentEvalCase("en_lead_braking", "The ego follows a lead vehicle that suddenly brakes.", "lead_vehicle_braking"),
        IntentEvalCase("zh_lead_braking", "生成一个城市道路自车跟随前车行驶，前车突然急刹的场景。", "lead_vehicle_braking"),
        IntentEvalCase("mixed_lead_braking", "城市道路 lead vehicle hard braking, ego follows closely.", "lead_vehicle_braking"),
        IntentEvalCase("en_ped_speed", "A pedestrian occlusion scenario with the ego at 40 km/h.", "pedestrian_occlusion"),
        IntentEvalCase("zh_rain_occlusion", "雨天湿滑路面，行人被路边停靠车辆遮挡后横穿。", "pedestrian_occlusion"),
        IntentEvalCase(
            "en_child_delivery_van_occlusion",
            "Urban scenario at night with a child suddenly emerging from behind a delivery van.",
            "pedestrian_occlusion",
        ),
        IntentEvalCase("en_gap_braking", "Lead vehicle braking with an initial gap around 30 meters.", "lead_vehicle_braking"),
        IntentEvalCase("zh_ttc_braking", "前车急刹，目标最小 TTC 大约 2 秒。", "lead_vehicle_braking"),
        IntentEvalCase("en_clear_pedestrian", "A clear dry urban pedestrian occlusion near a parked van.", "pedestrian_occlusion"),
        IntentEvalCase(
            "en_cut_in",
            "A vehicle in the adjacent lane cuts into the ego lane on an urban multilane road.",
            "cut_in",
        ),
        IntentEvalCase(
            "zh_cut_in",
            "生成一个城市多车道场景，旁边车道车辆突然并入自车车道。",
            "cut_in",
        ),
        IntentEvalCase(
            "en_crossing_vehicle",
            "An ego vehicle approaches an intersection while a crossing vehicle enters its path.",
            "crossing_vehicle",
        ),
        IntentEvalCase(
            "zh_crossing_vehicle",
            "生成一个城市路口场景，自车接近路口，横向车辆进入自车路径。",
            "crossing_vehicle",
        ),
        IntentEvalCase(
            "en_oncoming_turn",
            "An oncoming vehicle turns left across the ego vehicle path at an urban intersection.",
            "oncoming_turn_across_path",
        ),
        IntentEvalCase(
            "zh_oncoming_turn",
            "生成一个城市路口对向车转弯场景，对向车辆左转穿过自车路径。",
            "oncoming_turn_across_path",
        ),
        IntentEvalCase(
            "unsupported_highway_cut_in",
            "Generate a highway cut-in with three lanes.",
            expected_status="unsupported",
            expected_nearest_template_candidates=("lead_vehicle_braking",),
        ),
        IntentEvalCase(
            "unsupported_highway_cut_in_zh",
            "生成一个高速公路三车道车辆切入 cut-in 场景。",
            expected_status="unsupported",
            expected_nearest_template_candidates=("lead_vehicle_braking",),
        ),
        IntentEvalCase("unsupported_signalized_intersection", "A signalized red-light violation with traffic light phases.", expected_status="unsupported"),
        IntentEvalCase("unsupported_complex_unprotected_turn", "A multi-lane unprotected turn with traffic signals and pedestrians.", expected_status="unsupported"),
        IntentEvalCase("unsupported_construction", "A work-zone lane closure with cones and a police vehicle.", expected_status="unsupported"),
        IntentEvalCase("unsupported_roundabout", "A multi-agent roundabout negotiation scenario.", expected_status="unsupported"),
        IntentEvalCase("unsupported_rear_end", "A vehicle behind ego rear-ends the ego vehicle.", expected_status="unsupported"),
        IntentEvalCase("unsupported_bus_stop", "A bus pulls out from a bus stop into traffic.", expected_status="unsupported"),
        IntentEvalCase("clarify_actor", "Generate a dangerous urban scenario with another actor.", expected_status="clarification_required"),
        IntentEvalCase("clarify_weather", "Make it risky in the city with low visibility.", expected_status="clarification_required"),
        IntentEvalCase("clarify_zh", "生成一个危险场景，但我还没想好参与者。", expected_status="clarification_required"),
        IntentEvalCase("clarify_mixed", "Create an urban hazard scenario, maybe pedestrian or braking.", expected_status="clarification_required"),
    )


def _status_failures(
    *,
    expected_status: IntentProposalStatus,
    actual_status: IntentProposalStatus,
    expected_candidates: tuple[str, ...],
    actual_candidates: tuple[str, ...],
) -> list[str]:
    failures: list[str] = []
    if actual_status != expected_status:
        failures.append(f"expected status={expected_status}, got {actual_status}")
    for candidate in expected_candidates:
        if candidate not in actual_candidates:
            failures.append(f"expected nearest candidate {candidate}")
    return failures


def _request(case: IntentEvalCase) -> IntentRequest:
    templates = registered_templates()
    return IntentRequest(
        user_text=case.user_text,
        available_templates=tuple(sorted(templates)),
        template_contract_summary={
            template_id: {
                "description": template.description,
                "required_actors": list(template.required_actors),
                "capability": template.capability.to_dict(),
            }
            for template_id, template in sorted(templates.items())
        },
        metadata={
            "eval_case_id": case.case_id,
            "family_taxonomy": {template_id: family.to_dict() for template_id, family in family_declarations().items()},
        },
    )
