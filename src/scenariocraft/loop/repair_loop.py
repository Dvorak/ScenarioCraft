from __future__ import annotations

from pathlib import Path

from scenariocraft.loop.types import RepairRoundTrace, RepairRunResult, TerminalStatus
from scenariocraft.probes import (
    run_artifact_consistency_probes,
    run_pedestrian_occlusion_probes,
    run_pedestrian_occlusion_timing_probes,
)
from scenariocraft.repair import PatchApplicationError, apply_patch
from scenariocraft.repair.providers import RepairProvider, RepairRequest
from scenariocraft.build import build_openscenario
from scenariocraft.schemas import ProbeResult, ScenarioSpec


ALLOWED_OPERATION_TYPES = (
    "set_actor_pose",
    "reposition_actor_to_band",
    "set_path_points",
    "set_named_point",
    "set_trigger_point_by_lead_time",
)


def run_bounded_repair_loop(
    spec: ScenarioSpec,
    *,
    provider: RepairProvider,
    output_dir: Path,
    user_intent: str | None = None,
    max_rounds: int = 2,
) -> RepairRunResult:
    """Repair geometry within a fixed bound, then build and validate artifacts."""
    if not isinstance(spec, ScenarioSpec):
        raise TypeError("spec must be a ScenarioSpec.")
    if not isinstance(max_rounds, int) or isinstance(max_rounds, bool) or max_rounds < 0:
        raise ValueError("max_rounds must be a non-negative integer.")

    initial_spec = ScenarioSpec.from_dict(spec.to_dict())
    current_spec = initial_spec
    rounds: list[RepairRoundTrace] = []

    if current_spec.scenario_type != "pedestrian_occlusion" or current_spec.layout is None:
        return _result(
            initial_spec,
            current_spec,
            rounds,
            (),
            status="unsupported_scenario",
            reason="The bounded repair loop supports layout-backed pedestrian_occlusion scenarios only.",
        )

    validation_results = _scenario_validation_results(current_spec)
    if not validation_results:
        return _result(
            initial_spec,
            current_spec,
            rounds,
            validation_results,
            status="geometry_validation_failed",
            reason="No geometry or timing probe evidence was produced for the supported scenario.",
        )
    failures = _failures(validation_results)
    if failures and max_rounds == 0:
        return _result(
            initial_spec,
            current_spec,
            rounds,
            validation_results,
            status="max_rounds_reached",
            reason="Scenario validation failures remain and max_rounds is zero.",
        )

    while failures and len(rounds) < max_rounds:
        proposal = provider.propose_patch(
            RepairRequest(
                user_intent=user_intent,
                scenario_spec=current_spec,
                failed_probe_results=failures,
                allowed_operation_types=ALLOWED_OPERATION_TYPES,
            )
        )
        if proposal.patch is None:
            rounds.append(
                RepairRoundTrace(
                    round_index=len(rounds) + 1,
                    input_probe_results=validation_results,
                    allowed_operation_types=ALLOWED_OPERATION_TYPES,
                    provider_name=proposal.provider_name,
                    proposal_rationale=proposal.rationale,
                    proposed_patch=None,
                    patch_applied=False,
                )
            )
            return _result(
                initial_spec,
                current_spec,
                rounds,
                validation_results,
                status="provider_refused",
                reason="The repair provider returned no patch for the current scenario validation failures.",
            )

        try:
            patched_spec = apply_patch(current_spec, proposal.patch)
        except PatchApplicationError as exc:
            rounds.append(
                RepairRoundTrace(
                    round_index=len(rounds) + 1,
                    input_probe_results=validation_results,
                    allowed_operation_types=ALLOWED_OPERATION_TYPES,
                    provider_name=proposal.provider_name,
                    proposal_rationale=proposal.rationale,
                    proposed_patch=proposal.patch,
                    patch_applied=False,
                    application_error=str(exc),
                )
            )
            return _result(
                initial_spec,
                current_spec,
                rounds,
                validation_results,
                status="patch_application_failed",
                reason=f"Patch application failed: {exc}",
            )

        rounds.append(
            RepairRoundTrace(
                round_index=len(rounds) + 1,
                input_probe_results=validation_results,
                allowed_operation_types=ALLOWED_OPERATION_TYPES,
                provider_name=proposal.provider_name,
                proposal_rationale=proposal.rationale,
                proposed_patch=proposal.patch,
                patch_applied=True,
            )
        )
        current_spec = patched_spec
        validation_results = _scenario_validation_results(current_spec)
        if not validation_results:
            return _result(
                initial_spec,
                current_spec,
                rounds,
                validation_results,
                status="geometry_validation_failed",
                reason="No geometry or timing probe evidence was produced after patch application.",
            )
        failures = _failures(validation_results)

    if failures:
        return _result(
            initial_spec,
            current_spec,
            rounds,
            validation_results,
            status="max_rounds_reached",
            reason=f"Scenario validation failures remain after {max_rounds} repair round(s).",
        )

    try:
        build_result = build_openscenario(current_spec, Path(output_dir))
    except Exception as exc:
        return _result(
            initial_spec,
            current_spec,
            rounds,
            validation_results,
            status="build_failed",
            reason=f"Deterministic artifact build failed with {type(exc).__name__}: {exc}",
        )

    artifact_results = run_artifact_consistency_probes(
        current_spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    if not artifact_results or _failures(artifact_results):
        return _result(
            initial_spec,
            current_spec,
            rounds,
            validation_results,
            artifact_results=artifact_results,
            status="artifact_validation_failed",
            reason=(
                "No static artifact consistency probe evidence was produced."
                if not artifact_results
                else "One or more static artifact consistency probes failed."
            ),
            xosc_path=build_result.xosc_path,
            xodr_path=build_result.xodr_path,
        )
    return _result(
        initial_spec,
        current_spec,
        rounds,
        validation_results,
        artifact_results=artifact_results,
        status="passed",
        reason="Geometry, timing, and static artifact consistency probes passed.",
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )


def _failures(results: tuple[ProbeResult, ...]) -> tuple[ProbeResult, ...]:
    return tuple(result for result in results if not result.passed)


def _scenario_validation_results(spec: ScenarioSpec) -> tuple[ProbeResult, ...]:
    geometry_results = run_pedestrian_occlusion_probes(spec)
    if not geometry_results:
        return ()
    timing_results = run_pedestrian_occlusion_timing_probes(spec)
    return geometry_results + timing_results


def _result(
    initial_spec: ScenarioSpec,
    final_spec: ScenarioSpec,
    rounds: list[RepairRoundTrace],
    geometry_results: tuple[ProbeResult, ...],
    *,
    status: TerminalStatus,
    reason: str,
    artifact_results: tuple[ProbeResult, ...] = (),
    xosc_path: Path | None = None,
    xodr_path: Path | None = None,
) -> RepairRunResult:
    return RepairRunResult(
        initial_spec=initial_spec,
        final_spec=final_spec,
        rounds=tuple(rounds),
        final_geometry_probe_results=geometry_results,
        final_artifact_probe_results=artifact_results,
        terminal_status=status,
        terminal_reason=reason,
        xosc_path=xosc_path,
        xodr_path=xodr_path,
    )
