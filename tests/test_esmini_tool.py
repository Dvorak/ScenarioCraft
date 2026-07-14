import json
import subprocess
from pathlib import Path

import scenariocraft.external_tools.esmini as esmini_tool
from scenariocraft.external_tools.esmini import (
    _build_playback_media,
    _build_presentation_frames,
    _build_capture_command,
    _capture_mode_for_platform,
    _classify_media_quality,
    _discover_native_capture_frames,
    classify_esmini_timeout,
    resolve_esmini_binary,
    run_esmini,
    run_esmini_playback,
    supports_native_video_export,
)


def _write_image(path: Path, color: tuple[int, int, int] = (255, 0, 0)) -> None:
    from PIL import Image

    Image.new("RGB", (3, 2), color=color).save(path)


def _write_directional_image(path: Path) -> None:
    from PIL import Image

    image = Image.new("RGB", (2, 2))
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 255, 0))
    image.putpixel((0, 1), (0, 0, 255))
    image.putpixel((1, 1), (255, 255, 0))
    image.save(path)


def _pixels(path: Path) -> dict[tuple[int, int], tuple[int, int, int]]:
    from PIL import Image

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        return {
            (x, y): rgb.getpixel((x, y))
            for y in range(rgb.height)
            for x in range(rgb.width)
        }


def test_esmini_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    result = run_esmini(tmp_path / "scenario.xosc", tmp_path, required=True)

    assert result.esmini_available is False
    assert result.executed is None
    assert result.required is True
    assert result.working_dir == str(tmp_path)
    assert result.error_message == "esmini was not found."
    assert "not found" in result.stderr
    assert (tmp_path / "esmini_log.txt").exists()
    assert (tmp_path / "esmini_stdout.txt").exists()
    assert (tmp_path / "esmini_stderr.txt").exists()


def test_esmini_success(monkeypatch, tmp_path) -> None:
    xosc_path = tmp_path / "scenario.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")
    captured = {}
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        captured["command"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(args[0], 0, "loaded", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_esmini(xosc_path)

    assert result.esmini_available is True
    assert result.executed is True
    assert result.return_code == 0
    assert result.error_message is None
    assert result.working_dir == str(tmp_path)
    assert captured["cwd"] == tmp_path
    assert captured["command"][2] == "scenario.xosc"


def test_esmini_resolves_local_prebuilt_binary(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _binary: None)
    local_bin = tmp_path / "third_party" / "esmini" / "v3.3.0" / "extracted" / "esmini-bin_macOS" / "bin" / "esmini"
    local_bin.parent.mkdir(parents=True)
    local_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    local_bin.chmod(0o755)

    resolved = resolve_esmini_binary(search_root=tmp_path)

    assert resolved == local_bin.resolve()


def test_esmini_default_search_root_matches_repository_root() -> None:
    repository_root = Path(__file__).resolve().parents[1]

    assert esmini_tool._project_root() == repository_root


def test_esmini_local_marker_precedes_cached_version_scan(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _binary: None)
    old_binary = tmp_path / "third_party" / "esmini" / "v3.3.0" / "bin" / "esmini"
    selected_binary = tmp_path / "third_party" / "esmini" / "v3.5.0" / "bin" / "esmini"
    for binary in (old_binary, selected_binary):
        binary.parent.mkdir(parents=True)
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        binary.chmod(0o755)
    (tmp_path / "third_party" / "esmini" / "ESMINI_BIN").write_text(
        str(selected_binary),
        encoding="utf-8",
    )

    resolved = resolve_esmini_binary(search_root=tmp_path)

    assert resolved == selected_binary.resolve()


def test_esmini_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failed"),
    )

    result = run_esmini(tmp_path / "scenario.xosc")

    assert result.esmini_available is True
    assert result.executed is False
    assert result.return_code == 1
    assert result.error_message == "esmini exited with code 1."


def test_esmini_working_dir_defaults_to_xosc_parent(monkeypatch, tmp_path) -> None:
    scenario_dir = tmp_path / "reference"
    scenario_dir.mkdir()
    xosc_path = scenario_dir / "external.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")
    captured = {}
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        captured["cwd"] = kwargs["cwd"]
        captured["command"] = args[0]
        return subprocess.CompletedProcess(args[0], 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_esmini(xosc_path)

    assert result.working_dir == str(scenario_dir)
    assert captured["cwd"] == scenario_dir
    assert captured["command"][2] == "external.xosc"


def test_esmini_timeout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="partial", stderr="still running")

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = run_esmini(tmp_path / "scenario.xosc", timeout_s=0.1)

    assert result.esmini_available is True
    assert result.executed is False
    assert result.timed_out is True
    assert result.timeout_s == 0.1
    assert result.timeout_classification == "timeout_possible_long_scenario"


def test_esmini_smoke_mode_uses_short_process_timeout_and_marks_startup_timeout_as_executed(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")
    captured = {}

    def raise_timeout(*args, **kwargs):
        captured["command"] = args[0]
        captured["timeout"] = kwargs["timeout"]
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="OpenSCENARIO loaded", stderr="")

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = run_esmini(tmp_path / "scenario.xosc", timeout_s=30, mode="smoke", sim_duration_s=3)

    assert "--fixed_timestep" in captured["command"]
    assert "--quit_at_end" not in captured["command"]
    assert captured["timeout"] == 3
    assert result.mode == "smoke"
    assert result.timeout_s == 30
    assert result.process_timeout_s == 3
    assert result.sim_duration_s == 3
    assert result.timed_out is True
    assert result.timeout_classification == "timeout_after_start"
    assert result.executed is True


def test_esmini_timeout_classifier_distinguishes_common_timeout_shapes() -> None:
    assert classify_esmini_timeout("", "", mode="smoke") == "timeout_no_output"
    assert classify_esmini_timeout("", "Viewer window waiting", mode="smoke") == "timeout_possible_viewer_block"
    assert classify_esmini_timeout("OpenDRIVE loaded", "", mode="smoke") == "timeout_after_start"
    assert classify_esmini_timeout("OpenDRIVE loaded", "", mode="full") == "timeout_possible_long_scenario"


def test_esmini_playback_falls_back_when_esmini_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
    monkeypatch.setattr("shutil.which", lambda _binary: None)
    xosc_path = tmp_path / "scenario.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")

    result = run_esmini_playback(xosc_path, tmp_path, timeout_s=30, sim_duration_s=3)

    assert result.esmini_available is False
    assert result.playback_generated is False
    assert result.playback_path is None
    assert result.playback_kind == "unavailable"
    assert result.playback_frame_count == 0
    assert result.playback_is_animated is False
    assert "not found" in (result.fallback_reason or "")
    assert (tmp_path / "esmini_playback_result.json").exists()
    serialized = json.loads((tmp_path / "esmini_playback_result.json").read_text(encoding="utf-8"))
    assert serialized["playback_generated"] is False
    assert serialized["playback_kind"] == "unavailable"


def test_esmini_playback_falls_back_when_video_export_is_not_advertised(monkeypatch, tmp_path) -> None:
    xosc_path = tmp_path / "scenario.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[-1] == "--help":
            return subprocess.CompletedProcess(command, 0, "usage: esmini --osc file.xosc --headless", "")
        return subprocess.CompletedProcess(command, 0, "scenario loaded", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_esmini_playback(xosc_path, tmp_path, timeout_s=30, sim_duration_s=3, try_video=True)

    assert result.esmini_available is True
    assert result.executed is True
    assert result.playback_generated is False
    assert result.playback_kind == "unavailable"
    assert "does not advertise --capture_screen" in (result.fallback_reason or "")
    assert (tmp_path / "esmini_result.json").exists()
    assert (tmp_path / "esmini_help.txt").read_text(encoding="utf-8")


def test_esmini_playback_falls_back_when_capture_produces_no_frames(monkeypatch, tmp_path) -> None:
    xosc_path = tmp_path / "scenario.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[-1] == "--help":
            return subprocess.CompletedProcess(command, 0, "usage: esmini --capture_screen --headless", "")
        if "--capture_screen" in command:
            return subprocess.CompletedProcess(command, 0, "capture complete but no files", "")
        return subprocess.CompletedProcess(command, 0, "fallback execution ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_esmini_playback(xosc_path, tmp_path, timeout_s=30, sim_duration_s=3, try_video=True)

    assert result.esmini_available is True
    assert result.executed is True
    assert result.playback_generated is False
    assert result.playback_path is None
    assert result.playback_kind == "unavailable"
    assert result.playback_frame_count == 0
    assert result.media_quality_status == "corrupt"
    assert "no native screen_shot" in (result.media_quality_reason or "")
    assert "--capture_screen" in result.command
    assert "no native screen_shot" in (result.fallback_reason or "")
    assert "fallback execution ok" in result.stdout


def test_macos_capture_command_uses_windowed_strategy() -> None:
    command = _build_capture_command("/fake/esmini", "scenario.xosc", Path("/tmp/work"), platform_name="Darwin")

    assert "--capture_screen" in command
    assert "--camera_mode" in command
    assert "top" in command
    assert "--headless" not in command
    window_index = command.index("--window")
    assert command[window_index + 1: window_index + 5] == ["2500", "1200", "960", "540"]
    assert _capture_mode_for_platform("Darwin") == "windowed"


def test_non_macos_capture_command_preserves_headless_strategy() -> None:
    command = _build_capture_command("/fake/esmini", "scenario.xosc", Path("/tmp/work"), platform_name="Linux")

    assert "--headless" in command
    assert "--capture_screen" in command
    window_index = command.index("--window")
    assert command[window_index + 1: window_index + 5] == ["0", "0", "960", "540"]
    assert _capture_mode_for_platform("Linux") == "headless"


def test_discovers_and_numerically_sorts_screen_shot_tga_frames(tmp_path) -> None:
    _write_image(tmp_path / "screen_shot_00010.tga")
    _write_image(tmp_path / "screen_shot_00002.tga")
    _write_image(tmp_path / "screen_shot_00001.tga")
    _write_image(tmp_path / "preview_2d.png")

    frames = _discover_native_capture_frames(tmp_path)

    assert [frame.frame_index for frame in frames] == [1, 2, 10]
    assert [frame.source_path.name for frame in frames] == [
        "screen_shot_00001.tga",
        "screen_shot_00002.tga",
        "screen_shot_00010.tga",
    ]


def test_build_playback_media_ignores_preview_and_preserves_provenance(tmp_path) -> None:
    _write_image(tmp_path / "preview_2d.png", color=(0, 0, 255))
    _write_image(tmp_path / "screen_shot_00000.tga", color=(255, 0, 0))
    _write_image(tmp_path / "screen_shot_00001.tga", color=(0, 255, 0))

    media = _build_playback_media(tmp_path, frame_duration_s=0.05)

    assert media["playback_kind"] == "esmini_gif"
    assert media["playback_frame_count"] == 2
    assert media["playback_is_animated"] is True
    assert media["playback_frame_duration_s"] == 0.05
    assert media["playback_path"] == str(tmp_path / "playback_esmini_raw.gif")
    assert not (tmp_path / "playback_esmini_aligned.gif").exists()
    assert (tmp_path / "playback_esmini_raw.gif").exists()
    assert (tmp_path / "frames" / "frame_000001.png").exists()
    assert not (tmp_path / "frames_aligned").exists()
    assert media["playback_frames"][0]["original_source_path"].endswith("screen_shot_00000.tga")
    assert media["playback_frames"][0]["normalized_frame_path"].endswith("frames/frame_000001.png")
    assert media["playback_frames"][0]["presentation_frame_path"] is None
    assert media["playback_frames"][0]["source_extension"] == ".tga"
    assert media["semantic_visual_orientation"] == "world_x_screen_right_world_y_screen_up"
    assert media["raw_visual_orientation"] == "world_x_screen_left_world_y_screen_down"
    assert media["ui_visual_orientation"] == "world_x_screen_left_world_y_screen_down"
    assert media["presentation_transform"] == "none"
    assert media["presentation_transform_reason"] == "raw_esmini_media_is_authoritative"
    assert media["preview_display_orientation"] == "esmini_top_camera_raw"
    assert "preview_2d.png" not in {
        Path(frame["original_source_path"]).name for frame in media["playback_frames"]
    }


def test_presentation_transform_none_preserves_raw_media_path(tmp_path) -> None:
    raw_dir = tmp_path / "frames"
    raw_dir.mkdir()
    raw = raw_dir / "frame_000001.png"
    _write_directional_image(raw)
    before = raw.read_bytes()

    frames, reason = _build_presentation_frames([raw], tmp_path / "frames_aligned", "none")

    assert reason is None
    assert frames == [raw]
    assert raw.read_bytes() == before
    assert not (tmp_path / "frames_aligned").exists()


def test_presentation_transform_horizontal_mirror_affects_x_only(tmp_path) -> None:
    raw = tmp_path / "frame_000001.png"
    _write_directional_image(raw)

    frames, reason = _build_presentation_frames([raw], tmp_path / "frames_aligned", "horizontal_mirror")

    assert reason is None
    pixels = _pixels(frames[0])
    assert pixels[(0, 0)] == (0, 255, 0)
    assert pixels[(1, 0)] == (255, 0, 0)
    assert pixels[(0, 1)] == (255, 255, 0)
    assert pixels[(1, 1)] == (0, 0, 255)


def test_presentation_transform_vertical_mirror_affects_y_only(tmp_path) -> None:
    raw = tmp_path / "frame_000001.png"
    _write_directional_image(raw)

    frames, reason = _build_presentation_frames([raw], tmp_path / "frames_aligned", "vertical_mirror")

    assert reason is None
    pixels = _pixels(frames[0])
    assert pixels[(0, 0)] == (0, 0, 255)
    assert pixels[(1, 0)] == (255, 255, 0)
    assert pixels[(0, 1)] == (255, 0, 0)
    assert pixels[(1, 1)] == (0, 255, 0)


def test_presentation_transform_rotate_180_affects_x_and_y(tmp_path) -> None:
    raw = tmp_path / "frame_000001.png"
    _write_directional_image(raw)

    frames, reason = _build_presentation_frames([raw], tmp_path / "frames_aligned", "rotate_180")

    assert reason is None
    pixels = _pixels(frames[0])
    assert pixels[(0, 0)] == (255, 255, 0)
    assert pixels[(1, 0)] == (0, 0, 255)
    assert pixels[(0, 1)] == (0, 255, 0)
    assert pixels[(1, 1)] == (255, 0, 0)


def test_build_playback_media_uses_raw_artifacts_for_normal_playback(tmp_path) -> None:
    _write_directional_image(tmp_path / "screen_shot_00000.tga")
    _write_image(tmp_path / "screen_shot_00001.tga", color=(0, 255, 0))

    media = _build_playback_media(tmp_path, frame_duration_s=0.05)

    raw_frame = tmp_path / "frames" / "frame_000001.png"
    assert raw_frame.exists()
    assert (tmp_path / "playback_esmini_raw.gif").exists()
    assert media["playback_path"] == str(tmp_path / "playback_esmini_raw.gif")
    assert not (tmp_path / "playback_esmini_aligned.gif").exists()
    assert not (tmp_path / "frames_aligned").exists()
    assert media["playback_frames"][0]["normalized_frame_path"] == str(raw_frame)
    assert media["playback_frames"][0]["presentation_frame_path"] is None


def test_classifies_multiple_esmini_frames_as_sequence_when_gif_encoder_unavailable(monkeypatch, tmp_path) -> None:
    _write_image(tmp_path / "screen_shot_00000.tga")
    _write_image(tmp_path / "screen_shot_00001.tga", color=(0, 255, 0))
    monkeypatch.setattr(esmini_tool, "_encode_esmini_gif", lambda frames, gif_path, frame_duration_s: "encoder unavailable")

    media = _build_playback_media(tmp_path, frame_duration_s=0.05)

    assert media["playback_kind"] == "esmini_frame_sequence"
    assert media["playback_generated"] is True
    assert media["playback_frame_count"] == 2
    assert media["playback_is_animated"] is False
    assert media["playback_path"] is None
    assert media["playback_fallback_reason"] == "encoder unavailable"
    assert media["media_quality_status"] == "valid"


def test_classifies_all_black_representative_frames_as_corrupt(monkeypatch, tmp_path) -> None:
    _write_image(tmp_path / "screen_shot_00000.tga", color=(0, 0, 0))
    _write_image(tmp_path / "screen_shot_00001.tga", color=(0, 0, 0))
    monkeypatch.setattr(esmini_tool, "_encode_esmini_gif", lambda frames, gif_path, frame_duration_s: "encoder unavailable")

    media = _build_playback_media(tmp_path, frame_duration_s=0.05)

    assert media["playback_kind"] == "unavailable"
    assert media["playback_generated"] is False
    assert media["media_quality_status"] == "corrupt"
    assert "near-black" in (media["media_quality_reason"] or "")


def test_quality_gate_accepts_valid_representative_frames(tmp_path) -> None:
    first = tmp_path / "frame_000001.png"
    middle = tmp_path / "frame_000002.png"
    final = tmp_path / "frame_000003.png"
    _write_image(first, color=(255, 0, 0))
    _write_image(middle, color=(0, 255, 0))
    _write_image(final, color=(0, 0, 255))

    status, reason = _classify_media_quality([first, middle, final])

    assert status == "valid"
    assert reason is None


def test_classifies_one_esmini_frame_as_single_frame(tmp_path) -> None:
    _write_image(tmp_path / "screen_shot_00000.tga")

    media = _build_playback_media(tmp_path, frame_duration_s=0.05)

    assert media["playback_kind"] == "esmini_single_frame"
    assert media["playback_generated"] is True
    assert media["playback_frame_count"] == 1
    assert media["playback_is_animated"] is False
    assert media["playback_path"] == str(tmp_path / "frames" / "frame_000001.png")
    assert media["playback_frames"][0]["normalized_frame_path"].endswith("frames/frame_000001.png")
    assert media["playback_frames"][0]["presentation_frame_path"] is None
    assert media["presentation_transform"] == "none"


def test_preview_fallback_is_explicit_and_never_esmini_gif(monkeypatch, tmp_path) -> None:
    xosc_path = tmp_path / "scenario.xosc"
    xosc_path.write_text("<OpenSCENARIO/>", encoding="utf-8")
    _write_image(tmp_path / "preview_2d.png")
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        command = args[0]
        if command[-1] == "--help":
            return subprocess.CompletedProcess(command, 0, "usage: esmini --capture_screen --headless", "")
        if "--capture_screen" in command:
            return subprocess.CompletedProcess(command, 0, "capture complete but no files", "")
        return subprocess.CompletedProcess(command, 0, "fallback execution ok", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_esmini_playback(xosc_path, tmp_path, timeout_s=30, sim_duration_s=3, try_video=True)

    assert result.playback_generated is False
    assert result.playback_kind == "unavailable"
    assert result.playback_path is None
    assert result.playback_frame_count == 0
    assert result.playback_is_animated is False
    assert result.playback_fallback_reason
    assert result.media_quality_status == "corrupt"
    assert result.playback_kind != "esmini_gif"


def test_esmini_capture_screen_support_detection_is_string_based() -> None:
    assert supports_native_video_export("usage: esmini --record output.dat") is False
    assert supports_native_video_export("usage: esmini --capture_screen") is True
    assert supports_native_video_export("usage: esmini --osc scenario.xosc --headless") is False
