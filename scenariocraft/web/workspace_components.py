from __future__ import annotations

from collections.abc import Callable
from html import escape
from pathlib import Path

import streamlit as st

from scenariocraft.application.demo_cases import PreparedDemoCase
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.web.media_view import render_workspace_runtime_media
from scenariocraft.web.state import WORKSPACE_MEDIA_TITLES
from scenariocraft.web.view_models import (
    GeneratedScenarioViewModel,
    build_workspace_repair_view_model,
    build_workspace_status_view_model,
)


def render_workspace_status_panel(
    *,
    current_spec: Callable[[], ScenarioSpec | None],
    prepared_case: PreparedDemoCase | None,
    semantic_result: object,
    qc_result: object,
    esmini_result: object,
    intent_proposal: object | None = None,
    candidate_trace: object | None = None,
) -> None:
    with st.container(border=True, key="workspace_status"):
        st.markdown("### Status")
        status = build_workspace_status_view_model(
            current_spec(),
            prepared_case=prepared_case,
            semantic_result=semantic_result,
            qc_result=qc_result,
            esmini_result=esmini_result,
            intent_proposal=intent_proposal,
            candidate_trace=candidate_trace,
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
            '<div class="workspace-loop-status" role="status">'
            f'<div class="workspace-loop-title">{escape(status.loop_label)}</div>'
            f'<div class="workspace-status-grid">{items}</div>'
            "</div>",
            unsafe_allow_html=True,
        )


def render_workspace_repair_panel(prepared_case: PreparedDemoCase | None) -> None:
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


def render_workspace_brief_panel(
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
        metric_tiles = "".join(
            '<div class="workspace-brief-metric" tabindex="0" '
            f'title="{escape(card.detail)}" aria-label="{escape(card.label)}: {escape(card.value)}. {escape(card.detail)}">'
            f'<span>{escape(card.label)}</span><strong>{escape(card.value)}</strong></div>'
            for card in vm.brief_metrics
        )
        details = [vm.context_summary, vm.trigger_threshold_summary]
        if vm.pedestrian_conflict_summary:
            details.append(vm.pedestrian_conflict_summary)
        if vm.trigger_summary and vm.trigger_summary != "n/a":
            details.append(vm.trigger_summary)
        detail_markup = "".join(
            f'<span>{escape(detail)}</span>' for detail in details if detail
        )
        st.markdown(
            '<div class="workspace-brief">'
            f'<strong class="workspace-brief-title">{escape(vm.title)}</strong>'
            f'<div class="workspace-brief-metrics">{metric_tiles}</div>'
            f'<div class="workspace-brief-details">{detail_markup}</div>'
            "</div>",
            unsafe_allow_html=True,
        )


def render_workspace_visuals_panel(
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
