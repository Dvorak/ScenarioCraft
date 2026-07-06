from __future__ import annotations

from pathlib import Path

import streamlit as st

from scenariocraft.application.demo_cases import DEMO_CASES


DEFAULT_SCENARIO_TEXT = (
    "A rainy urban pedestrian occlusion scenario where the ego vehicle approaches a parked van "
    "and a pedestrian suddenly crosses from behind it."
)
DEFAULT_OUTPUT_ROOT = Path("outputs/web_demo")
DEFAULT_OUTPUT_DIR = DEFAULT_OUTPUT_ROOT / "latest"
DEFAULT_EXTERNAL_ROOT = Path("external")
REFERENCE_SOURCES = ("All", "OSC-NCAP-scenarios", "ALKS scenarios", "Other external scenarios")
CURATED_REFERENCE_EXAMPLES_PATH = Path("examples/reference_examples.yaml")
RECOMMENDED_EXAMPLE_FILES = (
    Path("outputs/reference_scan/external_esmini_smoke_real_10/recommended_examples.json"),
    Path("outputs/reference_scan/ncap_qc_esmini_real_20/recommended_examples.json"),
    Path("outputs/reference_scan/alks_qc_esmini_real_20/recommended_examples.json"),
    Path("outputs/reference_scan/ncap_esmini_real_20/recommended_examples.json"),
    Path("outputs/reference_scan/alks_esmini_real_20/recommended_examples.json"),
)
REFERENCE_CATEGORIES = ("stable_demo", "qc_fail", "esmini_long_running")
CRITICALITY_MAX_TTC_S = 3.0
WEB_PREVIEW_DISPLAY_ORIENTATION = "esmini_top_camera_raw"
WEB_PREVIEW_PRESENTATION_STYLE = "clean_split"
PREVIEW_VISUAL_CAPTION = "Renderer-aligned ScenarioSpec layout · world +x → left · world +y → down"
RUNTIME_VISUAL_CAPTION = "Raw OpenSCENARIO + OpenDRIVE runtime view · world +x → left · world +y → down"
WORKSPACE_PAGES = ("Workspace", "Advanced")
WORKSPACE_PROVIDER = "mock"
WORKSPACE_PROVIDER_OPTIONS = ("Demo / mock", "Local LLM")
WORKSPACE_PROVIDER_VALUES = {
    "Demo / mock": "mock",
    "Local LLM": "openai-compatible",
}
WORKSPACE_GENERATE_ICON = ":material/send:"
WORKSPACE_REPAIR_ICON = ":material/build:"
WORKSPACE_DESKTOP_HEIGHT = "clamp(720px, calc(100dvh - 6.5rem), 960px)"
WORKSPACE_MEDIA_TITLES = ("Preview 2D Semantic", "Playback Esmini")
WORKSPACE_MEDIA_ASPECT_RATIO = "16 / 9"


def ensure_session_state() -> None:
    defaults = {
        "active_page": "Workspace",
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
        "playback_result": None,
        "runtime_check_results": (),
        "repair_history": [],
        "selected_demo_case_id": DEMO_CASES[0].case_id,
        "demo_experiment_trace": None,
        "workspace_original_spec": None,
        "workspace_prepared_case": None,
        "workspace_execution": None,
        "workspace_provider_label": WORKSPACE_PROVIDER_OPTIONS[0],
        "workspace_intent_proposal": None,
        "output_root": str(DEFAULT_OUTPUT_ROOT),
        "output_dir": str(DEFAULT_OUTPUT_DIR),
        "external_root": str(DEFAULT_EXTERNAL_ROOT),
        "reference_options": [],
        "reference_browser_initialized": False,
        "reference_source_filter": REFERENCE_SOURCES[0],
        "selected_reference_label": "",
        "loaded_xosc_source": "",
        "loaded_xosc_relative_path": "",
        "loaded_xosc_working_dir": "",
        "workflow_mode": "Generate from prompt",
        "loaded_xosc_path": "",
        "loaded_xosc_metadata": None,
        "demo_mode": "Normal good scenario",
        "run_esmini_check": False,
        "try_playback_video": True,
        "playback_mode": "full/playback attempt",
        "require_esmini": False,
        "esmini_bin": "",
        "esmini_timeout": 20.0,
        "playback_timeout": 30.0,
        "external_esmini_mode": "smoke",
        "esmini_sim_duration": 3.0,
        "last_error": "",
        "last_info": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_generated_scenario_state() -> None:
    st.session_state.build_result = None
    st.session_state.xosc_text = ""
    st.session_state.preview_path = ""
    st.session_state.semantic_result = None
    st.session_state.qc_result = None
    st.session_state.esmini_result = None
    st.session_state.playback_result = None
    st.session_state.runtime_check_results = ()
    st.session_state.report_text = ""
    st.session_state.demo_experiment_trace = None
    st.session_state.workspace_intent_proposal = None
