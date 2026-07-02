from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import streamlit as st

from scenariocraft.core.build import BuildResult
from scenariocraft.external_tools import EsminiPlaybackResult


def render_workspace_runtime_media(output_dir: Path, playback_result: object) -> None:
    if not isinstance(playback_result, EsminiPlaybackResult):
        st.info("Playback Esmini has not been generated.")
        return
    playback_path = Path(playback_result.playback_path) if playback_result.playback_path else None
    if playback_result.media_quality_status == "corrupt":
        st.warning("Playback Esmini unavailable.")
        if playback_result.media_quality_reason:
            st.caption(playback_result.media_quality_reason)
    elif playback_result.playback_kind == "esmini_gif" and _playback_generated_media_exists(playback_result, playback_path):
        st.image(str(playback_path), width="stretch")
    elif _should_render_frame_sequence(playback_result):
        frames = _verified_esmini_frame_paths(playback_result, output_dir)
        if frames:
            selected = st.slider("Frame", 1, len(frames), 1, label_visibility="collapsed")
            st.image(str(frames[selected - 1]), width="stretch")
    elif playback_result.playback_kind == "esmini_single_frame":
        frames = _verified_esmini_frame_paths(playback_result, output_dir)
        if frames:
            st.image(str(frames[0]), width="stretch")
    elif playback_result.playback_kind in {"preview_fallback_gif", "preview_static_image"}:
        st.warning("Playback Esmini unavailable.")
        st.info("2D Preview Fallback")
        if playback_result.playback_fallback_reason:
            st.caption(playback_result.playback_fallback_reason)
    else:
        st.warning("Playback Esmini unavailable.")
        if playback_result.playback_fallback_reason:
            st.caption(playback_result.playback_fallback_reason)


def render_playback_panel(
    output_dir: Path,
    *,
    build_result: object,
    playback_result: object,
    run_playback: Callable[[Path], None],
) -> None:
    if not isinstance(build_result, BuildResult):
        st.info("Generate & Play to build OpenSCENARIO and run esmini playback/check.")
        return
    if isinstance(playback_result, EsminiPlaybackResult):
        playback_path = Path(playback_result.playback_path) if playback_result.playback_path else None
        st.caption(_playback_media_label(playback_result.playback_kind))
        if playback_result.media_quality_status == "corrupt":
            _render_corrupt_capture(playback_result)
        elif _should_render_frame_sequence(playback_result):
            _render_esmini_frame_sequence(output_dir, playback_result)
        elif playback_result.playback_kind == "esmini_single_frame":
            _render_esmini_single_frame(output_dir, playback_result)
        elif playback_result.playback_kind == "esmini_gif" and _playback_generated_media_exists(playback_result, playback_path):
            st.success("Playback Esmini")
            if playback_path.suffix.lower() in {".gif", ".png", ".jpg", ".jpeg"}:
                st.image(str(playback_path), width="stretch", caption="Playback Esmini · esmini Rendered GIF")
            else:
                st.video(str(playback_path))
        elif playback_result.playback_kind in {"preview_fallback_gif", "preview_static_image"}:
            _render_preview_fallback_media(playback_result, playback_path)
        elif playback_result.executed:
            st.warning("Simulation may have completed, but valid esmini visual media is unavailable.")
        elif playback_result.esmini_available:
            st.warning("Simulation may have completed, but valid esmini visual media is unavailable.")
        else:
            st.warning("esmini was not found. Playback/check was skipped.")
        if playback_result.playback_fallback_reason:
            st.caption(playback_result.playback_fallback_reason)
        _render_playback_details(playback_result)
    else:
        st.info("esmini playback/check has not run for this generated scenario.")
    controls = st.columns(2)
    with controls[0]:
        if st.button("Run esmini playback", width="stretch"):
            run_playback(output_dir)
    with controls[1]:
        st.caption(f"Output: `{output_dir}`")


def _playback_generated_media_exists(playback_result: EsminiPlaybackResult, playback_path: Path | None) -> bool:
    return playback_result.playback_generated and playback_path is not None and playback_path.exists()


def _render_corrupt_capture(playback_result: EsminiPlaybackResult) -> None:
    if playback_result.executed:
        st.success("esmini Runtime: passed")
    st.warning("Simulation may have completed, but valid esmini visual media is unavailable.")
    if playback_result.media_quality_reason:
        st.caption(f"Reason: {playback_result.media_quality_reason}")
    st.caption("2D Preview remains available separately.")


def _render_esmini_frame_sequence(output_dir: Path, playback_result: EsminiPlaybackResult) -> None:
    frames = _verified_esmini_frame_paths(playback_result, output_dir)
    if not frames:
        st.warning("esmini frame sequence metadata was present, but no normalized PNG frames were available.")
        return
    state = _frame_sequence_state(playback_result, output_dir, selected_index=0)
    frame_count = int(state["frame_count"])
    st.success("Playback Esmini")
    metrics = st.columns(4)
    metrics[0].metric("Frames", str(frame_count))
    metrics[1].metric("Frame duration", _format_optional_seconds(state["frame_duration_s"]))
    metrics[2].metric("Estimated FPS", _format_optional_number(state["estimated_fps"]))
    metrics[3].metric("Kind", _playback_media_label(playback_result.playback_kind))
    selected_index = st.slider(
        "Frame",
        min_value=1,
        max_value=frame_count,
        value=1,
        step=1,
        help="Select a normalized PNG frame derived from native esmini capture.",
    )
    state = _frame_sequence_state(playback_result, output_dir, selected_index=selected_index - 1)
    selected_frame = Path(str(state["selected_frame_path"]))
    st.image(str(selected_frame), width="stretch", caption="Playback Esmini · esmini Frame Sequence")
    st.caption(f"Source provenance: `{state['source_provenance']}`")
    st.caption(f"Selected frame path: `{state['selected_frame_path']}`")
    st.caption(f"First frame path: `{state['first_frame_path']}`")
    st.caption(f"Last frame path: `{state['last_frame_path']}`")
    _render_preview_vs_esmini_comparison(output_dir, selected_frame)


def _render_esmini_single_frame(output_dir: Path, playback_result: EsminiPlaybackResult) -> None:
    frames = _verified_esmini_frame_paths(playback_result, output_dir)
    frame_path = frames[0] if frames else _resolve_media_path(playback_result.playback_path, output_dir)
    if frame_path is not None and frame_path.exists():
        st.success("Playback Esmini")
        st.image(str(frame_path), width="stretch", caption="Playback Esmini · esmini Screenshot")
        st.caption(f"Source: `{playback_result.playback_source_path}`")
        st.caption("Single esmini screenshot; not animation.")
        _render_preview_vs_esmini_comparison(output_dir, frame_path)
    else:
        st.warning("esmini screenshot metadata was present, but no normalized PNG frame was available.")


def _render_preview_fallback_media(playback_result: EsminiPlaybackResult, playback_path: Path | None) -> None:
    if _playback_generated_media_exists(playback_result, playback_path):
        st.info(_playback_media_label(playback_result.playback_kind))
        st.image(str(playback_path), width="stretch")
    else:
        st.warning("2D preview fallback media is unavailable.")


def _render_preview_vs_esmini_comparison(output_dir: Path, esmini_frame_path: Path) -> None:
    preview_path = output_dir / "preview_2d.png"
    if not preview_path.exists():
        return
    with st.expander("2D Preview vs esmini Rendered Frame", expanded=False):
        cols = st.columns(2)
        with cols[0]:
            st.caption("2D Preview")
            st.image(str(preview_path), width="stretch")
        with cols[1]:
            st.caption("Real esmini-rendered frame")
            st.image(str(esmini_frame_path), width="stretch")


def _render_playback_details(playback_result: EsminiPlaybackResult) -> None:
    with st.expander("Advanced playback details", expanded=False):
        st.caption(f"Frame count: `{playback_result.playback_frame_count}`")
        st.caption(f"Capture policy: `{playback_result.capture_window_policy}`")
        st.caption(f"Media quality: `{playback_result.media_quality_status}`")
        st.caption(f"Semantic orientation: `{playback_result.semantic_visual_orientation}`")
        st.caption(f"Raw orientation: `{playback_result.raw_visual_orientation}`")
        st.caption(f"UI orientation: `{playback_result.ui_visual_orientation}`")
        st.caption(f"Presentation transform: `{playback_result.presentation_transform}`")
        st.caption(
            "2D preview orientation is aligned to the raw esmini top-camera view; "
            "simulation coordinates and runtime media are not transformed."
        )
        st.json(playback_result.to_dict())


def _should_render_frame_sequence(playback_result: EsminiPlaybackResult) -> bool:
    if playback_result.media_quality_status == "corrupt":
        return False
    if playback_result.playback_kind == "esmini_frame_sequence":
        return playback_result.media_quality_status in {"valid", "suspicious"}
    if playback_result.playback_kind in {"esmini_gif", "esmini_single_frame", "preview_fallback_gif", "preview_static_image"}:
        return False
    return bool(_verified_esmini_frame_entries(playback_result))


def _frame_sequence_state(
    playback_result: EsminiPlaybackResult,
    output_dir: Path,
    selected_index: int,
) -> dict[str, object]:
    frames = _verified_esmini_frame_paths(playback_result, output_dir)
    if not frames:
        return {
            "frame_count": 0,
            "frame_duration_s": playback_result.playback_frame_duration_s,
            "estimated_fps": None,
            "source_provenance": playback_result.playback_source_path,
            "first_frame_path": None,
            "last_frame_path": None,
            "selected_frame_path": None,
        }
    bounded_index = min(max(selected_index, 0), len(frames) - 1)
    frame_duration = playback_result.playback_frame_duration_s
    estimated_fps = (1.0 / frame_duration) if frame_duration and frame_duration > 0 else None
    return {
        "frame_count": playback_result.playback_frame_count or len(frames),
        "frame_duration_s": frame_duration,
        "estimated_fps": estimated_fps,
        "source_provenance": playback_result.playback_source_path,
        "first_frame_path": str(frames[0]),
        "last_frame_path": str(frames[-1]),
        "selected_frame_path": str(frames[bounded_index]),
    }


def _verified_esmini_frame_paths(playback_result: EsminiPlaybackResult, output_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for frame in _verified_esmini_frame_entries(playback_result):
        path = _resolve_media_path(frame.get("normalized_frame_path"), output_dir)
        if path is not None and path.exists():
            paths.append(path)
    return paths


def _verified_esmini_frame_entries(playback_result: EsminiPlaybackResult) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for frame in playback_result.playback_frames:
        normalized_path = frame.get("normalized_frame_path")
        original_path = frame.get("original_source_path")
        if not normalized_path or not original_path:
            continue
        if Path(str(original_path)).name == "preview_2d.png":
            continue
        entries.append(frame)
    return entries


def _resolve_media_path(raw_path: object, output_dir: Path) -> Path | None:
    if not raw_path:
        return None
    path = Path(str(raw_path))
    if path.is_absolute() or path.exists():
        return path
    return output_dir / path


def _format_optional_seconds(value: object) -> str:
    if isinstance(value, (float, int)):
        return f"{value:.3f}s"
    return "n/a"


def _format_optional_number(value: object) -> str:
    if isinstance(value, (float, int)):
        return f"{value:.1f}"
    return "n/a"


def _playback_media_label(playback_kind: str) -> str:
    labels = {
        "esmini_gif": "esmini Rendered GIF",
        "esmini_frame_sequence": "esmini Frame Sequence",
        "esmini_single_frame": "esmini Screenshot",
        "preview_fallback_gif": "2D Preview Fallback",
        "preview_static_image": "2D Preview",
        "unavailable": "Playback Unavailable",
    }
    return labels.get(playback_kind, "Playback Unavailable")
