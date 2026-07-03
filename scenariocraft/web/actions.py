from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from scenariocraft.core.checks import run_and_write_runtime_consistency_checks
from scenariocraft.core.build import BuildResult
from scenariocraft.rendering import generate_validation_report
from scenariocraft.external_tools import AsamQcResult, EsminiPlaybackResult, EsminiResult
from scenariocraft.core.schemas import CheckResult, ScenarioSpec
from scenariocraft.core.checks import SemanticValidationResult


def run_runtime_checks_for_generated_scenario(
    spec: ScenarioSpec,
    *,
    build_result: BuildResult,
    output_dir: Path,
) -> tuple[CheckResult, ...]:
    return run_and_write_runtime_consistency_checks(
        spec,
        output_dir=output_dir,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )


def write_generated_validation_report(
    *,
    scenario_text: str,
    spec: ScenarioSpec,
    build_result: BuildResult,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
    semantic_result: SemanticValidationResult,
    output_dir: Path,
    playback_result: EsminiPlaybackResult | None = None,
    runtime_check_results: Sequence[CheckResult] | None = None,
) -> Path:
    return generate_validation_report(
        scenario_text,
        spec,
        build_result,
        qc_result,
        esmini_result,
        semantic_result,
        output_dir,
        playback_result=playback_result,
        runtime_check_results=runtime_check_results,
    )
