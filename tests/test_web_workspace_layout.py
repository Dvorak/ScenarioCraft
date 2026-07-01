from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from scenariocraft.core.generators import MockScenarioGenerator
from scenariocraft.core.repair.providers import FakeRepairProvider
from scenariocraft.runtime import AsamQcResult, EsminiResult
from scenariocraft.application.demo_cases import (
    DEMO_CASES,
    execute_prepared_demo_case,
    prepare_demo_case,
)
from scenariocraft.web.app import (
    WORKSPACE_DESKTOP_HEIGHT,
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_MEDIA_TITLES,
    WORKSPACE_MEDIA_ASPECT_RATIO,
    WORKSPACE_PAGES,
    WORKSPACE_PROVIDER,
    WORKSPACE_REPAIR_ICON,
    WEB_PREVIEW_PRESENTATION_STYLE,
    workspace_case_options,
)
from scenariocraft.web.view_models import (
    build_generated_scenario_view_model,
    build_workspace_repair_view_model,
    build_workspace_status_view_model,
    workspace_section_ids,
)


def test_workspace_navigation_and_media_contract() -> None:
    assert WORKSPACE_PAGES == ("Workspace", "Advanced")
    assert WORKSPACE_DESKTOP_HEIGHT == "clamp(720px, calc(100dvh - 6.5rem), 960px)"
    assert WORKSPACE_MEDIA_TITLES == ("Preview 2D Semantic", "Playback Esmini")
    assert WORKSPACE_MEDIA_ASPECT_RATIO == "16 / 9"
    assert WORKSPACE_PROVIDER == "mock"
    assert WORKSPACE_GENERATE_ICON == ":material/send:"
    assert WORKSPACE_REPAIR_ICON == ":material/build:"
    assert WEB_PREVIEW_PRESENTATION_STYLE == "clean_split"


def test_workspace_media_copy_uses_playback_esmini_naming() -> None:
    source = Path("scenariocraft/web/media_view.py").read_text(encoding="utf-8")

    assert "Playback Esmini" in source
    assert "esmini Runtime Playback" not in source
    assert "esmini Runtime Frame Sequence" not in source
    assert "esmini Runtime Screenshot" not in source


def test_workspace_is_default_and_has_one_demo_case_selector() -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=10).run()

    assert not app.exception
    assert [item.label for item in app.selectbox] == ["Demo Case"]
    assert set(app.selectbox[0].options) == {case.display_name for case in DEMO_CASES}
    assert [button.label for button in app.button] == ["Generate"]
    assert app.button[0].help == "Generate selected scenario"
    assert app.button[0].icon == WORKSPACE_GENERATE_ICON
    markdown = [item.value for item in app.markdown]
    assert "### Preview 2D Semantic" in markdown
    assert "### Playback Esmini" in markdown
    assert "### 2D Semantic Preview" not in markdown
    assert "### esmini Runtime Playback" not in markdown
    assert "Playback Esmini has not been generated." in [item.value for item in app.info]


def test_workspace_playback_panel_explains_preview_fallback_after_generation(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    next(button for button in app.button if button.label == "Generate").click().run()

    markdown = [item.value for item in app.markdown]
    assert "### Playback Esmini" in markdown
    assert "Playback Esmini unavailable." in [item.value for item in app.warning]
    assert "2D Preview Fallback" in [item.value for item in app.info]


def test_web_app_removes_legacy_generated_pipeline_helpers() -> None:
    source = Path("scenariocraft/web/app.py").read_text(encoding="utf-8")

    for helper_name in (
        "_generate_and_run",
        "_generate_and_play",
        "_apply_demo_mode",
        "_run_pipeline",
        "_repair_current_scenario",
        "_repair_spec",
        "_repair_summary",
        "_write_repair_history",
    ):
        assert f"def {helper_name}" not in source
    callback = source[
        source.index("def _generate_selected_case") : source.index("def _apply_workflow_result")
    ]
    assert "run_generated_scenario_workflow" in callback
    for legacy_call in ("_build_xml(", "_run_qc(", "_run_playback(", "_write_report(", "_run_pipeline("):
        assert legacy_call not in callback


def test_workspace_visual_components_are_extracted_from_page_composition() -> None:
    workspace_source = Path("scenariocraft/web/workspace_view.py").read_text(encoding="utf-8")
    component_source = Path("scenariocraft/web/workspace_components.py").read_text(encoding="utf-8")

    assert "render_workspace_status_panel" in workspace_source
    assert "render_workspace_repair_panel" in workspace_source
    assert "render_workspace_brief_panel" in workspace_source
    assert "render_workspace_visuals_panel" in workspace_source
    assert "workspace-status-grid" not in workspace_source
    assert "repair-failure-list" not in workspace_source
    assert "render_workspace_runtime_media" not in workspace_source

    assert "workspace-status-grid" in component_source
    assert "repair-failure-list" in component_source
    assert "render_workspace_runtime_media" in component_source


def test_advanced_page_retains_diagnostic_artifact_sections() -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=10).run()
    app.session_state["active_page"] = "Advanced"
    app.run()

    markdown = [item.value for item in app.markdown]
    assert '<span class="advanced-page-marker" aria-hidden="true"></span>' in markdown
    assert "</div>" not in markdown
    labels = {item.label for item in app.expander}
    assert {
        "ScenarioSpec JSON",
        "OpenSCENARIO XML",
        "Repair / Experiment Trace",
        "Semantic / Geometry Validation",
        "ASAM QC",
        "esmini / Media Provenance",
        "Artifacts / Report",
    }.issubset(labels)


def test_workspace_repair_appears_only_until_successful_revalidation(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    app.selectbox[0].select("geometry_van_in_ego_lane")
    next(button for button in app.button if button.label == "Generate").click().run()

    assert "### Repair required" in [item.value for item in app.markdown]
    assert "### Scenario Brief" in [item.value for item in app.markdown]
    repair_button = next(button for button in app.button if button.label == "Repair")
    assert repair_button.disabled is False
    assert repair_button.help == "Repair and revalidate scenario"
    assert repair_button.icon == WORKSPACE_REPAIR_ICON

    repair_button.click().run()
    app.run()

    assert not app.exception
    assert "### Repair required" not in [item.value for item in app.markdown]
    assert "Repair" not in [button.label for button in app.button]


def test_workspace_brief_uses_explicit_timing_metric_labels(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    next(button for button in app.button if button.label == "Generate").click().run()

    labels = [metric.label for metric in app.metric]
    assert "Target TTC" in labels
    assert "Lead Time" in labels
    assert "TTC" not in labels
    assert "Estimated TTC" not in labels
    captions = "\n".join(item.value for item in app.caption)
    assert "Trigger threshold:" in captions
    assert "Pedestrian to conflict:" in captions


def test_artifact_detection_only_does_not_render_repair_action(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    app.selectbox[0].select("artifact_xosc_actor_pose_drift")
    next(button for button in app.button if button.label == "Generate").click().run()

    assert not app.exception
    assert "### Artifact mismatch" in [item.value for item in app.markdown]
    assert [button.label for button in app.button] == ["Generate"]


def test_workspace_css_hides_streamlit_chrome_and_scopes_icon_controls() -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=10).run()
    css = "\n".join(item.value for item in app.markdown if "<style>" in item.value)

    assert "--sc-bg: #ffffff" in css
    assert "--sc-text: #171717" in css
    assert "--sc-blue: #006bff" in css
    assert "--sc-radius-sm: 6px" in css
    assert "--sc-focus-ring:" in css
    assert "--sc-font-sans:" in css
    assert "--sc-purple: #a000f8" in css
    assert 'header[data-testid="stHeader"] { display: none; }' in css
    assert '[data-testid="stDeployButton"] { display: none; }' in css
    assert ".st-key-workspace_toolbar" in css
    assert ".st-key-workspace_generate" in css
    assert ".st-key-workspace_repair" in css
    assert f"--workspace-desktop-height: {WORKSPACE_DESKTOP_HEIGHT}" in css
    assert ".st-key-workspace_left_normal" in css
    assert ".st-key-workspace_left_repair" in css
    assert ".st-key-workspace_right" in css
    assert "grid-template-rows: repeat(2, minmax(0, 1fr))" in css
    assert ".st-key-workspace_preview_stage" in css
    assert ".st-key-workspace_playback_stage" in css
    assert ".st-key-workspace_preview_stage [data-testid=\"stImageContainer\"]" in css
    assert ".st-key-workspace_playback_stage [data-testid=\"stImageContainer\"]" in css
    assert ".st-key-workspace_preview_stage [data-testid=\"stFullScreenFrame\"] > div" in css
    assert "width: 100%" in css
    assert "justify-content: center" in css
    assert f"--workspace-media-aspect-ratio: {WORKSPACE_MEDIA_ASPECT_RATIO}" in css
    assert "object-fit: contain" in css
    assert "max-height: 390px" not in css
    assert "max-height: 100% !important" in css
    assert "box-shadow: var(--sc-shadow-raised)" in css
    assert "background: var(--sc-bg-subtle)" in css
    assert '[data-testid="stAlert"]' in css
    assert '[data-testid="stMetricValue"]' in css
    assert "font-family: var(--sc-font-sans)" in css
    assert ".advanced-page-marker" in css
    assert ".stApp:has(.advanced-page-marker)" in css
    assert '[data-testid="stExpander"]' in css
    assert "font-family: var(--sc-font-mono)" in css
    assert "@media (max-width: 900px)" in css
    assert '[data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal, .st-key-workspace_left_repair)' in css
    assert '> [data-testid="stColumn"]' in css
    assert "height: auto" in css


def test_workspace_status_is_one_textual_four_stage_grid() -> None:
    app = AppTest.from_file("scenariocraft/web/app.py", default_timeout=10).run()
    status_markup = next(
        item.value
        for item in app.markdown
        if 'class="workspace-status-grid"' in item.value
    )

    assert status_markup.count('class="status-item ') == 4
    for label in ("Scenario", "Probes", "OSC Quality", "Simulation"):
        assert label in status_markup
    assert status_markup.count("</i>Not run</strong>") == 4
    assert status_markup.count('tabindex="0"') == 4
    assert status_markup.count("aria-label=") == 4
    assert "Structured source: ScenarioSpec" in status_markup
    assert "Current checker: ASAM QC" in status_markup
    assert "Current simulator: esmini" in status_markup


def test_workspace_uses_only_registered_demo_cases() -> None:
    options = workspace_case_options()

    assert options == tuple((case.case_id, case.display_name) for case in DEMO_CASES)
    assert "Missing pedestrian" not in {label for _, label in options}
    assert "Low criticality" not in {label for _, label in options}


def test_case_selection_and_preparation_do_not_execute_provider(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def forbidden_provider(*args, **kwargs):
        raise AssertionError("Case preparation executed the repair provider.")

    monkeypatch.setattr(FakeRepairProvider, "propose_patch", forbidden_provider)
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")

    prepared = prepare_demo_case("geometry_van_in_ego_lane", spec, tmp_path)

    assert prepared.repair_required is True
    assert prepared.terminal_status == "repair_required"


def test_normal_workspace_has_no_repair_section(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("normal_good_scenario", spec, tmp_path)
    repair = build_workspace_repair_view_model(prepared)

    assert repair.visible is False
    assert workspace_section_ids(repair) == ("request", "status", "brief")


def test_geometry_failure_exposes_explicit_fake_repair(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("geometry_trigger_after_conflict", spec, tmp_path)
    repair = build_workspace_repair_view_model(prepared)

    assert repair.visible is True
    assert repair.can_repair is True
    assert repair.provider_name == "FakeRepairProvider"
    assert workspace_section_ids(repair) == ("request", "status", "repair", "brief")

    execution = execute_prepared_demo_case(prepared, tmp_path)

    assert execution.provider_requested is True
    assert execution.terminal_status == "passed"
    assert all(result.passed for result in execution.final_geometry_probe_results)


def test_trigger_after_conflict_view_model_shows_negative_lead_time_before_repair(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("geometry_trigger_after_conflict", spec, tmp_path)

    vm = build_generated_scenario_view_model(prepared.experiment_spec)

    assert vm.ego_lead_time == "-0.1 s"
    assert vm.trigger_threshold_time == "1.9 s"
    assert vm.target_ttc == "1.5 s"


def test_repaired_trigger_changes_lead_time_not_trigger_threshold_time(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("geometry_trigger_after_conflict", spec, tmp_path)
    before = build_generated_scenario_view_model(prepared.experiment_spec)

    execution = execute_prepared_demo_case(prepared, tmp_path)
    assert execution.repair_run_result is not None
    after = build_generated_scenario_view_model(execution.repair_run_result.final_spec)

    assert before.trigger_threshold_time == after.trigger_threshold_time == "1.9 s"
    assert before.ego_lead_time == "-0.1 s"
    assert after.ego_lead_time == "1.6 s"


def test_artifact_failure_is_detection_only_without_patch_provider(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("artifact_xosc_actor_pose_drift", spec, tmp_path)
    repair = build_workspace_repair_view_model(prepared)

    assert repair.visible is True
    assert repair.detection_only is True
    assert repair.can_repair is False
    assert repair.provider_name is None
    assert repair.suggested_operations[0]["op"] == "rebuild_artifacts"


def test_workspace_status_reports_prepared_probe_failure(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    prepared = prepare_demo_case("geometry_van_in_ego_lane", spec, tmp_path)

    status = build_workspace_status_view_model(spec, prepared_case=prepared)

    values = {item.label: item.value for item in status.items}
    assert values == {
        "Scenario": "Generated",
        "Probes": "Failed",
        "OSC Quality": "Waiting",
        "Simulation": "Waiting",
    }
    details = {item.label: item.detail for item in status.items}
    assert "ScenarioSpec" in details["Scenario"]
    assert "probes passed" in details["Probes"]
    assert "ASAM QC" in details["OSC Quality"]
    assert "esmini" in details["Simulation"]


def test_workspace_status_keeps_optional_tool_unavailability_explicit() -> None:
    spec = MockScenarioGenerator().generate_spec("pedestrian occlusion")
    qc_result = AsamQcResult(False, ["qc_openscenario"], None, "", "missing", None)
    esmini_result = EsminiResult(
        False,
        ["esmini"],
        None,
        None,
        "",
        "missing",
        None,
        "esmini was not found",
        None,
    )

    status = build_workspace_status_view_model(
        spec,
        qc_result=qc_result,
        esmini_result=esmini_result,
    )

    items = {item.label: item for item in status.items}
    assert items["OSC Quality"].value == "Unavailable"
    assert items["OSC Quality"].tool_name == "ASAM QC"
    assert items["OSC Quality"].detail.endswith("unavailable")
    assert items["Simulation"].value == "Unavailable"
    assert items["Simulation"].tool_name == "esmini"
    assert items["Simulation"].detail.endswith("unavailable")
