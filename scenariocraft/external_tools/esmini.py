"""Runtime adapter for invoking an already-configured esmini executable."""

from __future__ import annotations

import json
import os
import hashlib
import platform
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path


ESMINI_MODES = {"smoke", "full"}
CAPTURE_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tga"}
SCREENSHOT_RE = re.compile(r"^screen_shot_(\d+)\.(jpg|jpeg|png|tga)$", re.IGNORECASE)
DEFAULT_FRAME_DURATION_S = 0.05
MEDIA_QUALITY_NEAR_BLACK_FRACTION_THRESHOLD = 0.98
MEDIA_QUALITY_MIN_DIMENSION_PX = 2
SEMANTIC_VISUAL_ORIENTATION = "world_x_screen_right_world_y_screen_up"
RAW_VISUAL_ORIENTATION = "world_x_screen_left_world_y_screen_down"
PRESENTATION_TRANSFORM = "none"
PRESENTATION_TRANSFORM_REASON = "raw_esmini_media_is_authoritative"
PREVIEW_DISPLAY_ORIENTATION = "esmini_top_camera_raw"
MACOS_PREFERRED_CAPTURE_WINDOW = ("2500", "1200", "960", "540")
MACOS_FALLBACK_CAPTURE_WINDOW = ("100", "100", "960", "540")
DEFAULT_PLATFORM_CAPTURE_WINDOW = ("0", "0", "960", "540")
PLAYBACK_KINDS = {
    "esmini_gif",
    "esmini_frame_sequence",
    "esmini_single_frame",
    "preview_fallback_gif",
    "preview_static_image",
    "unavailable",
}


@dataclass(frozen=True)
class EsminiResult:
    esmini_available: bool
    command: list[str]
    working_dir: str | None
    return_code: int | None
    stdout: str
    stderr: str
    executed: bool | None
    error_message: str | None
    playback_path: str | None
    required: bool = False
    install_hint: str | None = None
    timeout_s: float | None = None
    process_timeout_s: float | None = None
    timed_out: bool = False
    mode: str = "full"
    sim_duration_s: float | None = None
    timeout_classification: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class EsminiPlaybackResult:
    esmini_available: bool
    command: list[str]
    working_dir: str | None
    mode: str
    return_code: int | None
    stdout: str
    stderr: str
    executed: bool | None
    playback_path: str | None
    playback_generated: bool
    playback_kind: str
    playback_source_path: str | None
    playback_frame_count: int
    playback_is_animated: bool
    playback_frame_duration_s: float | None
    playback_fallback_reason: str | None
    playback_frames: list[dict[str, object]]
    timeout_s: float | int
    sim_duration_s: float | int | None = None
    fallback_reason: str | None = None
    capture_mode: str = "unavailable"
    capture_platform_strategy: str = "unavailable"
    media_quality_status: str = "unavailable"
    media_quality_reason: str | None = None
    capture_window_x: int | None = None
    capture_window_y: int | None = None
    capture_window_width: int | None = None
    capture_window_height: int | None = None
    capture_window_policy: str = "unavailable"
    capture_attempts: list[dict[str, object]] = field(default_factory=list)
    semantic_visual_orientation: str = SEMANTIC_VISUAL_ORIENTATION
    raw_visual_orientation: str = "unknown"
    ui_visual_orientation: str = "unknown"
    presentation_transform: str = "none"
    presentation_transform_reason: str | None = None
    preview_display_orientation: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


@dataclass(frozen=True)
class CaptureFrame:
    source_path: Path
    frame_index: int
    source_extension: str


@dataclass(frozen=True)
class FrameProvenance:
    original_source_path: str
    normalized_frame_path: str | None
    source_extension: str
    frame_index: int
    presentation_frame_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_esmini(
    xosc_path: Path,
    output_dir: Path | None = None,
    working_dir: Path | None = None,
    required: bool = False,
    binary: str | None = None,
    timeout_s: float = 20.0,
    mode: str = "full",
    sim_duration_s: float = 3.0,
) -> EsminiResult:
    if mode not in ESMINI_MODES:
        raise ValueError(f"Unsupported esmini mode: {mode}")
    resolved_xosc_path = Path(xosc_path).expanduser().resolve()
    resolved_working_dir = Path(working_dir).expanduser().resolve() if working_dir else resolved_xosc_path.parent
    result_working_dir = _display_path(resolved_working_dir)
    command_xosc_path = os.path.relpath(resolved_xosc_path, resolved_working_dir)
    resolved_binary = resolve_esmini_binary(binary)
    command_binary = str(resolved_binary or binary or os.environ.get("ESMINI_BIN", "esmini"))
    command = _build_command(command_binary, command_xosc_path, mode)
    process_timeout_s = sim_duration_s if mode == "smoke" else timeout_s
    if resolved_binary is None:
        result = EsminiResult(
            esmini_available=False,
            command=command,
            working_dir=result_working_dir,
            return_code=None,
            stdout="",
            stderr="esmini was not found.",
            executed=None,
            error_message="esmini was not found.",
            playback_path=None,
            required=required,
            install_hint=_install_hint(),
            timeout_s=timeout_s,
            process_timeout_s=process_timeout_s,
            timed_out=False,
            mode=mode,
            sim_duration_s=sim_duration_s if mode == "smoke" else None,
            timeout_classification=None,
        )
    else:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=process_timeout_s,
                cwd=resolved_working_dir,
            )
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                executed=completed.returncode == 0,
                error_message=None if completed.returncode == 0 else f"esmini exited with code {completed.returncode}.",
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                process_timeout_s=process_timeout_s,
                timed_out=False,
                mode=mode,
                sim_duration_s=sim_duration_s if mode == "smoke" else None,
                timeout_classification=None,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = _decode_timeout_output(exc.stderr) or f"esmini timed out after {timeout_s:g} seconds."
            stdout = _decode_timeout_output(exc.stdout)
            timeout_classification = classify_esmini_timeout(stdout=stdout, stderr=stderr, mode=mode)
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=None,
                stdout=stdout,
                stderr=stderr,
                executed=mode == "smoke" and timeout_classification in {
                    "timeout_after_start",
                    "timeout_possible_long_scenario",
                },
                error_message=stderr,
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                process_timeout_s=process_timeout_s,
                timed_out=True,
                mode=mode,
                sim_duration_s=sim_duration_s if mode == "smoke" else None,
                timeout_classification=timeout_classification,
            )
        except OSError as exc:
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=None,
                stdout="",
                stderr=str(exc),
                executed=False,
                error_message=str(exc),
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                process_timeout_s=process_timeout_s,
                timed_out=False,
                mode=mode,
                sim_duration_s=sim_duration_s if mode == "smoke" else None,
                timeout_classification=None,
            )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "esmini_log.txt").write_text(_format_log(result), encoding="utf-8")
        (output_dir / "esmini_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (output_dir / "esmini_stderr.txt").write_text(result.stderr, encoding="utf-8")
    return result


def run_esmini_playback(
    xosc_path: Path,
    output_dir: Path,
    working_dir: Path | None = None,
    binary: str | None = None,
    timeout_s: float = 30.0,
    sim_duration_s: float = 3.0,
    try_video: bool = True,
    mode: str = "playback",
) -> EsminiPlaybackResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_xosc_path = Path(xosc_path).expanduser().resolve()
    resolved_working_dir = Path(working_dir).expanduser().resolve() if working_dir else resolved_xosc_path.parent
    resolved_binary = resolve_esmini_binary(binary)
    fallback_reason: str | None = None
    help_text = ""
    command: list[str] = []
    stdout = ""
    stderr = ""
    return_code: int | None = None
    executed: bool | None = None
    playback_path: str | None = None
    playback_generated = False
    playback_kind = "unavailable"
    playback_source_path: str | None = None
    playback_frame_count = 0
    playback_is_animated = False
    playback_frame_duration_s: float | None = None
    playback_frames: list[dict[str, object]] = []
    capture_mode = "unavailable"
    capture_platform_strategy = "unavailable"
    media_quality_status = "unavailable"
    media_quality_reason: str | None = None
    capture_window_x: int | None = None
    capture_window_y: int | None = None
    capture_window_width: int | None = None
    capture_window_height: int | None = None
    capture_window_policy = "unavailable"
    capture_attempts: list[dict[str, object]] = []
    semantic_visual_orientation = SEMANTIC_VISUAL_ORIENTATION
    raw_visual_orientation = "unknown"
    ui_visual_orientation = "unknown"
    presentation_transform = "none"
    presentation_transform_reason: str | None = None
    preview_display_orientation: str | None = None
    if resolved_binary is None:
        fallback_reason = "esmini was not found. Playback video could not be generated."
        esmini_result = run_esmini(
            resolved_xosc_path,
            output_dir,
            working_dir=resolved_working_dir,
            binary=binary,
            timeout_s=timeout_s,
            mode="smoke",
            sim_duration_s=sim_duration_s,
        )
        command = esmini_result.command
        stdout = esmini_result.stdout
        stderr = esmini_result.stderr
        return_code = esmini_result.return_code
        executed = esmini_result.executed
        preview_media = _preview_fallback(output_dir, fallback_reason)
        if preview_media is not None:
            playback_path = preview_media
            playback_generated = True
            playback_kind = "preview_static_image"
            playback_source_path = preview_media
            playback_frame_count = 1
    else:
        help_text = get_esmini_help_text(resolved_binary)
        capture_supported = supports_frame_capture(help_text)
        if not try_video:
            fallback_reason = "Playback video generation was disabled. Execution check completed instead."
        elif not capture_supported:
            fallback_reason = "This esmini build/help output does not advertise --capture_screen. Execution check completed instead."
        else:
            capture_mode = _capture_mode_for_platform()
            capture_platform_strategy = _capture_platform_strategy()
            capture_result = None
            media: dict[str, object] | None = None
            fallback_note: str | None = None
            for attempt_index, attempt_policy in enumerate(_capture_attempt_policies()):
                _clear_capture_artifacts(output_dir)
                capture_result = _run_esmini_capture(
                    binary=resolved_binary,
                    xosc_path=resolved_xosc_path,
                    output_dir=output_dir,
                    working_dir=resolved_working_dir,
                    timeout_s=timeout_s,
                    sim_duration_s=sim_duration_s,
                    capture_window_policy=attempt_policy,
                )
                media = _build_playback_media(output_dir, DEFAULT_FRAME_DURATION_S)
                if (
                    str(media["media_quality_status"]) == "unavailable"
                    and capture_result.executed
                    and capture_result.return_code == 0
                    and not media["playback_frames"]
                ):
                    media = {
                        **media,
                        "media_quality_status": "corrupt",
                        "media_quality_reason": "esmini capture completed, but no native screen_shot_* frames were produced.",
                    }
                capture_attempts.append(_capture_attempt_metadata(attempt_policy, capture_result, media))
                command = capture_result.command
                stdout = capture_result.stdout
                stderr = capture_result.stderr
                return_code = capture_result.return_code
                executed = capture_result.executed
                if _capture_media_is_usable(media):
                    if attempt_index > 0:
                        fallback_note = "Playback rendered using compatibility window placement."
                    break
                if not _should_retry_capture(attempt_policy, capture_result, media):
                    break
            if media is None or capture_result is None:
                media = _build_playback_media(output_dir, DEFAULT_FRAME_DURATION_S)
            playback_path = media["playback_path"]
            playback_generated = bool(media["playback_generated"])
            playback_kind = str(media["playback_kind"])
            playback_source_path = media["playback_source_path"]
            playback_frame_count = int(media["playback_frame_count"])
            playback_is_animated = bool(media["playback_is_animated"])
            playback_frame_duration_s = media["playback_frame_duration_s"]
            playback_frames = media["playback_frames"]
            media_quality_status = str(media["media_quality_status"])
            media_quality_reason = media["media_quality_reason"]
            raw_visual_orientation = str(media["raw_visual_orientation"])
            ui_visual_orientation = str(media["ui_visual_orientation"])
            semantic_visual_orientation = str(media["semantic_visual_orientation"])
            presentation_transform = str(media["presentation_transform"])
            presentation_transform_reason = media["presentation_transform_reason"]
            preview_display_orientation = str(media["preview_display_orientation"])
            fallback_reason = fallback_note or media["playback_fallback_reason"]
            capture_window_policy = _selected_capture_window_policy(capture_attempts)
            capture_window_x, capture_window_y, capture_window_width, capture_window_height = _capture_window_numbers(
                capture_window_policy
            )
            if media_quality_status == "corrupt":
                playback_path = None
                playback_generated = False
                playback_kind = "unavailable"
                playback_is_animated = False
                fallback_reason = media_quality_reason
            if (
                media_quality_status == "unavailable"
                and capture_result.executed
                and capture_result.return_code == 0
                and not playback_frames
            ):
                media_quality_status = "corrupt"
                media_quality_reason = "esmini capture completed, but no native screen_shot_* frames were produced."
                fallback_reason = media_quality_reason
            if playback_kind == "unavailable" and media_quality_status != "corrupt":
                preview_media = _preview_fallback(output_dir, fallback_reason)
                if preview_media is not None:
                    playback_path = preview_media
                    playback_generated = True
                    playback_kind = "preview_static_image"
                    playback_source_path = preview_media
                    playback_frame_count = 1
                    playback_is_animated = False
                    playback_frame_duration_s = None
                    playback_frames = []
                    fallback_reason = (
                        "esmini capture did not produce usable browser media; "
                        f"using 2D preview fallback. {fallback_reason or ''}"
                    ).strip()
            esmini_result = capture_result
        if fallback_reason is not None and playback_kind in {"unavailable", "preview_static_image", "preview_fallback_gif"}:
            esmini_result = run_esmini(
                resolved_xosc_path,
                output_dir,
                working_dir=resolved_working_dir,
                binary=str(resolved_binary),
                timeout_s=timeout_s,
                mode="full" if mode in {"playback", "full"} else "smoke",
                sim_duration_s=sim_duration_s,
            )
            if not command:
                command = esmini_result.command
                stdout = esmini_result.stdout
                stderr = esmini_result.stderr
                return_code = esmini_result.return_code
                executed = esmini_result.executed
            else:
                stdout = "\n".join(part for part in [stdout, "Fallback execution stdout:", esmini_result.stdout] if part)
                stderr = "\n".join(part for part in [stderr, "Fallback execution stderr:", esmini_result.stderr] if part)
                return_code = esmini_result.return_code
                executed = esmini_result.executed
        else:
            (output_dir / "esmini_log.txt").write_text(_format_log(esmini_result), encoding="utf-8")
            (output_dir / "esmini_stdout.txt").write_text(stdout, encoding="utf-8")
            (output_dir / "esmini_stderr.txt").write_text(stderr, encoding="utf-8")
    playback_result = EsminiPlaybackResult(
        esmini_available=resolved_binary is not None,
        command=command,
        working_dir=esmini_result.working_dir,
        mode=mode,
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        executed=executed,
        playback_path=playback_path,
        playback_generated=playback_generated,
        playback_kind=playback_kind,
        playback_source_path=playback_source_path,
        playback_frame_count=playback_frame_count,
        playback_is_animated=playback_is_animated,
        playback_frame_duration_s=playback_frame_duration_s,
        playback_fallback_reason=fallback_reason,
        playback_frames=playback_frames,
        timeout_s=timeout_s,
        sim_duration_s=sim_duration_s if mode in {"playback", "smoke"} else None,
        fallback_reason=fallback_reason,
        capture_mode=capture_mode,
        capture_platform_strategy=capture_platform_strategy,
        media_quality_status=media_quality_status,
        media_quality_reason=media_quality_reason,
        capture_window_x=capture_window_x,
        capture_window_y=capture_window_y,
        capture_window_width=capture_window_width,
        capture_window_height=capture_window_height,
        capture_window_policy=capture_window_policy,
        capture_attempts=capture_attempts,
        semantic_visual_orientation=semantic_visual_orientation,
        raw_visual_orientation=raw_visual_orientation,
        ui_visual_orientation=ui_visual_orientation,
        presentation_transform=presentation_transform,
        presentation_transform_reason=presentation_transform_reason,
        preview_display_orientation=preview_display_orientation,
    )
    (output_dir / "esmini_result.json").write_text(esmini_result.to_json(), encoding="utf-8")
    (output_dir / "esmini_playback_result.json").write_text(playback_result.to_json(), encoding="utf-8")
    (output_dir / "esmini_help.txt").write_text(help_text, encoding="utf-8")
    return playback_result


def get_esmini_help_text(binary: Path | str) -> str:
    try:
        completed = subprocess.run(
            [str(binary), "--help"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return str(exc)
    return "\n".join([completed.stdout, completed.stderr]).strip()


def supports_native_video_export(help_text: str) -> bool:
    return supports_frame_capture(help_text)


def supports_frame_capture(help_text: str) -> bool:
    lowered = help_text.lower()
    return "--capture_screen" in lowered


def _run_esmini_capture(
    binary: Path,
    xosc_path: Path,
    output_dir: Path,
    working_dir: Path,
    timeout_s: float,
    sim_duration_s: float,
    capture_window_policy: str | None = None,
) -> EsminiResult:
    capture_cwd = output_dir.resolve()
    command_xosc_path = os.path.relpath(xosc_path, capture_cwd)
    command = _build_capture_command(binary, command_xosc_path, working_dir, capture_window_policy=capture_window_policy)
    process_timeout_s = min(timeout_s, max(0.5, sim_duration_s))
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=process_timeout_s,
            cwd=capture_cwd,
        )
        return EsminiResult(
            esmini_available=True,
            command=command,
            working_dir=_display_path(capture_cwd),
            return_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            executed=completed.returncode == 0,
            error_message=None if completed.returncode == 0 else f"esmini exited with code {completed.returncode}.",
            playback_path=None,
            timeout_s=timeout_s,
            process_timeout_s=process_timeout_s,
            timed_out=False,
            mode="playback_capture",
            sim_duration_s=sim_duration_s,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _decode_timeout_output(exc.stdout)
        stderr = _decode_timeout_output(exc.stderr) or f"esmini capture stopped after {process_timeout_s:g} seconds."
        return EsminiResult(
            esmini_available=True,
            command=command,
            working_dir=_display_path(capture_cwd),
            return_code=None,
            stdout=stdout,
            stderr=stderr,
            executed=True,
            error_message=stderr,
            playback_path=None,
            timeout_s=timeout_s,
            process_timeout_s=process_timeout_s,
            timed_out=True,
            mode="playback_capture",
            sim_duration_s=sim_duration_s,
            timeout_classification=classify_esmini_timeout(stdout=stdout, stderr=stderr, mode="smoke"),
        )
    except OSError as exc:
        return EsminiResult(
            esmini_available=True,
            command=command,
            working_dir=_display_path(capture_cwd),
            return_code=None,
            stdout="",
            stderr=str(exc),
            executed=False,
            error_message=str(exc),
            playback_path=None,
            timeout_s=timeout_s,
            process_timeout_s=process_timeout_s,
            timed_out=False,
            mode="playback_capture",
            sim_duration_s=sim_duration_s,
        )


def _build_capture_command(
    binary: Path | str,
    command_xosc_path: str,
    working_dir: Path,
    platform_name: str | None = None,
    capture_window_policy: str | None = None,
) -> list[str]:
    capture_mode = _capture_mode_for_platform(platform_name)
    window_policy = capture_window_policy or _capture_window_policy_for_platform(platform_name)
    command = [
        str(binary),
        "--osc",
        command_xosc_path,
        "--path",
        str(working_dir),
    ]
    if capture_mode == "headless":
        command.append("--headless")
    command.extend([
        "--capture_screen",
        "--camera_mode",
        "top",
        "--fixed_timestep",
        "0.05",
        "--window",
        *_capture_window_for_platform(platform_name, window_policy),
        "--log_level",
        "info",
        "--logfile_path",
        "esmini_capture_log.txt",
    ])
    return command


def _capture_mode_for_platform(platform_name: str | None = None) -> str:
    return "windowed" if _is_macos(platform_name) else "headless"


def _capture_platform_strategy(platform_name: str | None = None) -> str:
    return "macos_windowed_capture" if _is_macos(platform_name) else "default_headless_capture"


def _capture_window_policy_for_platform(platform_name: str | None = None) -> str:
    return "macos_offscreen_preferred" if _is_macos(platform_name) else "default_platform_window"


def _capture_attempt_policies(platform_name: str | None = None) -> list[str]:
    if _is_macos(platform_name):
        return ["macos_offscreen_preferred", "macos_visible_fallback"]
    return ["default_platform_window"]


def _capture_window_for_platform(
    platform_name: str | None = None,
    capture_window_policy: str | None = None,
) -> list[str]:
    policy = capture_window_policy or _capture_window_policy_for_platform(platform_name)
    return [str(value) for value in _capture_window_values(policy)]


def _capture_window_values(capture_window_policy: str) -> tuple[str, str, str, str]:
    if capture_window_policy == "macos_offscreen_preferred":
        return MACOS_PREFERRED_CAPTURE_WINDOW
    if capture_window_policy == "macos_visible_fallback":
        return MACOS_FALLBACK_CAPTURE_WINDOW
    return DEFAULT_PLATFORM_CAPTURE_WINDOW


def _capture_window_numbers(capture_window_policy: str) -> tuple[int | None, int | None, int | None, int | None]:
    if capture_window_policy == "unavailable":
        return None, None, None, None
    return tuple(int(value) for value in _capture_window_values(capture_window_policy))


def _selected_capture_window_policy(capture_attempts: list[dict[str, object]]) -> str:
    if not capture_attempts:
        return "unavailable"
    return str(capture_attempts[-1].get("capture_window_policy") or "unavailable")


def _capture_attempt_metadata(
    capture_window_policy: str,
    result: EsminiResult,
    media: dict[str, object],
) -> dict[str, object]:
    x, y, width, height = _capture_window_numbers(capture_window_policy)
    return {
        "capture_window_policy": capture_window_policy,
        "capture_window_x": x,
        "capture_window_y": y,
        "capture_window_width": width,
        "capture_window_height": height,
        "command": result.command,
        "return_code": result.return_code,
        "executed": result.executed,
        "timed_out": result.timed_out,
        "playback_kind": media["playback_kind"],
        "playback_frame_count": media["playback_frame_count"],
        "media_quality_status": media["media_quality_status"],
        "media_quality_reason": media["media_quality_reason"],
    }


def _capture_media_is_usable(media: dict[str, object]) -> bool:
    return (
        bool(media["playback_generated"])
        and str(media["media_quality_status"]) in {"valid", "suspicious"}
        and int(media["playback_frame_count"]) > 0
    )


def _should_retry_capture(capture_window_policy: str, result: EsminiResult, media: dict[str, object]) -> bool:
    if capture_window_policy != "macos_offscreen_preferred":
        return False
    if _capture_media_is_usable(media):
        return False
    return not _scenario_failed_before_rendering(result)


def _scenario_failed_before_rendering(result: EsminiResult) -> bool:
    combined_output = "\n".join([result.stdout, result.stderr])
    if "Window created" in combined_output or "Activate continuous screen capture" in combined_output:
        return False
    return result.return_code not in (0, None) and "Loaded" not in combined_output


def _clear_capture_artifacts(output_dir: Path) -> None:
    for frame in output_dir.glob("screen_shot_*"):
        if frame.is_file():
            frame.unlink()
    for dirname in ("frames", "frames_aligned"):
        frames_dir = output_dir / dirname
        if frames_dir.exists():
            shutil.rmtree(frames_dir)
    for media_path in (
        output_dir / "playback_esmini.gif",
        output_dir / "playback_esmini_raw.gif",
        output_dir / "playback_esmini_aligned.gif",
        output_dir / "playback.gif",
        output_dir / "playback.mp4",
    ):
        if media_path.exists():
            media_path.unlink()


def _is_macos(platform_name: str | None = None) -> bool:
    return (platform_name or platform.system()).lower() == "darwin"


def _collect_capture_frames(capture_dir: Path, frames_dir: Path) -> list[Path]:
    media = _build_playback_media(capture_dir, DEFAULT_FRAME_DURATION_S, frames_dir=frames_dir)
    return [
        Path(frame["normalized_frame_path"])
        for frame in media["playback_frames"]
        if frame.get("normalized_frame_path")
    ]


def _build_playback_media(
    output_dir: Path,
    frame_duration_s: float,
    frames_dir: Path | None = None,
) -> dict[str, object]:
    frames_dir = frames_dir or output_dir / "frames"
    presentation_frames_dir = output_dir / "frames_aligned"
    native_frames = _discover_native_capture_frames(output_dir)
    if not native_frames:
        return _media_result(
            playback_generated=False,
            playback_kind="unavailable",
            playback_source_path=None,
            playback_frame_count=0,
            playback_is_animated=False,
            playback_frame_duration_s=None,
            playback_path=None,
            playback_fallback_reason="esmini --capture_screen did not produce native screen_shot_* frame images.",
            playback_frames=[],
            media_quality_status="unavailable",
            media_quality_reason="No native esmini screen_shot_* frames were found.",
            raw_visual_orientation="unknown",
            ui_visual_orientation="unknown",
            presentation_transform="none",
            presentation_transform_reason=None,
        )

    normalized_frames, provenance, normalize_reason = _normalize_capture_frames(native_frames, frames_dir)
    if normalized_frames:
        quality_status, quality_reason = _classify_media_quality(normalized_frames)
        if quality_status == "corrupt":
            return _media_result(
                playback_generated=False,
                playback_kind="unavailable",
                playback_source_path=str(frames_dir),
                playback_frame_count=len(normalized_frames),
                playback_is_animated=False,
                playback_frame_duration_s=frame_duration_s if len(normalized_frames) > 1 else None,
                playback_path=None,
                playback_fallback_reason=quality_reason,
                playback_frames=[item.to_dict() for item in provenance],
                media_quality_status=quality_status,
                media_quality_reason=quality_reason,
                raw_visual_orientation=RAW_VISUAL_ORIENTATION,
                ui_visual_orientation=RAW_VISUAL_ORIENTATION,
                presentation_transform="none",
                presentation_transform_reason=quality_reason,
            )
        presentation_frames, presentation_reason = _build_presentation_frames(
            normalized_frames,
            presentation_frames_dir,
            PRESENTATION_TRANSFORM,
        )
        if PRESENTATION_TRANSFORM != "none" and presentation_frames:
            provenance = _attach_presentation_frames(provenance, presentation_frames)
        else:
            presentation_frames = normalized_frames
        frame_count = len(normalized_frames)
        if frame_count == 1:
            return _media_result(
                playback_generated=True,
                playback_kind="esmini_single_frame",
                playback_source_path=str(native_frames[0].source_path),
                playback_frame_count=1,
                playback_is_animated=False,
                playback_frame_duration_s=None,
                playback_path=str(normalized_frames[0]),
                playback_fallback_reason=presentation_reason,
                playback_frames=[item.to_dict() for item in provenance],
                media_quality_status=quality_status,
                media_quality_reason=quality_reason,
                raw_visual_orientation=RAW_VISUAL_ORIENTATION,
                ui_visual_orientation=_orientation_after_presentation_transform(PRESENTATION_TRANSFORM)
                if presentation_reason is None
                else RAW_VISUAL_ORIENTATION,
                presentation_transform=PRESENTATION_TRANSFORM if presentation_reason is None else "none",
                presentation_transform_reason=PRESENTATION_TRANSFORM_REASON if presentation_reason is None else presentation_reason,
            )
        raw_gif_path = output_dir / "playback_esmini_raw.gif"
        raw_gif_reason = _encode_esmini_gif(normalized_frames, raw_gif_path, frame_duration_s)
        gif_path = raw_gif_path if PRESENTATION_TRANSFORM == "none" else output_dir / "playback_esmini_aligned.gif"
        gif_reason = raw_gif_reason if PRESENTATION_TRANSFORM == "none" else (
            _encode_esmini_gif(presentation_frames, gif_path, frame_duration_s)
            if presentation_reason is None
            else presentation_reason
        )
        gif_frame_count = _gif_frame_count(gif_path) if gif_reason is None else 0
        if gif_reason is None and gif_path.exists() and gif_path.stat().st_size > 0 and gif_frame_count > 1:
            return _media_result(
                playback_generated=True,
                playback_kind="esmini_gif",
                playback_source_path=str(frames_dir),
                playback_frame_count=frame_count,
                playback_is_animated=True,
                playback_frame_duration_s=frame_duration_s,
                playback_path=str(gif_path),
                playback_fallback_reason=raw_gif_reason,
                playback_frames=[item.to_dict() for item in provenance],
                media_quality_status=quality_status,
                media_quality_reason=quality_reason,
                raw_visual_orientation=RAW_VISUAL_ORIENTATION,
                ui_visual_orientation=_orientation_after_presentation_transform(PRESENTATION_TRANSFORM),
                presentation_transform=PRESENTATION_TRANSFORM,
                presentation_transform_reason=PRESENTATION_TRANSFORM_REASON,
            )
        if gif_path.exists():
            gif_path.unlink()
        return _media_result(
            playback_generated=True,
            playback_kind="esmini_frame_sequence",
            playback_source_path=str(frames_dir),
            playback_frame_count=frame_count,
            playback_is_animated=False,
            playback_frame_duration_s=frame_duration_s,
            playback_path=None,
            playback_fallback_reason=gif_reason
            or "esmini frames were collected, but GIF encoding did not produce animated output.",
            playback_frames=[item.to_dict() for item in provenance],
            media_quality_status=quality_status,
            media_quality_reason=quality_reason,
            raw_visual_orientation=RAW_VISUAL_ORIENTATION,
            ui_visual_orientation=_orientation_after_presentation_transform(PRESENTATION_TRANSFORM)
            if presentation_reason is None
            else RAW_VISUAL_ORIENTATION,
            presentation_transform=PRESENTATION_TRANSFORM if presentation_reason is None else "none",
            presentation_transform_reason=PRESENTATION_TRANSFORM_REASON if presentation_reason is None else presentation_reason,
        )

    return _media_result(
        playback_generated=True,
        playback_kind="esmini_frame_sequence" if len(native_frames) > 1 else "esmini_single_frame",
        playback_source_path=str(output_dir),
        playback_frame_count=len(native_frames),
        playback_is_animated=False,
        playback_frame_duration_s=frame_duration_s if len(native_frames) > 1 else None,
        playback_path=None,
        playback_fallback_reason=normalize_reason or "esmini native frames exist, but browser-friendly conversion was unavailable.",
        playback_frames=[
            FrameProvenance(
                original_source_path=str(frame.source_path),
                normalized_frame_path=None,
                source_extension=frame.source_extension,
                frame_index=frame.frame_index,
            ).to_dict()
            for frame in native_frames
        ],
        media_quality_status="corrupt",
        media_quality_reason=normalize_reason or "Native esmini frames exist, but normalized PNG quality could not be verified.",
        raw_visual_orientation="unknown",
        ui_visual_orientation="unknown",
        presentation_transform="none",
        presentation_transform_reason=normalize_reason,
    )


def _media_result(
    *,
    playback_generated: bool,
    playback_kind: str,
    playback_source_path: str | None,
    playback_frame_count: int,
    playback_is_animated: bool,
    playback_frame_duration_s: float | None,
    playback_path: str | None,
    playback_fallback_reason: str | None,
    playback_frames: list[dict[str, object]],
    media_quality_status: str,
    media_quality_reason: str | None,
    raw_visual_orientation: str,
    ui_visual_orientation: str,
    presentation_transform: str,
    presentation_transform_reason: str | None,
    semantic_visual_orientation: str = SEMANTIC_VISUAL_ORIENTATION,
) -> dict[str, object]:
    if playback_kind not in PLAYBACK_KINDS:
        raise ValueError(f"Unsupported playback kind: {playback_kind}")
    return {
        "playback_generated": playback_generated,
        "playback_kind": playback_kind,
        "playback_source_path": playback_source_path,
        "playback_frame_count": playback_frame_count,
        "playback_is_animated": playback_is_animated,
        "playback_frame_duration_s": playback_frame_duration_s,
        "playback_path": playback_path,
        "playback_fallback_reason": playback_fallback_reason,
        "playback_frames": playback_frames,
        "media_quality_status": media_quality_status,
        "media_quality_reason": media_quality_reason,
        "semantic_visual_orientation": semantic_visual_orientation,
        "raw_visual_orientation": raw_visual_orientation,
        "ui_visual_orientation": ui_visual_orientation,
        "presentation_transform": presentation_transform,
        "presentation_transform_reason": presentation_transform_reason,
        "preview_display_orientation": PREVIEW_DISPLAY_ORIENTATION,
    }


def _classify_media_quality(frames: list[Path]) -> tuple[str, str | None]:
    representatives = _representative_frame_paths(frames)
    if not representatives:
        return "unavailable", "No normalized frames were available for media quality analysis."
    metrics = []
    for frame in representatives:
        metric = _frame_quality_metrics(frame)
        metrics.append(metric)
        if not metric["decode_success"]:
            return "corrupt", f"Representative frame could not be decoded: {frame}"
        if metric["width"] < MEDIA_QUALITY_MIN_DIMENSION_PX or metric["height"] < MEDIA_QUALITY_MIN_DIMENSION_PX:
            return "corrupt", f"Representative frame has invalid dimensions: {frame}"
    if all(metric["near_black_fraction"] >= MEDIA_QUALITY_NEAR_BLACK_FRACTION_THRESHOLD for metric in metrics):
        return (
            "corrupt",
            "Representative frames are overwhelmingly near-black; likely invalid capture framebuffer.",
        )
    hashes = {metric["sha256"] for metric in metrics}
    if len(representatives) > 1 and len(hashes) == 1:
        return "suspicious", "Representative frame hashes are identical."
    return "valid", None


def _representative_frame_paths(frames: list[Path]) -> list[Path]:
    if not frames:
        return []
    indexes = sorted({0, len(frames) // 2, len(frames) - 1})
    return [frames[index] for index in indexes]


def _frame_quality_metrics(path: Path) -> dict[str, object]:
    try:
        from PIL import Image
    except ImportError:
        return {"decode_success": False, "width": 0, "height": 0, "near_black_fraction": 1.0, "sha256": ""}
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            pixel_bytes = rgb.tobytes()
    except OSError:
        return {"decode_success": False, "width": 0, "height": 0, "near_black_fraction": 1.0, "sha256": ""}
    total = len(pixel_bytes) // 3
    near_black = sum(
        1
        for red, green, blue in zip(pixel_bytes[0::3], pixel_bytes[1::3], pixel_bytes[2::3])
        if (0.2126 * red + 0.7152 * green + 0.0722 * blue) <= 5.0
    )
    return {
        "decode_success": True,
        "width": rgb.width,
        "height": rgb.height,
        "near_black_fraction": near_black / total if total else 1.0,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _discover_native_capture_frames(capture_dir: Path) -> list[CaptureFrame]:
    frames: list[CaptureFrame] = []
    if not capture_dir.exists():
        return frames
    for path in capture_dir.iterdir():
        if not path.is_file():
            continue
        match = SCREENSHOT_RE.match(path.name)
        if match is None:
            continue
        suffix = path.suffix.lower()
        if suffix not in CAPTURE_IMAGE_SUFFIXES:
            continue
        frames.append(CaptureFrame(path, int(match.group(1)), suffix))
    return sorted(frames, key=lambda frame: (frame.frame_index, frame.source_path.name))


def _normalize_capture_frames(native_frames: list[CaptureFrame], frames_dir: Path) -> tuple[list[Path], list[FrameProvenance], str | None]:
    try:
        from PIL import Image
    except ImportError:
        return [], [], "Pillow was not available, so native esmini frames could not be converted to PNG."

    frames_dir.mkdir(parents=True, exist_ok=True)
    normalized: list[Path] = []
    provenance: list[FrameProvenance] = []
    for ordinal, frame in enumerate(native_frames, start=1):
        target = frames_dir / f"frame_{ordinal:06d}.png"
        try:
            with Image.open(frame.source_path) as image:
                image.save(target, format="PNG")
        except OSError as exc:
            return [], [], f"Native esmini frame conversion failed: {exc}"
        normalized.append(target)
        provenance.append(
            FrameProvenance(
                original_source_path=str(frame.source_path),
                normalized_frame_path=str(target),
                source_extension=frame.source_extension,
                frame_index=frame.frame_index,
            )
        )
    return normalized, provenance, None


def _build_presentation_frames(
    normalized_frames: list[Path],
    presentation_frames_dir: Path,
    presentation_transform: str,
) -> tuple[list[Path], str | None]:
    if presentation_transform == "none":
        return normalized_frames, None
    if presentation_transform not in {"horizontal_mirror", "vertical_mirror", "rotate_180"}:
        return [], f"Unsupported presentation transform: {presentation_transform}"
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return [], "Pillow was not available, so aligned presentation frames could not be generated."

    presentation_frames_dir.mkdir(parents=True, exist_ok=True)
    presentation_frames: list[Path] = []
    for frame in normalized_frames:
        target = presentation_frames_dir / frame.name
        try:
            with Image.open(frame) as image:
                _apply_presentation_transform(image, presentation_transform, ImageOps).save(target, format="PNG")
        except OSError as exc:
            return [], f"Aligned presentation frame generation failed: {exc}"
        presentation_frames.append(target)
    return presentation_frames, None


def _apply_presentation_transform(image, presentation_transform: str, image_ops):
    if presentation_transform == "horizontal_mirror":
        return image_ops.mirror(image)
    if presentation_transform == "vertical_mirror":
        return image_ops.flip(image)
    if presentation_transform == "rotate_180":
        return image.rotate(180)
    return image


def _orientation_after_presentation_transform(presentation_transform: str) -> str:
    orientations = {
        "none": RAW_VISUAL_ORIENTATION,
        "horizontal_mirror": "world_x_screen_right_world_y_screen_down",
        "vertical_mirror": "world_x_screen_left_world_y_screen_up",
        "rotate_180": SEMANTIC_VISUAL_ORIENTATION,
    }
    return orientations.get(presentation_transform, "unknown")


def _attach_presentation_frames(
    provenance: list[FrameProvenance],
    presentation_frames: list[Path],
) -> list[FrameProvenance]:
    return [
        FrameProvenance(
            original_source_path=item.original_source_path,
            normalized_frame_path=item.normalized_frame_path,
            source_extension=item.source_extension,
            frame_index=item.frame_index,
            presentation_frame_path=str(presentation_frame),
        )
        for item, presentation_frame in zip(provenance, presentation_frames)
    ]


def _encode_esmini_gif(frames: list[Path], gif_path: Path, frame_duration_s: float) -> str | None:
    if len(frames) < 2:
        return "At least two esmini frames are required for animated GIF encoding."
    try:
        from PIL import Image
    except ImportError:
        return "Pillow was not available, so GIF encoding was skipped."
    try:
        images = [Image.open(frame).convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=max(1, int(frame_duration_s * 1000)),
            loop=0,
        )
    except OSError as exc:
        return f"GIF encoding failed: {exc}"
    finally:
        for image in locals().get("images", []):
            image.close()
    return None


def _gif_frame_count(gif_path: Path) -> int:
    if not gif_path.exists():
        return 0
    try:
        from PIL import Image, ImageSequence
    except ImportError:
        return 0
    try:
        with Image.open(gif_path) as image:
            return sum(1 for _ in ImageSequence.Iterator(image))
    except OSError:
        return 0


def _preview_fallback(output_dir: Path, reason: str | None) -> str | None:
    preview_path = output_dir / "preview_2d.png"
    if not preview_path.exists():
        return None
    return str(preview_path)


def _encode_playback(frames: list[Path], output_dir: Path) -> tuple[Path | None, str | None]:
    if not frames:
        return None, "esmini --capture_screen did not produce frame images. Execution check completed instead."
    mp4_path = output_dir / "playback.mp4"
    ffmpeg_reason = _encode_mp4_with_ffmpeg(frames, mp4_path)
    if ffmpeg_reason is None and mp4_path.exists() and mp4_path.stat().st_size > 0:
        return mp4_path, None
    gif_path = output_dir / "playback.gif"
    gif_reason = _encode_gif_with_pillow(frames, gif_path)
    if gif_reason is None and gif_path.exists() and gif_path.stat().st_size > 0:
        return gif_path, None
    return None, "; ".join(reason for reason in [ffmpeg_reason, gif_reason] if reason)


def _encode_mp4_with_ffmpeg(frames: list[Path], mp4_path: Path) -> str | None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return "ffmpeg was not found, so MP4 encoding was skipped."
    suffix = frames[0].suffix.lower()
    pattern = frames[0].parent / f"frame_%06d{suffix}"
    command = [
        ffmpeg,
        "-y",
        "-framerate",
        "10",
        "-i",
        str(pattern),
        "-pix_fmt",
        "yuv420p",
        str(mp4_path),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return "ffmpeg failed: " + (completed.stderr or completed.stdout or f"exit code {completed.returncode}")
    return None


def _encode_gif_with_pillow(frames: list[Path], gif_path: Path) -> str | None:
    try:
        from PIL import Image
    except ImportError:
        return "Pillow was not available, so GIF encoding was skipped."
    try:
        images = [Image.open(frame).convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
        if not images:
            return "No frames were available for GIF encoding."
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=100,
            loop=0,
        )
    except OSError as exc:
        return f"GIF encoding failed: {exc}"
    finally:
        for image in locals().get("images", []):
            image.close()
    return None


def _format_log(result: EsminiResult) -> str:
    return "\n".join([
        f"command: {' '.join(result.command)}",
        f"working_dir: {result.working_dir}",
        f"available: {result.esmini_available}",
        f"required: {result.required}",
        f"mode: {result.mode}",
        f"timeout_s: {result.timeout_s}",
        f"process_timeout_s: {result.process_timeout_s}",
        f"sim_duration_s: {result.sim_duration_s}",
        f"timed_out: {result.timed_out}",
        f"timeout_classification: {result.timeout_classification or ''}",
        f"return_code: {result.return_code}",
        f"executed: {result.executed}",
        f"error_message: {result.error_message or ''}",
        "",
        "stdout:",
        result.stdout,
        "",
        "stderr:",
        result.stderr,
        "",
        "install_hint:",
        result.install_hint or "",
        "",
    ])


def _build_command(command_binary: str, command_xosc_path: str, mode: str) -> list[str]:
    command = [command_binary, "--osc", command_xosc_path, "--headless", "--disable_log"]
    if mode == "full":
        command.append("--quit_at_end")
    else:
        command.extend(["--fixed_timestep", "0.01", "--log_level", "info"])
    return command


def classify_esmini_timeout(stdout: str, stderr: str, mode: str) -> str:
    output = " ".join([stdout, stderr]).lower()
    if not output.strip():
        return "timeout_no_output"
    if any(token in output for token in ("viewer", "window", "graphics", "display", "opengl", "osg", "screen")):
        return "timeout_possible_viewer_block"
    if any(
        token in output
        for token in ("scenarioengine", "scenario engine", "open scenario", "openscenario", "opendrive", "roadmanager", "loaded", "start")
    ):
        return "timeout_after_start" if mode == "smoke" else "timeout_possible_long_scenario"
    return "timeout_possible_long_scenario"


def resolve_esmini_binary(binary: str | None = None, search_root: Path | None = None) -> Path | None:
    configured = binary or os.environ.get("ESMINI_BIN")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists():
            return configured_path.resolve()
        resolved = shutil.which(configured)
        if resolved is not None:
            return Path(resolved).resolve()
        return None

    resolved = shutil.which("esmini")
    if resolved is not None:
        return Path(resolved).resolve()

    root = search_root or _project_root()
    for candidate_root in [
        root / "third_party" / "esmini",
        root / "tools" / "esmini",
    ]:
        candidate = _find_esmini_executable(candidate_root)
        if candidate is not None:
            return candidate
    return None


def _find_esmini_executable(search_dir: Path) -> Path | None:
    if not search_dir.exists():
        return None
    names = {"esmini", "esmini.exe"}
    for path in sorted(search_dir.rglob("*")):
        if path.name in names and path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _install_hint() -> str:
    return (
        "Install a prebuilt esmini release with "
        "`python -m scenariocraft.tooling.install_esmini --package bin`, set ESMINI_BIN, "
        "or add esmini to PATH."
    )


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
