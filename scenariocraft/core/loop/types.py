from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from scenariocraft.core.schemas import PatchSpec, ProbeResult, ScenarioSpec


TerminalStatus: TypeAlias = Literal[
    "passed",
    "provider_refused",
    "patch_application_failed",
    "geometry_validation_failed",
    "artifact_validation_failed",
    "max_rounds_reached",
    "unsupported_scenario",
    "build_failed",
]


@dataclass(frozen=True)
class RepairRoundTrace:
    round_index: int
    input_probe_results: tuple[ProbeResult, ...]
    allowed_operation_types: tuple[str, ...]
    provider_name: str
    proposal_rationale: str
    proposed_patch: PatchSpec | None
    patch_applied: bool
    application_error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "round_index": self.round_index,
            "input_probe_results": [result.to_dict() for result in self.input_probe_results],
            "allowed_operation_types": list(self.allowed_operation_types),
            "provider_name": self.provider_name,
            "proposal_rationale": self.proposal_rationale,
            "proposed_patch": self.proposed_patch.to_dict() if self.proposed_patch is not None else None,
            "patch_applied": self.patch_applied,
            "application_error": self.application_error,
        }


@dataclass(frozen=True)
class RepairRunResult:
    initial_spec: ScenarioSpec
    final_spec: ScenarioSpec
    rounds: tuple[RepairRoundTrace, ...]
    final_geometry_probe_results: tuple[ProbeResult, ...]
    final_artifact_probe_results: tuple[ProbeResult, ...]
    terminal_status: TerminalStatus
    terminal_reason: str
    xosc_path: Path | None = None
    xodr_path: Path | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "initial_spec": self.initial_spec.to_dict(),
            "final_spec": self.final_spec.to_dict(),
            "rounds": [round_trace.to_dict() for round_trace in self.rounds],
            "final_geometry_probe_results": [
                result.to_dict() for result in self.final_geometry_probe_results
            ],
            "final_artifact_probe_results": [
                result.to_dict() for result in self.final_artifact_probe_results
            ],
            "terminal_status": self.terminal_status,
            "terminal_reason": self.terminal_reason,
            "xosc_path": str(self.xosc_path) if self.xosc_path is not None else None,
            "xodr_path": str(self.xodr_path) if self.xodr_path is not None else None,
        }
