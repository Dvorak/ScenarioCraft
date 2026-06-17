from __future__ import annotations

import json
from dataclasses import replace
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
from scenariocraft.references import ReferenceScenarioOption, XoscMetadata, discover_external_scenarios, extract_xosc_metadata
from scenariocraft.schemas import ActorSpec, CriticalitySpec, ScenarioSpec, TriggerSpec
from scenariocraft.tools import (
    AsamQcResult,
    BuildResult,
    EsminiResult,
    build_openscenario,
    estimate_ttc_s,
    generate_2d_preview,
    generate_validation_report,
    run_asam_qc,
    run_esmini,
    validate_semantics,
)
from scenariocraft.tools.semantic_validator import SemanticValidationResult


DEFAULT_SCENARIO_TEXT = (
    "A rainy urban pedestrian occlusion scenario where the ego vehicle approaches a parked van "
    "and a pedestrian suddenly crosses from behind it."
)
DEFAULT_OUTPUT_DIR = Path("outputs/web-demo")
DEFAULT_EXTERNAL_ROOT = Path("external")
WORKFLOW_MODES = ("Generate from prompt", "Load existing .xosc")
DEMO_MODES = ("Normal good scenario", "Missing pedestrian", "Low criticality")
REFERENCE_SOURCES = ("All", "OSC-NCAP-scenarios", "ALKS scenarios", "Other external scenarios")
CRITICALITY_MAX_TTC_S = 3.0


def main() -> None:
    st.set_page_config(page_title="ScenarioCraft-Agent", layout="wide")
    _inject_css()
    _ensure_state()

    st.markdown("## ScenarioCraft-Agent")
    st.caption("LLM-assisted OpenSCENARIO generation, validation, and playback")

    first_row = st.columns([0.28, 0.36, 0.36], gap="large")
    with first_row[0]:
        _render_request_panel()
    with first_row[1]:
        _render_xml_panel(Path(st.session_state.output_dir))
    with first_row[2]:
        _render_preview_panel()

    _render_advanced_artifacts(Path(st.session_state.output_dir))


def _render_request_panel() -> None:
    st.markdown("### Scenario Request")
    workflow_mode = st.selectbox("Mode", WORKFLOW_MODES, index=WORKFLOW_MODES.index(st.session_state.workflow_mode))
    st.session_state.workflow_mode = workflow_mode
    if _is_load_mode():
        _render_load_request_panel()
        return

    scenario_text = st.text_area("Request", value=st.session_state.scenario_text, height=145, label_visibility="collapsed")
    st.session_state.scenario_text = scenario_text
    provider_name = st.selectbox("Provider", ["mock"], index=0)
    demo_mode = st.selectbox("Demo Mode", DEMO_MODES, index=DEMO_MODES.index(st.session_state.demo_mode))
    st.session_state.demo_mode = demo_mode

    status = _status_label()
    st.markdown(status, unsafe_allow_html=True)

    actions = st.columns(2)
    with actions[0]:
        if st.button("Generate & Run", type="primary", width="stretch"):
            _generate_and_run(provider_name, demo_mode)
    with actions[1]:
        if _needs_repair():
            if st.button("Repair Scenario", width="stretch"):
                _repair_current_scenario(output_dir=Path(st.session_state.output_dir))
        else:
            st.button("Repair Scenario", disabled=True, width="stretch")

    with st.expander("Advanced settings", expanded=False):
        output_dir = Path(st.text_input("Output directory", st.session_state.output_dir))
        st.session_state.output_dir = str(output_dir)
        run_esmini_check = st.checkbox("Run esmini", value=st.session_state.run_esmini_check)
        st.session_state.run_esmini_check = run_esmini_check
        require_esmini = st.checkbox("Require esmini", value=st.session_state.require_esmini)
        st.session_state.require_esmini = require_esmini
        esmini_timeout = st.number_input(
            "esmini timeout",
            min_value=1.0,
            max_value=120.0,
            value=st.session_state.esmini_timeout,
            step=1.0,
        )
        st.session_state.esmini_timeout = float(esmini_timeout)
        esmini_bin = st.text_input("esmini binary", value=st.session_state.esmini_bin)
        st.session_state.esmini_bin = esmini_bin
    st.caption(f"Artifacts: `{st.session_state.output_dir}`")


def _render_load_request_panel() -> None:
    _ensure_reference_options_loaded()

    refresh_col, count_col = st.columns([0.56, 0.44])
    with refresh_col:
        if st.button("Refresh scenario list", width="stretch"):
            _refresh_reference_options()
    with count_col:
        st.caption(f"{len(_reference_options())} discovered .xosc files")

    source_filter = st.selectbox(
        "Source",
        REFERENCE_SOURCES,
        index=REFERENCE_SOURCES.index(st.session_state.reference_source_filter),
    )
    st.session_state.reference_source_filter = source_filter
    options = _filtered_reference_options(source_filter)
    if not _reference_options():
        st.info("No external scenarios found. Place ALKS/NCAP repositories under external/ or use custom path.")
    elif not options:
        st.info("No scenarios found for the selected source filter.")
    else:
        labels = [option.label for option in options]
        current_label = st.session_state.selected_reference_label
        index = labels.index(current_label) if current_label in labels else 0
        selected_label = st.selectbox("Scenario", labels, index=index)
        st.session_state.selected_reference_label = selected_label
        selected_option = _option_by_label(options, selected_label)
        if selected_option is not None:
            st.caption(f"Source: `{selected_option.source}`")
            st.caption(f"Relative path: `{selected_option.relative_path}`")
            actions = st.columns(2)
            with actions[0]:
                if st.button("Load selected scenario", type="primary", width="stretch"):
                    _load_reference_option(Path(st.session_state.output_dir), selected_option)
            with actions[1]:
                if st.button("Run Checks", width="stretch"):
                    _run_loaded_xosc_checks(Path(st.session_state.output_dir))

    st.markdown(_status_label(), unsafe_allow_html=True)

    with st.expander("Advanced: custom .xosc path", expanded=False):
        xosc_path = st.text_input("Local .xosc path", value=st.session_state.loaded_xosc_path)
        st.session_state.loaded_xosc_path = xosc_path
        if st.button("Load custom XOSC", width="stretch"):
            _load_existing_xosc(Path(st.session_state.output_dir), xosc_path)

    with st.expander("Advanced settings", expanded=False):
        external_root = Path(st.text_input("External scenario root", st.session_state.external_root))
        if str(external_root) != st.session_state.external_root:
            st.session_state.external_root = str(external_root)
            _refresh_reference_options()
        output_dir = Path(st.text_input("Output directory", st.session_state.output_dir))
        st.session_state.output_dir = str(output_dir)
        require_esmini = st.checkbox("Require esmini", value=st.session_state.require_esmini)
        st.session_state.require_esmini = require_esmini
        esmini_timeout = st.number_input(
            "esmini timeout",
            min_value=1.0,
            max_value=120.0,
            value=st.session_state.esmini_timeout,
            step=1.0,
        )
        st.session_state.esmini_timeout = float(esmini_timeout)
        esmini_bin = st.text_input("esmini binary", value=st.session_state.esmini_bin)
        st.session_state.esmini_bin = esmini_bin
    st.caption(f"Artifacts: `{st.session_state.output_dir}`")


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
        _render_loaded_playback_panel()
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
        metric_cols = st.columns(4)
        metric_cols[0].metric("Ego Speed", _ego_speed_label(spec))
        metric_cols[1].metric("Trigger Dist", f"{spec.trigger.distance_m:g} m")
        metric_cols[2].metric("Ped Speed", _pedestrian_speed_label(spec))
        metric_cols[3].metric("Estimated TTC", _ttc_label(spec))
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
    if not _is_load_mode():
        with st.expander("ScenarioSpec JSON", expanded=False):
            spec_json = st.text_area("ScenarioSpec JSON", value=st.session_state.spec_json, height=320, label_visibility="collapsed")
            st.session_state.spec_json = spec_json
    with st.expander("Loaded XOSC metadata", expanded=_is_load_mode()):
        metadata = _current_metadata()
        if metadata is None:
            st.info("No external .xosc metadata loaded.")
        else:
            if st.session_state.loaded_xosc_source:
                st.caption(f"Selected source: `{st.session_state.loaded_xosc_source}`")
            if st.session_state.loaded_xosc_relative_path:
                st.caption(f"Selected relative path: `{st.session_state.loaded_xosc_relative_path}`")
            st.json(metadata.to_dict())
            if metadata.logic_file_paths:
                st.info(
                    "OpenDRIVE LogicFile references were detected. esmini checks preserve these relative paths by "
                    "running from the .xosc file's parent directory."
                )
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
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            st.json(esmini_result.to_dict())
            log_path = output_dir / "esmini_log.txt"
            if log_path.exists():
                st.text_area("esmini_log.txt", log_path.read_text(encoding="utf-8"), height=220, label_visibility="collapsed")
        else:
            st.info("esmini has not run.")
    with st.expander("repair history", expanded=False):
        if st.session_state.repair_history:
            st.json(st.session_state.repair_history)
        else:
            st.info("No repairs recorded.")
    with st.expander("validation_report.md", expanded=False):
        st.text_area("validation_report.md", st.session_state.report_text, height=320, label_visibility="collapsed")


def _ensure_state() -> None:
    defaults = {
        "scenario_text": DEFAULT_SCENARIO_TEXT,
        "spec_json": "",
        "xosc_text": "",
        "report_text": "",
        "spec": None,
        "build_result": None,
        "preview_path": "",
        "semantic_result": None,
        "qc_result": None,
        "esmini_result": None,
        "repair_history": [],
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "external_root": str(DEFAULT_EXTERNAL_ROOT),
        "reference_options": [],
        "reference_browser_initialized": False,
        "reference_source_filter": REFERENCE_SOURCES[0],
        "selected_reference_label": "",
        "loaded_xosc_source": "",
        "loaded_xosc_relative_path": "",
        "loaded_xosc_working_dir": "",
        "workflow_mode": WORKFLOW_MODES[0],
        "loaded_xosc_path": "",
        "loaded_xosc_metadata": None,
        "demo_mode": DEMO_MODES[0],
        "run_esmini_check": False,
        "require_esmini": False,
        "esmini_bin": "",
        "esmini_timeout": 20.0,
        "last_error": "",
        "last_info": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _generator(provider_name: str) -> ScenarioGenerator:
    if provider_name == "mock":
        return MockScenarioGenerator()
    raise ValueError(f"Unsupported provider: {provider_name}")


def _is_load_mode() -> bool:
    return st.session_state.workflow_mode == "Load existing .xosc"


def _ensure_reference_options_loaded() -> None:
    if not st.session_state.reference_browser_initialized:
        _refresh_reference_options()
        st.session_state.reference_browser_initialized = True


def _refresh_reference_options() -> None:
    st.session_state.reference_options = discover_external_scenarios(Path(st.session_state.external_root))


def _reference_options() -> list[ReferenceScenarioOption]:
    return [
        option
        for option in st.session_state.reference_options
        if isinstance(option, ReferenceScenarioOption)
    ]


def _filtered_reference_options(source_filter: str) -> list[ReferenceScenarioOption]:
    options = _reference_options()
    if source_filter == "All":
        return options
    return [option for option in options if option.source == source_filter]


def _option_by_label(options: list[ReferenceScenarioOption], label: str) -> ReferenceScenarioOption | None:
    return next((option for option in options if option.label == label), None)


def _load_existing_xosc(
    output_dir: Path,
    xosc_path_value: str,
    source: str = "",
    relative_path: str = "",
) -> None:
    xosc_path = Path(xosc_path_value).expanduser()
    if not xosc_path.exists():
        _error(f"OpenSCENARIO file does not exist: {xosc_path}")
        return
    if not xosc_path.is_file():
        _error(f"OpenSCENARIO path is not a file: {xosc_path}")
        return
    try:
        xml_text = xosc_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        _error(f"Failed to read OpenSCENARIO file: {exc}")
        return
    metadata = extract_xosc_metadata(xosc_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    st.session_state.loaded_xosc_path = str(xosc_path)
    st.session_state.loaded_xosc_source = source
    st.session_state.loaded_xosc_relative_path = relative_path
    st.session_state.loaded_xosc_working_dir = str(xosc_path.parent)
    st.session_state.loaded_xosc_metadata = metadata
    st.session_state.xosc_text = xml_text
    st.session_state.spec_json = ""
    st.session_state.spec = None
    st.session_state.build_result = BuildResult(xosc_path=xosc_path, builder="loaded_xosc")
    st.session_state.preview_path = ""
    st.session_state.semantic_result = None
    st.session_state.qc_result = None
    st.session_state.esmini_result = None
    st.session_state.report_text = ""
    _info("Loaded external OpenSCENARIO file.")


def _load_reference_option(output_dir: Path, option: ReferenceScenarioOption) -> None:
    _load_existing_xosc(
        output_dir,
        str(option.xosc_path),
        source=option.source,
        relative_path=option.relative_path,
    )


def _run_loaded_xosc_checks(output_dir: Path) -> None:
    build_result = st.session_state.build_result
    if not isinstance(build_result, BuildResult):
        _load_existing_xosc(output_dir, st.session_state.loaded_xosc_path)
        build_result = st.session_state.build_result
    if not isinstance(build_result, BuildResult):
        return
    xosc_path = build_result.xosc_path
    st.session_state.loaded_xosc_metadata = extract_xosc_metadata(xosc_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    qc_result = run_asam_qc(xosc_path, output_dir)
    esmini_result = run_esmini(
        xosc_path,
        output_dir,
        working_dir=xosc_path.parent,
        required=st.session_state.require_esmini,
        binary=st.session_state.esmini_bin or None,
        timeout_s=st.session_state.esmini_timeout,
    )
    st.session_state.qc_result = qc_result
    st.session_state.esmini_result = esmini_result
    _write_loaded_xosc_report(output_dir, xosc_path, _current_metadata(), qc_result, esmini_result)
    _info("External OpenSCENARIO checks completed.")


def _generate_and_run(provider_name: str, demo_mode: str) -> None:
    _generate_spec(provider_name, st.session_state.scenario_text, demo_mode)
    _run_pipeline(
        Path(st.session_state.output_dir),
        st.session_state.run_esmini_check,
        st.session_state.require_esmini,
        st.session_state.esmini_bin or None,
        st.session_state.esmini_timeout,
    )


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
    st.session_state.build_result = None
    st.session_state.xosc_text = ""
    st.session_state.preview_path = ""
    st.session_state.semantic_result = None
    st.session_state.qc_result = None
    st.session_state.esmini_result = None
    st.session_state.report_text = ""


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
        preview_path = generate_2d_preview(spec, output_dir / "preview_2d.png")
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
        preview_path = generate_2d_preview(spec, preview_path)
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


def _render_loaded_playback_panel() -> None:
    preview_tab, esmini_tab = st.tabs(["2D Preview", "Execution Check"])
    with preview_tab:
        st.info("2D preview is currently available for ScenarioSpec-generated scenarios only.")
        if st.session_state.loaded_xosc_source:
            st.caption(f"Selected source: `{st.session_state.loaded_xosc_source}`")
        if st.session_state.loaded_xosc_relative_path:
            st.caption(f"Selected relative path: `{st.session_state.loaded_xosc_relative_path}`")
        metadata = _current_metadata()
        if metadata is not None and metadata.logic_file_paths:
            st.caption("Detected OpenDRIVE LogicFile references: " + ", ".join(f"`{path}`" for path in metadata.logic_file_paths))
    with esmini_tab:
        st.caption("esmini runs from the loaded .xosc file's parent directory to preserve relative OpenDRIVE and catalog paths.")
        if st.session_state.loaded_xosc_working_dir:
            st.caption(f"esmini working directory: `{st.session_state.loaded_xosc_working_dir}`")
        if st.button("Run esmini Check", width="stretch"):
            _run_loaded_xosc_checks(Path(st.session_state.output_dir))
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            if esmini_result.executed:
                st.success("Executable")
            elif esmini_result.esmini_available:
                st.error(f"Execution failed: {esmini_result.error_message}")
            else:
                st.warning("esmini was not found. Scenario playback/execution check was skipped.")
            st.json(esmini_result.to_dict())
        else:
            st.info("Load an external .xosc and run checks to see execution status.")


def _write_report(output_dir: Path) -> None:
    spec = _current_spec()
    if spec is None:
        return
    build_result = _ensure_build_result(output_dir)
    semantic_result = st.session_state.semantic_result or validate_semantics(spec)
    qc_result = st.session_state.qc_result or _missing_qc_result(build_result.xosc_path, output_dir)
    esmini_result = st.session_state.esmini_result or _missing_esmini_result(build_result.xosc_path)
    report_path = generate_validation_report(
        st.session_state.scenario_text,
        spec,
        build_result,
        qc_result,
        esmini_result,
        semantic_result,
        output_dir,
    )
    st.session_state.semantic_result = semantic_result
    st.session_state.report_text = report_path.read_text(encoding="utf-8")
    _info("Validation report generated.")


def _write_loaded_xosc_report(
    output_dir: Path,
    xosc_path: Path,
    metadata: XoscMetadata | None,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
) -> Path:
    report_path = output_dir / "validation_report.md"
    report_path.write_text(
        "\n".join([
            "# ScenarioCraft Loaded OpenSCENARIO Report",
            "",
            "## Loaded OpenSCENARIO",
            "",
            f"- Source file: `{xosc_path}`",
            f"- Selected source: `{st.session_state.loaded_xosc_source or 'custom path'}`",
            f"- Selected relative path: `{st.session_state.loaded_xosc_relative_path or 'n/a'}`",
            f"- esmini working directory: `{xosc_path.parent}`",
            "- The file was inspected in place; ScenarioCraft did not modify it.",
            "",
            "## Extracted Metadata",
            "",
            _metadata_markdown(metadata),
            "",
            "## ASAM Quality Check",
            "",
            _qc_markdown(qc_result),
            "",
            "## esmini Execution / Playback",
            "",
            _esmini_markdown(esmini_result),
            "",
            "## Known Limitations",
            "",
            "- 2D preview is currently available for ScenarioSpec-generated scenarios only.",
            "- External `.xosc` files are not reconstructed as ScenarioSpec.",
            "- Natural-language editing for external `.xosc` is not implemented yet.",
        ]),
        encoding="utf-8",
    )
    st.session_state.report_text = report_path.read_text(encoding="utf-8")
    return report_path


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


def _current_metadata() -> XoscMetadata | None:
    metadata = st.session_state.loaded_xosc_metadata
    return metadata if isinstance(metadata, XoscMetadata) else None


def _metadata_markdown(metadata: XoscMetadata | None) -> str:
    if metadata is None:
        return "No metadata extracted."
    if not metadata.file_exists:
        return "OpenSCENARIO file does not exist."
    if not metadata.parse_success:
        return f"OpenSCENARIO XML parsing failed: `{metadata.parse_error}`"
    logic_note = ""
    if metadata.logic_file_paths:
        logic_note = (
            "\n- Relative path handling: esmini checks run from the `.xosc` parent directory so "
            "OpenDRIVE LogicFile references remain relative to the source scenario."
        )
    return "\n".join([
        f"- Parse success: `{metadata.parse_success}`",
        f"- OpenSCENARIO version: `{metadata.open_scenario_version}`",
        f"- FileHeader: `{metadata.file_header}`",
        f"- Logic files: `{metadata.logic_file_paths}`",
        f"- Scene graph files: `{metadata.scene_graph_file_paths}`",
        f"- Catalog locations: `{metadata.catalog_locations}`",
        f"- Parameters: `{metadata.parameter_names}`",
        f"- Scenario objects: `{metadata.scenario_object_names}`",
        f"- Has storyboard: `{metadata.has_storyboard}`",
        "- Approximate counts: "
        f"parameters={metadata.parameter_count}, "
        f"scenario_objects={metadata.scenario_object_count}, "
        f"maneuvers={metadata.maneuver_count}, "
        f"events={metadata.event_count}, "
        f"conditions={metadata.condition_count}",
        logic_note,
    ]).strip()


def _qc_markdown(result: AsamQcResult) -> str:
    if not result.checker_available:
        return "ASAM OpenSCENARIO XML checker was not found. Standard-compliance checking was skipped."
    return "\n".join([
        f"- Command: `{' '.join(result.command)}`",
        f"- Return code: `{result.return_code}`",
        f"- Passed: `{result.passed}`",
        f"- Result path: `{result.result_path}`",
    ])


def _esmini_markdown(result: EsminiResult) -> str:
    if not result.esmini_available:
        return "esmini was not found. Scenario playback/execution check was skipped."
    return "\n".join([
        f"- Command: `{' '.join(result.command)}`",
        f"- Working directory: `{result.working_dir}`",
        f"- Return code: `{result.return_code}`",
        f"- Executed: `{result.executed}`",
        f"- Error message: `{result.error_message}`",
    ])


def _status_label() -> str:
    if st.session_state.last_error:
        return f'<div class="status-error">{escape(st.session_state.last_error)}</div>'
    if st.session_state.last_info:
        return f'<div class="status-ok">{escape(st.session_state.last_info)}</div>'
    return '<div class="status-muted">Ready</div>'


def _ego_speed_label(spec: ScenarioSpec) -> str:
    ego = spec.actor_by_role("ego")
    if ego is None or ego.initial_speed_kph is None:
        return "missing"
    return f"{ego.initial_speed_kph:g} km/h"


def _pedestrian_speed_label(spec: ScenarioSpec) -> str:
    pedestrian = spec.actor_by_role("crossing_actor")
    if pedestrian is None or pedestrian.speed_mps is None:
        return "missing"
    return f"{pedestrian.speed_mps:g} m/s"


def _ttc_label(spec: ScenarioSpec) -> str:
    estimate = estimate_ttc_s(spec)
    if estimate is None:
        return "n/a"
    return f"{estimate:.1f} s"


def _inject_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.6rem; }
        textarea { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
        .status-ok, .status-error, .status-muted {
            border-radius: 8px;
            padding: 0.6rem 0.75rem;
            margin: 0.4rem 0 0.8rem 0;
            font-size: 0.92rem;
        }
        .status-ok { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
        .status-error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
        .status-muted { background: #f8fafc; color: #475569; border: 1px solid #e2e8f0; }
        .preview-shell {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 0.5rem;
            background: #ffffff;
        }
        .legend {
            display: flex;
            gap: 0.85rem;
            flex-wrap: wrap;
            font-size: 0.78rem;
            color: #334155;
            padding: 0 0.25rem 0.25rem 0.25rem;
        }
        .legend b {
            display: inline-block;
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 2px;
            margin-right: 0.32rem;
            vertical-align: -0.08rem;
        }
        .legend .ego { background: #111827; }
        .legend .van { background: #1d4ed8; }
        .legend .ped { background: #dc2626; }
        .legend .trigger { background: #7c3aed; }
        .vehicle-label { fill: white; font-size: 13px; font-weight: 700; }
        .label { fill: #0f172a; font-size: 12px; font-weight: 650; }
        .lane-label { fill: #f8fafc; font-size: 13px; font-weight: 650; opacity: 0.92; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _info(message: str) -> None:
    st.session_state.last_info = message
    st.session_state.last_error = ""


def _error(message: str) -> None:
    st.session_state.last_error = message
    st.session_state.last_info = ""


if __name__ == "__main__":
    main()
