from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.application.demo_cases import DEMO_CASES, PreparedDemoCase, get_demo_case
from scenariocraft.schemas import ScenarioSpec
from scenariocraft.web.media_view import render_workspace_runtime_media
from scenariocraft.web.state import (
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_MEDIA_TITLES,
    WORKSPACE_PROVIDER,
    WORKSPACE_REPAIR_ICON,
)
from scenariocraft.web.view_models import (
    GeneratedScenarioViewModel,
    build_workspace_repair_view_model,
    build_workspace_status_view_model,
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
    workspace = st.columns([0.4, 0.6], gap="large", vertical_alignment="top")
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
            _render_workspace_status(
                current_spec=current_spec,
                prepared_case=prepared_case,
                semantic_result=semantic_result,
                qc_result=qc_result,
                esmini_result=esmini_result,
            )
            _render_workspace_repair(prepared_case)
            _render_workspace_brief(current_spec=current_spec, generated_view_model=generated_view_model)
    with workspace[1]:
        with st.container(key="workspace_right"):
            _render_workspace_visuals(
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


def _render_workspace_status(
    *,
    current_spec: Callable[[], ScenarioSpec | None],
    prepared_case: PreparedDemoCase | None,
    semantic_result: object,
    qc_result: object,
    esmini_result: object,
) -> None:
    with st.container(border=True, key="workspace_status"):
        st.markdown("### Status")
        status = build_workspace_status_view_model(
            current_spec(),
            prepared_case=prepared_case,
            semantic_result=semantic_result,
            qc_result=qc_result,
            esmini_result=esmini_result,
        )
        items = "".join(
            f'<div class="status-item status-{escape(item.state)}" tabindex="0" '
            f'title="{escape(item.detail)}" '
            f'aria-label="{escape(item.label)}: {escape(item.value)}. {escape(item.detail)}">'
            f'<span class="status-label">{escape(item.label)}</span>'
            f'<strong><i aria-hidden="true"></i>{escape(item.value)}</strong></div>'
            for item in status.items
        )
        st.markdown(
            f'<div class="workspace-status-grid" role="status">{items}</div>',
            unsafe_allow_html=True,
        )


def _render_workspace_repair(prepared_case: PreparedDemoCase | None) -> None:
    repair = build_workspace_repair_view_model(prepared_case)
    if not repair.visible:
        return
    with st.container(border=True, key="workspace_repair_panel"):
        heading = "Artifact mismatch" if repair.detection_only else "Repair required"
        st.markdown(f"### {heading}")
        failures = "".join(
            '<div class="repair-failure">'
            f'<strong>{escape(failure.name)}</strong>'
            f'<span>{escape(failure.message)}</span></div>'
            for failure in repair.failures
        )
        st.markdown(f'<div class="repair-failure-list">{failures}</div>', unsafe_allow_html=True)
        if repair.detection_only:
            st.caption("Detection only · no provider or ScenarioSpec patch is allowed for this case.")
        else:
            st.caption(f"Provider · {repair.provider_name}")
            if repair.suggested_operations:
                operation_names = [str(item.get("op", "operation")) for item in repair.suggested_operations]
                st.caption("Suggested operation · " + ", ".join(operation_names))
        with st.expander("Evidence", expanded=False):
            for failure in repair.failures:
                st.markdown(f"**{failure.name}**")
                st.json(failure.measured)


def _render_workspace_brief(
    *,
    current_spec: Callable[[], ScenarioSpec | None],
    generated_view_model: Callable[[], GeneratedScenarioViewModel],
) -> None:
    with st.container(border=True, key="workspace_brief"):
        st.markdown("### Scenario Brief")
        vm = generated_view_model()
        if current_spec() is None:
            st.caption("Generate a scenario to see its semantic brief.")
            return
        st.markdown(f"**{vm.title}**")
        metrics = st.columns(4)
        metrics[0].metric("Ego", vm.ego_speed)
        metrics[1].metric("Pedestrian", vm.pedestrian_speed)
        metrics[2].metric("Target TTC", vm.target_ttc)
        metrics[3].metric("Lead Time", vm.ego_lead_time)
        st.caption(f"{vm.road_summary} · {vm.weather_summary}")
        st.caption(f"{vm.trigger_threshold_summary} · {vm.pedestrian_conflict_summary}")
        st.caption(vm.trigger_summary)


def _render_workspace_visuals(
    output_dir: Path,
    *,
    current_spec: Callable[[], ScenarioSpec | None],
    ensure_preview: Callable[[Path, ScenarioSpec], Path | None],
    playback_result: object,
) -> None:
    with st.container(border=True, key="workspace_preview_panel"):
        st.markdown(f"### {WORKSPACE_MEDIA_TITLES[0]}")
        with st.container(key="workspace_preview_stage"):
            spec = current_spec()
            if spec is None:
                st.info("Generate a scenario to preview it.")
            else:
                preview_path = ensure_preview(output_dir, spec)
                if preview_path is not None and preview_path.exists():
                    st.image(str(preview_path), width="stretch")
                else:
                    st.warning("Preview unavailable.")
    with st.container(border=True, key="workspace_playback_panel"):
        st.markdown(f"### {WORKSPACE_MEDIA_TITLES[1]}")
        with st.container(key="workspace_playback_stage"):
            render_workspace_runtime_media(output_dir, playback_result)
