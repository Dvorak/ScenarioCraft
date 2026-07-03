from __future__ import annotations

"""CheckResult validation-evidence contract.

CheckResult is the current compatibility shape for scenario check evidence.
Checks return measured evidence and optional PatchSpec-compatible suggestions;
they do not apply repair or call providers.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from scenariocraft.core.checks.constants import (
    CHECK_CATEGORIES,
    CHECK_SEVERITIES,
    INTENT_RELATIONS,
    LEGACY_SEVERITIES,
    REPAIR_ACTIONS,
)


class CheckResultError(ValueError):
    """Raised when a CheckResult cannot be validated."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckResultError(f"{field_name} must be a non-empty string.")
    return value


def _require_json_compatible(value: object, field_name: str) -> None:
    try:
        json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise CheckResultError(f"{field_name} must be JSON-compatible.") from exc


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    severity: str
    message: str
    category: str = "unknown"
    intent_relation: str = "unknown"
    repair_action: str | None = None
    expected: dict[str, object] | None = None
    measured: dict[str, object] = field(default_factory=dict)
    suggested_operations: tuple[dict[str, object], ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "check_result.name")
        _require_non_empty(self.message, "check_result.message")
        if self.severity not in CHECK_SEVERITIES | LEGACY_SEVERITIES:
            raise CheckResultError("check_result.severity must be blocking, repairable, warning, failure, or note.")
        if self.category not in CHECK_CATEGORIES:
            raise CheckResultError("check_result.category is not supported.")
        if self.intent_relation not in INTENT_RELATIONS:
            raise CheckResultError("check_result.intent_relation is not supported.")
        if self.repair_action is not None and self.repair_action not in REPAIR_ACTIONS:
            raise CheckResultError("check_result.repair_action is not supported.")
        if self.expected is not None and not isinstance(self.expected, dict):
            raise CheckResultError("check_result.expected must be a dict or None.")
        _require_json_compatible(self.expected, "check_result.expected")
        if not isinstance(self.measured, dict):
            raise CheckResultError("check_result.measured must be a dict.")
        _require_json_compatible(self.measured, "check_result.measured")
        for index, operation in enumerate(self.suggested_operations):
            if not isinstance(operation, dict):
                raise CheckResultError(f"check_result.suggested_operations[{index}] must be a dict.")
        _require_json_compatible(list(self.suggested_operations), "check_result.suggested_operations")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "passed": self.passed,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "intent_relation": self.intent_relation,
        }
        if self.repair_action is not None:
            data["repair_action"] = self.repair_action
        if self.expected is not None:
            data["expected"] = self.expected
        if self.measured:
            data["measured"] = self.measured
        if self.suggested_operations:
            data["suggested_operations"] = [dict(operation) for operation in self.suggested_operations]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckResult":
        return cls(
            name=str(data["name"]),
            passed=bool(data["passed"]),
            severity=str(data.get("severity", "warning")),
            message=str(data["message"]),
            category=str(data.get("category", "unknown")),
            intent_relation=str(data.get("intent_relation", "unknown")),
            repair_action=None if data.get("repair_action") is None else str(data["repair_action"]),
            expected=None if data.get("expected") is None else dict(data["expected"]),
            measured=dict(data.get("measured", {})),
            suggested_operations=tuple(dict(operation) for operation in data.get("suggested_operations", ())),
        )
