from __future__ import annotations

from pathlib import Path
import json
from collections.abc import Sequence

from scenariocraft.schemas import ProbeResult, ScenarioSpec
from scenariocraft.tools.asam_qc_tool import AsamQcResult
from scenariocraft.tools.esmini_tool import EsminiPlaybackResult, EsminiResult
from scenariocraft.tools.scenario_builder import BuildResult
from scenariocraft.tools.semantic_validator import SemanticValidationResult


def generate_validation_report(
    scenario_text: str,
    spec: ScenarioSpec,
    build_result: BuildResult,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
    semantic_result: SemanticValidationResult,
    output_dir: Path,
    probe_results: Sequence[ProbeResult] | None = None,
    playback_result: EsminiPlaybackResult | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.md"
    report_path.write_text(
        _render_report(
            scenario_text,
            spec,
            build_result,
            qc_result,
            esmini_result,
            semantic_result,
            probe_results,
            playback_result,
        ),
        encoding="utf-8",
    )
    return report_path


def _render_report(
    scenario_text: str,
    spec: ScenarioSpec,
    build_result: BuildResult,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
    semantic_result: SemanticValidationResult,
    probe_results: Sequence[ProbeResult] | None = None,
    playback_result: EsminiPlaybackResult | None = None,
) -> str:
    semantic_lines = "\n".join(
        f"- [{'x' if check.passed else ' '}] `{check.name}`: {check.message}" for check in semantic_result.checks
    )
    artifact_lines = "\n".join(f"- `{path.name}`" for path in build_result.artifact_paths())
    qc_summary = _qc_summary(qc_result)
    esmini_summary = _esmini_summary(esmini_result)
    esmini_media_summary = _esmini_media_summary(playback_result)
    probe_section = _probe_section(probe_results)
    return f"""# scenarioCraft Validation Report

## Input Scenario Intent

{scenario_text}

## Generated ScenarioSpec

- Scenario name: `{spec.scenario_name}`
- Scenario type: `{spec.scenario_type}`
- Road: `{spec.road.type}`, {spec.road.lanes_per_direction} lane(s) per direction, {spec.road.speed_limit_kph:g} kph speed limit
- Weather: rain=`{spec.weather.rain}`, road condition=`{spec.weather.road_condition}`
- Actors: {", ".join(f"`{actor.id}`/{actor.role}" for actor in spec.actors)}
- Trigger: `{spec.trigger.type}` from `{spec.trigger.source}` to `{spec.trigger.target}` at {spec.trigger.distance_m:g} m
- Intended criticality: `{spec.intended_criticality.type}`, target min TTC {spec.intended_criticality.target_min_ttc_s:g} s

## Generated Artifacts

- `scenario_spec.json`
- `preview_2d.png`
{artifact_lines}
- `qc_config.xml`
- `qc_report.json`
- `qc_result.xqar`, if ASAM QC runs
- `esmini_log.txt`
- `validation_report.md`

## ASAM Quality Check

{qc_summary}

## esmini Execution

{esmini_summary}

## esmini Media

{esmini_media_summary}

## Semantic Validation

Overall result: `{'passed' if semantic_result.passed else 'failed'}`

{semantic_lines}
{probe_section}

## Known Limitations

- The OpenSCENARIO XML builder used `{build_result.builder}`.
- No CARLA, CAMEL, OpenAI provider, local LLM provider, Docker setup, or full repair loop is included in this version.
- esmini currently acts as an optional execution/load check; browser video rendering is future work.
- External ASAM QC and esmini checks are optional and may be skipped when the tools are unavailable.

## Repair Suggestions

- No automated repair loop is implemented in this version.
"""


def _probe_section(probe_results: Sequence[ProbeResult] | None) -> str:
    if not probe_results:
        return ""
    lines = ["", "## Template-Aware Probes", ""]
    for result in probe_results:
        state = "PASS" if result.passed else "FAIL"
        lines.append(f"- [{state}] `{result.name}` ({result.severity}): {result.message}")
        if result.measured:
            lines.append(f"  - measured: `{json.dumps(result.measured, sort_keys=True)}`")
        if result.suggested_operations:
            lines.append(
                f"  - suggested_operations: `{json.dumps(list(result.suggested_operations), sort_keys=True)}`"
            )
    return "\n".join(lines)


def _qc_summary(result: AsamQcResult) -> str:
    if not result.checker_available:
        return "\n".join([
            "ASAM OpenSCENARIO XML checker was not found. Standard-compliance checking was skipped.",
            f"- Config path: `{result.config_path}`",
            f"- Expected result path: `{result.result_path}`",
        ])
    lines = [
        f"- Command: `{' '.join(result.command)}`",
        f"- Config path: `{result.config_path}`",
        f"- Result path: `{result.result_path}`",
        f"- Return code: `{result.return_code}`",
        f"- Passed: `{result.passed}`",
    ]
    if result.stdout:
        lines.append("")
        lines.append("stdout:")
        lines.append("```text")
        lines.append(result.stdout.strip())
        lines.append("```")
    if result.stderr:
        lines.append("")
        lines.append("stderr:")
        lines.append("```text")
        lines.append(result.stderr.strip())
        lines.append("```")
    return "\n".join(lines)


def _esmini_summary(result: EsminiResult) -> str:
    if not result.esmini_available:
        lines = ["esmini was not found. Scenario playback/execution check was skipped."]
        if result.install_hint:
            lines.append(f"- Install hint: {result.install_hint}")
        return "\n".join(lines)
    return "\n".join([
        f"- Command: `{' '.join(result.command)}`",
        f"- Working directory: `{result.working_dir}`",
        f"- Required: `{result.required}`",
        f"- Timeout seconds: `{result.timeout_s}`",
        f"- Timed out: `{result.timed_out}`",
        f"- Return code: `{result.return_code}`",
        f"- Executed: `{result.executed}`",
        f"- Error message: `{result.error_message}`",
    ])


def _esmini_media_summary(result: EsminiPlaybackResult | None) -> str:
    if result is None:
        return "No playback media generation result was recorded."
    label = _playback_label(result.playback_kind)
    lines = [
        f"- Label: `{label}`",
        f"- Playback kind: `{result.playback_kind}`",
        f"- Capture mode: `{result.capture_mode}`",
        f"- Platform strategy: `{result.capture_platform_strategy}`",
        f"- Capture window policy: `{result.capture_window_policy}`",
        f"- Capture window: `{result.capture_window_x}, {result.capture_window_y}, {result.capture_window_width}, {result.capture_window_height}`",
        f"- Capture attempts: `{len(result.capture_attempts)}`",
        f"- Media quality status: `{result.media_quality_status}`",
        f"- Media quality reason: `{result.media_quality_reason}`",
        f"- Semantic visual orientation: `{result.semantic_visual_orientation}`",
        f"- Raw visual orientation: `{result.raw_visual_orientation}`",
        f"- UI visual orientation: `{result.ui_visual_orientation}`",
        f"- Presentation transform: `{result.presentation_transform}`",
        f"- Presentation transform reason: `{result.presentation_transform_reason}`",
        f"- Visual media safe to display: `{_visual_media_safe_to_display(result)}`",
        f"- Frame count: `{result.playback_frame_count}`",
        f"- Animated: `{result.playback_is_animated}`",
        f"- Frame duration seconds: `{result.playback_frame_duration_s}`",
        f"- Media path: `{result.playback_path}`",
        f"- Source path: `{result.playback_source_path}`",
    ]
    if result.playback_frames:
        first = result.playback_frames[0]
        lines.append(
            "- First frame source: "
            f"`{first.get('original_source_path')}` -> `{first.get('normalized_frame_path')}` "
            f"(index `{first.get('frame_index')}`, ext `{first.get('source_extension')}`)"
        )
        if first.get("presentation_frame_path"):
            lines.append(f"- First presentation frame: `{first.get('presentation_frame_path')}`")
    for index, attempt in enumerate(result.capture_attempts, start=1):
        lines.append(
            f"- Capture attempt {index}: "
            f"policy `{attempt.get('capture_window_policy')}`, "
            f"quality `{attempt.get('media_quality_status')}`, "
            f"frames `{attempt.get('playback_frame_count')}`"
        )
    if result.playback_fallback_reason:
        lines.append(f"- Fallback reason: {result.playback_fallback_reason}")
    return "\n".join(lines)


def _visual_media_safe_to_display(result: EsminiPlaybackResult) -> bool:
    return (
        result.media_quality_status in {"valid", "suspicious"}
        and result.playback_kind in {"esmini_gif", "esmini_frame_sequence", "esmini_single_frame"}
    )


def _playback_label(playback_kind: str) -> str:
    labels = {
        "esmini_gif": "esmini Rendered GIF",
        "esmini_frame_sequence": "esmini Frame Sequence",
        "esmini_single_frame": "esmini Screenshot",
        "preview_fallback_gif": "2D Preview Fallback",
        "preview_static_image": "2D Preview",
        "unavailable": "Playback Unavailable",
    }
    return labels.get(playback_kind, "Playback Unavailable")
