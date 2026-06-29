from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, ClassVar, Mapping, TypeAlias

from scenariocraft.schemas.scenario_spec import Point2D


class PatchSpecError(ValueError):
    """Raised when a PatchSpec or operation payload is invalid."""


def _require_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PatchSpecError(f"{field_name} must be a non-empty string.")
    return value


def _require_finite_number(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise PatchSpecError(f"{field_name} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise PatchSpecError(f"{field_name} must be a finite number.") from exc
    if not math.isfinite(number):
        raise PatchSpecError(f"{field_name} must be a finite number.")
    return number


@dataclass(frozen=True)
class SetActorPoseOperation:
    actor_id: str
    x_m: float
    y_m: float
    heading_rad: float

    op: ClassVar[str] = "set_actor_pose"

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _require_non_empty_string(self.actor_id, "actor_id"))
        object.__setattr__(self, "x_m", _require_finite_number(self.x_m, "x_m"))
        object.__setattr__(self, "y_m", _require_finite_number(self.y_m, "y_m"))
        object.__setattr__(self, "heading_rad", _require_finite_number(self.heading_rad, "heading_rad"))

    def to_dict(self) -> dict[str, object]:
        return {
            "op": self.op,
            "actor_id": self.actor_id,
            "x_m": self.x_m,
            "y_m": self.y_m,
            "heading_rad": self.heading_rad,
        }


@dataclass(frozen=True)
class RepositionActorToBandOperation:
    actor_id: str
    target_band_id: str

    op: ClassVar[str] = "reposition_actor_to_band"

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor_id", _require_non_empty_string(self.actor_id, "actor_id"))
        object.__setattr__(
            self,
            "target_band_id",
            _require_non_empty_string(self.target_band_id, "target_band_id"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "op": self.op,
            "actor_id": self.actor_id,
            "target_band_id": self.target_band_id,
        }


@dataclass(frozen=True)
class SetPathPointsOperation:
    path_id: str
    points: tuple[Point2D, ...]

    op: ClassVar[str] = "set_path_points"

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", _require_non_empty_string(self.path_id, "path_id"))
        points = tuple(self.points)
        if len(points) < 2:
            raise PatchSpecError("set_path_points.points must contain at least two points.")
        for index, point in enumerate(points):
            if not isinstance(point, Point2D):
                raise PatchSpecError(f"set_path_points.points[{index}] must be a Point2D.")
        object.__setattr__(self, "points", points)

    def to_dict(self) -> dict[str, object]:
        return {
            "op": self.op,
            "path_id": self.path_id,
            "points": [point.to_dict() for point in self.points],
        }


@dataclass(frozen=True)
class SetNamedPointOperation:
    point_id: str
    x_m: float
    y_m: float

    op: ClassVar[str] = "set_named_point"

    def __post_init__(self) -> None:
        object.__setattr__(self, "point_id", _require_non_empty_string(self.point_id, "point_id"))
        object.__setattr__(self, "x_m", _require_finite_number(self.x_m, "x_m"))
        object.__setattr__(self, "y_m", _require_finite_number(self.y_m, "y_m"))

    def to_dict(self) -> dict[str, object]:
        return {
            "op": self.op,
            "point_id": self.point_id,
            "x_m": self.x_m,
            "y_m": self.y_m,
        }


@dataclass(frozen=True)
class SetTriggerPointByLeadTimeOperation:
    point_id: str
    reference_point_id: str
    speed_source_actor_id: str
    lead_time_s: float

    op: ClassVar[str] = "set_trigger_point_by_lead_time"

    def __post_init__(self) -> None:
        object.__setattr__(self, "point_id", _require_non_empty_string(self.point_id, "point_id"))
        object.__setattr__(
            self,
            "reference_point_id",
            _require_non_empty_string(self.reference_point_id, "reference_point_id"),
        )
        object.__setattr__(
            self,
            "speed_source_actor_id",
            _require_non_empty_string(self.speed_source_actor_id, "speed_source_actor_id"),
        )
        lead_time_s = _require_finite_number(self.lead_time_s, "lead_time_s")
        if lead_time_s <= 0.0:
            raise PatchSpecError("lead_time_s must be positive.")
        object.__setattr__(self, "lead_time_s", lead_time_s)

    def to_dict(self) -> dict[str, object]:
        return {
            "op": self.op,
            "point_id": self.point_id,
            "reference_point_id": self.reference_point_id,
            "speed_source_actor_id": self.speed_source_actor_id,
            "lead_time_s": self.lead_time_s,
        }


PatchOperation: TypeAlias = (
    SetActorPoseOperation
    | RepositionActorToBandOperation
    | SetPathPointsOperation
    | SetNamedPointOperation
    | SetTriggerPointByLeadTimeOperation
)

_OPERATION_TYPES = (
    SetActorPoseOperation,
    RepositionActorToBandOperation,
    SetPathPointsOperation,
    SetNamedPointOperation,
    SetTriggerPointByLeadTimeOperation,
)


@dataclass(frozen=True)
class PatchSpec:
    operations: tuple[PatchOperation, ...]

    def __post_init__(self) -> None:
        operations = tuple(self.operations)
        if not operations:
            raise PatchSpecError("operations must contain at least one patch operation.")
        fingerprints: set[str] = set()
        for index, operation in enumerate(operations):
            if not isinstance(operation, _OPERATION_TYPES):
                raise PatchSpecError(f"operations[{index}] is not a supported patch operation.")
            fingerprint = json.dumps(operation.to_dict(), sort_keys=True)
            if fingerprint in fingerprints:
                raise PatchSpecError(f"operations[{index}] duplicates an earlier operation.")
            fingerprints.add(fingerprint)
        object.__setattr__(self, "operations", operations)

    def to_dict(self) -> dict[str, object]:
        return {"operations": [operation.to_dict() for operation in self.operations]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> "PatchSpec":
        _require_exact_fields(data, {"operations"}, "PatchSpec")
        raw_operations = data["operations"]
        if not isinstance(raw_operations, (list, tuple)):
            raise PatchSpecError("operations must be a list.")
        return cls(operations=tuple(_operation_from_dict(item, index) for index, item in enumerate(raw_operations)))

    @classmethod
    def from_json(cls, raw: str) -> "PatchSpec":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PatchSpecError("PatchSpec JSON is invalid.") from exc
        if not isinstance(data, dict):
            raise PatchSpecError("PatchSpec JSON must be an object.")
        return cls.from_dict(data)


def _operation_from_dict(value: object, index: int) -> PatchOperation:
    if not isinstance(value, Mapping):
        raise PatchSpecError(f"operations[{index}] must be an object.")
    op = _require_non_empty_string(value.get("op"), f"operations[{index}].op")
    canonical_op = "reposition_actor_to_band" if op == "reposition_actor" else op
    if canonical_op == "set_actor_pose":
        _require_exact_fields(value, {"op", "actor_id", "x_m", "y_m", "heading_rad"}, f"operations[{index}]")
        return SetActorPoseOperation(
            actor_id=value["actor_id"],
            x_m=value["x_m"],
            y_m=value["y_m"],
            heading_rad=value["heading_rad"],
        )
    if canonical_op == "reposition_actor_to_band":
        _require_exact_fields(value, {"op", "actor_id", "target_band_id"}, f"operations[{index}]")
        return RepositionActorToBandOperation(
            actor_id=value["actor_id"],
            target_band_id=value["target_band_id"],
        )
    if canonical_op == "set_path_points":
        _require_exact_fields(value, {"op", "path_id", "points"}, f"operations[{index}]")
        raw_points = value["points"]
        if not isinstance(raw_points, (list, tuple)):
            raise PatchSpecError(f"operations[{index}].points must be a list.")
        return SetPathPointsOperation(
            path_id=value["path_id"],
            points=tuple(_point_from_dict(point, index, point_index) for point_index, point in enumerate(raw_points)),
        )
    if canonical_op == "set_named_point":
        _require_exact_fields(value, {"op", "point_id", "x_m", "y_m"}, f"operations[{index}]")
        return SetNamedPointOperation(
            point_id=value["point_id"],
            x_m=value["x_m"],
            y_m=value["y_m"],
        )
    if canonical_op == "set_trigger_point_by_lead_time":
        _require_exact_fields(
            value,
            {"op", "point_id", "reference_point_id", "speed_source_actor_id", "lead_time_s"},
            f"operations[{index}]",
        )
        return SetTriggerPointByLeadTimeOperation(
            point_id=value["point_id"],
            reference_point_id=value["reference_point_id"],
            speed_source_actor_id=value["speed_source_actor_id"],
            lead_time_s=value["lead_time_s"],
        )
    raise PatchSpecError(f"Unknown patch operation: {op}.")


def _point_from_dict(value: object, operation_index: int, point_index: int) -> Point2D:
    field_name = f"operations[{operation_index}].points[{point_index}]"
    if not isinstance(value, Mapping):
        raise PatchSpecError(f"{field_name} must be an object.")
    _require_exact_fields(value, {"x_m", "y_m"}, field_name)
    return Point2D(
        x_m=_require_finite_number(value["x_m"], f"{field_name}.x_m"),
        y_m=_require_finite_number(value["y_m"], f"{field_name}.y_m"),
    )


def _require_exact_fields(data: Mapping[str, object], expected: set[str], field_name: str) -> None:
    actual = set(data)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    if missing:
        raise PatchSpecError(f"{field_name} is missing required fields: {', '.join(missing)}.")
    if extra:
        raise PatchSpecError(f"{field_name} has unsupported fields: {', '.join(extra)}.")
