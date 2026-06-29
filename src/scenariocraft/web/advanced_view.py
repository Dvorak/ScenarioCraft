from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from scenariocraft.runtime import AsamQcResult, EsminiPlaybackResult
from scenariocraft_core.validation import SemanticValidationResult
from scenariocraft.application.demo_cases import PreparedDemoCase
from scenariocraft.web.view_models import DemoExperimentTraceViewModel


def render_advanced_page(
    output_dir: Path,
    *,
    spec_json: str,
    semantic_result: object,
    prepared_case: PreparedDemoCase | None,
    qc_result: object,
    playback_result: object,
    runtime_probe_results: object,
    report_text: str,
    render_xml_panel: Callable[[Path], None],
    render_demo_trace: Callable[[DemoExperimentTraceViewModel], None],
    demo_trace: object,
) -> str:
    st.markdown("### Advanced")
    updated_spec_json = spec_json
    columns = st.columns(2, gap="large", vertical_alignment="top")
    with columns[0]:
        with st.expander("ScenarioSpec JSON", expanded=True):
            updated_spec_json = st.text_area(
                "ScenarioSpec JSON",
                updated_spec_json,
                height=320,
                label_visibility="collapsed",
            )
        with st.expander("OpenSCENARIO XML", expanded=False):
            render_xml_panel(output_dir)
        with st.expander("Repair / Experiment Trace", expanded=False):
            if isinstance(demo_trace, DemoExperimentTraceViewModel):
                render_demo_trace(demo_trace)
            else:
                st.info("No repair experiment trace.")
    with columns[1]:
        with st.expander("Semantic / Geometry Validation", expanded=True):
            if isinstance(semantic_result, SemanticValidationResult):
                st.json(semantic_result.to_dict())
            if prepared_case is not None:
                st.json([probe.to_dict() for probe in prepared_case.initial_geometry_probe_results])
        with st.expander("ASAM QC", expanded=False):
            st.json(qc_result.to_dict()) if isinstance(qc_result, AsamQcResult) else st.info("ASAM QC has not run.")
        with st.expander("esmini / Media Provenance", expanded=False):
            if isinstance(playback_result, EsminiPlaybackResult):
                st.json(playback_result.to_dict())
            else:
                st.info("esmini playback has not run.")
        with st.expander("Runtime Consistency Probes", expanded=False):
            if runtime_probe_results:
                st.json([probe.to_dict() for probe in runtime_probe_results])
            else:
                st.info("Runtime probes have not run.")
        with st.expander("Artifacts / Report", expanded=False):
            st.caption(f"Output · `{output_dir}`")
            st.text_area("validation_report.md", report_text, height=220, label_visibility="collapsed")
    return updated_spec_json
