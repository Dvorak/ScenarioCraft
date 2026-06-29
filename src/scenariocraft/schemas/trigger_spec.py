from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scenariocraft.schemas.common import (
    ScenarioSpecError,
    require_non_empty,
    require_non_negative_number,
)


@dataclass(frozen=True)
class TriggerConditionSpec:
    id: str
    metric: str
    source: str | None
    target: str | None
    rule: str
    value: float
    unit: str
    coordinate_system: str | None = None
    relative_distance_type: str | None = None
    freespace: bool | None = None
    target_kind: str = "entity"
    notes: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.id, "trigger.condition.id")
        if self.metric not in {"relative_distance", "time_to_collision", "time_headway", "simulation_time"}:
            raise ScenarioSpecError("trigger.condition.metric is not supported.")
        if self.source is not None:
            require_non_empty(self.source, "trigger.condition.source")
        if self.target is not None:
            require_non_empty(self.target, "trigger.condition.target")
        if self.rule not in {"lessThan", "greaterThan", "equalTo"}:
            raise ScenarioSpecError("trigger.condition.rule must be lessThan, greaterThan, or equalTo.")
        value = require_non_negative_number(self.value, "trigger.condition.value")
        if self.unit not in {"m", "s"}:
            raise ScenarioSpecError("trigger.condition.unit must be 'm' or 's'.")
        if self.coordinate_system is not None and self.coordinate_system not in {"entity", "road", "lane", "trajectory"}:
            raise ScenarioSpecError("trigger.condition.coordinate_system is not supported.")
        if self.relative_distance_type is not None and self.relative_distance_type not in {
            "cartesianDistance",
            "euclidianDistance",
            "longitudinal",
            "lateral",
        }:
            raise ScenarioSpecError("trigger.condition.relative_distance_type is not supported.")
        if self.target_kind not in {"entity", "named_point", "path_position", "simulation_time"}:
            raise ScenarioSpecError("trigger.condition.target_kind is not supported.")
        if self.notes is not None:
            require_non_empty(self.notes, "trigger.condition.notes")
        object.__setattr__(self, "value", value)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "metric": self.metric,
            "rule": self.rule,
            "value": self.value,
            "unit": self.unit,
            "target_kind": self.target_kind,
        }
        if self.source is not None:
            data["source"] = self.source
        if self.target is not None:
            data["target"] = self.target
        if self.coordinate_system is not None:
            data["coordinate_system"] = self.coordinate_system
        if self.relative_distance_type is not None:
            data["relative_distance_type"] = self.relative_distance_type
        if self.freespace is not None:
            data["freespace"] = self.freespace
        if self.notes is not None:
            data["notes"] = self.notes
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerConditionSpec":
        return cls(
            id=str(data["id"]),
            metric=str(data["metric"]),
            source=str(data["source"]) if data.get("source") is not None else None,
            target=str(data["target"]) if data.get("target") is not None else None,
            rule=str(data["rule"]),
            value=float(data["value"]),
            unit=str(data["unit"]),
            coordinate_system=str(data["coordinate_system"]) if data.get("coordinate_system") is not None else None,
            relative_distance_type=(
                str(data["relative_distance_type"]) if data.get("relative_distance_type") is not None else None
            ),
            freespace=bool(data["freespace"]) if data.get("freespace") is not None else None,
            target_kind=str(data.get("target_kind", "entity")),
            notes=str(data["notes"]) if data.get("notes") is not None else None,
        )


@dataclass(frozen=True)
class TriggerSpec:
    type: str
    source: str
    target: str
    distance_m: float
    condition: TriggerConditionSpec | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.type, "trigger.type")
        require_non_empty(self.source, "trigger.source")
        require_non_empty(self.target, "trigger.target")
        if not 0.5 <= self.distance_m <= 500:
            raise ScenarioSpecError("trigger.distance_m must be between 0.5 and 500.")
        if self.condition is not None and not isinstance(self.condition, TriggerConditionSpec):
            raise ScenarioSpecError("trigger.condition must be a TriggerConditionSpec or None.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "distance_m": self.distance_m,
        }
        if self.condition is not None:
            data["condition"] = self.condition.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerSpec":
        return cls(
            type=str(data["type"]),
            source=str(data["source"]),
            target=str(data["target"]),
            distance_m=float(data["distance_m"]),
            condition=TriggerConditionSpec.from_dict(data["condition"]) if data.get("condition") is not None else None,
        )


@dataclass(frozen=True)
class CriticalitySpec:
    type: str
    target_min_ttc_s: float

    def __post_init__(self) -> None:
        require_non_empty(self.type, "intended_criticality.type")
        if not 0.1 <= self.target_min_ttc_s <= 10:
            raise ScenarioSpecError("intended_criticality.target_min_ttc_s must be between 0.1 and 10.")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "target_min_ttc_s": self.target_min_ttc_s}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticalitySpec":
        return cls(type=str(data["type"]), target_min_ttc_s=float(data["target_min_ttc_s"]))
