from __future__ import annotations

import json
from pathlib import Path

from scenariocraft_core.generators import MockScenarioGenerator
from scenariocraft_core.probes import (
    RUNTIME_PROBE_NAMES,
    run_and_write_runtime_consistency_probes,
    run_runtime_consistency_probes,
)


def test_missing_runtime_artifacts_warn_without_hard_failures() -> None:
    spec = _spec()

    results = run_runtime_consistency_probes(spec)
    by_name = _by_name(results)

    assert [result.name for result in results] == list(RUNTIME_PROBE_NAMES)
    assert by_name["runtime_esmini_execution_available"].severity == "warning"
    assert by_name["runtime_xodr_loaded"].severity == "note"
    assert by_name["runtime_pedestrian_event_reached_running_state"].severity == "warning"
    assert by_name["runtime_visual_media_provenance_valid"].severity == "warning"
    assert by_name["runtime_motion_verifiable"].severity == "warning"


def test_successful_synthetic_esmini_log_and_media_pass_runtime_probes(tmp_path: Path) -> None:
    log_path = _write_log(tmp_path, _successful_log())
    playback_path = _write_playback(tmp_path, _playback_result("esmini_gif", frame_count=3, animated=True))
    xodr_path = tmp_path / "urban_two_way_parking.xodr"
    xodr_path.write_text("xodr", encoding="utf-8")

    results = run_runtime_consistency_probes(
        _spec(),
        xosc_path=tmp_path / "scenario.xosc",
        xodr_path=xodr_path,
        esmini_log_path=log_path,
        playback_result_path=playback_path,
    )

    assert all(result.passed for result in results)
    by_name = _by_name(results)
    assert by_name["runtime_xodr_loaded"].measured["xodr_loaded"] is True
    assert by_name["runtime_motion_verifiable"].measured["runtime_motion_verifiable"] is True


def test_standby_complete_without_running_does_not_pass_running_state_probe(tmp_path: Path) -> None:
    log_path = _write_log(
        tmp_path,
        "\n".join([
            "Loaded scenario.xosc",
            "Loading roadmanager urban_two_way_parking.xodr",
            "[0.000] pedestrian_starts_crossing initState -> initToStandbyTransition -> standbyState",
            "[8.050] pedestrian_starts_crossing standbyState -> stopTransition -> completeState",
        ]),
    )
    playback_path = _write_playback(tmp_path, _playback_result("esmini_gif", frame_count=3, animated=True))

    by_name = _by_name(
        run_runtime_consistency_probes(
            _spec(),
            xodr_path=tmp_path / "urban_two_way_parking.xodr",
            esmini_log_path=log_path,
            playback_result_path=playback_path,
        )
    )

    assert by_name["runtime_pedestrian_event_started"].passed is False
    assert by_name["runtime_pedestrian_event_started"].severity == "failure"
    assert by_name["runtime_pedestrian_event_reached_running_state"].passed is False
    assert by_name["runtime_pedestrian_event_reached_running_state"].severity == "failure"
    assert by_name["runtime_pedestrian_event_completed"].passed is True
    assert by_name["runtime_motion_verifiable"].passed is False


def test_esmini_gif_with_valid_quality_passes_visual_media_provenance(tmp_path: Path) -> None:
    playback_path = _write_playback(tmp_path, _playback_result("esmini_gif", frame_count=4, animated=True))

    by_name = _by_name(run_runtime_consistency_probes(_spec(), playback_result_path=playback_path))

    assert by_name["runtime_visual_media_provenance_valid"].passed is True
    assert by_name["runtime_visual_media_provenance_valid"].measured["playback_kind"] == "esmini_gif"


def test_preview_fallback_does_not_pass_as_valid_esmini_runtime_media(tmp_path: Path) -> None:
    playback_path = _write_playback(
        tmp_path,
        _playback_result("preview_fallback_gif", frame_count=1, animated=False, quality="valid"),
    )

    by_name = _by_name(run_runtime_consistency_probes(_spec(), playback_result_path=playback_path))

    assert by_name["runtime_visual_media_provenance_valid"].passed is False
    assert by_name["runtime_visual_media_provenance_valid"].severity == "failure"
    assert by_name["runtime_visual_media_provenance_valid"].measured["visual_media_genuine_esmini"] is False


def test_corrupt_capture_quality_does_not_pass_visual_media_provenance(tmp_path: Path) -> None:
    playback_path = _write_playback(
        tmp_path,
        _playback_result("unavailable", frame_count=0, animated=False, quality="corrupt"),
    )

    by_name = _by_name(run_runtime_consistency_probes(_spec(), playback_result_path=playback_path))

    assert by_name["runtime_visual_media_provenance_valid"].passed is False
    assert by_name["runtime_visual_media_provenance_valid"].severity == "failure"
    assert by_name["runtime_visual_media_provenance_valid"].measured["media_quality_status"] == "corrupt"


def test_motion_requires_event_action_evidence_and_animated_esmini_media(tmp_path: Path) -> None:
    log_path = _write_log(tmp_path, _successful_log())
    single_frame = _write_playback(tmp_path, _playback_result("esmini_single_frame", frame_count=1, animated=False))

    by_name = _by_name(run_runtime_consistency_probes(_spec(), esmini_log_path=log_path, playback_result_path=single_frame))

    assert by_name["runtime_pedestrian_event_reached_running_state"].passed is True
    assert by_name["runtime_trajectory_action_started"].passed is True
    assert by_name["runtime_visual_media_provenance_valid"].passed is True
    assert by_name["runtime_motion_verifiable"].passed is False
    assert by_name["runtime_motion_verifiable"].measured["visual_media_animated_esmini"] is False


def test_runtime_pipeline_writes_results_from_generated_artifacts(tmp_path: Path) -> None:
    _write_log(tmp_path, _successful_log())
    _write_playback(tmp_path, _playback_result("esmini_frame_sequence", frame_count=2, animated=True))
    xosc_path = tmp_path / "scenario.xosc"
    xodr_path = tmp_path / "urban_two_way_parking.xodr"
    xosc_path.write_text("xosc", encoding="utf-8")
    xodr_path.write_text("xodr", encoding="utf-8")

    results = run_and_write_runtime_consistency_probes(
        _spec(),
        output_dir=tmp_path,
        xosc_path=xosc_path,
        xodr_path=xodr_path,
    )

    result_path = tmp_path / "runtime_probe_results.json"
    assert result_path.exists()
    assert all(result.passed for result in results)
    written = json.loads(result_path.read_text(encoding="utf-8"))
    assert written[0]["name"] == "runtime_esmini_execution_available"
    assert written[-1]["name"] == "runtime_motion_verifiable"


def _spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")


def _successful_log() -> str:
    return "\n".join([
        "Loaded scenario.xosc",
        "Loading roadmanager urban_two_way_parking.xodr",
        "[0.250] pedestrian_starts_crossing standbyState -> startTransition -> runningState",
        "FollowTrajectoryAction pedestrian_follow_crossing_path started",
        "[3.950] pedestrian_starts_crossing runningState -> endTransition -> completeState",
    ])


def _playback_result(
    playback_kind: str,
    *,
    frame_count: int,
    animated: bool,
    quality: str = "valid",
) -> dict[str, object]:
    return {
        "esmini_available": True,
        "executed": True,
        "return_code": 0,
        "playback_kind": playback_kind,
        "playback_frame_count": frame_count,
        "playback_is_animated": animated,
        "playback_frames": [
            {
                "original_source_path": f"screen_shot_{index:05d}.tga",
                "normalized_frame_path": f"frames/frame_{index + 1:06d}.png",
                "source_extension": ".tga",
                "frame_index": index + 1,
            }
            for index in range(frame_count)
        ],
        "media_quality_status": quality,
        "playback_source_path": "frames",
        "playback_fallback_reason": None,
    }


def _write_log(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "esmini_capture_log.txt"
    path.write_text(text, encoding="utf-8")
    return path


def _write_playback(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "esmini_playback_result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _by_name(results):
    return {result.name: result for result in results}
