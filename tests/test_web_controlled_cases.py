from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from scenariocraft.application.controlled_cases import (
    CONTROLLED_CASES,
    controlled_case_options,
    get_controlled_case,
    controlled_case_prompt_variant,
    instantiate_controlled_case,
)
from scenariocraft.application.demo_cases import DEMO_CASES
from scenariocraft.core.templates.registry import registered_templates
from scenariocraft._legacy_streamlit.state import WORKSPACE_PROVIDER_OPTIONS


EXPECTED_FAMILY_IDS = {
    "pedestrian_occlusion",
    "lead_vehicle_braking",
    "cut_in",
    "crossing_vehicle",
    "oncoming_turn_across_path",
}


def test_controlled_cases_cover_all_executable_golden_families() -> None:
    assert {case.template_id for case in CONTROLLED_CASES} == EXPECTED_FAMILY_IDS
    assert {case.template_id for case in CONTROLLED_CASES} <= set(registered_templates())
    assert {case.case_id for case in CONTROLLED_CASES} == EXPECTED_FAMILY_IDS
    assert all(case.display_name for case in CONTROLLED_CASES)
    assert all(case.description for case in CONTROLLED_CASES)
    assert all(case.seed is not None for case in CONTROLLED_CASES)


def test_controlled_cases_have_prompt_variants_for_natural_language_ui() -> None:
    for case in CONTROLLED_CASES:
        assert len(case.source_text_variants) >= 3
        assert case.source_text == case.source_text_variants[0]
        assert len(set(case.source_text_variants)) == len(case.source_text_variants)
        assert controlled_case_prompt_variant(case.case_id, 0) == case.source_text
        assert controlled_case_prompt_variant(case.case_id, 99) in case.source_text_variants


def test_controlled_demo_prompt_variants_are_english_only() -> None:
    for case in CONTROLLED_CASES:
        assert all(variant.isascii() for variant in case.source_text_variants)


def test_controlled_case_instantiation_produces_matching_scenario_spec() -> None:
    for case in CONTROLLED_CASES:
        spec = instantiate_controlled_case(case.case_id)

        assert spec.scenario_type == case.template_id
        assert spec.layout is not None
        assert spec.metadata["template_resolution"]["template_id"] == case.template_id
        assert spec.metadata["template_resolution"]["seed"] == case.seed


def test_controlled_case_options_are_not_repair_experiment_cases() -> None:
    controlled_ids = {case_id for case_id, _label in controlled_case_options()}
    repair_experiment_ids = {case.case_id for case in DEMO_CASES}

    assert controlled_ids == EXPECTED_FAMILY_IDS
    assert controlled_ids.isdisjoint(repair_experiment_ids - {"pedestrian_occlusion"})
    assert get_controlled_case("cut_in").display_name == "Cut-in"


def test_workspace_defaults_to_provider_first_with_controlled_case_fallback() -> None:
    assert WORKSPACE_PROVIDER_OPTIONS[0] == "LLM"
    assert "Demo" in WORKSPACE_PROVIDER_OPTIONS
    assert "Demo / mock" not in WORKSPACE_PROVIDER_OPTIONS


def test_workspace_controlled_case_selector_lists_five_golden_families(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/_legacy_streamlit/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)

    labels = [item.label for item in app.selectbox]
    assert labels == ["Provider", "Controlled Case"]
    assert set(app.selectbox[0].options) == set(WORKSPACE_PROVIDER_OPTIONS)
    assert set(app.selectbox[1].options) == {case.display_name for case in CONTROLLED_CASES}

    app.selectbox[1].select("cut_in").run()
    next(button for button in app.button if button.label == "Generate").click().run()

    assert not app.exception
    assert app.session_state["spec"].scenario_type == "cut_in"
    assert app.session_state["workspace_prepared_case"] is None
    assert any(
        'class="workspace-micro-status"' in item.value
        and "Candidate Generation · accepted · cut in" in item.value
        for item in app.markdown
    )
    assert not any(
        "Candidate Generation Loop · accepted" in item.value for item in app.caption
    )


def test_workspace_controlled_case_selection_updates_request_text(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/_legacy_streamlit/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)

    app.selectbox[1].select("crossing_vehicle").run()

    expected = controlled_case_prompt_variant("crossing_vehicle", 0)
    assert app.session_state["selected_demo_case_id"] == "crossing_vehicle"
    assert app.session_state["scenario_text"] == expected
    assert "pedestrian occlusion" not in app.session_state["scenario_text"].lower()


def test_workspace_controlled_case_selection_clears_stale_generated_result(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/_legacy_streamlit/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)
    next(button for button in app.button if button.label == "Generate").click().run()

    assert app.session_state["spec"] is not None

    app.selectbox[1].select("lead_vehicle_braking").run()

    assert app.session_state["selected_demo_case_id"] == "lead_vehicle_braking"
    assert app.session_state["spec"] is None
    assert app.session_state["spec_json"] == ""
    assert app.session_state["preview_path"] == ""
    assert app.session_state["workspace_candidate_trace"] is None


def test_workspace_default_request_comes_from_selected_controlled_case(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/_legacy_streamlit/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)

    selected_case_id = app.session_state["selected_demo_case_id"]
    case = get_controlled_case(selected_case_id)

    assert app.session_state["scenario_text"] in case.source_text_variants


def test_workspace_can_shuffle_controlled_case_prompt_variant(tmp_path: Path) -> None:
    app = AppTest.from_file("scenariocraft/_legacy_streamlit/app.py", default_timeout=20).run()
    app.session_state["output_root"] = str(tmp_path)

    before = app.session_state["scenario_text"]
    next(button for button in app.button if button.label == "Shuffle prompt").click().run()

    after = app.session_state["scenario_text"]
    selected_case_id = app.session_state["selected_demo_case_id"]
    case = get_controlled_case(selected_case_id)
    assert before in case.source_text_variants
    assert after in case.source_text_variants
    assert after != before


def test_cli_examples_cover_five_golden_families() -> None:
    for family_id in EXPECTED_FAMILY_IDS:
        path = Path("examples") / f"{family_id}.txt"
        assert path.exists()
        assert path.read_text(encoding="utf-8").strip()
