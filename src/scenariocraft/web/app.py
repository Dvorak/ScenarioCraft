from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
from scenariocraft.schemas import ScenarioSpec
from scenariocraft.tools import (
    AsamQcResult,
    BuildResult,
    EsminiResult,
    build_openscenario,
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


def main() -> None:
    st.set_page_config(page_title="ScenarioCraft", layout="wide")
    st.title("ScenarioCraft")

    _ensure_state()
    output_dir = Path(st.sidebar.text_input("Output directory", str(DEFAULT_OUTPUT_DIR)))
    provider_name = st.sidebar.selectbox("Provider", ["mock"], index=0)
    require_esmini = st.sidebar.checkbox("Require esmini", value=False)
    esmini_timeout = st.sidebar.number_input("esmini timeout", min_value=1.0, max_value=120.0, value=20.0, step=1.0)
    esmini_bin = st.sidebar.text_input("esmini binary", value="")

    scenario_text = st.text_area("Input scenario", value=st.session_state.scenario_text, height=130)
    st.session_state.scenario_text = scenario_text

    if st.button("Generate ScenarioSpec", type="primary"):
        _generate_spec(provider_name, scenario_text)

    spec_json = st.text_area("ScenarioSpec JSON", value=st.session_state.spec_json, height=320)
    st.session_state.spec_json = spec_json

    controls = st.columns(5)
    with controls[0]:
        if st.button("Build XML"):
            _build_xml(output_dir)
    with controls[1]:
        if st.button("Validate Semantics"):
            _run_semantics()
    with controls[2]:
        if st.button("Run ASAM QC"):
            _run_qc(output_dir)
    with controls[3]:
        if st.button("Run esmini"):
            _run_esmini(output_dir, require_esmini=require_esmini, esmini_bin=esmini_bin or None, timeout_s=esmini_timeout)
    with controls[4]:
        if st.button("Generate Report"):
            _write_report(output_dir)

    left, right = st.columns(2)
    with left:
        xml_value = st.text_area("OpenSCENARIO XML", value=st.session_state.xosc_text, height=460)
        st.session_state.xosc_text = xml_value
        if st.button("Save XML"):
            _save_xml(output_dir, xml_value)
    with right:
        st.text_area("Validation Report", value=st.session_state.report_text, height=460)

    _render_status()


def _ensure_state() -> None:
    defaults = {
        "scenario_text": DEFAULT_SCENARIO_TEXT,
        "spec_json": "",
        "xosc_text": "",
        "report_text": "",
        "spec": None,
        "build_result": None,
        "semantic_result": None,
        "qc_result": None,
        "esmini_result": None,
        "messages": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _generator(provider_name: str) -> ScenarioGenerator:
    if provider_name == "mock":
        return MockScenarioGenerator()
    raise ValueError(f"Unsupported provider: {provider_name}")


def _generate_spec(provider_name: str, scenario_text: str) -> None:
    try:
        spec = _generator(provider_name).generate_spec(scenario_text)
    except Exception as exc:
        _error(f"ScenarioSpec generation failed: {exc}")
        return
    st.session_state.spec = spec
    st.session_state.spec_json = spec.to_json()
    _info("ScenarioSpec generated.")


def _current_spec() -> ScenarioSpec | None:
    try:
        spec = ScenarioSpec.from_json(st.session_state.spec_json)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        _error(f"ScenarioSpec JSON is invalid: {exc}")
        return None
    st.session_state.spec = spec
    return spec


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
    _info(f"OpenSCENARIO built with {build_result.builder}.")


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
        return_code=None,
        stdout="",
        stderr="esmini has not been run.",
        executed=None,
        playback_path=None,
    )


def _render_status() -> None:
    with st.expander("Run status", expanded=True):
        if st.session_state.messages:
            for level, message in st.session_state.messages[-6:]:
                if level == "error":
                    st.error(message)
                else:
                    st.info(message)
        semantic_result = st.session_state.semantic_result
        if isinstance(semantic_result, SemanticValidationResult):
            st.json(semantic_result.to_dict())
        qc_result = st.session_state.qc_result
        if isinstance(qc_result, AsamQcResult):
            st.json(qc_result.to_dict())
        esmini_result = st.session_state.esmini_result
        if isinstance(esmini_result, EsminiResult):
            st.json(esmini_result.to_dict())


def _info(message: str) -> None:
    st.session_state.messages.append(("info", message))


def _error(message: str) -> None:
    st.session_state.messages.append(("error", message))


if __name__ == "__main__":
    main()
