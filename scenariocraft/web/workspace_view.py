from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from scenariocraft.application.demo_cases import DEMO_CASES, PreparedDemoCase, get_demo_case
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.web.state import (
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_PROVIDER,
    WORKSPACE_REPAIR_ICON,
)
from scenariocraft.web.view_models import (
    GeneratedScenarioViewModel,
    build_workspace_repair_view_model,
)
from scenariocraft.web.workspace_components import (
    render_workspace_brief_panel,
    render_workspace_repair_panel,
    render_workspace_status_panel,
    render_workspace_visuals_panel,
)


def workspace_case_options() -> tuple[tuple[str, str], ...]:
    return tuple((case.case_id, case.display_name) for case in DEMO_CASES)


def render_workspace(
    output_dir: Path,
    *,
    scenario_text: str,
    selected_demo_case_id: str,
    prepared_case: PreparedDemoCase | None,
    semantic_result: object,
    qc_result: object,
    esmini_result: object,
    playback_result: object,
    current_spec: Callable[[], ScenarioSpec | None],
    generated_view_model: Callable[[], GeneratedScenarioViewModel],
    ensure_preview: Callable[[Path, ScenarioSpec], Path | None],
    set_scenario_text: Callable[[str], None],
    set_selected_demo_case_id: Callable[[str], None],
    generate_selected_case: Callable[[str, str], None],
    execute_workspace_repair: Callable[[Path], object],
) -> None:
    workspace = st.columns([0.25, 0.75], gap="small", vertical_alignment="top")
    with workspace[0]:
        left_key = "workspace_left_repair" if build_workspace_repair_view_model(prepared_case).visible else "workspace_left_normal"
        with st.container(key=left_key):
            _render_workspace_request(
                output_dir,
                scenario_text=scenario_text,
                selected_demo_case_id=selected_demo_case_id,
                prepared_case=prepared_case,
                set_scenario_text=set_scenario_text,
                set_selected_demo_case_id=set_selected_demo_case_id,
                generate_selected_case=generate_selected_case,
                execute_workspace_repair=execute_workspace_repair,
            )
            render_workspace_status_panel(
                current_spec=current_spec,
                prepared_case=prepared_case,
                semantic_result=semantic_result,
                qc_result=qc_result,
                esmini_result=esmini_result,
            )
            render_workspace_repair_panel(prepared_case)
            render_workspace_brief_panel(current_spec=current_spec, generated_view_model=generated_view_model)
    with workspace[1]:
        with st.container(key="workspace_right"):
            render_workspace_visuals_panel(
                output_dir,
                current_spec=current_spec,
                ensure_preview=ensure_preview,
                playback_result=playback_result,
            )


def _render_workspace_request(
    output_dir: Path,
    *,
    scenario_text: str,
    selected_demo_case_id: str,
    prepared_case: PreparedDemoCase | None,
    set_scenario_text: Callable[[str], None],
    set_selected_demo_case_id: Callable[[str], None],
    generate_selected_case: Callable[[str, str], None],
    execute_workspace_repair: Callable[[Path], object],
) -> None:
    with st.container(border=True, key="workspace_request"):
        st.markdown("### Scenario Request")
        updated_text = st.text_area(
            "Request",
            value=scenario_text,
            height=118,
            label_visibility="collapsed",
            placeholder="Describe the scenario to generate...",
        )
        set_scenario_text(updated_text)
        repair = build_workspace_repair_view_model(prepared_case)
        with st.container(key="workspace_toolbar"):
            tools = st.columns(
                [1.0, 0.12, 0.12] if repair.can_repair else [1.0, 0.12],
                vertical_alignment="bottom",
            )
            with tools[0]:
                case_ids = [case_id for case_id, _ in workspace_case_options()]
                selected_case_id = st.selectbox(
                    "Demo Case",
                    case_ids,
                    index=case_ids.index(selected_demo_case_id),
                    format_func=lambda case_id: get_demo_case(case_id).display_name,
                    label_visibility="collapsed",
                )
                set_selected_demo_case_id(selected_case_id)
            with tools[1]:
                if st.button(
                    "Generate",
                    type="primary",
                    icon=WORKSPACE_GENERATE_ICON,
                    help="Generate selected scenario",
                    key="workspace_generate",
                    width="stretch",
                ):
                    generate_selected_case(WORKSPACE_PROVIDER, selected_case_id)
                    st.rerun()
            if repair.can_repair:
                with tools[2]:
                    if st.button(
                        "Repair",
                        icon=WORKSPACE_REPAIR_ICON,
                        help="Repair and revalidate scenario",
                        key="workspace_repair",
                        width="stretch",
                    ):
                        execute_workspace_repair(output_dir)
                        st.rerun()
