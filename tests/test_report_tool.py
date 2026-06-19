from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.probes import run_pedestrian_occlusion_probes
from scenariocraft.schemas import ProbeResult
from scenariocraft.tools import build_openscenario, generate_validation_report, validate_semantics
from scenariocraft.tools.asam_qc_tool import AsamQcResult
from scenariocraft.tools.esmini_tool import EsminiPlaybackResult, EsminiResult


def test_report_includes_missing_tool_warnings(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario text")
    build_result = build_openscenario(spec, tmp_path)
    qc_result = AsamQcResult(False, ["asam-qc-openscenarioxml", "scenario.xosc"], None, "", "", None)
    esmini_result = EsminiResult(False, ["esmini", "--osc", "scenario.xosc"], None, None, "", "", None, None, None)

    report_path = generate_validation_report(
        "scenario text",
        spec,
        build_result,
        qc_result,
        esmini_result,
        validate_semantics(spec),
        tmp_path,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "ASAM OpenSCENARIO XML checker was not found" in report
    assert "esmini was not found" in report
    assert "rainy_pedestrian_occlusion" in report
    assert "## Timing Harness" in report
    assert "Preferred trigger window: `1.5` s to `3` s" in report
    assert "Predicted trigger time: `3` s" in report
    assert "Timing classification: `preferred`" in report
    assert "Template-Aware Probes" not in report


def test_report_includes_optional_probe_results(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario text")
    build_result = build_openscenario(spec, tmp_path)
    qc_result = AsamQcResult(False, ["asam-qc-openscenarioxml", "scenario.xosc"], None, "", "", None)
    esmini_result = EsminiResult(False, ["esmini", "--osc", "scenario.xosc"], None, None, "", "", None, None, None)
    probe_results = (
        ProbeResult(
            name="future_geometry_probe",
            passed=False,
            severity="warning",
            message="Geometry probe placeholder result.",
            measured={"clearance_m": 0.25},
            suggested_operations=({"operation": "future_patch_placeholder", "target": "layout"},),
        ),
    )

    report_path = generate_validation_report(
        "scenario text",
        spec,
        build_result,
        qc_result,
        esmini_result,
        validate_semantics(spec),
        tmp_path,
        probe_results=probe_results,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "## Template-Aware Probes" in report
    assert "`future_geometry_probe`" in report
    assert "[FAIL]" in report
    assert "(warning)" in report
    assert "Geometry probe placeholder result." in report
    assert '"clearance_m": 0.25' in report
    assert "future_patch_placeholder" in report


def test_report_includes_canonical_pedestrian_occlusion_probe_results(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario text")
    build_result = build_openscenario(spec, tmp_path)
    qc_result = AsamQcResult(False, ["asam-qc-openscenarioxml", "scenario.xosc"], None, "", "", None)
    esmini_result = EsminiResult(False, ["esmini", "--osc", "scenario.xosc"], None, None, "", "", None, None, None)

    report_path = generate_validation_report(
        "scenario text",
        spec,
        build_result,
        qc_result,
        esmini_result,
        validate_semantics(spec),
        tmp_path,
        probe_results=run_pedestrian_occlusion_probes(spec),
    )

    report = report_path.read_text(encoding="utf-8")
    assert "## Template-Aware Probes" in report
    assert "`ego_footprint_in_ego_lane`" in report
    assert "`pedestrian_line_of_sight_occluded_by_van`" in report
    assert '"actor_id": "ego"' in report


def test_report_includes_playback_provenance_labels(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario text")
    build_result = build_openscenario(spec, tmp_path)
    qc_result = AsamQcResult(False, ["asam-qc-openscenarioxml", "scenario.xosc"], None, "", "", None)
    esmini_result = EsminiResult(
        True,
        ["esmini", "--osc", "scenario.xosc"],
        str(tmp_path),
        0,
        "loaded",
        "",
        True,
        None,
        None,
        timeout_s=30,
        process_timeout_s=3,
        mode="playback_capture",
        sim_duration_s=3,
    )
    playback_result = EsminiPlaybackResult(
        esmini_available=True,
        command=["esmini", "--capture_screen"],
        working_dir=str(tmp_path),
        mode="playback",
        return_code=0,
        stdout="loaded",
        stderr="",
        executed=True,
        playback_path=str(tmp_path / "playback_esmini.gif"),
        playback_generated=True,
        playback_kind="esmini_gif",
        playback_source_path=str(tmp_path / "frames"),
        playback_frame_count=3,
        playback_is_animated=True,
        playback_frame_duration_s=0.05,
        playback_fallback_reason=None,
        playback_frames=[
            {
                "original_source_path": str(tmp_path / "screen_shot_00000.tga"),
                "normalized_frame_path": str(tmp_path / "frames" / "frame_000001.png"),
                "source_extension": ".tga",
                "frame_index": 0,
            }
        ],
        timeout_s=30,
        sim_duration_s=3,
        capture_mode="windowed",
        capture_platform_strategy="macos_windowed_capture",
        media_quality_status="valid",
        media_quality_reason=None,
        semantic_visual_orientation="world_x_screen_right_world_y_screen_up",
        raw_visual_orientation="world_x_screen_left_world_y_screen_down",
        ui_visual_orientation="world_x_screen_left_world_y_screen_down",
        presentation_transform="none",
        presentation_transform_reason="raw_esmini_media_is_authoritative",
        preview_display_orientation="esmini_top_camera_raw",
    )

    report_path = generate_validation_report(
        "scenario text",
        spec,
        build_result,
        qc_result,
        esmini_result,
        validate_semantics(spec),
        tmp_path,
        playback_result=playback_result,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "## esmini Execution" in report
    assert "## esmini Media" in report
    assert "esmini Rendered GIF" in report
    assert "Playback kind: `esmini_gif`" in report
    assert "Capture mode: `windowed`" in report
    assert "Platform strategy: `macos_windowed_capture`" in report
    assert "Media quality status: `valid`" in report
    assert "Semantic visual orientation: `world_x_screen_right_world_y_screen_up`" in report
    assert "Raw visual orientation: `world_x_screen_left_world_y_screen_down`" in report
    assert "UI visual orientation: `world_x_screen_left_world_y_screen_down`" in report
    assert "Presentation transform: `none`" in report
    assert "Presentation transform reason: `raw_esmini_media_is_authoritative`" in report
    assert "Preview display orientation: `esmini_top_camera_raw`" in report
    assert "Visual media safe to display: `True`" in report
    assert "Frame count: `3`" in report
    assert "screen_shot_00000.tga" in report
