from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class ProbeResultError(ValueError):
    """Raised when a ProbeResult cannot be validated."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProbeResultError(f"{field_name} must be a non-empty string.")
    return value


def _require_json_compatible(value: object, field_name: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ProbeResultError(f"{field_name} must be JSON-compatible.") from exc


@dataclass(frozen=True)
class ProbeResult:
    name: str
    passed: bool
    severity: str
    message: str
    measured: dict[str, object] = field(default_factory=dict)
    suggested_operations: tuple[dict[str, object], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "probe_result.name")
        _require_non_empty(self.message, "probe_result.message")
        if self.severity not in {"failure", "warning", "note"}:
            raise ProbeResultError("probe_result.severity must be failure, warning, or note.")
        if not isinstance(self.measured, dict):
            raise ProbeResultError("probe_result.measured must be a dict.")
        _require_json_compatible(self.measured, "probe_result.measured")
        for index, operation in enumerate(self.suggested_operations):
            if not isinstance(operation, dict):
                raise ProbeResultError(f"probe_result.suggested_operations[{index}] must be a dict.")
        _require_json_compatible(list(self.suggested_operations), "probe_result.suggested_operations")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
        }
        if self.measured:
            data["measured"] = self.measured
        if self.suggested_operations:
            data["suggested_operations"] = [dict(operation) for operation in self.suggested_operations]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProbeResult":
        return cls(
            name=str(data["name"]),
            passed=bool(data["passed"]),
            severity=str(data["severity"]),
            message=str(data["message"]),
            measured=dict(data.get("measured", {})),
            suggested_operations=tuple(dict(operation) for operation in data.get("suggested_operations", ())),
        )
