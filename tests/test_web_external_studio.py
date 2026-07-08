from __future__ import annotations

import json
from pathlib import Path

from scenariocraft.references.metadata_extractor import XoscMetadata
from scenariocraft.external_tools import AsamQcResult, EsminiPlaybackResult, EsminiResult
from scenariocraft.web.app import (
    PREVIEW_VISUAL_CAPTION,
    RUNTIME_VISUAL_CAPTION,
    WEB_PREVIEW_DISPLAY_ORIENTATION,
    _frame_sequence_state,
    _playback_media_label,
    _should_render_frame_sequence,
    _verified_esmini_frame_paths,
)
from scenariocraft.web.external_view import _recommended_reference_examples
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


def test_visual_comparison_captions_state_orientation_contract() -> None:
    assert WEB_PREVIEW_DISPLAY_ORIENTATION == "esmini_top_camera_raw"
    assert PREVIEW_VISUAL_CAPTION == "Renderer-aligned ScenarioSpec layout · world +x → left · world +y → down"
    assert RUNTIME_VISUAL_CAPTION == "Raw OpenSCENARIO + OpenDRIVE runtime view · world +x → left · world +y → down"


def test_frame_sequence_state_uses_normalized_esmini_frames_not_preview(tmp_path: Path) -> None:
    preview = tmp_path / "preview_2d.png"
    preview.write_bytes(b"preview")
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    first = frames_dir / "frame_000001.png"
    middle = frames_dir / "frame_000082.png"
    last = frames_dir / "frame_000163.png"
    for path in (first, middle, last):
        path.write_bytes(b"frame")
    result = _playback_result(
        playback_kind="esmini_frame_sequence",
        playback_source_path=str(frames_dir),
        playback_frame_count=163,
        playback_frame_duration_s=0.05,
        playback_frames=[
            {
                "original_source_path": str(tmp_path / "screen_shot_00000.tga"),
                "normalized_frame_path": str(first),
                "source_extension": ".tga",
                "frame_index": 0,
            },
            {
                "original_source_path": str(preview),
                "normalized_frame_path": str(preview),
                "source_extension": ".png",
                "frame_index": 1,
            },
            {
                "original_source_path": str(tmp_path / "screen_shot_00081.tga"),
                "normalized_frame_path": str(middle),
                "source_extension": ".tga",
                "frame_index": 81,
            },
            {
                "original_source_path": str(tmp_path / "screen_shot_00162.tga"),
                "normalized_frame_path": str(last),
                "source_extension": ".tga",
                "frame_index": 162,
            },
        ],
    )

    assert _should_render_frame_sequence(result) is True
    assert _verified_esmini_frame_paths(result, tmp_path) == [first, middle, last]
    assert _frame_sequence_state(result, tmp_path, selected_index=1)["selected_frame_path"] == str(middle)
    assert _frame_sequence_state(result, tmp_path, selected_index=2)["last_frame_path"] == str(last)
    assert _frame_sequence_state(result, tmp_path, selected_index=1)["estimated_fps"] == 20.0


def test_frame_sequence_state_uses_raw_frames_even_when_stale_aligned_paths_exist(tmp_path: Path) -> None:
    raw_dir = tmp_path / "frames"
    aligned_dir = tmp_path / "frames_aligned"
    raw_dir.mkdir()
    aligned_dir.mkdir()
    raw = raw_dir / "frame_000001.png"
    aligned = aligned_dir / "frame_000001.png"
    raw.write_bytes(b"raw")
    aligned.write_bytes(b"aligned")
    result = _playback_result(
        playback_kind="esmini_frame_sequence",
        playback_source_path=str(raw_dir),
        playback_frame_count=1,
        playback_frame_duration_s=0.05,
        playback_frames=[
            {
                "original_source_path": str(tmp_path / "screen_shot_00000.tga"),
                "normalized_frame_path": str(raw),
                "presentation_frame_path": str(aligned),
                "source_extension": ".tga",
                "frame_index": 0,
            }
        ],
    )

    assert _verified_esmini_frame_paths(result, tmp_path) == [raw]
    assert _frame_sequence_state(result, tmp_path, selected_index=0)["selected_frame_path"] == str(raw)


def test_corrupt_capture_is_not_displayed_as_normal_esmini_playback(tmp_path: Path) -> None:
    frame = tmp_path / "frames" / "frame_000001.png"
    frame.parent.mkdir()
    frame.write_bytes(b"corrupt")
    result = _playback_result(
        playback_kind="esmini_frame_sequence",
        playback_frame_count=1,
        playback_frames=[
            {
                "original_source_path": str(tmp_path / "screen_shot_00000.tga"),
                "normalized_frame_path": str(frame),
                "source_extension": ".tga",
                "frame_index": 0,
            }
        ],
        media_quality_status="corrupt",
        media_quality_reason="Representative frames are overwhelmingly near-black.",
    )

    assert _should_render_frame_sequence(result) is False


def test_single_frame_is_screenshot_not_frame_sequence(tmp_path: Path) -> None:
    frame = tmp_path / "frames" / "frame_000001.png"
    frame.parent.mkdir()
    frame.write_bytes(b"frame")
    result = _playback_result(
        playback_kind="esmini_single_frame",
        playback_path=str(frame),
        playback_frame_count=1,
        playback_frames=[
            {
                "original_source_path": str(tmp_path / "screen_shot_00000.tga"),
                "normalized_frame_path": str(frame),
                "source_extension": ".tga",
                "frame_index": 0,
            }
        ],
    )

    assert _playback_media_label(result.playback_kind) == "esmini Screenshot"
    assert _should_render_frame_sequence(result) is False


def test_preview_fallback_is_explicit_and_not_esmini_media(tmp_path: Path) -> None:
    preview = tmp_path / "preview_2d.png"
    preview.write_bytes(b"preview")
    result = _playback_result(
        playback_kind="preview_fallback_gif",
        playback_path=str(preview),
        playback_frame_count=1,
        playback_frames=[
            {
                "original_source_path": str(preview),
                "normalized_frame_path": str(preview),
                "source_extension": ".png",
                "frame_index": 1,
            }
        ],
    )

    assert _playback_media_label(result.playback_kind) == "2D Preview Fallback"
    assert _should_render_frame_sequence(result) is False
    assert _verified_esmini_frame_paths(result, tmp_path) == []


def test_unavailable_media_has_no_misleading_esmini_playback_label(tmp_path: Path) -> None:
    result = _playback_result(playback_kind="unavailable", playback_frame_count=0)

    assert _playback_media_label(result.playback_kind) == "Playback Unavailable"
    assert _should_render_frame_sequence(result) is False
    assert _frame_sequence_state(result, tmp_path, selected_index=0)["selected_frame_path"] is None


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
    from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    view_model = build_generated_scenario_view_model(spec)

    assert view_model.title == "Rainy pedestrian occlusion"
    assert view_model.scenario_type == "pedestrian_occlusion"
    assert [(card.label, card.value) for card in view_model.brief_metrics] == [
        ("Ego", "35 km/h"),
        ("Pedestrian", "1.5 m/s"),
        ("Target TTC", "1.5 s"),
        ("Lead Time", "2.4 s"),
    ]
    assert view_model.status_cards[0].value == "generated"


def _playback_result(
    *,
    playback_kind: str,
    playback_path: str | None = None,
    playback_source_path: str | None = None,
    playback_frame_count: int = 0,
    playback_frame_duration_s: float | None = None,
    playback_frames: list[dict[str, object]] | None = None,
    media_quality_status: str = "valid",
    media_quality_reason: str | None = None,
) -> EsminiPlaybackResult:
    return EsminiPlaybackResult(
        esmini_available=True,
        command=["esmini"],
        working_dir=None,
        mode="playback",
        return_code=0,
        stdout="",
        stderr="",
        executed=True,
        playback_path=playback_path,
        playback_generated=playback_kind != "unavailable",
        playback_kind=playback_kind,
        playback_source_path=playback_source_path,
        playback_frame_count=playback_frame_count,
        playback_is_animated=playback_kind == "esmini_gif",
        playback_frame_duration_s=playback_frame_duration_s,
        playback_fallback_reason=None,
        playback_frames=playback_frames or [],
        timeout_s=30,
        sim_duration_s=3,
        capture_mode="windowed",
        capture_platform_strategy="macos_windowed_capture",
        media_quality_status=media_quality_status,
        media_quality_reason=media_quality_reason,
    )
