from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from scenariocraft.probes import run_and_write_runtime_consistency_probes
from scenariocraft.schemas import ProbeResult, ScenarioSpec
from scenariocraft.tools import (
    AsamQcResult,
    BuildResult,
    EsminiPlaybackResult,
    EsminiResult,
    generate_validation_report,
)
from scenariocraft.tools.semantic_validator import SemanticValidationResult


def run_runtime_probes_for_generated_scenario(
    spec: ScenarioSpec,
    *,
    build_result: BuildResult,
    output_dir: Path,
) -> tuple[ProbeResult, ...]:
    return run_and_write_runtime_consistency_probes(
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
    runtime_probe_results: Sequence[ProbeResult] | None = None,
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
        runtime_probe_results=runtime_probe_results,
    )
