from pathlib import Path

from scenariocraft.application import (
    ScenarioWorkflowOptions,
    ScenarioWorkflowRequest,
    run_generated_scenario_workflow,
)
from scenariocraft.providers.openai_intent import OpenAIIntentProvider
from tests.local_llm import ensure_ollama_server


def _minimal_options() -> ScenarioWorkflowOptions:
    return ScenarioWorkflowOptions(
        run_preview=False,
        run_semantics=True,
        run_geometry_checks=True,
        run_artifact_checks=False,
        run_runtime_checks=False,
        run_report=False,
        run_asam_qc=False,
        run_esmini=False,
        run_playback=False,
    )


def test_local_llm_workflow_generates_and_revises_lead_vehicle_braking(tmp_path: Path) -> None:
    ensure_ollama_server()
    provider = OpenAIIntentProvider.from_env()
    base_request = (
        "Create an urban same-lane scenario where the ego car follows a lead vehicle "
        "and the lead vehicle suddenly brakes."
    )

    first = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text=base_request,
            output_dir=tmp_path / "initial",
            provider_name="openai-compatible",
            intent_provider=provider,
            options=_minimal_options(),
        )
    )

    assert first.spec.scenario_type == "lead_vehicle_braking"
    assert first.intent_proposal is not None
    assert first.intent_proposal.intent is not None
    assert first.candidate_trace is not None
    assert first.candidate_trace.loop_name == "Candidate Generation Loop"
    assert first.candidate_trace.acceptance_status == "accepted"

    revision_request = "Make this a shorter-gap variant while keeping the lead vehicle braking interaction."
    revised = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text=f"{base_request}\n\nRevision request: {revision_request}",
            output_dir=tmp_path / "revision",
            provider_name="openai-compatible",
            intent_provider=provider,
            revision_request=revision_request,
            options=_minimal_options(),
        )
    )

    assert revised.spec.scenario_type == "lead_vehicle_braking"
    assert revised.intent_proposal is not None
    assert revised.intent_proposal.intent is not None
    assert revised.candidate_trace is not None
    assert revised.candidate_trace.acceptance_status == "accepted"
    assert revised.request.revision_request == revision_request
