from __future__ import annotations

"""Dispatch deterministic checks for the active scenario family."""

from scenariocraft.core.checks.crossing_vehicle import run_crossing_vehicle_checks
from scenariocraft.core.checks.cut_in import run_cut_in_checks
from scenariocraft.core.checks.lead_vehicle_braking import run_lead_vehicle_braking_checks
from scenariocraft.core.checks.oncoming_turn_across_path import run_oncoming_turn_across_path_checks
from scenariocraft.core.checks.pedestrian_occlusion import (
    run_pedestrian_occlusion_checks,
    run_pedestrian_occlusion_timing_checks,
)
from scenariocraft.core.schemas import CheckResult, ScenarioSpec


def run_family_checks(spec: ScenarioSpec, *, include_timing: bool = False) -> tuple[CheckResult, ...]:
    """Run checks owned by the scenario's registered interaction family."""

    if spec.scenario_type == "cut_in":
        return run_cut_in_checks(spec)
    if spec.scenario_type == "crossing_vehicle":
        return run_crossing_vehicle_checks(spec)
    if spec.scenario_type == "oncoming_turn_across_path":
        return run_oncoming_turn_across_path_checks(spec)
    if spec.scenario_type == "lead_vehicle_braking":
        return run_lead_vehicle_braking_checks(spec)
    if spec.scenario_type == "pedestrian_occlusion":
        geometry_results = run_pedestrian_occlusion_checks(spec)
        if not include_timing or not geometry_results:
            return geometry_results
        return geometry_results + run_pedestrian_occlusion_timing_checks(spec)
    return ()


__all__ = ["run_family_checks"]
