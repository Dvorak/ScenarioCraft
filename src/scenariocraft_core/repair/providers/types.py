from __future__ import annotations

from dataclasses import dataclass

from scenariocraft_core.schemas import PatchSpec, ProbeResult, ScenarioSpec


class RepairProviderContractError(ValueError):
    """Raised when a repair provider request or proposal is invalid."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RepairProviderContractError(f"{field_name} must be a non-empty string.")
    return value


@dataclass(frozen=True)
class RepairRequest:
    user_intent: str | None
    scenario_spec: ScenarioSpec
    failed_probe_results: tuple[ProbeResult, ...]
    allowed_operation_types: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.user_intent is not None:
            _require_non_empty(self.user_intent, "user_intent")
        if not isinstance(self.scenario_spec, ScenarioSpec):
            raise RepairProviderContractError("scenario_spec must be a ScenarioSpec.")
        failed_results = tuple(self.failed_probe_results)
        for index, result in enumerate(failed_results):
            if not isinstance(result, ProbeResult):
                raise RepairProviderContractError(f"failed_probe_results[{index}] must be a ProbeResult.")
            if result.passed:
                raise RepairProviderContractError(f"failed_probe_results[{index}] must be a failed result.")
        allowed_types = tuple(self.allowed_operation_types)
        for index, operation_type in enumerate(allowed_types):
            _require_non_empty(operation_type, f"allowed_operation_types[{index}]")
        if len(allowed_types) != len(set(allowed_types)):
            raise RepairProviderContractError("allowed_operation_types must be unique.")
        object.__setattr__(self, "failed_probe_results", failed_results)
        object.__setattr__(self, "allowed_operation_types", allowed_types)


@dataclass(frozen=True)
class RepairProposal:
    patch: PatchSpec | None
    rationale: str
    provider_name: str

    def __post_init__(self) -> None:
        if self.patch is not None and not isinstance(self.patch, PatchSpec):
            raise RepairProviderContractError("patch must be a PatchSpec or None.")
        _require_non_empty(self.rationale, "rationale")
        _require_non_empty(self.provider_name, "provider_name")
