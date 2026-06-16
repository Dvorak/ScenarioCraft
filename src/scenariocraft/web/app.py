from __future__ import annotations

import json
from dataclasses import replace
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
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
DEMO_MODES = ("Normal good scenario", "Missing pedestrian", "Low criticality")
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
    scenario_text = st.text_area("Request", value=st.session_state.scenario_text, height=185, label_visibility="collapsed")
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


def _render_xml_panel(output_dir: Path) -> None:
    st.markdown("### Generated OpenSCENARIO XML")
    xml_value = st.text_area("OpenSCENARIO XML", value=st.session_state.xosc_text, height=365, label_visibility="collapsed")
    st.session_state.xosc_text = xml_value

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
    with st.expander("ScenarioSpec JSON", expanded=False):
        spec_json = st.text_area("ScenarioSpec JSON", value=st.session_state.spec_json, height=320, label_visibility="collapsed")
        st.session_state.spec_json = spec_json
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
    result = run_esmini(build_result.xosc_path, output_dir, required=require_esmini, binary=esmini_bin, timeout_s=timeout_s)
    st.session_state.esmini_result = result
    _info("esmini completed." if result.executed else "esmini skipped or failed.")


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
