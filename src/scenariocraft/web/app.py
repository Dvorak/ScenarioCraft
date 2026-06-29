from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
from scenariocraft.schemas import (
    ActorSpec,
    CriticalitySpec,
    ScenarioSpec,
    TriggerSpec,
)
from scenariocraft.tools import (
    AsamQcResult,
    BuildResult,
    EsminiPlaybackResult,
    EsminiResult,
    build_openscenario,
    generate_2d_preview,
    run_asam_qc,
    run_esmini,
    run_esmini_playback,
    validate_semantics,
)
from scenariocraft.tools.semantic_validator import SemanticValidationResult
from scenariocraft.web.actions import run_runtime_probes_for_generated_scenario, write_generated_validation_report
from scenariocraft.web.advanced_view import render_advanced_page
from scenariocraft.web.demo_cases import (
    DEMO_CASES,
    DemoCaseExecution,
    PreparedDemoCase,
    execute_prepared_demo_case,
    get_demo_case,
    prepare_demo_case,
    run_demo_case,
)
from scenariocraft.web.external_view import (
    render_external_scenario_studio,
    render_loaded_playback_panel,
)
from scenariocraft.web.media_view import (
    _frame_sequence_state,
    _playback_media_label,
    _should_render_frame_sequence,
    _verified_esmini_frame_paths,
    render_playback_panel,
    render_workspace_runtime_media,
)
from scenariocraft.web.state import (
    CRITICALITY_MAX_TTC_S,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_SCENARIO_TEXT,
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
    StatusCardViewModel,
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


def _render_request_panel() -> None:
    st.markdown("### Scenario Request")

    scenario_text = st.text_area("Request", value=st.session_state.scenario_text, height=145, label_visibility="collapsed")
    st.session_state.scenario_text = scenario_text
    provider_name = st.selectbox("Provider", ["mock"], index=0)
    demo_mode = st.selectbox("Demo Mode", DEMO_MODES, index=DEMO_MODES.index(st.session_state.demo_mode))
    st.session_state.demo_mode = demo_mode

    status = _status_label()
    st.markdown(status, unsafe_allow_html=True)

    actions = st.columns(2)
    with actions[0]:
        if st.button("Generate & Play", type="primary", width="stretch"):
            _generate_and_play(provider_name, demo_mode)
    with actions[1]:
        if _needs_repair():
            if st.button("Repair Scenario", width="stretch"):
                _repair_current_scenario(output_dir=Path(st.session_state.output_dir))
        else:
            st.button("Repair Scenario", disabled=True, width="stretch")

    with st.expander("Advanced settings", expanded=False):
        output_root = Path(st.text_input("Output root", st.session_state.output_root))
        st.session_state.output_root = str(output_root)
        try_video = st.checkbox("Try to generate playback video", value=st.session_state.try_playback_video)
        st.session_state.try_playback_video = try_video
        playback_mode = st.selectbox(
            "esmini mode",
            ["full/playback attempt", "smoke check"],
            index=["full/playback attempt", "smoke check"].index(st.session_state.playback_mode),
        )
        st.session_state.playback_mode = playback_mode
        require_esmini = st.checkbox("Require esmini", value=st.session_state.require_esmini)
        st.session_state.require_esmini = require_esmini
        esmini_timeout = st.number_input(
            "esmini timeout",
            min_value=1.0,
            max_value=120.0,
            value=st.session_state.playback_timeout,
            step=1.0,
        )
        st.session_state.playback_timeout = float(esmini_timeout)
        sim_duration = st.number_input(
            "sim duration",
            min_value=0.5,
            max_value=30.0,
            value=st.session_state.esmini_sim_duration,
            step=0.5,
        )
        st.session_state.esmini_sim_duration = float(sim_duration)
        esmini_bin = st.text_input("esmini binary", value=st.session_state.esmini_bin)
        st.session_state.esmini_bin = esmini_bin
    st.caption(f"Artifacts: `{st.session_state.output_dir}`")


def _render_generated_brief_panel() -> None:
    st.markdown("### Scenario Brief")
    vm = _generated_view_model()
    if _current_spec(show_error=False) is None:
        st.info(vm.road_summary)
        return
    st.markdown(f"#### {vm.title}")
    st.caption(vm.scenario_type)
    cols = st.columns(4)
    cols[0].metric("Ego speed", vm.ego_speed)
    cols[1].metric("Pedestrian", vm.pedestrian_speed)
    cols[2].metric("Target TTC", vm.target_ttc)
    cols[3].metric("Lead Time", vm.ego_lead_time)
    st.markdown(f"**Road**: {vm.road_summary}")
    st.markdown(f"**Weather**: {vm.weather_summary}")
    st.markdown(f"**Trigger**: {vm.trigger_summary}")
    st.markdown(f"**Trigger threshold**: {vm.trigger_threshold_time}")
    st.markdown(f"**Pedestrian to conflict**: {vm.pedestrian_time_to_conflict}")
    st.markdown(f"**Criticality**: {vm.criticality_summary}")
    if vm.actor_summary:
        st.caption("Actors: " + ", ".join(f"`{actor}`" for actor in vm.actor_summary))
    _render_status_cards(vm.status_cards)
    if vm.recommendation == "Use as generated demo":
        st.success(vm.recommendation)
    else:
        st.info(vm.recommendation)
    for item in vm.diagnostics:
        st.caption(item)


def _render_playback_tabs(output_dir: Path) -> None:
    st.markdown("### Visual Comparison")
    preview_col, playback_col = st.columns(2, gap="large")
    with preview_col:
        st.markdown("#### 2D Semantic Preview")
        st.caption(PREVIEW_VISUAL_CAPTION)
        spec = _current_spec(show_error=False)
        if spec is None:
            st.info("Generate a mock ScenarioSpec to see the deterministic 2D preview.")
        else:
            preview_path = _ensure_preview(output_dir, spec)
            if preview_path is not None and preview_path.exists():
                st.image(str(preview_path), width="stretch", caption="2D Semantic Preview")
            else:
                st.warning("2D preview could not be generated.")
    with playback_col:
        st.markdown("#### esmini Runtime Playback")
        st.caption(RUNTIME_VISUAL_CAPTION)
        _render_playback_panel(output_dir)


def _render_playback_panel(output_dir: Path) -> None:
    render_playback_panel(
        output_dir,
        build_result=st.session_state.build_result,
        playback_result=st.session_state.playback_result,
        run_playback=_run_playback,
    )


def _render_validation_status_panel() -> None:
    st.markdown("### Validation Status")
    vm = _generated_view_model()
    _render_status_cards(vm.status_cards)
    if _needs_repair():
        st.warning(_failure_summary())
    elif isinstance(st.session_state.semantic_result, SemanticValidationResult) and st.session_state.semantic_result.passed:
        st.success("Generated scenario validation passed.")
    else:
        st.info("Generate & Play to run validation.")


def _render_demo_experiments(output_dir: Path) -> None:
    with st.expander("Demo Mode: Validation and Repair Experiments", expanded=False):
        spec = _current_spec(show_error=False)
        case_ids = [case.case_id for case in DEMO_CASES]
        selected_case_id = st.selectbox(
            "Controlled case",
            case_ids,
            index=case_ids.index(st.session_state.selected_demo_case_id),
            format_func=lambda case_id: get_demo_case(case_id).display_name,
        )
        st.session_state.selected_demo_case_id = selected_case_id
        selected_case = get_demo_case(selected_case_id)
        case_columns = st.columns(3)
        case_columns[0].metric("Fault domain", selected_case.fault_domain)
        case_columns[1].metric("Repair expectation", selected_case.repair_expectation)
        case_columns[2].metric("Provider used", "Yes - Fake" if selected_case.uses_provider else "No")
        st.caption(selected_case.description)
        requested = st.button(
            "Run Selected Demo",
            disabled=spec is None,
            key="run_selected_demo_experiment",
        )
        if spec is None:
            st.info("Generate a layout-backed pedestrian_occlusion ScenarioSpec first.")
        elif requested:
            try:
                experiment = _run_demo_experiment_if_requested(
                    selected_case_id,
                    spec,
                    output_dir,
                    requested=True,
                )
                if experiment is not None:
                    _, trace = experiment
                    st.session_state.demo_experiment_trace = trace
                _info("Selected validation and repair experiment completed.")
            except Exception as exc:
                st.session_state.demo_experiment_trace = None
                _error(f"Demo experiment failed: {exc}")

        trace = st.session_state.demo_experiment_trace
        if isinstance(trace, DemoExperimentTraceViewModel) and trace.case_id == selected_case_id:
            _render_demo_experiment_trace(trace)
        elif spec is not None:
            st.info("The selected experiment has not been run for this generated scenario.")


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


def _render_external_scenario_studio(output_dir: Path) -> None:
    render_external_scenario_studio(output_dir)


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


def _render_preview_panel() -> None:
    st.markdown("### Playback / 2D Preview")
    if _is_load_mode():
        render_loaded_playback_panel()
        return
    spec = _current_spec(show_error=False)
    if spec is None:
        st.info("Generate a ScenarioSpec to see the 2D preview.")
        return
    preview_tab, esmini_tab = st.tabs(["2D Preview", "esmini Check"])
    with preview_tab:
        preview_path = _ensure_preview(Path(st.session_state.output_dir), spec)
        if preview_path is not None and preview_path.exists():
            st.image(str(preview_path), width="stretch")
        else:
            st.warning("2D preview could not be generated.")
        vm = _generated_view_model()
        metric_cols = st.columns(4)
        metric_cols[0].metric("Ego Speed", vm.ego_speed)
        metric_cols[1].metric("Trigger Dist", f"{spec.trigger.distance_m:g} m")
        metric_cols[2].metric("Ped Speed", vm.pedestrian_speed)
        metric_cols[3].metric("Lead Time", vm.ego_lead_time)
        st.caption(f"{vm.trigger_threshold_summary} · Target TTC: {vm.target_ttc}")
        _render_status_label()
    with esmini_tab:
        st.caption("Optional esmini execution/load check. MP4/GIF rendering is not implemented yet.")
        if st.button("Run esmini Check", width="stretch"):
            _run_esmini(
                Path(st.session_state.output_dir),
                require_esmini=st.session_state.require_esmini,
                esmini_bin=st.session_state.esmini_bin or None,
                timeout_s=st.session_state.esmini_timeout,
            )
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            st.json(esmini_result.to_dict())
        else:
            st.info("esmini has not run.")


def _render_advanced_artifacts(output_dir: Path) -> None:
    st.markdown("### Advanced")
    with st.expander("ScenarioSpec JSON", expanded=False):
        spec_json = st.text_area("ScenarioSpec JSON", value=st.session_state.spec_json, height=320, label_visibility="collapsed")
        st.session_state.spec_json = spec_json
    with st.expander("OpenSCENARIO XML", expanded=False):
        _render_xml_panel(output_dir)
    with st.expander("Semantic validation", expanded=False):
        semantic_result = st.session_state.semantic_result
        if isinstance(semantic_result, SemanticValidationResult):
            st.json(semantic_result.to_dict())
        else:
            st.info("Semantic validation has not run.")
    with st.expander("ASAM QC report", expanded=False):
        qc_result = st.session_state.qc_result
        if isinstance(qc_result, AsamQcResult):
            st.json(qc_result.to_dict())
        else:
            st.info("ASAM QC has not run.")
    with st.expander("esmini log", expanded=False):
        playback_result = st.session_state.playback_result
        if isinstance(playback_result, EsminiPlaybackResult):
            st.json(playback_result.to_dict())
            playback_json = output_dir / "esmini_playback_result.json"
            if playback_json.exists():
                st.text_area("esmini_playback_result.json", playback_json.read_text(encoding="utf-8"), height=180, label_visibility="collapsed")
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            st.json(esmini_result.to_dict())
            for name in ("esmini_log.txt", "esmini_stdout.txt", "esmini_stderr.txt", "esmini_help.txt"):
                log_path = output_dir / name
                if log_path.exists():
                    st.text_area(name, log_path.read_text(encoding="utf-8"), height=180, label_visibility="collapsed")
        else:
            st.info("esmini has not run.")
    with st.expander("Generated artifact paths", expanded=False):
        for artifact in [
            "input.txt",
            "scenario_spec.json",
            "scenario.xosc",
            "preview_2d.png",
            "playback.mp4",
            "playback.gif",
            "esmini_result.json",
            "esmini_playback_result.json",
            "validation_report.md",
        ]:
            path = output_dir / artifact
            st.caption(f"{artifact}: `{path}`" + (" exists" if path.exists() else ""))
    with st.expander("repair history", expanded=False):
        if st.session_state.repair_history:
            st.json(st.session_state.repair_history)
        else:
            st.info("No repairs recorded.")
    with st.expander("validation_report.md", expanded=False):
        st.text_area("validation_report.md", st.session_state.report_text, height=320, label_visibility="collapsed")


def _ensure_state() -> None:
    ensure_session_state()


def _generator(provider_name: str) -> ScenarioGenerator:
    if provider_name == "mock":
        return MockScenarioGenerator()
    raise ValueError(f"Unsupported provider: {provider_name}")


def _is_load_mode() -> bool:
    return st.session_state.workflow_mode == "Load existing .xosc"


def _generate_and_run(provider_name: str, demo_mode: str) -> None:
    _generate_spec(provider_name, st.session_state.scenario_text, demo_mode)
    _run_pipeline(
        Path(st.session_state.output_dir),
        st.session_state.run_esmini_check,
        st.session_state.require_esmini,
        st.session_state.esmini_bin or None,
        st.session_state.esmini_timeout,
    )


def _generate_and_play(provider_name: str, demo_mode: str) -> None:
    output_dir = _new_web_output_dir()
    _generate_spec(provider_name, st.session_state.scenario_text, demo_mode)
    _run_pipeline(
        output_dir,
        run_esmini_check=False,
        require_esmini=st.session_state.require_esmini,
        esmini_bin=st.session_state.esmini_bin or None,
        esmini_timeout=st.session_state.playback_timeout,
    )
    _run_playback(output_dir)
    _write_report(output_dir)
    _info("Generated scenario, preview, playback/check, and validation report completed.")


def _generate_selected_case(provider_name: str, case_id: str) -> None:
    output_dir = _new_web_output_dir()
    try:
        canonical = _generator(provider_name).generate_spec(st.session_state.scenario_text)
        prepared = prepare_demo_case(case_id, canonical, output_dir)
    except Exception as exc:
        _error(f"Scenario generation or case preparation failed: {exc}")
        return

    _set_spec(prepared.experiment_spec)
    st.session_state.workspace_original_spec = prepared.original_spec
    st.session_state.workspace_prepared_case = prepared
    st.session_state.workspace_execution = None
    try:
        _build_xml(output_dir)
        _run_semantics()
        if prepared.case.fault_domain == "none":
            _run_qc(output_dir)
            _run_playback(output_dir)
            _write_report(output_dir)
        else:
            st.session_state.qc_result = None
            st.session_state.esmini_result = None
            st.session_state.playback_result = None
    except Exception as exc:
        _error(f"Scenario preparation failed: {exc}")
        return
    _info(f"Prepared {prepared.case.display_name}.")


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


def _run_playback(output_dir: Path) -> None:
    build_result = _ensure_build_result(output_dir)
    _write_current_xml_if_present(build_result)
    mode = "smoke" if st.session_state.playback_mode == "smoke check" else "playback"
    playback_result = run_esmini_playback(
        build_result.xosc_path,
        output_dir,
        working_dir=build_result.xosc_path.parent,
        binary=st.session_state.esmini_bin or None,
        timeout_s=st.session_state.playback_timeout,
        sim_duration_s=st.session_state.esmini_sim_duration,
        try_video=st.session_state.try_playback_video,
        mode=mode,
    )
    st.session_state.playback_result = playback_result
    esmini_json = output_dir / "esmini_result.json"
    if esmini_json.exists():
        try:
            st.session_state.esmini_result = EsminiResult(**json.loads(esmini_json.read_text(encoding="utf-8")))
        except (TypeError, json.JSONDecodeError):
            st.session_state.esmini_result = None
    _run_runtime_probes(output_dir)
    _info("esmini playback/check completed." if playback_result.esmini_available else "esmini playback/check skipped.")


def _generate_spec(provider_name: str, scenario_text: str, demo_mode: str) -> None:
    try:
        spec = _apply_demo_mode(_generator(provider_name).generate_spec(scenario_text), demo_mode)
    except Exception as exc:
        _error(f"ScenarioSpec generation failed: {exc}")
        return
    _set_spec(spec)
    _info(f"ScenarioSpec generated: {demo_mode}.")


def _apply_demo_mode(spec: ScenarioSpec, demo_mode: str) -> ScenarioSpec:
    if demo_mode == "Missing pedestrian":
        return replace(
            spec,
            actors=[actor for actor in spec.actors if actor.role != "crossing_actor"],
            metadata={**spec.metadata, "demo_mode": demo_mode},
        )
    if demo_mode == "Low criticality":
        return replace(
            spec,
            trigger=TriggerSpec(
                type=spec.trigger.type,
                source=spec.trigger.source,
                target=spec.trigger.target,
                distance_m=60,
            ),
            intended_criticality=CriticalitySpec(type="non_critical", target_min_ttc_s=6),
            metadata={**spec.metadata, "demo_mode": demo_mode},
        )
    return replace(spec, metadata={**spec.metadata, "demo_mode": demo_mode})


def _run_pipeline(
    output_dir: Path,
    run_esmini_check: bool,
    require_esmini: bool,
    esmini_bin: str | None,
    esmini_timeout: float,
) -> None:
    if _current_spec() is None:
        _error("Generate a ScenarioSpec before running the pipeline.")
        return
    try:
        _build_xml(output_dir)
        _generate_preview(output_dir)
        _run_semantics()
        _run_qc(output_dir)
        if run_esmini_check:
            _run_esmini(output_dir, require_esmini=require_esmini, esmini_bin=esmini_bin, timeout_s=esmini_timeout)
        else:
            st.session_state.esmini_result = _missing_esmini_result(_ensure_build_result(output_dir).xosc_path)
        _run_runtime_probes(output_dir)
        _write_report(output_dir)
        _write_repair_history(output_dir)
        _info("Pipeline run completed.")
    except Exception as exc:
        _error(f"Pipeline run failed: {exc}")


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


def _repair_current_scenario(output_dir: Path) -> None:
    spec = _current_spec()
    if spec is None:
        return
    repaired = _repair_spec(spec)
    st.session_state.repair_history.append({
        "round": len(st.session_state.repair_history) + 1,
        "previous_demo_mode": spec.metadata.get("demo_mode", "unknown"),
        "changes": _repair_summary(spec, repaired),
    })
    _set_spec(repaired)
    _write_repair_history(output_dir)
    _run_pipeline(
        output_dir,
        st.session_state.run_esmini_check,
        st.session_state.require_esmini,
        st.session_state.esmini_bin or None,
        st.session_state.esmini_timeout,
    )


def _repair_spec(spec: ScenarioSpec) -> ScenarioSpec:
    actors = list(spec.actors)
    if spec.actor_by_role("crossing_actor") is None:
        actors.append(ActorSpec(id="pedestrian", type="pedestrian", role="crossing_actor", speed_mps=1.5))
    repaired_trigger = spec.trigger
    if spec.trigger.distance_m > 30:
        repaired_trigger = TriggerSpec(
            type=spec.trigger.type,
            source=spec.trigger.source,
            target=spec.trigger.target,
            distance_m=18,
        )
    repaired_criticality = spec.intended_criticality
    if _criticality_too_low(spec):
        repaired_criticality = CriticalitySpec(type="near_miss", target_min_ttc_s=1.5)
    return replace(
        spec,
        actors=actors,
        trigger=repaired_trigger,
        intended_criticality=repaired_criticality,
        metadata={**spec.metadata, "demo_mode": "Normal good scenario", "repaired": True},
    )


def _repair_summary(previous: ScenarioSpec, repaired: ScenarioSpec) -> list[str]:
    changes: list[str] = []
    if previous.actor_by_role("crossing_actor") is None and repaired.actor_by_role("crossing_actor") is not None:
        changes.append("Added pedestrian crossing actor.")
    if previous.trigger.distance_m != repaired.trigger.distance_m:
        changes.append(f"Changed trigger distance from {previous.trigger.distance_m:g} m to {repaired.trigger.distance_m:g} m.")
    if previous.intended_criticality.target_min_ttc_s != repaired.intended_criticality.target_min_ttc_s:
        changes.append(
            "Changed target TTC from "
            f"{previous.intended_criticality.target_min_ttc_s:g} s to "
            f"{repaired.intended_criticality.target_min_ttc_s:g} s."
        )
    return changes or ["No deterministic repair was needed."]


def _write_repair_history(output_dir: Path) -> None:
    if not st.session_state.repair_history:
        return
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "repair_history.json").write_text(
        json.dumps(st.session_state.repair_history, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
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


def _render_status_label() -> None:
    if _needs_repair():
        st.error(f"Needs repair: {_failure_summary()}")
    elif st.session_state.semantic_result and st.session_state.semantic_result.passed:
        st.success("Executable")
    else:
        st.warning("Validation warning: semantic validation has not run.")


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


def _render_status_cards(status_cards: list[StatusCardViewModel]) -> None:
    if not status_cards:
        return
    cards = st.columns(min(len(status_cards), 4))
    for column, card in zip(cards, status_cards):
        column.metric(card.label, card.value)
        column.caption(card.detail)


def _status_label() -> str:
    if st.session_state.last_error:
        return f'<div class="status-error">{escape(st.session_state.last_error)}</div>'
    if st.session_state.last_info:
        return f'<div class="status-ok">{escape(st.session_state.last_info)}</div>'
    return '<div class="status-muted">Ready</div>'


def _info(message: str) -> None:
    st.session_state.last_info = message
    st.session_state.last_error = ""


def _error(message: str) -> None:
    st.session_state.last_error = message
    st.session_state.last_info = ""


if __name__ == "__main__":
    main()
