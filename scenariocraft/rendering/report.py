from __future__ import annotations

from pathlib import Path
import json
from collections.abc import Sequence

from scenariocraft.core.schemas import CheckResult, ScenarioSpec
from scenariocraft.core.templates.pedestrian_occlusion import assess_pedestrian_occlusion_timing
from scenariocraft.external_tools import (
    AsamQcResult,
    EsminiPlaybackResult,
    EsminiResult,
    OpenDriveMcpEvidence,
)
from scenariocraft.core.build import BuildResult
from scenariocraft.core.checks import SemanticValidationResult
from scenariocraft.core.metrics import compute_timing_metrics


def generate_validation_report(
    scenario_text: str,
    spec: ScenarioSpec,
    build_result: BuildResult,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
    semantic_result: SemanticValidationResult,
    output_dir: Path,
    check_results: Sequence[CheckResult] | None = None,
    playback_result: EsminiPlaybackResult | None = None,
    artifact_check_results: Sequence[CheckResult] | None = None,
    runtime_check_results: Sequence[CheckResult] | None = None,
    opendrive_mcp_result: OpenDriveMcpEvidence | None = None,
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
            check_results,
            playback_result,
            artifact_check_results,
            runtime_check_results,
            opendrive_mcp_result,
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
    check_results: Sequence[CheckResult] | None = None,
    playback_result: EsminiPlaybackResult | None = None,
    artifact_check_results: Sequence[CheckResult] | None = None,
    runtime_check_results: Sequence[CheckResult] | None = None,
    opendrive_mcp_result: OpenDriveMcpEvidence | None = None,
) -> str:
    semantic_lines = "\n".join(
        f"- [{'x' if check.passed else ' '}] `{check.name}`: {check.message}" for check in semantic_result.checks
    )
    artifact_lines = "\n".join(f"- `{path.name}`" for path in build_result.artifact_paths())
    qc_summary = _qc_summary(qc_result)
    esmini_summary = _esmini_summary(esmini_result)
    esmini_media_summary = _esmini_media_summary(playback_result)
    template_resolution_section = _template_resolution_section(spec)
    timing_section = _timing_section(spec)
    check_section = _check_section(check_results)
    artifact_check_section = _artifact_check_section(artifact_check_results)
    runtime_check_section = _runtime_check_section(runtime_check_results)
    opendrive_mcp_section = _opendrive_mcp_section(opendrive_mcp_result)
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
{template_resolution_section}
{timing_section}

## Generated Artifacts

- `scenario_spec.json`
- `preview_2d.png`
{artifact_lines}
- `qc_config.xml`
- `qc_report.json`
- `qc_result.xqar`, if ASAM QC runs
- `esmini_log.txt`
- `opendrive_mcp_result.json`, if OpenDRIVE MCP runs
- `validation_report.md`
{opendrive_mcp_section}

## ASAM Quality Check

{qc_summary}

## esmini Execution

{esmini_summary}

## esmini Media

{esmini_media_summary}

## Semantic Validation

Overall result: `{'passed' if semantic_result.passed else 'failed'}`

{semantic_lines}
{check_section}
{artifact_check_section}
{runtime_check_section}

## Known Limitations

- The OpenSCENARIO XML builder used `{build_result.builder}`.
- No CARLA, CAMEL, OpenAI provider, local LLM provider, Docker setup, or full repair loop is included in this version.
- esmini currently acts as an optional execution/load check; browser video rendering is future work.
- External ASAM QC and esmini checks are optional and may be skipped when the tools are unavailable.

## Repair Suggestions

- No automated repair loop is implemented in this version.
"""


def _timing_section(spec: ScenarioSpec) -> str:
    metrics = compute_timing_metrics(spec)
    lines = [
        "",
        "## Timing Metrics",
        "",
        f"- Target TTC: `{_format_seconds(metrics.target_ttc_s)}`",
        f"- Trigger threshold time: `{_format_seconds(metrics.trigger_threshold_time_s)}`",
        f"- Ego lead time to conflict: `{_format_seconds(metrics.ego_lead_time_to_conflict_s)}`",
        f"- Pedestrian time to conflict: `{_format_seconds(metrics.pedestrian_time_to_conflict_s)}`",
        "- Runtime minimum TTC: `not implemented`",
        "- Time headway: `not implemented`",
    ]
    if spec.timing is None:
        return "\n".join(lines)
    assessment = assess_pedestrian_occlusion_timing(spec)
    lines.extend([
        "",
        "## Timing Harness",
        "",
        f"- Total duration: `{spec.timing.total_duration_s:g}` s",
        "- Preferred trigger window: "
        f"`{spec.timing.preferred_trigger_earliest_s:g}` s to `{spec.timing.preferred_trigger_latest_s:g}` s",
        f"- Minimum pre-trigger context: `{spec.timing.minimum_pre_trigger_context_s:g}` s",
        f"- Minimum post-trigger buffer: `{spec.timing.minimum_post_trigger_buffer_s:g}` s",
    ])
    if assessment is None:
        lines.append("- Timing classification: `unavailable`")
        return "\n".join(lines)
    lines.extend([
        f"- Predicted trigger time: `{assessment.predicted_trigger_time_s:g}` s",
        f"- Pedestrian crossing duration: `{assessment.pedestrian_crossing_duration_s:g}` s",
        f"- Hard latest feasible trigger time: `{assessment.hard_latest_trigger_s:g}` s",
        f"- Timing classification: `{assessment.classification}`",
    ])
    derivation = _timing_derivation(spec)
    if derivation:
        lines.append(f"- Trigger-time estimate formula: `{derivation}`")
    return "\n".join(lines)


def _opendrive_mcp_section(result: OpenDriveMcpEvidence | None) -> str:
    if result is None:
        return ""
    tool_names = tuple(dict.fromkeys(tool.tool_name for tool in result.tools))
    lines = [
        "",
        "## OpenDRIVE MCP Road Evidence",
        "",
        f"- Available: `{result.available}`",
        f"- Passed: `{result.passed}`",
        f"- Backend: `{result.backend_name or 'unavailable'}`",
        f"- Tools: `{', '.join(tool_names) or 'none'}`",
    ]
    if result.error_message:
        lines.append(f"- Error: `{result.error_message}`")
    lines.append("- Sidecar evidence does not determine scenario acceptance in this phase.")
    return "\n".join(lines)


def _template_resolution_section(spec: ScenarioSpec) -> str:
    resolution = spec.template_resolution_metadata()
    if not resolution:
        return ""
    parameters = resolution.get("parameters", ())
    if not isinstance(parameters, list):
        parameters = ()
    lines = [
        "",
        "## Template Resolution",
        "",
        f"- Template: `{resolution.get('template_id', spec.scenario_type)}`",
        f"- Seed: `{_format_template_seed(resolution.get('seed'))}`",
        f"- Variant index: `{resolution.get('variant_index', 0)}`",
        f"- Sampled: `{resolution.get('sampled', False)}`",
    ]
    if parameters:
        lines.append("- Resolved parameters:")
        for parameter in parameters:
            if not isinstance(parameter, dict):
                continue
            name = parameter.get("name", "parameter")
            value = parameter.get("value", "n/a")
            source = parameter.get("source", "unknown")
            unit = parameter.get("unit")
            suffix = f" {unit}" if unit else ""
            lines.append(f"  - `{name}` = `{value}{suffix}` ({source})")
    unsupported = resolution.get("unsupported_fields", ())
    if unsupported:
        lines.append(f"- Unsupported intent parameter fields: `{', '.join(str(field) for field in unsupported)}`")
    return "\n".join(lines)


def _format_template_seed(seed: object) -> str:
    if seed is None:
        return "none"
    return str(seed)


def _format_seconds(value_s: float | None) -> str:
    if value_s is None:
        return "n/a"
    return f"{value_s:.1f} s"


def _timing_derivation(spec: ScenarioSpec) -> str | None:
    if spec.layout is None:
        return None
    source_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    source_actor = spec.actor_by_id(spec.trigger.source)
    if source_pose is None or target_pose is None or source_actor is None or source_actor.initial_speed_kph is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    trigger_x = target_pose.x_m - spec.trigger.distance_m
    trigger_time_s = (trigger_x - source_pose.x_m) / speed_mps
    return (
        f"(({target_pose.x_m:g} m - {spec.trigger.distance_m:g} m) - {source_pose.x_m:g} m) "
        f"/ {speed_mps:g} m/s = {trigger_time_s:g} s"
    )


def _check_section(check_results: Sequence[CheckResult] | None) -> str:
    if not check_results:
        return ""
    lines = ["", "## Template-Aware Checks", ""]
    for result in check_results:
        state = "PASS" if result.passed else "FAIL"
        lines.append(f"- [{state}] `{result.name}` ({result.severity}): {result.message}")
        lines.extend(_check_metadata_lines(result))
        if result.measured:
            lines.append(f"  - measured: `{json.dumps(result.measured, sort_keys=True)}`")
        if result.suggested_operations:
            lines.append(
                f"  - suggested_operations: `{json.dumps(list(result.suggested_operations), sort_keys=True)}`"
            )
    return "\n".join(lines)


def _artifact_check_section(check_results: Sequence[CheckResult] | None) -> str:
    if not check_results:
        return ""
    lines = ["", "## Artifact Consistency Checks", ""]
    for result in check_results:
        state = "PASS" if result.passed else "FAIL"
        lines.append(f"- [{state}] `{result.name}` ({result.severity}): {result.message}")
        lines.extend(_check_metadata_lines(result))
        if result.measured:
            lines.append(f"  - measured: `{json.dumps(result.measured, sort_keys=True)}`")
        if result.suggested_operations:
            lines.append(
                f"  - suggested_operations: `{json.dumps(list(result.suggested_operations), sort_keys=True)}`"
            )
    return "\n".join(lines)


def _runtime_check_section(check_results: Sequence[CheckResult] | None) -> str:
    if not check_results:
        return ""
    lines = ["", "## Runtime Consistency Checks", ""]
    for result in check_results:
        state = "PASS" if result.passed else ("WARN" if result.severity == "warning" else "FAIL")
        lines.append(f"- [{state}] `{result.name}` ({result.severity}): {result.message}")
        lines.extend(_check_metadata_lines(result))
        if result.measured:
            lines.append(f"  - measured: `{json.dumps(result.measured, sort_keys=True)}`")
    return "\n".join(lines)


def _check_metadata_lines(result: CheckResult) -> list[str]:
    lines = [
        f"  - category: `{result.category}`",
        f"  - intent_relation: `{result.intent_relation}`",
    ]
    if result.repair_action is not None:
        lines.append(f"  - repair_action: `{result.repair_action}`")
    if result.expected is not None:
        lines.append(f"  - expected: `{json.dumps(result.expected, sort_keys=True)}`")
    return lines


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
        f"- Preview display orientation: `{result.preview_display_orientation}`",
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
