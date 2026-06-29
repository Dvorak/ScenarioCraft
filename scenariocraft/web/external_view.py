from __future__ import annotations

import json
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.application import (
    ExternalScenarioWorkflowOptions,
    ExternalScenarioWorkflowRequest,
    ExternalScenarioWorkflowResult,
    run_external_scenario_workflow,
)
from scenariocraft.references import ReferenceScenarioOption, XoscMetadata, discover_external_scenarios, extract_xosc_metadata
from scenariocraft.core.build import BuildResult
from scenariocraft.runtime import AsamQcResult, EsminiResult
from scenariocraft.web.state import (
    CURATED_REFERENCE_EXAMPLES_PATH,
    RECOMMENDED_EXAMPLE_FILES,
    REFERENCE_CATEGORIES,
    REFERENCE_SOURCES,
)
from scenariocraft.web.view_models import (
    ExternalScenarioViewModel,
    StatusCardViewModel,
    build_external_scenario_view_model,
)


def render_external_scenario_studio(output_dir: Path) -> None:
    top_row = st.columns([0.34, 0.66], gap="large")
    with top_row[0]:
        st.markdown("### Scenario Library / Demo Gallery")
        _render_load_request_panel()
    with top_row[1]:
        _render_external_overview_panel()

    main_row = st.columns([0.58, 0.42], gap="large")
    with main_row[0]:
        _render_external_visual_summary_panel()
    with main_row[1]:
        _render_external_status_panel(output_dir)

    _render_external_advanced_artifacts(output_dir)


def render_loaded_playback_panel() -> None:
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


def _render_load_request_panel() -> None:
    _ensure_reference_options_loaded()
    _render_recommended_reference_panel()

    with st.expander("Advanced: full external browser", expanded=False):
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
        esmini_mode = st.selectbox("esmini mode", ["smoke", "full"], index=["smoke", "full"].index(st.session_state.external_esmini_mode))
        st.session_state.external_esmini_mode = esmini_mode
        sim_duration = st.number_input(
            "smoke duration",
            min_value=0.5,
            max_value=30.0,
            value=st.session_state.esmini_sim_duration,
            step=0.5,
        )
        st.session_state.esmini_sim_duration = float(sim_duration)
    st.caption(f"Artifacts: `{st.session_state.output_dir}`")


def _render_external_overview_panel() -> None:
    st.markdown("### Scenario Overview")
    vm = _external_view_model()
    metadata = _current_metadata()
    if metadata is None:
        st.info("Select a reference scenario to inspect metadata, dependencies, and runtime readiness.")
        return
    if not metadata.parse_success:
        st.error(vm.parse_message)
    metric_cols = st.columns(4)
    metric_cols[0].metric("Source", vm.source)
    metric_cols[1].metric("OSC Version", vm.version)
    metric_cols[2].metric("Entities", vm.entity_count)
    metric_cols[3].metric("Events", vm.event_count)
    st.caption(f"Path: `{vm.relative_path}`")
    if vm.entity_names:
        st.markdown("**Entities**")
        st.caption(", ".join(f"`{name}`" for name in vm.entity_names))
    if vm.parameter_names:
        st.markdown("**Parameters**")
        st.caption(", ".join(f"`{name}`" for name in vm.parameter_names))
    if vm.logic_file_paths:
        st.markdown("**RoadNetwork / LogicFile**")
        st.caption(", ".join(f"`{path}`" for path in vm.logic_file_paths))
        st.info("Relative OpenDRIVE paths are preserved by running esmini from the .xosc directory.")
    if vm.catalog_locations:
        st.markdown("**CatalogLocations**")
        st.caption(", ".join(f"`{path}`" for path in vm.catalog_locations))
    st.caption(f"Conditions: `{vm.condition_count}`")


def _render_external_visual_summary_panel() -> None:
    st.markdown("### Visual Preview / Summary")
    vm = _external_view_model()
    if _current_metadata() is None:
        st.info(vm.title)
        return
    st.markdown(f"#### {vm.title}")
    st.caption(f"{vm.source} / {vm.relative_path}")
    cols = st.columns(4)
    cols[0].metric("Actors", vm.entity_count)
    cols[1].metric("Parameters", vm.parameter_count)
    cols[2].metric("Dependencies", vm.dependency_count)
    cols[3].metric("Storyboard", vm.storyboard_complexity)
    _render_summary_cards(vm.visual_summary_cards)
    st.info("Deterministic summary preview. Exact external-scenario geometry sketch is future work.")


def _render_external_status_panel(output_dir: Path) -> None:
    st.markdown("### Validation & Execution Status")
    vm = _external_view_model()
    metadata = _current_metadata()
    _render_status_cards(vm.status_cards)

    actions = st.columns(2)
    with actions[0]:
        if st.button("Run QC + esmini smoke", type="primary", width="stretch", disabled=metadata is None):
            _run_loaded_xosc_checks(output_dir)
    with actions[1]:
        if st.button("Run ASAM QC only", width="stretch", disabled=metadata is None):
            _run_loaded_qc_only(output_dir)

    st.markdown("#### Recommended Action")
    if vm.compatibility_category in {"full_pass", "smoke_pass_long_running"}:
        st.success(vm.recommendation)
    elif vm.compatibility_category in {"qc_fail", "esmini_fail", "metadata_fail"}:
        st.warning(vm.recommendation)
    else:
        st.info(vm.recommendation)

    st.markdown("#### Key Diagnostics")
    for item in vm.diagnostics:
        st.markdown(f"- {item}")
    if st.session_state.loaded_xosc_working_dir:
        st.caption(f"esmini working directory: `{st.session_state.loaded_xosc_working_dir}`")


def _render_external_advanced_artifacts(output_dir: Path) -> None:
    st.markdown("### Advanced")
    st.warning("External files are read-only. Create a workspace copy before editing.")
    with st.expander("Advanced: OpenSCENARIO XML", expanded=False):
        st.text_area("OpenSCENARIO XML", value=st.session_state.xosc_text, height=360, label_visibility="collapsed")
    with st.expander("Advanced: metadata", expanded=False):
        metadata = _current_metadata()
        if metadata is None:
            st.info("No external .xosc metadata loaded.")
        else:
            st.json(metadata.to_dict())
    with st.expander("Advanced: ASAM QC report", expanded=False):
        qc_result = st.session_state.qc_result
        if isinstance(qc_result, AsamQcResult):
            st.json(qc_result.to_dict())
        else:
            st.info("ASAM QC has not run.")
    with st.expander("Advanced: esmini logs", expanded=False):
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            st.json(esmini_result.to_dict())
            for name in ("esmini_log.txt", "esmini_stdout.txt", "esmini_stderr.txt"):
                log_path = output_dir / name
                if log_path.exists():
                    st.text_area(name, log_path.read_text(encoding="utf-8"), height=180, label_visibility="collapsed")
        else:
            st.info("esmini has not run.")
    with st.expander("Advanced: validation_report.md", expanded=False):
        st.text_area("validation_report.md", st.session_state.report_text, height=300, label_visibility="collapsed")


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


def _render_recommended_reference_panel() -> None:
    categories = _recommended_reference_examples()
    if not any(categories.values()):
        st.info("No recommended reference examples found yet. Run a real reference scan or use the full scenario browser below.")
        return

    st.markdown("#### Demo Gallery")
    columns = st.columns(3, gap="medium")
    gallery_specs = [
        (
            columns[0],
            "stable_demo",
            categories["stable_demo"],
            "Stable demo",
            "Best first choice for a clean live demo.",
            "Load stable demo",
        ),
        (
            columns[1],
            "qc_fail",
            categories["qc_fail"],
            "QC issue",
            "Useful for showing standard-compliance diagnosis.",
            "Load QC example",
        ),
        (
            columns[2],
            "esmini_long_running",
            categories["esmini_long_running"],
            "Runtime diagnostic",
            "Useful for missing dependency, timeout, or playback diagnosis.",
            "Load runtime example",
        ),
    ]
    for column, category, examples, title, caption, action_label in gallery_specs:
        with column:
            with st.container(border=True):
                _render_recommended_category(category, examples, title, caption, action_label)


def _render_recommended_category(
    category: str,
    examples: list[dict[str, str]],
    title: str,
    caption: str,
    action_label: str,
) -> None:
    st.markdown(f"##### {title}")
    st.caption(caption)
    if not examples:
        st.info("No examples found for this category.")
        return
    labels = [_recommended_label(example) for example in examples]
    selected_label = st.selectbox("Scenario", labels, key=f"recommended_{category}_select")
    selected = examples[labels.index(selected_label)]
    st.markdown(f"**{_recommended_short_name(selected)}**")
    st.caption(selected["source"])
    st.caption(selected["relative_path"])
    status = f"{_recommended_status_label(category)} | QC {selected.get('qc_status', 'unknown')} | esmini {selected.get('esmini_status', 'unknown')}"
    failure_class = selected.get("esmini_failure_class")
    if failure_class:
        status += f" | {failure_class}"
    st.caption(status)
    failure_message = selected.get("failure_message")
    if failure_message:
        st.caption(f"Observed issue: {failure_message}")
    if st.button(action_label, key=f"recommended_{category}_load", width="stretch"):
        _load_recommended_example(Path(st.session_state.output_dir), selected)


def _recommended_reference_examples(
    curated_path: Path = CURATED_REFERENCE_EXAMPLES_PATH,
    recommended_files: tuple[Path, ...] = RECOMMENDED_EXAMPLE_FILES,
) -> dict[str, list[dict[str, str]]]:
    curated = _curated_reference_examples(curated_path)
    if any(curated.values()):
        return curated

    categories = {
        "stable_demo": [],
        "qc_fail": [],
        "esmini_long_running": [],
    }
    seen: set[tuple[str, str, str]] = set()
    payloads: list[dict[str, object]] = []
    for path in recommended_files:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(payload, dict):
            payloads.append(payload)

    known_failure_paths: set[str] = set()
    for payload in payloads:
        for category_name in ("qc_fail", "esmini_fail"):
            for raw_example in payload.get(category_name, []):
                example = _normalize_recommended_example(raw_example)
                if example is not None:
                    known_failure_paths.add(example["xosc_path"])

    for payload in payloads:
        for category_name, target in [
            ("full_pass", "stable_demo"),
            ("qc_fail", "qc_fail"),
            ("esmini_fail", "esmini_long_running"),
        ]:
            for raw_example in payload.get(category_name, []):
                example = _normalize_recommended_example(raw_example)
                if example is None:
                    continue
                if target == "stable_demo" and example["xosc_path"] in known_failure_paths:
                    continue
                key = (target, example["source"], example["relative_path"])
                if key in seen:
                    continue
                categories[target].append(example)
                seen.add(key)
    return {name: examples[:8] for name, examples in categories.items()}


def _curated_reference_examples(path: Path) -> dict[str, list[dict[str, str]]]:
    categories = {name: [] for name in REFERENCE_CATEGORIES}
    if not path.exists():
        return categories
    for raw_example in _parse_reference_examples_yaml(path):
        example = _normalize_curated_example(raw_example)
        if example is None:
            continue
        category = _ui_category_for_reference(example.get("compatibility_category", ""))
        categories[category].append(example)
    return {name: examples[:8] for name, examples in categories.items()}


def _parse_reference_examples_yaml(path: Path) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            if current:
                examples.append(current)
            current = {}
            line = line[2:].strip()
        if ":" not in line or current is None:
            continue
        key, value = line.split(":", 1)
        current[key.strip()] = _unquote_yaml_scalar(value.strip())
    if current:
        examples.append(current)
    return examples


def _unquote_yaml_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _normalize_curated_example(raw_example: dict[str, str]) -> dict[str, str] | None:
    xosc_path_value = raw_example.get("xosc_path") or raw_example.get("path")
    relative_path = raw_example.get("relative_path")
    source = raw_example.get("source")
    if not xosc_path_value or not relative_path or not source:
        return None
    xosc_path = Path(xosc_path_value)
    if not xosc_path.exists():
        return None
    return {
        "source": source,
        "relative_path": relative_path,
        "xosc_path": str(xosc_path),
        "qc_status": raw_example.get("qc_status", "unknown"),
        "esmini_status": raw_example.get("esmini_status", "unknown"),
        "esmini_failure_class": raw_example.get("esmini_failure_class", ""),
        "failure_message": raw_example.get("failure_message", ""),
        "compatibility_category": raw_example.get("compatibility_category", "unknown"),
    }


def _ui_category_for_reference(category: str) -> str:
    if category == "full_pass":
        return "stable_demo"
    if category == "qc_fail":
        return "qc_fail"
    if category in {"esmini_fail", "smoke_pass_long_running"}:
        return "esmini_long_running"
    return "esmini_long_running"


def _normalize_recommended_example(raw_example: object) -> dict[str, str] | None:
    if not isinstance(raw_example, dict):
        return None
    xosc_path_value = raw_example.get("xosc_path")
    relative_path = raw_example.get("relative_path")
    source = raw_example.get("source")
    if not isinstance(xosc_path_value, str) or not isinstance(relative_path, str) or not isinstance(source, str):
        return None
    xosc_path = Path(xosc_path_value)
    if not xosc_path.exists():
        return None
    return {
        "source": source,
        "relative_path": relative_path,
        "xosc_path": str(xosc_path),
        "qc_status": str(raw_example.get("qc_status") or "unknown"),
        "esmini_status": str(raw_example.get("esmini_status") or "unknown"),
        "esmini_failure_class": str(raw_example.get("esmini_failure_class") or ""),
        "failure_message": str(raw_example.get("failure_message") or ""),
    }


def _recommended_label(example: dict[str, str]) -> str:
    return f"{example['source']} / {example['relative_path']}"


def _recommended_short_name(example: dict[str, str]) -> str:
    return Path(example["relative_path"]).stem or "reference scenario"


def _recommended_status_label(category: str) -> str:
    labels = {
        "stable_demo": "Stable demo",
        "qc_fail": "QC issue",
        "esmini_long_running": "Runtime diagnostic",
    }
    return labels.get(category, "Needs attention")


def _load_recommended_example(output_dir: Path, example: dict[str, str]) -> None:
    _load_existing_xosc(
        output_dir,
        example["xosc_path"],
        source=example["source"],
        relative_path=example["relative_path"],
    )


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
    st.session_state.playback_result = None
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
    result = run_external_scenario_workflow(
        ExternalScenarioWorkflowRequest(
            xosc_path=build_result.xosc_path,
            output_dir=output_dir,
            source=st.session_state.loaded_xosc_source,
            relative_path=st.session_state.loaded_xosc_relative_path,
            options=ExternalScenarioWorkflowOptions(
                run_asam_qc=True,
                run_esmini=True,
                run_report=True,
                require_esmini=st.session_state.require_esmini,
                esmini_bin=st.session_state.esmini_bin or None,
                esmini_timeout_s=st.session_state.esmini_timeout,
                esmini_mode=st.session_state.external_esmini_mode,
                esmini_sim_duration_s=st.session_state.esmini_sim_duration,
            ),
        )
    )
    _apply_external_workflow_result(result)
    _info("External OpenSCENARIO checks completed.")


def _run_loaded_qc_only(output_dir: Path) -> None:
    build_result = st.session_state.build_result
    if not isinstance(build_result, BuildResult):
        _load_existing_xosc(output_dir, st.session_state.loaded_xosc_path)
        build_result = st.session_state.build_result
    if not isinstance(build_result, BuildResult):
        return
    result = run_external_scenario_workflow(
        ExternalScenarioWorkflowRequest(
            xosc_path=build_result.xosc_path,
            output_dir=output_dir,
            source=st.session_state.loaded_xosc_source,
            relative_path=st.session_state.loaded_xosc_relative_path,
            options=ExternalScenarioWorkflowOptions(
                run_asam_qc=True,
                run_esmini=False,
                run_report=True,
            ),
        )
    )
    _apply_external_workflow_result(result)
    qc_result = result.qc_result
    _info("ASAM QC completed." if isinstance(qc_result, AsamQcResult) and qc_result.checker_available else "ASAM QC skipped.")


def _apply_external_workflow_result(result: ExternalScenarioWorkflowResult) -> None:
    st.session_state.loaded_xosc_path = str(result.xosc_path)
    st.session_state.loaded_xosc_working_dir = str(result.working_dir)
    st.session_state.loaded_xosc_metadata = result.metadata
    st.session_state.xosc_text = result.xosc_text
    st.session_state.spec_json = ""
    st.session_state.spec = None
    st.session_state.build_result = result.build_result
    st.session_state.preview_path = ""
    st.session_state.semantic_result = None
    st.session_state.qc_result = result.qc_result
    st.session_state.esmini_result = result.esmini_result
    st.session_state.playback_result = None
    st.session_state.report_text = result.report_text


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


def _current_metadata() -> XoscMetadata | None:
    metadata = st.session_state.loaded_xosc_metadata
    return metadata if isinstance(metadata, XoscMetadata) else None


def _external_view_model() -> ExternalScenarioViewModel:
    return build_external_scenario_view_model(
        _current_metadata(),
        source=st.session_state.loaded_xosc_source,
        relative_path=st.session_state.loaded_xosc_relative_path,
        qc_result=st.session_state.qc_result if isinstance(st.session_state.qc_result, AsamQcResult) else None,
        esmini_result=st.session_state.esmini_result if isinstance(st.session_state.esmini_result, EsminiResult) else None,
    )


def _render_status_cards(status_cards: list[StatusCardViewModel]) -> None:
    if not status_cards:
        return
    cards = st.columns(min(len(status_cards), 4))
    for column, card in zip(cards, status_cards):
        column.metric(card.label, card.value)
        column.caption(card.detail)


def _render_summary_cards(cards: list[StatusCardViewModel]) -> None:
    if not cards:
        return
    rows = [cards[index:index + 2] for index in range(0, len(cards), 2)]
    for row in rows:
        cols = st.columns(len(row))
        for column, card in zip(cols, row):
            with column:
                st.markdown(f"**{card.label}**")
                st.caption(card.value)
                st.caption(card.detail)


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
