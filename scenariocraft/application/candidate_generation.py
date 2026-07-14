from __future__ import annotations

"""Candidate Generation Loop ownership for provider and controlled inputs.

This module stops `generated_scenario.py` from owning natural-language routing,
template fallback, and candidate acceptance trace construction. It does not
build artifacts, render previews, run external tools, or apply repairs.
"""

from dataclasses import replace

from scenariocraft.application.contracts import (
    CandidateAcceptanceTrace,
    ScenarioWorkflowRequest,
    ScenarioWorkflowStatus,
)
from scenariocraft.application.controlled_cases import controlled_case_intent
from scenariocraft.core.checks import SemanticValidationResult
from scenariocraft.core.schemas import ScenarioIntent, ScenarioSpec
from scenariocraft.core.templates import (
    family_declarations,
    generate_default_pedestrian_occlusion_spec,
    registered_templates,
    resolve_scenario_intent,
)
from scenariocraft.providers.intent import IntentProposal, IntentRequest


class IntentGenerationOutcomeError(ValueError):
    """Raised when an intent provider returns a terminal non-generation outcome."""

    def __init__(self, proposal: IntentProposal) -> None:
        self.proposal = proposal
        if proposal.status == "clarification_required":
            message = proposal.clarification_question or proposal.rationale
        else:
            message = proposal.refusal_reason or proposal.rationale
        super().__init__(message)


def generate_spec_with_intent(request: ScenarioWorkflowRequest) -> tuple[ScenarioSpec, IntentProposal | None]:
    """Resolve request text/provider state into a deterministic ScenarioSpec."""

    if request.provider_name == "controlled_case":
        if not request.controlled_case_id:
            raise ValueError("controlled_case_id is required for provider=controlled_case.")
        return resolve_scenario_intent(controlled_case_intent(request.controlled_case_id)), None
    if request.provider_name in {"openai-compatible", "openai_compatible"}:
        if request.intent_provider is None:
            raise ValueError("Intent provider is required for provider=openai-compatible.")
        proposal = request.intent_provider.propose_intent(intent_request(request))
        if proposal.status != "supported" or proposal.intent is None:
            raise IntentGenerationOutcomeError(proposal)
        spec, accepted_proposal = _resolve_provider_candidate(proposal)
        return spec, accepted_proposal
    if request.provider_name != "mock":
        raise ValueError(f"Unsupported provider: {request.provider_name}")
    return (
        generate_default_pedestrian_occlusion_spec(
            request.scenario_text,
            **request.template_parameters,
        ),
        None,
    )


def build_candidate_acceptance_trace(
    spec: ScenarioSpec,
    *,
    status: ScenarioWorkflowStatus,
    intent_proposal: IntentProposal | None,
    semantic_result: SemanticValidationResult | None,
    geometry_results: tuple,
    artifact_results: tuple,
) -> CandidateAcceptanceTrace:
    """Build pre-runtime evidence for candidate acceptance/rejection."""

    resolution = spec.template_resolution_metadata()
    parameters = resolution.get("parameters", [])
    resolved_parameters: dict[str, dict[str, object]] = {}
    if isinstance(parameters, list):
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            name = parameter.get("name")
            if isinstance(name, str):
                resolved_parameters[name] = {
                    key: value
                    for key, value in parameter.items()
                    if key in {"value", "source", "unit"}
                }
    check_results = tuple(geometry_results) + tuple(artifact_results)
    failed_names = tuple(str(result.name) for result in check_results if not getattr(result, "passed", False))
    semantic_failed = semantic_result is not None and not semantic_result.passed
    failed_count = len(failed_names) + (1 if semantic_failed else 0)
    check_summary: dict[str, object] = {
        "semantic": "passed" if semantic_result is not None and semantic_result.passed else "failed" if semantic_failed else "not_run",
        "total": len(check_results) + (1 if semantic_result is not None else 0),
        "failed": failed_count,
        "failed_checks": list(failed_names),
    }
    if semantic_failed:
        check_summary["failed_checks"] = ["semantic_validation", *list(failed_names)]
    return CandidateAcceptanceTrace(
        template_id=str(resolution.get("template_id") or spec.scenario_type),
        acceptance_status="accepted" if status.terminal_status == "passed" else "rejected",
        seed=resolution.get("seed") if resolution.get("seed") is not None else None,
        variant_index=int(resolution.get("variant_index", 0)),
        sampled=bool(resolution.get("sampled", False)),
        resolved_parameters=resolved_parameters,
        unsupported_fields=tuple(resolution.get("unsupported_fields", ())),
        fallback=_candidate_generation_fallback(intent_proposal),
        check_summary=check_summary,
    )


def intent_request(request: ScenarioWorkflowRequest) -> IntentRequest:
    """Build the provider-facing request with current template capability data."""

    templates = registered_templates()
    return IntentRequest(
        user_text=request.scenario_text,
        available_templates=tuple(sorted(templates)),
        template_contract_summary={
            template_id: {
                "description": template.description,
                "required_actors": list(template.required_actors),
                "supported_operations": list(template.supported_operations),
                "capability": template.capability.to_dict(),
            }
            for template_id, template in sorted(templates.items())
        },
        metadata={
            "provider_name": request.provider_name,
            "template_parameters": request.template_parameters,
            "revision_request": request.revision_request,
            "base_scenario_type": request.base_scenario_type,
            "family_taxonomy": {template_id: family.to_dict() for template_id, family in family_declarations().items()},
        },
    )


def _resolve_provider_candidate(proposal: IntentProposal) -> tuple[ScenarioSpec, IntentProposal]:
    if proposal.intent is None:
        raise IntentGenerationOutcomeError(proposal)
    try:
        return resolve_scenario_intent(proposal.intent), proposal
    except (TypeError, ValueError) as exc:
        fallback_intent = _fallback_intent_without_generated_parameters(proposal.intent, str(exc))
        fallback_proposal = IntentProposal(
            intent=fallback_intent,
            rationale=(
                proposal.rationale
                + " Candidate Generation Loop ignored provider-generated parameter values that failed "
                + f"template capability validation: {exc}"
            ),
            provider_name=proposal.provider_name,
            status="supported",
        )
        return resolve_scenario_intent(fallback_intent), fallback_proposal


def _fallback_intent_without_generated_parameters(intent: ScenarioIntent, reason: str) -> ScenarioIntent:
    preserved_parameters = {
        key: value
        for key, value in intent.parameters.items()
        if key in {"scenario_name", "source_text", "seed", "variant_index"}
    }
    metadata = {
        **intent.metadata,
        "candidate_generation_fallback": {
            "reason": reason,
            "discarded_parameters": {
                key: value
                for key, value in intent.parameters.items()
                if key not in preserved_parameters
            },
        },
    }
    return replace(intent, parameters=preserved_parameters, metadata=metadata)


def _candidate_generation_fallback(intent_proposal: IntentProposal | None) -> dict[str, object] | None:
    if intent_proposal is None or intent_proposal.intent is None:
        return None
    fallback = intent_proposal.intent.metadata.get("candidate_generation_fallback")
    if isinstance(fallback, dict):
        return dict(fallback)
    return None


__all__ = [
    "IntentGenerationOutcomeError",
    "build_candidate_acceptance_trace",
    "generate_spec_with_intent",
    "intent_request",
]
