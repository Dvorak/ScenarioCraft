from __future__ import annotations

import json

from scenariocraft.references.metadata_extractor import XoscMetadata
from scenariocraft.tools import AsamQcResult, EsminiResult
from scenariocraft.web.app import _playback_media_label, _recommended_reference_examples
from scenariocraft.web.view_models import (
    build_external_scenario_view_model,
    build_generated_scenario_view_model,
    compatibility_product_label,
)


def test_recommended_examples_prefers_curated_yaml(tmp_path):
    curated_xosc = tmp_path / "curated.xosc"
    curated_xosc.write_text("<OpenSCENARIO />", encoding="utf-8")
    fallback_xosc = tmp_path / "fallback.xosc"
    fallback_xosc.write_text("<OpenSCENARIO />", encoding="utf-8")
    curated_path = tmp_path / "reference_examples.yaml"
    curated_path.write_text(
        "\n".join([
            "- source: OSC-NCAP-scenarios",
            "  relative_path: OSC-NCAP-scenarios/demo/curated.xosc",
            f"  xosc_path: {curated_xosc}",
            "  compatibility_category: full_pass",
            "  qc_status: passed",
            "  esmini_status: passed",
        ]),
        encoding="utf-8",
    )
    recommended_path = tmp_path / "recommended_examples.json"
    recommended_path.write_text(
        json.dumps({
            "full_pass": [{
                "source": "Other external scenarios",
                "relative_path": "other/fallback.xosc",
                "xosc_path": str(fallback_xosc),
            }],
            "qc_fail": [],
            "esmini_fail": [],
        }),
        encoding="utf-8",
    )

    examples = _recommended_reference_examples(curated_path=curated_path, recommended_files=(recommended_path,))

    assert [item["relative_path"] for item in examples["stable_demo"]] == [
        "OSC-NCAP-scenarios/demo/curated.xosc"
    ]


def test_playback_media_labels_are_provenance_aware() -> None:
    assert _playback_media_label("esmini_gif") == "esmini Rendered GIF"
    assert _playback_media_label("esmini_frame_sequence") == "esmini Frame Sequence"
    assert _playback_media_label("esmini_single_frame") == "esmini Screenshot"
    assert _playback_media_label("preview_static_image") == "2D Preview"
    assert _playback_media_label("preview_fallback_gif") == "2D Preview Fallback"
    assert _playback_media_label("unavailable") == "Playback Unavailable"


def test_recommended_examples_falls_back_to_scan_outputs(tmp_path):
    full_pass_xosc = tmp_path / "full_pass.xosc"
    qc_fail_xosc = tmp_path / "qc_fail.xosc"
    esmini_fail_xosc = tmp_path / "esmini_fail.xosc"
    for path in (full_pass_xosc, qc_fail_xosc, esmini_fail_xosc):
        path.write_text("<OpenSCENARIO />", encoding="utf-8")
    recommended_path = tmp_path / "recommended_examples.json"
    recommended_path.write_text(
        json.dumps({
            "full_pass": [{
                "source": "OSC-NCAP-scenarios",
                "relative_path": "OSC-NCAP-scenarios/full_pass.xosc",
                "xosc_path": str(full_pass_xosc),
            }],
            "qc_fail": [{
                "source": "ALKS scenarios",
                "relative_path": "sl-3-1-osc-alks-scenarios/qc_fail.xosc",
                "xosc_path": str(qc_fail_xosc),
            }],
            "esmini_fail": [{
                "source": "Other external scenarios",
                "relative_path": "other/esmini_fail.xosc",
                "xosc_path": str(esmini_fail_xosc),
            }],
        }),
        encoding="utf-8",
    )

    examples = _recommended_reference_examples(curated_path=tmp_path / "missing.yaml", recommended_files=(recommended_path,))

    assert examples["stable_demo"][0]["relative_path"] == "OSC-NCAP-scenarios/full_pass.xosc"
    assert examples["qc_fail"][0]["relative_path"] == "sl-3-1-osc-alks-scenarios/qc_fail.xosc"
    assert examples["esmini_long_running"][0]["relative_path"] == "other/esmini_fail.xosc"


def test_external_visual_summary_uses_metadata():
    metadata = XoscMetadata(
        xosc_path="external/OSC-NCAP-scenarios/demo/reference.xosc",
        file_exists=True,
        parse_success=True,
        open_scenario_version="1.2",
        logic_file_paths=["roads/demo.xodr"],
        catalog_locations=["Catalogs/Vehicles"],
        parameter_names=["EgoSpeed", "PedestrianSpeed"],
        scenario_object_names=["Ego", "Pedestrian"],
        has_storyboard=True,
        parameter_count=2,
        scenario_object_count=2,
        maneuver_count=1,
        event_count=2,
        condition_count=3,
    )

    view_model = build_external_scenario_view_model(
        metadata,
        source="OSC-NCAP-scenarios",
        relative_path="OSC-NCAP-scenarios/demo/reference.xosc",
    )

    assert view_model.title == "reference"
    assert view_model.entity_count == "2"
    assert view_model.parameter_count == "2"
    assert view_model.visual_summary_cards[0].value == "roads/demo.xodr"
    assert view_model.storyboard_complexity == "low"


def test_external_view_model_uses_product_status_labels():
    metadata = XoscMetadata(
        xosc_path="external/OSC-NCAP-scenarios/demo/reference.xosc",
        file_exists=True,
        parse_success=True,
        open_scenario_version="1.2",
        scenario_object_names=["Ego"],
        has_storyboard=True,
        scenario_object_count=1,
    )
    qc_result = AsamQcResult(
        checker_available=True,
        command=["qc_openscenario"],
        return_code=0,
        stdout="",
        stderr="",
        passed=True,
    )
    esmini_result = EsminiResult(
        esmini_available=True,
        command=["esmini", "--osc", "reference.xosc"],
        working_dir="external/OSC-NCAP-scenarios/demo",
        return_code=0,
        stdout="",
        stderr="",
        executed=True,
        error_message=None,
        playback_path=None,
        mode="smoke",
    )

    view_model = build_external_scenario_view_model(metadata, qc_result=qc_result, esmini_result=esmini_result)

    assert view_model.compatibility_category == "full_pass"
    assert view_model.status_cards[0].value == "Ready"
    assert view_model.status_cards[1].value == "Passed"
    assert view_model.status_cards[2].value == "Smoke pass"
    assert view_model.status_cards[3].value == "Stable demo"
    assert compatibility_product_label("qc_fail") == "QC issue"
    assert compatibility_product_label("esmini_fail") == "Runtime diagnostic"
    assert compatibility_product_label("tool_skipped") == "Needs setup"


def test_external_visual_summary_handles_unpreviewable_metadata():
    metadata = XoscMetadata(
        xosc_path="broken.xosc",
        file_exists=True,
        parse_success=False,
        parse_error="not well-formed",
    )

    view_model = build_external_scenario_view_model(metadata)

    assert view_model.title == "broken"
    assert view_model.entity_count == "0"
    assert "XML parsing failed" in view_model.diagnostics[0]


def test_generated_view_model_summarizes_scenario():
    from scenariocraft.generators import MockScenarioGenerator

    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    view_model = build_generated_scenario_view_model(spec)

    assert view_model.title == "rainy_pedestrian_occlusion"
    assert view_model.scenario_type == "pedestrian_occlusion"
    assert view_model.ego_speed == "35 km/h"
    assert view_model.pedestrian_speed == "1.5 m/s"
    assert view_model.status_cards[0].value == "generated"
