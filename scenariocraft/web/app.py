from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import streamlit as st

from scenariocraft.application import (
    ScenarioWorkflowOptions,
    ScenarioWorkflowRequest,
    ScenarioWorkflowResult,
    run_generated_scenario_workflow,
)
from scenariocraft.application.demo_cases import (
    DEMO_CASES,
    DemoCaseExecution,
    PreparedDemoCase,
    execute_prepared_demo_case,
    get_demo_case,
    prepare_demo_case,
    run_demo_case,
)
from scenariocraft.core.build import BuildResult, build_openscenario
from scenariocraft.presentation import generate_2d_preview
from scenariocraft.runtime import (
    AsamQcResult,
    EsminiPlaybackResult,
    EsminiResult,
    run_asam_qc,
    run_esmini,
    run_esmini_playback,
)
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.core.validation import SemanticValidationResult
from scenariocraft.core.validation import validate_semantics
from scenariocraft.web.actions import run_runtime_probes_for_generated_scenario, write_generated_validation_report
from scenariocraft.web.advanced_view import render_advanced_page
from scenariocraft.web.media_view import (
    _frame_sequence_state,
    _playback_media_label,
    _should_render_frame_sequence,
    _verified_esmini_frame_paths,
)
from scenariocraft.web.state import (
    CRITICALITY_MAX_TTC_S,
    DEFAULT_OUTPUT_ROOT,
    PREVIEW_VISUAL_CAPTION,
    RUNTIME_VISUAL_CAPTION,
    WEB_PREVIEW_DISPLAY_ORIENTATION,
    WEB_PREVIEW_PRESENTATION_STYLE,
    WORKSPACE_DESKTOP_HEIGHT,
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_MEDIA_ASPECT_RATIO,
    WORKSPACE_MEDIA_TITLES,
    WORKSPACE_PAGES,
    WORKSPACE_PROVIDER,
    WORKSPACE_REPAIR_ICON,
    ensure_session_state,
    reset_generated_scenario_state,
)
from scenariocraft.web.styles import inject_css
from scenariocraft.web.view_models import (
    DemoExperimentTraceViewModel,
    GeneratedScenarioViewModel,
    RepairProbeTraceViewModel,
    build_demo_experiment_trace_view_model,
    build_generated_scenario_view_model,
)
from scenariocraft.web.workspace_view import render_workspace, workspace_case_options


def main() -> None:
    st.set_page_config(page_title="ScenarioCraft-Agent", layout="wide")
    inject_css()
    _ensure_state()

    header = st.columns([0.68, 0.32], vertical_alignment="center")
    with header[0]:
        st.markdown("## ScenarioCraft")
    with header[1]:
        active_page = st.segmented_control(
            "View",
            WORKSPACE_PAGES,
            default=st.session_state.active_page,
            label_visibility="collapsed",
            width="stretch",
        )
        st.session_state.active_page = active_page or "Workspace"

    output_dir = Path(st.session_state.output_dir)
    if st.session_state.active_page == "Advanced":
        _render_advanced_page(output_dir)
    else:
        _render_workspace(output_dir)


def _render_workspace(output_dir: Path) -> None:
    render_workspace(
        output_dir,
        scenario_text=st.session_state.scenario_text,
        selected_demo_case_id=st.session_state.selected_demo_case_id,
        prepared_case=_prepared_case(),
        semantic_result=st.session_state.semantic_result,
        qc_result=st.session_state.qc_result,
        esmini_result=st.session_state.esmini_result,
        playback_result=st.session_state.playback_result,
        current_spec=lambda: _current_spec(show_error=False),
        generated_view_model=_generated_view_model,
        ensure_preview=_ensure_preview,
        set_scenario_text=lambda value: setattr(st.session_state, "scenario_text", value),
        set_selected_demo_case_id=lambda value: setattr(st.session_state, "selected_demo_case_id", value),
        generate_selected_case=_generate_selected_case,
        execute_workspace_repair=_execute_workspace_repair,
    )


def _render_advanced_page(output_dir: Path) -> None:
    st.session_state.spec_json = render_advanced_page(
        output_dir,
        spec_json=st.session_state.spec_json,
        semantic_result=st.session_state.semantic_result,
        prepared_case=_prepared_case(),
        qc_result=st.session_state.qc_result,
        playback_result=st.session_state.playback_result,
        runtime_probe_results=st.session_state.runtime_probe_results,
        report_text=st.session_state.report_text,
        render_xml_panel=_render_xml_panel,
        render_demo_trace=_render_demo_experiment_trace,
        demo_trace=st.session_state.demo_experiment_trace,
    )


def _render_demo_experiment_trace(trace: DemoExperimentTraceViewModel) -> None:
    st.markdown(f"#### {trace.display_name}")
    st.caption(trace.description)

    st.markdown("##### 1. Scenario / Fault Setup")
    if trace.fault_domain == "none":
        st.success(trace.setup_description)
    elif trace.fault_domain == "geometry":
        st.warning(trace.setup_description)
    else:
        st.error(trace.setup_description)
    st.json(trace.setup_values)
    if trace.injected_operations:
        st.caption("Controlled ScenarioSpec injection PatchSpec")
        st.json(list(trace.injected_operations))

    st.markdown("##### 2. Initial Geometry Probe Result")
    _render_repair_probe_results(trace.initial_geometry_results, show_failure_evidence=True)

    st.markdown("##### 3. Provider Decision")
    if trace.provider_name is not None:
        st.caption(f"Provider: FakeRepairProvider (`{trace.provider_name}`)")
    st.info(trace.provider_decision)

    st.markdown("##### 4. PatchSpec Proposal")
    if trace.proposed_operations:
        st.json(list(trace.proposed_operations))
    else:
        st.info("No PatchSpec proposal.")

    st.markdown("##### 5. Patch Application Result")
    if trace.patch_applied:
        st.success("Patch applied through deterministic apply_patch.")
    elif trace.application_error:
        st.error(trace.application_error)
    else:
        st.info("No ScenarioSpec patch was applied.")

    st.markdown("##### 6. Geometry Revalidation")
    _render_repair_probe_results(trace.final_geometry_results)

    st.markdown("##### 7. Build and Artifact Validation")
    _render_repair_probe_results(trace.artifact_results, show_failure_evidence=True)

    st.markdown("##### 8. Terminal Status")
    if trace.terminal_status == "passed":
        st.success(f"{trace.terminal_status}: {trace.terminal_reason}")
    else:
        st.error(f"{trace.terminal_status}: {trace.terminal_reason}")

    st.markdown("##### 9. Artifact Paths")
    for path in trace.artifact_paths:
        st.caption(f"`{path}`")
    with st.expander("Diagnostic evidence", expanded=False):
        st.json({
            "setup_values": trace.setup_values,
            "initial_failures": [
                {"name": probe.name, "measured": probe.measured}
                for probe in trace.initial_geometry_results
                if not probe.passed
            ],
            "artifact_failures": [
                {"name": probe.name, "measured": probe.measured}
                for probe in trace.artifact_results
                if not probe.passed
            ],
            "artifact_paths": list(trace.artifact_paths),
        })


def _render_repair_probe_results(
    results: tuple[RepairProbeTraceViewModel, ...],
    *,
    show_failure_evidence: bool = False,
) -> None:
    if not results:
        st.warning("No probe evidence was produced.")
        return
    for probe in results:
        message = f"{probe.name}: {probe.message}"
        if probe.passed:
            st.success(message)
        else:
            st.error(message)
            if show_failure_evidence:
                st.json(probe.measured)


def _run_demo_experiment_if_requested(
    case_id: str,
    spec: ScenarioSpec,
    output_dir: Path,
    *,
    requested: bool,
) -> tuple[DemoCaseExecution, DemoExperimentTraceViewModel] | None:
    if not requested:
        return None
    execution = run_demo_case(case_id, spec, output_dir)
    return execution, build_demo_experiment_trace_view_model(execution)


def _render_xml_panel(output_dir: Path) -> None:
    st.markdown("### Generated OpenSCENARIO XML")
    xml_value = st.text_area("OpenSCENARIO XML", value=st.session_state.xosc_text, height=365, label_visibility="collapsed")
    st.session_state.xosc_text = xml_value

    if _is_load_mode():
        st.caption("Loaded external XML is displayed read-only by convention. ScenarioCraft does not modify the source file.")
        return

    buttons = st.columns(3)
    with buttons[0]:
        if st.button("Rebuild XML", width="stretch"):
            _build_xml(output_dir)
    with buttons[1]:
        if st.button("Save XML", width="stretch"):
            _save_xml(output_dir, xml_value)
    with buttons[2]:
        st.download_button(
            "Download .xosc",
            data=xml_value,
            file_name="scenario.xosc",
            mime="application/xml",
            disabled=not bool(xml_value),
            width="stretch",
        )


def _ensure_state() -> None:
    ensure_session_state()


def _is_load_mode() -> bool:
    return st.session_state.workflow_mode == "Load existing .xosc"


def _generate_selected_case(provider_name: str, case_id: str) -> None:
    output_dir = _new_web_output_dir()
    try:
        result = run_generated_scenario_workflow(
            ScenarioWorkflowRequest(
                scenario_text=st.session_state.scenario_text,
                output_dir=output_dir,
                provider_name=provider_name,
                demo_case_id=case_id,
                options=ScenarioWorkflowOptions(
                    run_preview=True,
                    run_semantics=True,
                    run_geometry_probes=True,
                    run_artifact_probes=False,
                    run_runtime_probes=True,
                    run_report=True,
                    run_asam_qc=True,
                    run_esmini=False,
                    run_playback=True,
                    require_esmini=st.session_state.require_esmini,
                    esmini_bin=st.session_state.esmini_bin or None,
                    playback_timeout_s=st.session_state.playback_timeout,
                    esmini_sim_duration_s=st.session_state.esmini_sim_duration,
                    try_playback_video=st.session_state.try_playback_video,
                    playback_mode="smoke"
                    if st.session_state.playback_mode == "smoke check"
                    else "playback",
                    preview_display_orientation=WEB_PREVIEW_DISPLAY_ORIENTATION,
                    preview_presentation_style=WEB_PREVIEW_PRESENTATION_STYLE,
                    stop_optional_integrations_when_demo_repair_required=True,
                ),
            )
        )
    except Exception as exc:
        _error(f"Scenario generation or case preparation failed: {exc}")
        return

    _apply_workflow_result(result)
    prepared = result.prepared_case
    display_name = prepared.case.display_name if isinstance(prepared, PreparedDemoCase) else result.spec.scenario_name
    _info(f"Prepared {display_name}.")


def _apply_workflow_result(result: ScenarioWorkflowResult) -> None:
    _set_spec(result.spec)
    st.session_state.output_dir = str(result.artifacts.output_dir)
    st.session_state.workspace_original_spec = result.original_spec
    st.session_state.workspace_prepared_case = (
        result.prepared_case if isinstance(result.prepared_case, PreparedDemoCase) else None
    )
    st.session_state.workspace_execution = None
    st.session_state.build_result = result.build_result
    st.session_state.xosc_text = result.xosc_text
    st.session_state.preview_path = str(result.artifacts.preview_path or "")
    st.session_state.semantic_result = result.semantic_result
    st.session_state.qc_result = result.qc_result
    st.session_state.esmini_result = result.esmini_result
    st.session_state.playback_result = result.playback_result
    st.session_state.runtime_probe_results = result.runtime_probe_results
    st.session_state.report_text = result.report_text


def _execute_workspace_repair(output_dir: Path) -> DemoCaseExecution | None:
    prepared = _prepared_case()
    if prepared is None or not prepared.repair_required:
        return None
    try:
        execution = execute_prepared_demo_case(prepared, output_dir)
    except Exception as exc:
        _error(f"Repair failed: {exc}")
        return None

    trace = build_demo_experiment_trace_view_model(execution)
    st.session_state.workspace_execution = execution
    st.session_state.demo_experiment_trace = trace
    if execution.terminal_status == "passed" and execution.repair_run_result is not None:
        _set_spec(execution.repair_run_result.final_spec)
        st.session_state.workspace_execution = execution
        st.session_state.demo_experiment_trace = trace
        st.session_state.workspace_prepared_case = None
        try:
            _build_xml(output_dir)
            _run_semantics()
        except Exception as exc:
            _error(f"Repair passed but refreshed artifacts failed: {exc}")
            return execution
        _info("Repair applied and geometry revalidated.")
    else:
        _error(execution.terminal_reason)
    return execution


def _new_web_output_dir() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(st.session_state.output_root) / timestamp
    st.session_state.output_dir = str(output_dir)
    return output_dir


def _current_spec(show_error: bool = True) -> ScenarioSpec | None:
    try:
        spec = ScenarioSpec.from_json(st.session_state.spec_json)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        if show_error:
            _error(f"ScenarioSpec JSON is invalid: {exc}")
        return None
    st.session_state.spec = spec
    return spec


def _set_spec(spec: ScenarioSpec) -> None:
    st.session_state.spec = spec
    st.session_state.spec_json = spec.to_json()
    reset_generated_scenario_state()


def _prepared_case() -> PreparedDemoCase | None:
    prepared = st.session_state.workspace_prepared_case
    return prepared if isinstance(prepared, PreparedDemoCase) else None


def _build_xml(output_dir: Path) -> None:
    spec = _current_spec()
    if spec is None:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "input.txt").write_text(st.session_state.scenario_text, encoding="utf-8")
    (output_dir / "scenario_spec.json").write_text(spec.to_json() + "\n", encoding="utf-8")
    build_result = build_openscenario(spec, output_dir)
    st.session_state.build_result = build_result
    st.session_state.xosc_text = build_result.xosc_path.read_text(encoding="utf-8")
    _generate_preview(output_dir)
    _info(f"OpenSCENARIO built with {build_result.builder}.")


def _generate_preview(output_dir: Path) -> Path | None:
    spec = _current_spec()
    if spec is None:
        return None
    try:
        preview_path = generate_2d_preview(
            spec,
            output_dir / "preview_2d.png",
            display_orientation=WEB_PREVIEW_DISPLAY_ORIENTATION,
            presentation_style=WEB_PREVIEW_PRESENTATION_STYLE,
        )
    except Exception as exc:
        _error(f"2D preview generation failed: {exc}")
        return None
    st.session_state.preview_path = str(preview_path)
    return preview_path


def _ensure_preview(output_dir: Path, spec: ScenarioSpec) -> Path | None:
    raw_path = st.session_state.preview_path
    preview_path = Path(raw_path) if raw_path else output_dir / "preview_2d.png"
    if preview_path.exists():
        return preview_path
    try:
        preview_path = generate_2d_preview(
            spec,
            preview_path,
            display_orientation=WEB_PREVIEW_DISPLAY_ORIENTATION,
            presentation_style=WEB_PREVIEW_PRESENTATION_STYLE,
        )
    except Exception as exc:
        st.warning(f"2D preview generation failed: {exc}")
        return None
    st.session_state.preview_path = str(preview_path)
    return preview_path


def _save_xml(output_dir: Path, xml_value: str) -> None:
    build_result = _ensure_build_result(output_dir)
    build_result.xosc_path.write_text(xml_value, encoding="utf-8")
    st.session_state.xosc_text = xml_value
    _info("OpenSCENARIO XML saved.")


def _run_semantics() -> None:
    spec = _current_spec()
    if spec is None:
        return
    result = validate_semantics(spec)
    st.session_state.semantic_result = result
    _info("Semantic validation completed.")


def _run_qc(output_dir: Path) -> None:
    build_result = _ensure_build_result(output_dir)
    _write_current_xml_if_present(build_result)
    result = run_asam_qc(build_result.xosc_path, output_dir)
    st.session_state.qc_result = result
    _info("ASAM QC completed." if result.checker_available else "ASAM QC skipped.")


def _run_esmini(output_dir: Path, require_esmini: bool, esmini_bin: str | None, timeout_s: float) -> None:
    build_result = _ensure_build_result(output_dir)
    _write_current_xml_if_present(build_result)
    working_dir = build_result.xosc_path.parent if _is_load_mode() else None
    result = run_esmini(
        build_result.xosc_path,
        output_dir,
        working_dir=working_dir,
        required=require_esmini,
        binary=esmini_bin,
        timeout_s=timeout_s,
    )
    st.session_state.esmini_result = result
    _info("esmini completed." if result.executed else "esmini skipped or failed.")


def _run_runtime_probes(output_dir: Path) -> None:
    spec = _current_spec()
    if spec is None:
        return
    build_result = _ensure_build_result(output_dir)
    st.session_state.runtime_probe_results = run_runtime_probes_for_generated_scenario(
        spec,
        build_result=build_result,
        output_dir=output_dir,
    )


def _write_report(output_dir: Path) -> None:
    spec = _current_spec()
    if spec is None:
        return
    build_result = _ensure_build_result(output_dir)
    semantic_result = st.session_state.semantic_result or validate_semantics(spec)
    qc_result = st.session_state.qc_result or _missing_qc_result(build_result.xosc_path, output_dir)
    esmini_result = st.session_state.esmini_result or _missing_esmini_result(build_result.xosc_path)
    report_path = write_generated_validation_report(
        scenario_text=st.session_state.scenario_text,
        spec=spec,
        build_result=build_result,
        qc_result=qc_result,
        esmini_result=esmini_result,
        semantic_result=semantic_result,
        output_dir=output_dir,
        playback_result=st.session_state.playback_result
        if isinstance(st.session_state.playback_result, EsminiPlaybackResult)
        else None,
        runtime_probe_results=st.session_state.runtime_probe_results,
    )
    st.session_state.semantic_result = semantic_result
    st.session_state.report_text = report_path.read_text(encoding="utf-8")
    _info("Validation report generated.")


def _ensure_build_result(output_dir: Path) -> BuildResult:
    build_result = st.session_state.build_result
    if build_result is not None:
        return build_result
    xosc_path = output_dir / "scenario.xosc"
    if xosc_path.exists():
        build_result = BuildResult(xosc_path=xosc_path, builder="existing_xml")
        st.session_state.build_result = build_result
        return build_result
    _build_xml(output_dir)
    build_result = st.session_state.build_result
    if build_result is None:
        raise RuntimeError("OpenSCENARIO XML has not been built.")
    return build_result


def _write_current_xml_if_present(build_result: BuildResult) -> None:
    if st.session_state.xosc_text:
        build_result.xosc_path.write_text(st.session_state.xosc_text, encoding="utf-8")


def _missing_qc_result(xosc_path: Path, output_dir: Path) -> AsamQcResult:
    config_path = output_dir / "qc_config.xml"
    result_path = output_dir / "qc_result.xqar"
    return AsamQcResult(
        checker_available=False,
        command=["qc_openscenario", "-c", str(config_path)],
        return_code=None,
        stdout="",
        stderr="ASAM OpenSCENARIO XML checker has not been run.",
        passed=None,
        config_path=str(config_path),
        result_path=str(result_path),
    )


def _missing_esmini_result(xosc_path: Path) -> EsminiResult:
    return EsminiResult(
        esmini_available=False,
        command=["esmini", "--osc", str(xosc_path), "--headless", "--quit_at_end", "--disable_log"],
        working_dir=str(xosc_path.parent),
        return_code=None,
        stdout="",
        stderr="esmini has not been run.",
        executed=None,
        error_message="esmini has not been run.",
        playback_path=None,
    )


def _needs_repair() -> bool:
    spec = _current_spec(show_error=False)
    if spec is None:
        return False
    semantic_result = st.session_state.semantic_result
    return bool(
        (isinstance(semantic_result, SemanticValidationResult) and not semantic_result.passed)
        or _criticality_too_low(spec)
    )


def _criticality_too_low(spec: ScenarioSpec) -> bool:
    return spec.intended_criticality.target_min_ttc_s > CRITICALITY_MAX_TTC_S or spec.trigger.distance_m > 30


def _failure_summary() -> str:
    spec = _current_spec(show_error=False)
    if spec is None:
        return "ScenarioSpec is invalid."
    semantic_result = st.session_state.semantic_result
    failures = []
    if isinstance(semantic_result, SemanticValidationResult):
        failures.extend(check.message for check in semantic_result.checks if not check.passed)
    if _criticality_too_low(spec):
        failures.append("Criticality is too low for the occlusion demo.")
    return " ".join(failures)


def _generated_view_model() -> GeneratedScenarioViewModel:
    semantic_result = st.session_state.semantic_result if isinstance(st.session_state.semantic_result, SemanticValidationResult) else None
    return build_generated_scenario_view_model(
        _current_spec(show_error=False),
        semantic_result=semantic_result,
        qc_result=st.session_state.qc_result if isinstance(st.session_state.qc_result, AsamQcResult) else None,
        esmini_result=st.session_state.esmini_result if isinstance(st.session_state.esmini_result, EsminiResult) else None,
        needs_repair=_needs_repair(),
        failure_summary=_failure_summary() if _current_spec(show_error=False) is not None else "",
    )


def _info(message: str) -> None:
    st.session_state.last_info = message
    st.session_state.last_error = ""


def _error(message: str) -> None:
    st.session_state.last_error = message
    st.session_state.last_info = ""


if __name__ == "__main__":
    main()
