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


def test_application_layer_has_no_delivery_or_process_imports() -> None:
    application_dir = Path("src/scenariocraft/application")
    source = "\n".join(path.read_text(encoding="utf-8") for path in application_dir.glob("*.py"))

    assert "import streamlit" not in source
    assert "import fastapi" not in source
    assert "import openai" not in source
    assert "import subprocess" not in source
    assert "st.session_state" not in source
    assert "scenariocraft.web" not in source


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
                run_geometry_probes=False,
                run_runtime_probes=False,
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
                run_geometry_probes=True,
                run_runtime_probes=False,
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
                run_runtime_probes=False,
                run_report=False,
            ),
        )
    )

    assert result.spec.timing is not None
    assert result.spec.timing.total_duration_s == 10.0
    assert result.spec.timing.preferred_trigger_earliest_s == 2.0
    assert result.spec.timing.preferred_trigger_latest_s == 4.0


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
                run_geometry_probes=True,
                run_runtime_probes=True,
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
    assert result.runtime_probe_results == ()
    assert result.artifacts.report_path is None
    assert result.artifacts.preview_path == tmp_path / "preview_2d.png"
    assert any(not probe.passed for probe in result.geometry_probe_results)


def test_workflow_request_and_result_contracts_are_json_friendly(tmp_path: Path) -> None:
    request = ScenarioWorkflowRequest(
        scenario_text="pedestrian occlusion",
        output_dir=tmp_path,
        provider_name="mock",
        options=ScenarioWorkflowOptions(run_preview=False, run_runtime_probes=False, run_report=False),
    )
    result = run_generated_scenario_workflow(request)

    assert request.to_dict()["output_dir"] == str(tmp_path)
    payload = result.to_dict()
    assert payload["request"]["provider_name"] == "mock"
    assert payload["artifacts"]["xosc_path"] == str(tmp_path / "scenario.xosc")
    json.dumps(payload, sort_keys=True)


def test_workspace_generate_callback_delegates_to_application_workflow() -> None:
    source = Path("src/scenariocraft/web/app.py").read_text(encoding="utf-8")
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
    source = Path("src/scenariocraft/web/external_view.py").read_text(encoding="utf-8")
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
