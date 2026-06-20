from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.repair.providers import FakeRepairProvider
from scenariocraft.web.app import (
    WORKSPACE_DESKTOP_HEIGHT,
    WORKSPACE_GENERATE_ICON,
    WORKSPACE_MEDIA_TITLES,
    WORKSPACE_PAGES,
    WORKSPACE_PROVIDER,
    WORKSPACE_REPAIR_ICON,
    workspace_case_options,
)
from scenariocraft.web.demo_cases import (
    DEMO_CASES,
    execute_prepared_demo_case,
    prepare_demo_case,
)
from scenariocraft.web.view_models import (
    build_workspace_repair_view_model,
    build_workspace_status_view_model,
    workspace_section_ids,
)


def test_workspace_navigation_and_media_contract() -> None:
    assert WORKSPACE_PAGES == ("Workspace", "Advanced")
    assert WORKSPACE_DESKTOP_HEIGHT == "clamp(720px, calc(100dvh - 6.5rem), 960px)"
    assert WORKSPACE_MEDIA_TITLES == ("Preview 2D Semantic", "Playback Esmini")
    assert WORKSPACE_PROVIDER == "mock"
    assert WORKSPACE_GENERATE_ICON == ":material/send:"
    assert WORKSPACE_REPAIR_ICON == ":material/build:"


def test_workspace_is_default_and_has_one_demo_case_selector() -> None:
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=10).run()

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


def test_advanced_page_retains_diagnostic_artifact_sections() -> None:
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=10).run()
    app.session_state["active_page"] = "Advanced"
    app.run()

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
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=20).run()
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


def test_artifact_detection_only_does_not_render_repair_action(tmp_path: Path) -> None:
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    app.selectbox[0].select("artifact_xosc_actor_pose_drift")
    next(button for button in app.button if button.label == "Generate").click().run()

    assert not app.exception
    assert "### Artifact mismatch" in [item.value for item in app.markdown]
    assert [button.label for button in app.button] == ["Generate"]


def test_workspace_css_hides_streamlit_chrome_and_scopes_icon_controls() -> None:
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=10).run()
    css = "\n".join(item.value for item in app.markdown if "<style>" in item.value)

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
    assert "object-fit: contain" in css
    assert "@media (max-width: 900px)" in css
    assert '[data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal, .st-key-workspace_left_repair)' in css
    assert '> [data-testid="stColumn"]' in css
    assert "height: auto" in css


def test_workspace_status_is_one_textual_four_stage_grid() -> None:
    app = AppTest.from_file("src/scenariocraft/web/app.py", default_timeout=10).run()
    status_markup = next(
        item.value
        for item in app.markdown
        if 'class="workspace-status-grid"' in item.value
    )

    assert status_markup.count('class="status-item ') == 4
    for label in ("ScenarioSpec", "Validation", "ASAM QC", "esmini"):
        assert label in status_markup
    assert status_markup.count("Not run") == 4


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
        "ScenarioSpec": "Generated",
        "Validation": "Failed",
        "ASAM QC": "Waiting",
        "esmini": "Waiting",
    }
