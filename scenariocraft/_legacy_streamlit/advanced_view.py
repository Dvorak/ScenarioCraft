from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.external_tools import AsamQcResult, EsminiPlaybackResult
from scenariocraft.application.controlled_cases import CONTROLLED_CASES
from scenariocraft.core.metrics import compute_timing_metrics
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.core.checks import SemanticValidationResult
from scenariocraft.application.demo_cases import PreparedDemoCase
from scenariocraft.application.demo_cases import DEMO_CASES
from scenariocraft.core.templates import family_asset_readiness_report
from scenariocraft._legacy_streamlit.view_models import DemoExperimentTraceViewModel


def render_advanced_page(
    output_dir: Path,
    *,
    spec_json: str,
    intent_proposal: object,
    semantic_result: object,
    prepared_case: PreparedDemoCase | None,
    candidate_trace: object | None,
    qc_result: object,
    playback_result: object,
    runtime_check_results: object,
    report_text: str,
    render_xml_panel: Callable[[Path], None],
    render_demo_trace: Callable[[DemoExperimentTraceViewModel], None],
    demo_trace: object,
) -> str:
    st.markdown('<span class="advanced-page-marker" aria-hidden="true"></span>', unsafe_allow_html=True)
    st.markdown("### Advanced")
    _render_pipeline_timeline(
        spec_available=bool(spec_json.strip()),
        semantic_result=semantic_result,
        qc_result=qc_result,
        playback_result=playback_result,
        runtime_check_results=runtime_check_results,
        demo_trace=demo_trace,
    )
    updated_spec_json = spec_json
    spec = _parse_spec(spec_json)
    columns = st.columns([0.48, 0.52], gap="large", vertical_alignment="top")
    with columns[0]:
        with st.container(border=True, key="advanced_capability_tree_card"):
            _render_card_heading("Capability Tree", "Supported families, provider path, and deterministic fallbacks.")
            _render_capability_tree_summary()
            _render_loop_model_summary()
            _render_candidate_acceptance_trace(candidate_trace)
        with st.container(border=True, key="advanced_intent_spec_card"):
            _render_card_heading("Intent & Spec", "Request interpretation and typed ScenarioSpec contract.")
            _render_summary_rows(
                (
                    ("Intent source", _intent_source_label(intent_proposal)),
                    ("ScenarioSpec", "Available" if spec is not None else "Not generated"),
                    ("Template resolution", _template_resolution_label(spec)),
                )
            )
            if intent_proposal is not None:
                _render_intent_proposal(intent_proposal)
            _render_template_resolution(spec)
            with st.expander("ScenarioSpec JSON", expanded=False):
                updated_spec_json = st.text_area(
                    "ScenarioSpec JSON",
                    updated_spec_json,
                    height=300,
                    label_visibility="collapsed",
                )
        with st.container(border=True, key="advanced_build_card"):
            _render_card_heading("Build", "Deterministic ScenarioSpec to XOSC/XODR artifact construction.")
            _render_summary_rows(
                (
                    ("OpenSCENARIO", "scenario.xosc" if (output_dir / "scenario.xosc").exists() else "Not built"),
                    ("OpenDRIVE", "urban_two_way_parking.xodr" if any(output_dir.glob("*.xodr")) else "Not built"),
                )
            )
            with st.expander("OpenSCENARIO XML", expanded=False):
                render_xml_panel(output_dir)
        with st.container(border=True, key="advanced_run_card"):
            _render_card_heading("Run Artifacts", "Generated output package and validation report.")
            _render_summary_rows((("Output directory", str(output_dir)), ("Report", "validation_report.md" if report_text else "Not generated")))
            with st.expander("validation_report.md", expanded=False):
                st.text_area("validation_report.md", report_text, height=220, label_visibility="collapsed")
    with columns[1]:
        with st.container(border=True, key="advanced_checks_card"):
            _render_card_heading("Checks", "Structural, intent, geometry, and artifact consistency evidence.")
            _render_checks_summary(semantic_result, prepared_case)
            with st.expander("Check Evidence", expanded=False):
                if isinstance(semantic_result, SemanticValidationResult):
                    st.json(semantic_result.to_dict())
                if prepared_case is not None:
                    st.json([check.to_dict() for check in prepared_case.initial_geometry_check_results])
        with st.container(border=True, key="advanced_metrics_card"):
            _render_card_heading("Metrics", "Timing, TTC, THW, and criticality measurements.")
            _render_metrics(spec)
        lower = st.columns(2, gap="medium", vertical_alignment="top")
        with lower[0]:
            with st.container(border=True, key="advanced_external_card"):
                _render_card_heading("Evidence", "OSC quality and simulation/runtime evidence.")
                _render_external_summary(qc_result, playback_result, runtime_check_results)
                with st.expander("External Evidence JSON", expanded=False):
                    st.markdown("**OSC Quality**")
                    st.json(qc_result.to_dict()) if isinstance(qc_result, AsamQcResult) else st.info("OSC Quality has not run.")
                    st.markdown("**Simulation Evidence**")
                    if isinstance(playback_result, EsminiPlaybackResult):
                        st.json(playback_result.to_dict())
                    else:
                        st.info("Simulation media has not run.")
                    st.markdown("**Runtime Checks**")
                    if runtime_check_results:
                        st.json([check.to_dict() for check in runtime_check_results])
                    else:
                        st.info("Runtime checks have not run.")
        with lower[1]:
            with st.container(border=True, key="advanced_repair_card"):
                _render_card_heading("Patch Repair Trace", "PatchSpec proposal and deterministic application history.")
                if isinstance(demo_trace, DemoExperimentTraceViewModel):
                    _render_summary_rows((("Status", "Trace available"), ("Provider", "FakeRepairProvider")))
                else:
                    _render_summary_rows((("Status", "No patch repair trace"), ("PatchSpec", "Not proposed")))
                with st.expander("Patch Repair Trace Detail", expanded=False):
                    if isinstance(demo_trace, DemoExperimentTraceViewModel):
                        render_demo_trace(demo_trace)
                    else:
                        st.info("No PatchSpec repair trace.")
    return updated_spec_json


def _render_capability_tree_summary() -> None:
    _render_summary_rows(
        (
            ("Provider-backed generation", "Local/OpenAI-compatible ScenarioIntent"),
            ("Controlled Case coverage", f"{len(CONTROLLED_CASES)} executable golden families"),
            ("Repair Experiments", f"{len(DEMO_CASES)} developer fault cases"),
        )
    )
    readiness = family_asset_readiness_report()
    rows = "".join(
        '<div class="advanced-summary-row">'
        f'<span>{escape(template_id)}</span>'
        f'<strong>{"ready" if item.executable else "not ready"}</strong>'
        '</div>'
        for template_id, item in sorted(readiness.items())
    )
    st.markdown(
        '<div class="advanced-summary-list advanced-readiness-list">'
        f"{rows}"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_loop_model_summary() -> None:
    _render_summary_rows(
        (
            ("Candidate Generation Loop", "new candidate acceptance"),
            ("Scenario Revision Loop", "variant from existing scenario"),
            ("PatchSpec Repair Loop", "minimal patch after failure evidence"),
        )
    )


def _render_candidate_acceptance_trace(candidate_trace: object | None) -> None:
    if candidate_trace is None:
        _render_summary_rows((("Candidate Acceptance", "not run"),))
        return
    template_id = getattr(candidate_trace, "template_id", "n/a")
    acceptance_status = getattr(candidate_trace, "acceptance_status", "n/a")
    check_summary = getattr(candidate_trace, "check_summary", {}) or {}
    failed = check_summary.get("failed", "n/a") if isinstance(check_summary, dict) else "n/a"
    _render_summary_rows(
        (
            ("Candidate Acceptance", str(acceptance_status)),
            ("Accepted template", str(template_id)),
            ("Failed checks", str(failed)),
        )
    )
    fallback = getattr(candidate_trace, "fallback", None)
    if isinstance(fallback, dict) and fallback:
        discarded = fallback.get("discarded_parameters")
        discarded_count = len(discarded) if isinstance(discarded, dict) else 0
        _render_summary_rows(
            (
                ("Candidate fallback", "provider parameters rejected"),
                ("Discarded parameters", str(discarded_count)),
            )
        )
    resolved_parameters = getattr(candidate_trace, "resolved_parameters", {}) or {}
    if not isinstance(resolved_parameters, dict) or not resolved_parameters:
        return
    rows = "".join(
        '<div class="advanced-summary-row">'
        f'<span>{escape(str(name))}</span>'
        f'<strong>{escape(_parameter_display(parameter))}</strong>'
        '</div>'
        for name, parameter in sorted(resolved_parameters.items())
    )
    st.markdown(
        '<div class="advanced-summary-list advanced-candidate-parameters">'
        f"{rows}"
        "</div>",
        unsafe_allow_html=True,
    )


def _parameter_display(parameter: object) -> str:
    if not isinstance(parameter, dict):
        return str(parameter)
    value = parameter.get("value")
    source = parameter.get("source")
    unit = parameter.get("unit")
    suffix = f" {unit}" if unit else ""
    source_text = f" · {source}" if source else ""
    return f"{value}{suffix}{source_text}"


def _render_pipeline_timeline(
    *,
    spec_available: bool,
    semantic_result: object,
    qc_result: object,
    playback_result: object,
    runtime_check_results: object,
    demo_trace: object,
) -> None:
    stages = (
        ("Intent", "waiting", "Natural language or selected demo case"),
        ("Spec", "passed" if spec_available else "neutral", "ScenarioSpec structured source"),
        ("Build", "passed" if spec_available else "neutral", "XOSC/XODR artifact build"),
        ("Checks", _semantic_state(semantic_result), "Structural, intent, geometry, and artifact checks"),
        ("Metrics", "passed" if spec_available else "neutral", "Timing and criticality measurements"),
        ("Quality", _qc_state(qc_result), "OSC Quality, currently ASAM QC"),
        ("Simulation", _simulation_state(playback_result, runtime_check_results), "Simulation evidence, currently esmini"),
        (
            "Patch Repair",
            "passed" if isinstance(demo_trace, DemoExperimentTraceViewModel) else "neutral",
            "PatchSpec repair trace for accepted specs or artifact failures",
        ),
    )
    nodes = "".join(
        '<div class="advanced-pipeline-node" tabindex="0" '
        f'title="{escape(detail)}" aria-label="{escape(label)}: {escape(state)}. {escape(detail)}">'
        f'<span class="advanced-pipeline-icon status-{escape(state)}">{escape(label[:1])}</span>'
        f'<strong>{escape(label)}</strong>'
        f'<span class="advanced-pipeline-dot status-{escape(state)}"></span>'
        f'<small>{escape(_state_label(state))}</small>'
        '</div>'
        for label, state, detail in stages
    )
    st.markdown(
        f'<div class="advanced-pipeline-timeline" role="list">{nodes}</div>',
        unsafe_allow_html=True,
    )


def _parse_spec(spec_json: str) -> ScenarioSpec | None:
    if not spec_json.strip():
        return None
    try:
        return ScenarioSpec.from_json(spec_json)
    except Exception:
        return None


def _intent_source_label(intent_proposal: object) -> str:
    if intent_proposal is None:
        return "Demo case / mock path"
    provider = str(getattr(intent_proposal, "provider_name", "provider"))
    intent = getattr(intent_proposal, "intent", None)
    if intent is None:
        return f"{provider} refusal"
    template_id = str(getattr(intent, "template_id", "ScenarioIntent"))
    return f"{template_id} via {provider}"


def _render_intent_proposal(intent_proposal: object) -> None:
    intent = getattr(intent_proposal, "intent", None)
    rationale = str(getattr(intent_proposal, "rationale", "") or "")
    with st.expander("ScenarioIntent", expanded=False):
        if intent is None:
            st.error(str(getattr(intent_proposal, "refusal_reason", "") or rationale or "Intent unavailable."))
        else:
            st.json(intent.to_dict())
        if rationale:
            st.caption(rationale)


def _template_resolution_label(spec: ScenarioSpec | None) -> str:
    if spec is None:
        return "Not generated"
    resolution = spec.metadata.get("template_resolution")
    if not isinstance(resolution, dict):
        return "Unavailable"
    seed = resolution.get("seed")
    sampled = bool(resolution.get("sampled", False))
    if sampled:
        return f"Seed {seed}"
    return "Canonical defaults"


def _render_template_resolution(spec: ScenarioSpec | None) -> None:
    if spec is None:
        return
    resolution = spec.metadata.get("template_resolution")
    if not isinstance(resolution, dict):
        return
    with st.expander("Template Resolution", expanded=False):
        st.json(resolution)


def _render_card_heading(title: str, detail: str) -> None:
    st.markdown(
        '<div class="advanced-card-heading">'
        f'<strong>{escape(title)}</strong>'
        f'<span>{escape(detail)}</span>'
        '</div>',
        unsafe_allow_html=True,
    )


def _render_summary_rows(rows: tuple[tuple[str, str], ...]) -> None:
    markup = "".join(
        '<div class="advanced-summary-row">'
        f'<span>{escape(label)}</span>'
        f'<strong>{escape(value)}</strong>'
        '</div>'
        for label, value in rows
    )
    st.markdown(f'<div class="advanced-summary-list">{markup}</div>', unsafe_allow_html=True)


def _render_checks_summary(semantic_result: object, prepared_case: PreparedDemoCase | None) -> None:
    semantic_value = "Not run"
    if isinstance(semantic_result, SemanticValidationResult):
        semantic_value = "Passed" if semantic_result.passed else "Failed"
    geometry_value = "Not run"
    if prepared_case is not None:
        passed = all(check.passed for check in prepared_case.initial_geometry_check_results)
        geometry_value = "Passed" if passed else "Failed"
    _render_summary_rows(
        (
            ("Structural checks", semantic_value),
            ("Intent / geometry checks", geometry_value),
            ("Artifact consistency", "Available after build"),
        )
    )


def _render_metrics(spec: ScenarioSpec | None) -> None:
    if spec is None:
        st.info("Metrics unavailable until ScenarioSpec JSON is valid.")
        return
    metrics = compute_timing_metrics(spec)
    tiles = (
        ("Target TTC", _format_seconds(metrics.target_ttc_s)),
        ("Lead Time", _format_seconds(metrics.ego_lead_time_to_conflict_s)),
        ("Trigger Threshold", _format_seconds(metrics.trigger_threshold_time_s)),
        ("Pedestrian Time", _format_seconds(metrics.pedestrian_time_to_conflict_s)),
        ("THW", _format_seconds(metrics.time_headway_s)),
    )
    markup = "".join(
        '<div class="advanced-metric-tile">'
        f'<span>{escape(label)}</span>'
        f'<strong>{escape(value)}</strong>'
        '</div>'
        for label, value in tiles
    )
    st.markdown(f'<div class="advanced-metric-grid">{markup}</div>', unsafe_allow_html=True)


def _render_external_summary(qc_result: object, playback_result: object, runtime_check_results: object) -> None:
    quality = _state_label(_qc_state(qc_result))
    simulation = _state_label(_simulation_state(playback_result, runtime_check_results))
    runtime = "ready" if runtime_check_results else "not run"
    _render_summary_rows(
        (
            ("OSC Quality", quality),
            ("Simulation", simulation),
            ("Runtime consistency", runtime),
        )
    )


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1f} s"


def _semantic_state(result: object) -> str:
    if isinstance(result, SemanticValidationResult):
        return "passed" if result.passed else "failed"
    return "neutral"


def _qc_state(result: object) -> str:
    if not isinstance(result, AsamQcResult):
        return "neutral"
    if not result.checker_available:
        return "waiting"
    return "passed" if result.passed else "failed"


def _simulation_state(playback_result: object, runtime_check_results: object) -> str:
    if runtime_check_results:
        try:
            return "passed" if all(check.passed for check in runtime_check_results) else "failed"
        except TypeError:
            return "waiting"
    if isinstance(playback_result, EsminiPlaybackResult):
        return "passed" if playback_result.playback_generated else "waiting"
    return "neutral"


def _state_label(state: str) -> str:
    return {
        "passed": "ready",
        "failed": "issue",
        "waiting": "waiting",
        "neutral": "not run",
    }.get(state, state)
