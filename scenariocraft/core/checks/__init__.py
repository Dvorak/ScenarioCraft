"""Unified check evidence layer for ScenarioCraft scenarios and artifacts."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "RUNTIME_CHECK_NAMES": "scenariocraft.core.checks.runtime_consistency",
    "RUNTIME_CHECK_RESULTS_FILENAME": "scenariocraft.core.checks.runtime_pipeline",
    "ScenarioCheck": "scenariocraft.core.checks.runner",
    "SemanticCheck": "scenariocraft.core.checks.structural",
    "SemanticValidationResult": "scenariocraft.core.checks.structural",
    "run_artifact_consistency_checks": "scenariocraft.core.checks.artifact_consistency",
    "run_and_write_runtime_consistency_checks": "scenariocraft.core.checks.runtime_pipeline",
    "run_pedestrian_occlusion_checks": "scenariocraft.core.checks.pedestrian_occlusion",
    "run_pedestrian_occlusion_timing_checks": "scenariocraft.core.checks.pedestrian_occlusion",
    "run_runtime_consistency_checks": "scenariocraft.core.checks.runtime_consistency",
    "run_checks": "scenariocraft.core.checks.runner",
    "run_structural_validity_checks": "scenariocraft.core.checks.structural",
    "run_time_headway_checks": "scenariocraft.core.checks.time_headway",
    "validate_semantics": "scenariocraft.core.checks.structural",
    "write_runtime_check_results": "scenariocraft.core.checks.runtime_pipeline",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
