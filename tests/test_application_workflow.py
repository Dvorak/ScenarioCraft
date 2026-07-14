from __future__ import annotations

import json
from pathlib import Path

from scenariocraft.application import (
    ExternalScenarioWorkflowOptions,
    ExternalScenarioWorkflowRequest,
    ScenarioWorkflowOptions,
    ScenarioWorkflowRequest,
    run_external_scenario_workflow,
    run_generated_scenario_workflow,
)
from scenariocraft.application.controlled_cases import CONTROLLED_CASES
from scenariocraft.application.candidate_generation import IntentGenerationOutcomeError
from scenariocraft.core.schemas import ScenarioIntent
from scenariocraft.providers.intent import IntentProposal


def test_application_layer_has_no_delivery_or_process_imports() -> None:
    application_dir = Path("scenariocraft/application")
    source = "\n".join(path.read_text(encoding="utf-8") for path in application_dir.glob("*.py"))

    assert "import streamlit" not in source
    assert "import fastapi" not in source
    assert "import openai" not in source
    assert "import subprocess" not in source
    assert "st.session_state" not in source
    assert "scenariocraft._legacy_streamlit" not in source


def test_controlled_demo_cases_are_owned_by_application_layer() -> None:
    from scenariocraft.application.demo_cases import DEMO_CASES, get_demo_case

    assert {case.case_id for case in DEMO_CASES} == {
        "normal_good_scenario",
        "geometry_van_in_ego_lane",
        "geometry_trigger_after_conflict",
        "artifact_xosc_actor_pose_drift",
    }
    assert get_demo_case("normal_good_scenario").display_name == "Normal Good Scenario"


def test_generated_scenario_workflow_builds_deterministic_artifacts(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="A rainy pedestrian occlusion scenario.",
            output_dir=tmp_path,
            provider_name="mock",
            options=ScenarioWorkflowOptions(
                run_preview=False,
                run_semantics=False,
                run_geometry_checks=False,
                run_runtime_checks=False,
                run_report=False,
            ),
        )
    )

    assert result.terminal_status == "passed"
    assert result.artifacts.input_path == tmp_path / "input.txt"
    assert result.artifacts.scenario_spec_path == tmp_path / "scenario_spec.json"
    assert result.artifacts.xosc_path == tmp_path / "scenario.xosc"
    assert result.artifacts.xodr_path == tmp_path / "urban_two_way_parking.xodr"
    assert result.artifacts.preview_path is None
    assert result.artifacts.report_path is None
    assert result.xosc_text.startswith("<?xml")
    assert (tmp_path / "input.txt").exists()
    assert (tmp_path / "scenario_spec.json").exists()
    assert (tmp_path / "scenario.xosc").exists()
    assert (tmp_path / "urban_two_way_parking.xodr").exists()


def test_generated_scenario_workflow_writes_preview_report_and_skipped_adapter_results(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="A rainy pedestrian occlusion scenario.",
            output_dir=tmp_path,
            provider_name="mock",
            options=ScenarioWorkflowOptions(
                run_preview=True,
                run_semantics=True,
                run_geometry_checks=True,
                run_runtime_checks=False,
                run_report=True,
                run_asam_qc=False,
                run_esmini=False,
                run_playback=False,
            ),
        )
    )

    assert result.terminal_status == "passed"
    assert result.semantic_result is not None
    assert result.semantic_result.passed is True
    assert result.qc_result is not None
    assert result.qc_result.checker_available is False
    assert result.esmini_result is not None
    assert result.esmini_result.esmini_available is False
    assert result.artifacts.preview_path == tmp_path / "preview_2d.png"
    assert result.artifacts.report_path == tmp_path / "validation_report.md"
    assert "## Timing Metrics" in result.report_text
    assert "Target TTC" in result.report_text
    json.dumps(result.to_dict())


def test_generated_scenario_workflow_applies_template_parameter_overrides(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="A rainy pedestrian occlusion scenario.",
            output_dir=tmp_path,
            provider_name="mock",
            template_parameters={
                "total_duration_s": 10.0,
                "preferred_trigger_earliest_s": 2.0,
                "preferred_trigger_latest_s": 4.0,
            },
            options=ScenarioWorkflowOptions(
                run_preview=False,
                run_runtime_checks=False,
                run_report=False,
            ),
        )
    )

    assert result.spec.timing is not None
    assert result.spec.timing.total_duration_s == 10.0
    assert result.spec.timing.preferred_trigger_earliest_s == 2.0
    assert result.spec.timing.preferred_trigger_latest_s == 4.0


class _StaticIntentProvider:
    provider_name = "static-intent"

    def __init__(self) -> None:
        self.requests = []

    def propose_intent(self, request):
        self.requests.append(request)
        return IntentProposal(
            intent=ScenarioIntent(
                template_id="lead_vehicle_braking",
                actors={"ego": {"speed_kph": 48.0}, "lead_vehicle": {"speed_kph": 30.0}},
                parameters={"scenario_name": "provider_backed_lead_braking", "initial_gap_m": 32.0},
            ),
            rationale="The prompt describes a lead vehicle braking scenario.",
            provider_name=self.provider_name,
        )


class _UnsupportedIntentProvider:
    provider_name = "unsupported-intent"

    def propose_intent(self, request):
        return IntentProposal(
            intent=None,
            rationale="The request is a highway cut-in.",
            provider_name=self.provider_name,
            status="unsupported",
            refusal_reason="No cut-in template is registered.",
            nearest_template_candidates=("lead_vehicle_braking",),
        )


class _ClarificationIntentProvider:
    provider_name = "clarification-intent"

    def propose_intent(self, request):
        return IntentProposal(
            intent=None,
            rationale="The request is ambiguous.",
            provider_name=self.provider_name,
            status="clarification_required",
            clarification_question="Should this be a pedestrian crossing or lead braking scenario?",
            nearest_template_candidates=("pedestrian_occlusion", "lead_vehicle_braking"),
        )


class _InvalidParameterIntentProvider:
    provider_name = "invalid-parameter-intent"

    def propose_intent(self, request):
        return IntentProposal(
            intent=ScenarioIntent(
                template_id="lead_vehicle_braking",
                parameters={
                    "scenario_name": "invalid_parameter_candidate",
                    "reaction_point_x_m": -4.0,
                    "target_min_ttc_s": 10.0,
                },
            ),
            rationale="The prompt describes lead vehicle braking but includes invalid generated parameters.",
            provider_name=self.provider_name,
        )


def test_generated_scenario_workflow_uses_intent_provider_before_resolver(tmp_path: Path) -> None:
    provider = _StaticIntentProvider()

    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="Ego follows a slower lead vehicle that brakes ahead.",
            output_dir=tmp_path,
            provider_name="openai-compatible",
            intent_provider=provider,
            options=ScenarioWorkflowOptions(
                run_preview=False,
                run_semantics=False,
                run_geometry_checks=False,
                run_runtime_checks=False,
                run_report=False,
            ),
        )
    )

    assert provider.requests
    assert provider.requests[0].user_text == "Ego follows a slower lead vehicle that brakes ahead."
    assert provider.requests[0].available_templates == (
        "crossing_vehicle",
        "cut_in",
        "lead_vehicle_braking",
        "oncoming_turn_across_path",
        "pedestrian_occlusion",
    )
    family_taxonomy = provider.requests[0].metadata["family_taxonomy"]
    assert family_taxonomy["cut_in"]["status"] == "early"
    assert family_taxonomy["lead_vehicle_braking"]["implemented"] is True
    assert result.spec.scenario_type == "lead_vehicle_braking"
    assert result.spec.scenario_name == "provider_backed_lead_braking"
    assert result.spec.layout.actor_poses["lead_vehicle"].x_m == 32.0
    assert result.intent_proposal is not None
    assert result.intent_proposal.intent is not None
    assert result.intent_proposal.intent.template_id == "lead_vehicle_braking"
    assert result.candidate_trace is not None
    assert result.candidate_trace.loop_name == "Candidate Generation Loop"
    assert result.candidate_trace.template_id == "lead_vehicle_braking"
    assert result.candidate_trace.acceptance_status == "accepted"
    assert result.candidate_trace.resolved_parameters["initial_gap_m"]["value"] == 32.0
    assert result.candidate_trace.resolved_parameters["initial_gap_m"]["source"] == "user"
    assert result.candidate_trace.check_summary["failed"] == 0


def test_generated_scenario_workflow_stops_on_unsupported_intent_without_building(tmp_path: Path) -> None:
    provider = _UnsupportedIntentProvider()

    try:
        run_generated_scenario_workflow(
            ScenarioWorkflowRequest(
                scenario_text="Generate a highway cut-in with three lanes.",
                output_dir=tmp_path,
                provider_name="openai-compatible",
                intent_provider=provider,
                options=ScenarioWorkflowOptions(run_preview=False, run_report=False),
            )
        )
    except IntentGenerationOutcomeError as exc:
        proposal = exc.proposal
    else:
        raise AssertionError("unsupported intent should stop before ScenarioSpec generation")

    assert proposal.status == "unsupported"
    assert proposal.nearest_template_candidates == ("lead_vehicle_braking",)
    assert not (tmp_path / "scenario_spec.json").exists()
    assert not (tmp_path / "scenario.xosc").exists()


def test_generated_scenario_workflow_stops_on_clarification_required_without_building(tmp_path: Path) -> None:
    provider = _ClarificationIntentProvider()

    try:
        run_generated_scenario_workflow(
            ScenarioWorkflowRequest(
                scenario_text="Generate an unclear dangerous urban scenario.",
                output_dir=tmp_path,
                provider_name="openai-compatible",
                intent_provider=provider,
                options=ScenarioWorkflowOptions(run_preview=False, run_report=False),
            )
        )
    except IntentGenerationOutcomeError as exc:
        proposal = exc.proposal
    else:
        raise AssertionError("clarification-required intent should stop before ScenarioSpec generation")

    assert proposal.status == "clarification_required"
    assert "pedestrian" in proposal.clarification_question


def test_candidate_generation_loop_falls_back_from_invalid_provider_parameters(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="An ego vehicle follows a lead vehicle that suddenly brakes.",
            output_dir=tmp_path,
            provider_name="openai-compatible",
            intent_provider=_InvalidParameterIntentProvider(),
            options=ScenarioWorkflowOptions(
                run_preview=False,
                run_semantics=False,
                run_geometry_checks=False,
                run_runtime_checks=False,
                run_report=False,
            ),
        )
    )

    assert result.terminal_status == "passed"
    assert result.spec.scenario_type == "lead_vehicle_braking"
    assert result.intent_proposal is not None
    assert result.intent_proposal.intent is not None
    assert result.intent_proposal.intent.parameters == {"scenario_name": "invalid_parameter_candidate"}
    assert "candidate_generation_fallback" in result.intent_proposal.intent.metadata
    assert result.candidate_trace is not None
    assert result.candidate_trace.fallback is not None
    assert result.candidate_trace.fallback["reason"] == "reaction_point_x_m must be >= 8."
    assert result.candidate_trace.fallback["discarded_parameters"] == {
        "reaction_point_x_m": -4.0,
        "target_min_ttc_s": 10.0,
    }
    assert result.candidate_trace.resolved_parameters["reaction_point_x_m"]["source"] == "default"
    assert (tmp_path / "scenario_spec.json").exists()


def test_controlled_golden_family_candidates_are_accepted_when_family_checks_pass(tmp_path: Path) -> None:
    for case in CONTROLLED_CASES:
        result = run_generated_scenario_workflow(
            ScenarioWorkflowRequest(
                scenario_text=case.source_text,
                output_dir=tmp_path / case.case_id,
                provider_name="controlled_case",
                controlled_case_id=case.case_id,
                options=ScenarioWorkflowOptions(
                    run_preview=False,
                    run_semantics=True,
                    run_geometry_checks=True,
                    run_artifact_checks=True,
                    run_runtime_checks=False,
                    run_report=False,
                    run_asam_qc=False,
                    run_esmini=False,
                    run_playback=False,
                ),
            )
        )

        assert result.terminal_status == "passed", case.case_id
        assert result.candidate_trace is not None
        assert result.candidate_trace.acceptance_status == "accepted", case.case_id
        assert result.candidate_trace.check_summary["failed"] == 0, case.case_id


def test_candidate_acceptance_trace_excludes_post_build_runtime_evidence(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="A pedestrian emerges from behind a parked van.",
            output_dir=tmp_path,
            provider_name="controlled_case",
            controlled_case_id="pedestrian_occlusion",
            options=ScenarioWorkflowOptions(
                run_preview=False,
                run_semantics=True,
                run_geometry_checks=True,
                run_artifact_checks=True,
                run_runtime_checks=True,
                run_report=False,
                run_asam_qc=False,
                run_esmini=False,
                run_playback=False,
            ),
        )
    )

    assert any(not check.passed for check in result.runtime_check_results)
    assert result.candidate_trace is not None
    assert result.candidate_trace.acceptance_status == "accepted"
    assert result.candidate_trace.check_summary["failed"] == 0
    assert result.candidate_trace.check_summary["failed_checks"] == []


def test_controlled_repair_case_skips_optional_integrations_until_repair(tmp_path: Path) -> None:
    result = run_generated_scenario_workflow(
        ScenarioWorkflowRequest(
            scenario_text="A rainy pedestrian occlusion scenario.",
            output_dir=tmp_path,
            provider_name="mock",
            demo_case_id="geometry_van_in_ego_lane",
            options=ScenarioWorkflowOptions(
                run_preview=True,
                run_semantics=True,
                run_geometry_checks=True,
                run_runtime_checks=True,
                run_report=True,
                run_asam_qc=True,
                run_playback=True,
                stop_optional_integrations_when_demo_repair_required=True,
            ),
        )
    )

    assert result.terminal_status == "repair_required"
    assert result.prepared_case is not None
    assert result.qc_result is None
    assert result.esmini_result is None
    assert result.playback_result is None
    assert result.runtime_check_results == ()
    assert result.artifacts.report_path is None
    assert result.artifacts.preview_path == tmp_path / "preview_2d.png"
    assert any(not check.passed for check in result.geometry_check_results)


def test_workflow_request_and_result_contracts_are_json_friendly(tmp_path: Path) -> None:
    request = ScenarioWorkflowRequest(
        scenario_text="pedestrian occlusion",
        output_dir=tmp_path,
        provider_name="mock",
        options=ScenarioWorkflowOptions(run_preview=False, run_runtime_checks=False, run_report=False),
    )
    result = run_generated_scenario_workflow(request)

    assert request.to_dict()["output_dir"] == str(tmp_path)
    payload = result.to_dict()
    assert payload["request"]["provider_name"] == "mock"
    assert payload["intent_proposal"] is None
    assert payload["artifacts"]["xosc_path"] == str(tmp_path / "scenario.xosc")
    json.dumps(payload, sort_keys=True)


def test_workspace_generate_callback_delegates_to_application_workflow() -> None:
    source = Path("scenariocraft/_legacy_streamlit/app.py").read_text(encoding="utf-8")
    callback = source[
        source.index("def _generate_selected_case") : source.index("def _apply_workflow_result")
    ]

    assert "run_generated_scenario_workflow" in callback
    assert "ScenarioWorkflowRequest" in callback
    assert "prepare_demo_case" not in callback
    assert "_build_xml" not in callback
    assert "_run_qc" not in callback
    assert "_run_playback" not in callback
    assert "_write_report" not in callback


def test_external_scenario_workflow_loads_metadata_without_running_optional_tools(tmp_path: Path) -> None:
    xosc_path = tmp_path / "reference.xosc"
    xosc_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="2" date="2026-06-29T00:00:00" description="test" author="ScenarioCraft"/>
  <RoadNetwork><LogicFile filepath="roads/test.xodr"/></RoadNetwork>
  <Entities><ScenarioObject name="Ego"/></Entities>
  <Storyboard/>
</OpenSCENARIO>
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"

    result = run_external_scenario_workflow(
        ExternalScenarioWorkflowRequest(
            xosc_path=xosc_path,
            output_dir=output_dir,
            source="unit",
            relative_path="fixtures/reference.xosc",
            options=ExternalScenarioWorkflowOptions(run_asam_qc=False, run_esmini=False, run_report=True),
        )
    )

    assert result.terminal_status == "loaded"
    assert result.xosc_path == xosc_path
    assert result.working_dir == xosc_path.parent
    assert result.xosc_text.startswith("<?xml")
    assert result.metadata.parse_success is True
    assert result.metadata.logic_file_paths == ["roads/test.xodr"]
    assert result.build_result.xosc_path == xosc_path
    assert result.build_result.builder == "loaded_xosc"
    assert result.qc_result is not None
    assert result.qc_result.checker_available is False
    assert result.esmini_result is not None
    assert result.esmini_result.esmini_available is False
    assert result.report_path == output_dir / "validation_report.md"
    assert "ScenarioCraft Loaded OpenSCENARIO Report" in result.report_text
    json.dumps(result.to_dict(), sort_keys=True)


def test_external_view_delegates_loaded_checks_to_application_workflow() -> None:
    source = Path("scenariocraft/_legacy_streamlit/external_view.py").read_text(encoding="utf-8")
    check_body = source[
        source.index("def _run_loaded_xosc_checks") : source.index("def _run_loaded_qc_only")
    ]
    qc_body = source[
        source.index("def _run_loaded_qc_only") : source.index("def _current_metadata")
    ]

    assert "run_external_scenario_workflow" in check_body
    assert "run_external_scenario_workflow" in qc_body
    assert "run_asam_qc(" not in check_body
    assert "run_esmini(" not in check_body
    assert "run_asam_qc(" not in qc_body
