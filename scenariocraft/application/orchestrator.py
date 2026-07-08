from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scenariocraft.core.loop.repair_loop import run_bounded_repair_loop
from scenariocraft.core.loop.types import RepairRunResult
from scenariocraft.core.checks import (
    run_and_write_runtime_consistency_checks,
    run_artifact_consistency_checks,
    run_family_checks,
)
from scenariocraft.core.repair.providers import RepairProvider
from scenariocraft.core.build import BuildResult, build_openscenario
from scenariocraft.rendering import generate_2d_preview, generate_validation_report
from scenariocraft.external_tools import (
    AsamQcResult,
    EsminiPlaybackResult,
    EsminiResult,
    run_asam_qc,
    run_esmini,
    run_esmini_playback,
)
from scenariocraft.core.schemas import CheckResult, ScenarioSpec
from scenariocraft.core.checks import SemanticValidationResult
from scenariocraft.core.checks import validate_semantics


ORCHESTRATOR_RESULT_FILENAME = "orchestrator_result.json"


@dataclass(frozen=True)
class OrchestratorRunResult:
    initial_spec: ScenarioSpec
    final_spec: ScenarioSpec
    initial_semantic_result: SemanticValidationResult
    final_semantic_result: SemanticValidationResult
    repair_run_result: RepairRunResult | None
    final_geometry_check_results: tuple[CheckResult, ...]
    final_artifact_check_results: tuple[CheckResult, ...]
    runtime_check_results: tuple[CheckResult, ...]
    build_result: BuildResult | None
    qc_result: AsamQcResult | None
    esmini_result: EsminiResult | None
    playback_result: EsminiPlaybackResult | None
    terminal_status: str
    terminal_reason: str
    report_path: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "initial_spec": self.initial_spec.to_dict(),
            "final_spec": self.final_spec.to_dict(),
            "initial_semantic_result": self.initial_semantic_result.to_dict(),
            "final_semantic_result": self.final_semantic_result.to_dict(),
            "repair_run_result": self.repair_run_result.to_dict() if self.repair_run_result is not None else None,
            "final_geometry_check_results": [result.to_dict() for result in self.final_geometry_check_results],
            "final_artifact_check_results": [result.to_dict() for result in self.final_artifact_check_results],
            "runtime_check_results": [result.to_dict() for result in self.runtime_check_results],
            "build_result": _build_result_dict(self.build_result),
            "qc_result": self.qc_result.to_dict() if self.qc_result is not None else None,
            "esmini_result": self.esmini_result.to_dict() if self.esmini_result is not None else None,
            "playback_result": self.playback_result.to_dict() if self.playback_result is not None else None,
            "terminal_status": self.terminal_status,
            "terminal_reason": self.terminal_reason,
            "report_path": str(self.report_path) if self.report_path is not None else None,
        }


def run_bounded_orchestrator(
    spec: ScenarioSpec,
    *,
    output_dir: Path,
    scenario_text: str = "",
    repair_provider: RepairProvider | None = None,
    max_repair_rounds: int = 2,
    run_runtime: bool = True,
    run_playback: bool = False,
    run_esmini_check: bool = True,
    require_esmini: bool = False,
    esmini_bin: str | None = None,
    esmini_timeout_s: float = 20.0,
    playback_timeout_s: float = 30.0,
    sim_duration_s: float = 3.0,
    try_video: bool = True,
) -> OrchestratorRunResult:
    """Run the bounded deterministic generate/build/check/repair harness."""
    if not isinstance(spec, ScenarioSpec):
        raise TypeError("spec must be a ScenarioSpec.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    initial_spec = ScenarioSpec.from_dict(spec.to_dict())
    initial_semantic = validate_semantics(initial_spec)
    (output_dir / "input.txt").write_text(scenario_text, encoding="utf-8")
    (output_dir / "initial_scenario_spec.json").write_text(initial_spec.to_json() + "\n", encoding="utf-8")

    repair_result: RepairRunResult | None = None
    final_spec = initial_spec
    geometry_results: tuple[CheckResult, ...] = ()
    artifact_results: tuple[CheckResult, ...] = ()
    build_result: BuildResult | None = None

    if repair_provider is not None:
        repair_result = run_bounded_repair_loop(
            initial_spec,
            provider=repair_provider,
            output_dir=output_dir,
            user_intent=scenario_text or None,
            max_rounds=max_repair_rounds,
        )
        final_spec = repair_result.final_spec
        geometry_results = repair_result.final_geometry_check_results
        artifact_results = repair_result.final_artifact_check_results
        if repair_result.xosc_path is not None:
            build_result = BuildResult(
                xosc_path=repair_result.xosc_path,
                xodr_path=repair_result.xodr_path,
                builder="repair_loop",
            )
        if repair_result.terminal_status != "passed":
            final_semantic = validate_semantics(final_spec)
            result = _result(
                initial_spec=initial_spec,
                final_spec=final_spec,
                initial_semantic=initial_semantic,
                final_semantic=final_semantic,
                repair_result=repair_result,
                geometry_results=geometry_results,
                artifact_results=artifact_results,
                runtime_results=(),
                build_result=build_result,
                qc_result=None,
                esmini_result=None,
                playback_result=None,
                terminal_status=repair_result.terminal_status,
                terminal_reason=repair_result.terminal_reason,
                report_path=None,
            )
            _write_orchestrator_result(output_dir, result)
            return result
    else:
        geometry_results = _scenario_validation_results(initial_spec)
        failures = _failed_checks(geometry_results)
        if failures:
            final_semantic = validate_semantics(final_spec)
            result = _result(
                initial_spec=initial_spec,
                final_spec=final_spec,
                initial_semantic=initial_semantic,
                final_semantic=final_semantic,
                repair_result=None,
                geometry_results=geometry_results,
                artifact_results=(),
                runtime_results=(),
                build_result=None,
                qc_result=None,
                esmini_result=None,
                playback_result=None,
                terminal_status="repair_required",
                terminal_reason="Scenario validation failures remain and no repair provider was configured.",
                report_path=None,
            )
            _write_orchestrator_result(output_dir, result)
            return result

        try:
            build_result = build_openscenario(final_spec, output_dir)
        except Exception as exc:
            final_semantic = validate_semantics(final_spec)
            result = _result(
                initial_spec=initial_spec,
                final_spec=final_spec,
                initial_semantic=initial_semantic,
                final_semantic=final_semantic,
                repair_result=None,
                geometry_results=geometry_results,
                artifact_results=(),
                runtime_results=(),
                build_result=None,
                qc_result=None,
                esmini_result=None,
                playback_result=None,
                terminal_status="build_failed",
                terminal_reason=f"Deterministic artifact build failed with {type(exc).__name__}: {exc}",
                report_path=None,
            )
            _write_orchestrator_result(output_dir, result)
            return result
        artifact_results = run_artifact_consistency_checks(
            final_spec,
            xosc_path=build_result.xosc_path,
            xodr_path=build_result.xodr_path,
        )
        if not artifact_results or _failed_checks(artifact_results):
            final_semantic = validate_semantics(final_spec)
            result = _result(
                initial_spec=initial_spec,
                final_spec=final_spec,
                initial_semantic=initial_semantic,
                final_semantic=final_semantic,
                repair_result=None,
                geometry_results=geometry_results,
                artifact_results=artifact_results,
                runtime_results=(),
                build_result=build_result,
                qc_result=None,
                esmini_result=None,
                playback_result=None,
                terminal_status="artifact_validation_failed",
                terminal_reason=(
                    "No static artifact consistency check evidence was produced."
                    if not artifact_results
                    else "One or more static artifact consistency checks failed."
                ),
                report_path=None,
            )
            _write_orchestrator_result(output_dir, result)
            return result

    if build_result is None:
        build_result = build_openscenario(final_spec, output_dir)
        artifact_results = run_artifact_consistency_checks(
            final_spec,
            xosc_path=build_result.xosc_path,
            xodr_path=build_result.xodr_path,
        )

    (output_dir / "scenario_spec.json").write_text(final_spec.to_json() + "\n", encoding="utf-8")
    generate_2d_preview(final_spec, output_dir / "preview_2d.png")
    qc_result = run_asam_qc(build_result.xosc_path, output_dir)
    playback_result: EsminiPlaybackResult | None = None
    if run_playback:
        playback_result = run_esmini_playback(
            build_result.xosc_path,
            output_dir,
            working_dir=build_result.xosc_path.parent,
            binary=esmini_bin,
            timeout_s=playback_timeout_s,
            sim_duration_s=sim_duration_s,
            try_video=try_video,
        )
        esmini_result = _read_esmini_result(output_dir) or _missing_esmini_result(build_result.xosc_path)
    elif run_esmini_check:
        esmini_result = run_esmini(
            build_result.xosc_path,
            output_dir,
            required=require_esmini,
            binary=esmini_bin,
            timeout_s=esmini_timeout_s,
        )
    else:
        esmini_result = _missing_esmini_result(build_result.xosc_path)
        (output_dir / "esmini_log.txt").write_text("esmini check was not requested.\n", encoding="utf-8")

    runtime_results = (
        run_and_write_runtime_consistency_checks(
            final_spec,
            output_dir=output_dir,
            xosc_path=build_result.xosc_path,
            xodr_path=build_result.xodr_path,
        )
        if run_runtime
        else ()
    )
    final_semantic = validate_semantics(final_spec)
    report_path = generate_validation_report(
        scenario_text,
        final_spec,
        build_result,
        qc_result,
        esmini_result,
        final_semantic,
        output_dir,
        check_results=geometry_results,
        playback_result=playback_result,
        artifact_check_results=artifact_results,
        runtime_check_results=runtime_results,
    )
    result = _result(
        initial_spec=initial_spec,
        final_spec=final_spec,
        initial_semantic=initial_semantic,
        final_semantic=final_semantic,
        repair_result=repair_result,
        geometry_results=geometry_results,
        artifact_results=artifact_results,
        runtime_results=runtime_results,
        build_result=build_result,
        qc_result=qc_result,
        esmini_result=esmini_result,
        playback_result=playback_result,
        terminal_status="passed",
        terminal_reason=_passed_reason(runtime_results),
        report_path=report_path,
    )
    _write_orchestrator_result(output_dir, result)
    return result


def _scenario_validation_results(spec: ScenarioSpec) -> tuple[CheckResult, ...]:
    return run_family_checks(spec, include_timing=True)


def _failed_checks(results: tuple[CheckResult, ...]) -> tuple[CheckResult, ...]:
    return tuple(result for result in results if not result.passed)


def _passed_reason(runtime_results: tuple[CheckResult, ...]) -> str:
    warnings = tuple(result for result in runtime_results if not result.passed and result.severity == "warning")
    failures = tuple(result for result in runtime_results if not result.passed and result.severity == "failure")
    if failures:
        return "Geometry, timing, and static artifact checks passed; runtime checks reported failures."
    if warnings:
        return "Geometry, timing, and static artifact checks passed; runtime evidence is incomplete or unavailable."
    return "Geometry, timing, static artifact, and runtime consistency checks passed."


def _result(
    *,
    initial_spec: ScenarioSpec,
    final_spec: ScenarioSpec,
    initial_semantic: SemanticValidationResult,
    final_semantic: SemanticValidationResult,
    repair_result: RepairRunResult | None,
    geometry_results: tuple[CheckResult, ...],
    artifact_results: tuple[CheckResult, ...],
    runtime_results: tuple[CheckResult, ...],
    build_result: BuildResult | None,
    qc_result: AsamQcResult | None,
    esmini_result: EsminiResult | None,
    playback_result: EsminiPlaybackResult | None,
    terminal_status: str,
    terminal_reason: str,
    report_path: Path | None,
) -> OrchestratorRunResult:
    return OrchestratorRunResult(
        initial_spec=initial_spec,
        final_spec=final_spec,
        initial_semantic_result=initial_semantic,
        final_semantic_result=final_semantic,
        repair_run_result=repair_result,
        final_geometry_check_results=geometry_results,
        final_artifact_check_results=artifact_results,
        runtime_check_results=runtime_results,
        build_result=build_result,
        qc_result=qc_result,
        esmini_result=esmini_result,
        playback_result=playback_result,
        terminal_status=terminal_status,
        terminal_reason=terminal_reason,
        report_path=report_path,
    )


def _write_orchestrator_result(output_dir: Path, result: OrchestratorRunResult) -> Path:
    path = output_dir / ORCHESTRATOR_RESULT_FILENAME
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _build_result_dict(build_result: BuildResult | None) -> dict[str, object] | None:
    if build_result is None:
        return None
    return {
        "xosc_path": str(build_result.xosc_path),
        "xodr_path": str(build_result.xodr_path) if build_result.xodr_path is not None else None,
        "builder": build_result.builder,
        "fallback_reason": build_result.fallback_reason,
    }


def _read_esmini_result(output_dir: Path) -> EsminiResult | None:
    path = output_dir / "esmini_result.json"
    if not path.exists():
        return None
    try:
        return EsminiResult(**json.loads(path.read_text(encoding="utf-8")))
    except (TypeError, json.JSONDecodeError):
        return None


def _missing_esmini_result(xosc_path: Path) -> EsminiResult:
    return EsminiResult(
        esmini_available=False,
        command=["esmini", "--osc", str(xosc_path)],
        working_dir=str(xosc_path.parent),
        return_code=None,
        stdout="",
        stderr="esmini has not been run.",
        executed=None,
        error_message="esmini has not been run.",
        playback_path=None,
    )
