from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from scenariocraft.application.demo_cases import DEMO_CASES, PreparedDemoCase, get_demo_case
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.web.state import (
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_PROVIDER,
    WORKSPACE_PROVIDER_OPTIONS,
    WORKSPACE_PROVIDER_VALUES,
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
    provider_label: str,
    selected_demo_case_id: str,
    prepared_case: PreparedDemoCase | None,
    intent_proposal: object,
    last_error: str,
    last_info: str,
    semantic_result: object,
    qc_result: object,
    esmini_result: object,
    playback_result: object,
    current_spec: Callable[[], ScenarioSpec | None],
    generated_view_model: Callable[[], GeneratedScenarioViewModel],
    ensure_preview: Callable[[Path, ScenarioSpec], Path | None],
    set_scenario_text: Callable[[str], None],
    set_provider_label: Callable[[str], None],
    set_selected_demo_case_id: Callable[[str], None],
    generate_selected_case: Callable[[str, str | None], None],
    execute_workspace_repair: Callable[[Path], object],
) -> None:
    repair_visible = build_workspace_repair_view_model(prepared_case).visible
    workspace = st.columns([0.36, 0.64] if repair_visible else [0.32, 0.68], gap="small", vertical_alignment="top")
    with workspace[0]:
        left_key = "workspace_left_repair" if repair_visible else "workspace_left_normal"
        with st.container(key=left_key):
            _render_workspace_request(
                output_dir,
                scenario_text=scenario_text,
                provider_label=provider_label,
                selected_demo_case_id=selected_demo_case_id,
                prepared_case=prepared_case,
                intent_proposal=intent_proposal,
                last_error=last_error,
                last_info=last_info,
                set_scenario_text=set_scenario_text,
                set_provider_label=set_provider_label,
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
    provider_label: str,
    selected_demo_case_id: str,
    prepared_case: PreparedDemoCase | None,
    intent_proposal: object,
    last_error: str,
    last_info: str,
    set_scenario_text: Callable[[str], None],
    set_provider_label: Callable[[str], None],
    set_selected_demo_case_id: Callable[[str], None],
    generate_selected_case: Callable[[str, str | None], None],
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
        if last_error:
            st.error(last_error)
        elif last_info:
            st.caption(last_info)
        repair = build_workspace_repair_view_model(prepared_case)
        with st.container(key="workspace_toolbar"):
            provider_options = list(WORKSPACE_PROVIDER_OPTIONS)
            if provider_label not in provider_options:
                provider_label = WORKSPACE_PROVIDER_OPTIONS[0]
            provider_name = WORKSPACE_PROVIDER_VALUES[provider_label]
            show_demo_case = provider_name == WORKSPACE_PROVIDER
            tools = st.columns(
                [0.32, 0.68, 0.12, 0.12]
                if repair.can_repair and show_demo_case
                else [0.32, 0.68, 0.12]
                if show_demo_case
                else [1.0, 0.12, 0.12]
                if repair.can_repair
                else [1.0, 0.12],
                vertical_alignment="bottom",
            )
            with tools[0]:
                selected_provider_label = st.selectbox(
                    "Provider",
                    provider_options,
                    index=provider_options.index(provider_label),
                    label_visibility="collapsed",
                )
                set_provider_label(selected_provider_label)
                provider_name = WORKSPACE_PROVIDER_VALUES[selected_provider_label]
                show_demo_case = provider_name == WORKSPACE_PROVIDER
            action_index = 1
            selected_case_id = selected_demo_case_id if show_demo_case else None
            if show_demo_case:
                case_ids = [case_id for case_id, _ in workspace_case_options()]
                with tools[1]:
                    selected_case_id = st.selectbox(
                        "Demo Case",
                        case_ids,
                        index=case_ids.index(selected_demo_case_id),
                        format_func=lambda case_id: get_demo_case(case_id).display_name,
                        label_visibility="collapsed",
                    )
                    set_selected_demo_case_id(selected_case_id)
                action_index = 2
            with tools[action_index]:
                if st.button(
                    "Generate",
                    type="primary",
                    icon=WORKSPACE_GENERATE_ICON,
                    help="Generate from text with selected provider",
                    key="workspace_generate",
                    width="stretch",
                ):
                    generate_selected_case(provider_name, selected_case_id)
                    st.rerun()
            if repair.can_repair:
                with tools[action_index + 1]:
                    if st.button(
                        "Repair",
                        icon=WORKSPACE_REPAIR_ICON,
                        help="Repair and revalidate scenario",
                        key="workspace_repair",
                        width="stretch",
                    ):
                        execute_workspace_repair(output_dir)
                        st.rerun()
        _render_intent_summary(intent_proposal, set_scenario_text=set_scenario_text)


def _render_intent_summary(intent_proposal: object, *, set_scenario_text: Callable[[str], None]) -> None:
    if intent_proposal is None:
        return
    intent = getattr(intent_proposal, "intent", None)
    provider_name = getattr(intent_proposal, "provider_name", "")
    rationale = getattr(intent_proposal, "rationale", "")
    status = getattr(intent_proposal, "status", "supported")
    if intent is None:
        if status == "clarification_required":
            question = getattr(intent_proposal, "clarification_question", "") or rationale
            st.caption(f"Intent clarification required · {provider_name}: {question}")
        else:
            refusal = getattr(intent_proposal, "refusal_reason", "") or rationale
            st.caption(f"Intent unsupported · {provider_name}: {refusal}")
        candidates = getattr(intent_proposal, "nearest_template_candidates", ())
        if candidates:
            st.caption(f"Nearest templates: {', '.join(str(candidate) for candidate in candidates)}")
        suggestions = tuple(getattr(intent_proposal, "refinement_suggestions", ()) or ())
        if suggestions:
            st.caption("Suggested request refinements:")
            suggestion_columns = st.columns(min(len(suggestions), 3), vertical_alignment="top")
            for index, suggestion in enumerate(suggestions[:3]):
                label = getattr(suggestion, "label", "")
                suggested_request = getattr(suggestion, "suggested_request", "")
                reason = getattr(suggestion, "reason", "")
                with suggestion_columns[index]:
                    if st.button(
                        f"Use: {label}",
                        key=f"intent_refinement_{index}",
                        help=reason or "Use this suggested request text",
                        width="stretch",
                    ):
                        set_scenario_text(str(suggested_request))
                        st.session_state["workspace_intent_proposal"] = None
                        st.session_state["last_error"] = ""
                        st.session_state["last_info"] = "Suggestion applied. Review the request and generate again."
                        st.rerun()
        return
    template_id = getattr(intent, "template_id", "")
    st.caption(f"Intent · {template_id} via {provider_name}")
    with st.expander("ScenarioIntent", expanded=False):
        st.json(intent.to_dict())
        if rationale:
            st.caption(rationale)
