from __future__ import annotations

from pathlib import Path

from scenariocraft.schemas import ScenarioSpec
from scenariocraft.tools.asam_qc_tool import AsamQcResult
from scenariocraft.tools.esmini_tool import EsminiResult
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
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "validation_report.md"
    report_path.write_text(
        _render_report(scenario_text, spec, build_result, qc_result, esmini_result, semantic_result),
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
) -> str:
    semantic_lines = "\n".join(
        f"- [{'x' if check.passed else ' '}] `{check.name}`: {check.message}" for check in semantic_result.checks
    )
    artifact_lines = "\n".join(f"- `{path.name}`" for path in build_result.artifact_paths())
    qc_summary = _qc_summary(qc_result)
    esmini_summary = _esmini_summary(esmini_result)
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

## esmini Execution / Playback

{esmini_summary}

## Semantic Validation

Overall result: `{'passed' if semantic_result.passed else 'failed'}`

{semantic_lines}

## Known Limitations

- The OpenSCENARIO XML builder used `{build_result.builder}`.
- No CARLA, CAMEL, OpenAI provider, local LLM provider, Docker setup, or full repair loop is included in this version.
- esmini currently acts as an optional execution/load check; browser video rendering is future work.
- External ASAM QC and esmini checks are optional and may be skipped when the tools are unavailable.

## Repair Suggestions

- No automated repair loop is implemented in this version.
"""


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
