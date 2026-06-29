from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from typing import Any


class ScenarioSpecError(ValueError):
    """Raised when a ScenarioSpec cannot be validated."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioSpecError(f"{field_name} must be a non-empty string.")
    return value


def _require_finite_number(value: float, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ScenarioSpecError(f"{field_name} must be a finite number.")
    return number


@dataclass(frozen=True)
class RoadSpec:
    type: str
    lanes_per_direction: int
    speed_limit_kph: float

    def __post_init__(self) -> None:
        _require_non_empty(self.type, "road.type")
        if not 1 <= self.lanes_per_direction <= 5:
            raise ScenarioSpecError("road.lanes_per_direction must be between 1 and 5.")
        if not 5 <= self.speed_limit_kph <= 130:
            raise ScenarioSpecError("road.speed_limit_kph must be between 5 and 130.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "lanes_per_direction": self.lanes_per_direction,
            "speed_limit_kph": self.speed_limit_kph,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoadSpec":
        return cls(
            type=str(data["type"]),
            lanes_per_direction=int(data["lanes_per_direction"]),
            speed_limit_kph=float(data["speed_limit_kph"]),
        )


@dataclass(frozen=True)
class WeatherSpec:
    rain: bool
    road_condition: str

    def __post_init__(self) -> None:
        _require_non_empty(self.road_condition, "weather.road_condition")

    def to_dict(self) -> dict[str, Any]:
        return {"rain": self.rain, "road_condition": self.road_condition}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeatherSpec":
        return cls(rain=bool(data["rain"]), road_condition=str(data["road_condition"]))


@dataclass(frozen=True)
class ActorSpec:
    id: str
    type: str
    role: str
    initial_speed_kph: float | None = None
    speed_mps: float | None = None
    state: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "actor.id")
        _require_non_empty(self.type, f"actor[{self.id}].type")
        _require_non_empty(self.role, f"actor[{self.id}].role")
        if self.initial_speed_kph is not None and not 0 <= self.initial_speed_kph <= 160:
            raise ScenarioSpecError(f"actor[{self.id}].initial_speed_kph must be between 0 and 160.")
        if self.speed_mps is not None and not 0 <= self.speed_mps <= 15:
            raise ScenarioSpecError(f"actor[{self.id}].speed_mps must be between 0 and 15.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"id": self.id, "type": self.type, "role": self.role}
        if self.initial_speed_kph is not None:
            data["initial_speed_kph"] = self.initial_speed_kph
        if self.speed_mps is not None:
            data["speed_mps"] = self.speed_mps
        if self.state is not None:
            data["state"] = self.state
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActorSpec":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            role=str(data["role"]),
            initial_speed_kph=float(data["initial_speed_kph"]) if "initial_speed_kph" in data else None,
            speed_mps=float(data["speed_mps"]) if "speed_mps" in data else None,
            state=str(data["state"]) if "state" in data else None,
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
        _require_non_empty(self.id, "trigger.condition.id")
        if self.metric not in {"relative_distance", "time_to_collision", "time_headway", "simulation_time"}:
            raise ScenarioSpecError("trigger.condition.metric is not supported.")
        if self.source is not None:
            _require_non_empty(self.source, "trigger.condition.source")
        if self.target is not None:
            _require_non_empty(self.target, "trigger.condition.target")
        if self.rule not in {"lessThan", "greaterThan", "equalTo"}:
            raise ScenarioSpecError("trigger.condition.rule must be lessThan, greaterThan, or equalTo.")
        value = _require_non_negative_number(self.value, "trigger.condition.value")
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
            _require_non_empty(self.notes, "trigger.condition.notes")
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
        _require_non_empty(self.type, "trigger.type")
        _require_non_empty(self.source, "trigger.source")
        _require_non_empty(self.target, "trigger.target")
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
            condition=(
                TriggerConditionSpec.from_dict(data["condition"])
                if data.get("condition") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class CriticalitySpec:
    type: str
    target_min_ttc_s: float

    def __post_init__(self) -> None:
        _require_non_empty(self.type, "intended_criticality.type")
        if not 0.1 <= self.target_min_ttc_s <= 10:
            raise ScenarioSpecError("intended_criticality.target_min_ttc_s must be between 0.1 and 10.")

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "target_min_ttc_s": self.target_min_ttc_s}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CriticalitySpec":
        return cls(type=str(data["type"]), target_min_ttc_s=float(data["target_min_ttc_s"]))


@dataclass(frozen=True)
class ScenarioTimingSpec:
    total_duration_s: float = 8.0
    preferred_trigger_earliest_s: float = 1.5
    preferred_trigger_latest_s: float = 3.0
    minimum_pre_trigger_context_s: float = 0.5
    minimum_post_trigger_buffer_s: float = 0.5

    def __post_init__(self) -> None:
        total = _require_positive_number(self.total_duration_s, "timing.total_duration_s")
        earliest = _require_non_negative_number(
            self.preferred_trigger_earliest_s,
            "timing.preferred_trigger_earliest_s",
        )
        latest = _require_non_negative_number(
            self.preferred_trigger_latest_s,
            "timing.preferred_trigger_latest_s",
        )
        pre_context = _require_non_negative_number(
            self.minimum_pre_trigger_context_s,
            "timing.minimum_pre_trigger_context_s",
        )
        buffer = _require_non_negative_number(
            self.minimum_post_trigger_buffer_s,
            "timing.minimum_post_trigger_buffer_s",
        )
        if earliest > latest:
            raise ScenarioSpecError(
                "timing.preferred_trigger_earliest_s must be less than or equal to preferred_trigger_latest_s."
            )
        if latest >= total:
            raise ScenarioSpecError("timing.preferred_trigger_latest_s must be less than total_duration_s.")
        object.__setattr__(self, "total_duration_s", total)
        object.__setattr__(self, "preferred_trigger_earliest_s", earliest)
        object.__setattr__(self, "preferred_trigger_latest_s", latest)
        object.__setattr__(self, "minimum_pre_trigger_context_s", pre_context)
        object.__setattr__(self, "minimum_post_trigger_buffer_s", buffer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_duration_s": self.total_duration_s,
            "preferred_trigger_earliest_s": self.preferred_trigger_earliest_s,
            "preferred_trigger_latest_s": self.preferred_trigger_latest_s,
            "minimum_pre_trigger_context_s": self.minimum_pre_trigger_context_s,
            "minimum_post_trigger_buffer_s": self.minimum_post_trigger_buffer_s,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioTimingSpec":
        return cls(
            total_duration_s=float(data.get("total_duration_s", 8.0)),
            preferred_trigger_earliest_s=float(data.get("preferred_trigger_earliest_s", 1.5)),
            preferred_trigger_latest_s=float(data.get("preferred_trigger_latest_s", 3.0)),
            minimum_pre_trigger_context_s=float(data.get("minimum_pre_trigger_context_s", 0.5)),
            minimum_post_trigger_buffer_s=float(data.get("minimum_post_trigger_buffer_s", 0.5)),
        )


def _require_positive_number(value: float, field_name: str) -> float:
    number = _require_finite_number(value, field_name)
    if number <= 0:
        raise ScenarioSpecError(f"{field_name} must be positive.")
    return number


def _require_non_negative_number(value: float, field_name: str) -> float:
    number = _require_finite_number(value, field_name)
    if number < 0:
        raise ScenarioSpecError(f"{field_name} must be non-negative.")
    return number


@dataclass(frozen=True)
class Point2D:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        _require_finite_number(self.x_m, "point.x_m")
        _require_finite_number(self.y_m, "point.y_m")

    def to_dict(self) -> dict[str, Any]:
        return {"x_m": self.x_m, "y_m": self.y_m}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Point2D":
        return cls(x_m=float(data["x_m"]), y_m=float(data["y_m"]))


@dataclass(frozen=True)
class Pose2D:
    x_m: float
    y_m: float
    heading_rad: float = 0.0

    def __post_init__(self) -> None:
        _require_finite_number(self.x_m, "pose.x_m")
        _require_finite_number(self.y_m, "pose.y_m")
        _require_finite_number(self.heading_rad, "pose.heading_rad")

    def to_dict(self) -> dict[str, Any]:
        return {"x_m": self.x_m, "y_m": self.y_m, "heading_rad": self.heading_rad}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Pose2D":
        return cls(
            x_m=float(data["x_m"]),
            y_m=float(data["y_m"]),
            heading_rad=float(data.get("heading_rad", 0.0)),
        )


@dataclass(frozen=True)
class PathSpec:
    name: str
    points: tuple[Point2D, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.name, "path.name")
        if not self.points:
            raise ScenarioSpecError(f"path[{self.name}].points must contain at least one point.")
        for index, point in enumerate(self.points):
            if not isinstance(point, Point2D):
                raise ScenarioSpecError(f"path[{self.name}].points[{index}] must be a Point2D.")

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "points": [point.to_dict() for point in self.points]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PathSpec":
        return cls(
            name=str(data["name"]),
            points=tuple(Point2D.from_dict(point) for point in data["points"]),
        )


@dataclass(frozen=True)
class FootprintSpec:
    length_m: float
    width_m: float
    reference_point: str = "center"

    def __post_init__(self) -> None:
        length = _require_finite_number(self.length_m, "footprint.length_m")
        width = _require_finite_number(self.width_m, "footprint.width_m")
        if length <= 0:
            raise ScenarioSpecError("footprint.length_m must be greater than zero.")
        if width <= 0:
            raise ScenarioSpecError("footprint.width_m must be greater than zero.")
        if self.reference_point != "center":
            raise ScenarioSpecError("footprint.reference_point must be 'center'.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "length_m": self.length_m,
            "width_m": self.width_m,
            "reference_point": self.reference_point,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FootprintSpec":
        return cls(
            length_m=float(data["length_m"]),
            width_m=float(data["width_m"]),
            reference_point=str(data.get("reference_point", "center")),
        )


@dataclass(frozen=True)
class RoadBandSpec:
    id: str
    kind: str
    y_min_m: float
    y_max_m: float
    travel_direction: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "road_band.id")
        _require_non_empty(self.kind, f"road_band[{self.id}].kind")
        if self.kind not in {"sidewalk", "parking_strip", "driving_lane", "center_divider", "shoulder"}:
            raise ScenarioSpecError(f"road_band[{self.id}].kind is not supported.")
        y_min = _require_finite_number(self.y_min_m, f"road_band[{self.id}].y_min_m")
        y_max = _require_finite_number(self.y_max_m, f"road_band[{self.id}].y_max_m")
        if y_min >= y_max:
            raise ScenarioSpecError(f"road_band[{self.id}].y_min_m must be less than y_max_m.")
        if self.travel_direction not in {"+x", "-x", None}:
            raise ScenarioSpecError(f"road_band[{self.id}].travel_direction must be '+x', '-x', or None.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind,
            "y_min_m": self.y_min_m,
            "y_max_m": self.y_max_m,
        }
        if self.travel_direction is not None:
            data["travel_direction"] = self.travel_direction
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RoadBandSpec":
        return cls(
            id=str(data["id"]),
            kind=str(data["kind"]),
            y_min_m=float(data["y_min_m"]),
            y_max_m=float(data["y_max_m"]),
            travel_direction=str(data["travel_direction"]) if data.get("travel_direction") is not None else None,
        )


@dataclass(frozen=True)
class LayoutSpec:
    coordinate_frame: str
    actor_poses: dict[str, Pose2D]
    paths: dict[str, PathSpec]
    points: dict[str, Point2D]
    actor_footprints: dict[str, FootprintSpec] = field(default_factory=dict)
    road_bands: tuple[RoadBandSpec, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty(self.coordinate_frame, "layout.coordinate_frame")
        for actor_id, pose in self.actor_poses.items():
            _require_non_empty(actor_id, "layout.actor_poses key")
            if not isinstance(pose, Pose2D):
                raise ScenarioSpecError(f"layout.actor_poses[{actor_id}] must be a Pose2D.")
        for path_name, path in self.paths.items():
            _require_non_empty(path_name, "layout.paths key")
            if not isinstance(path, PathSpec):
                raise ScenarioSpecError(f"layout.paths[{path_name}] must be a PathSpec.")
        for point_name, point in self.points.items():
            _require_non_empty(point_name, "layout.points key")
            if not isinstance(point, Point2D):
                raise ScenarioSpecError(f"layout.points[{point_name}] must be a Point2D.")
        for actor_id, footprint in self.actor_footprints.items():
            _require_non_empty(actor_id, "layout.actor_footprints key")
            if not isinstance(footprint, FootprintSpec):
                raise ScenarioSpecError(f"layout.actor_footprints[{actor_id}] must be a FootprintSpec.")
        band_ids = [band.id for band in self.road_bands]
        if len(band_ids) != len(set(band_ids)):
            raise ScenarioSpecError("layout.road_bands ids must be unique.")
        for index, band in enumerate(self.road_bands):
            if not isinstance(band, RoadBandSpec):
                raise ScenarioSpecError(f"layout.road_bands[{index}] must be a RoadBandSpec.")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "coordinate_frame": self.coordinate_frame,
            "actor_poses": {actor_id: pose.to_dict() for actor_id, pose in self.actor_poses.items()},
            "paths": {path_name: path.to_dict() for path_name, path in self.paths.items()},
            "points": {point_name: point.to_dict() for point_name, point in self.points.items()},
        }
        if self.actor_footprints:
            data["actor_footprints"] = {
                actor_id: footprint.to_dict() for actor_id, footprint in self.actor_footprints.items()
            }
        if self.road_bands:
            data["road_bands"] = [band.to_dict() for band in self.road_bands]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayoutSpec":
        return cls(
            coordinate_frame=str(data["coordinate_frame"]),
            actor_poses={
                str(actor_id): Pose2D.from_dict(pose)
                for actor_id, pose in dict(data.get("actor_poses", {})).items()
            },
            paths={
                str(path_name): PathSpec.from_dict(path)
                for path_name, path in dict(data.get("paths", {})).items()
            },
            points={
                str(point_name): Point2D.from_dict(point)
                for point_name, point in dict(data.get("points", {})).items()
            },
            actor_footprints={
                str(actor_id): FootprintSpec.from_dict(footprint)
                for actor_id, footprint in dict(data.get("actor_footprints", {})).items()
            },
            road_bands=tuple(RoadBandSpec.from_dict(band) for band in data.get("road_bands", ())),
        )


@dataclass(frozen=True)
class SpatialRelationSpec:
    relation_type: str
    subject: str
    object: str
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.relation_type, "spatial_relation.relation_type")
        _require_non_empty(self.subject, "spatial_relation.subject")
        _require_non_empty(self.object, "spatial_relation.object")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "relation_type": self.relation_type,
            "subject": self.subject,
            "object": self.object,
        }
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpatialRelationSpec":
        return cls(
            relation_type=str(data["relation_type"]),
            subject=str(data["subject"]),
            object=str(data["object"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class StoryboardActionSpec:
    id: str
    type: str
    actor_refs: tuple[str, ...] = ()
    path_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "storyboard.action.id")
        _require_non_empty(self.type, f"storyboard.action[{self.id}].type")
        for actor_ref in self.actor_refs:
            _require_non_empty(actor_ref, f"storyboard.action[{self.id}].actor_refs")
        if self.path_ref is not None:
            _require_non_empty(self.path_ref, f"storyboard.action[{self.id}].path_ref")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "actor_refs": list(self.actor_refs),
        }
        if self.path_ref is not None:
            data["path_ref"] = self.path_ref
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardActionSpec":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            actor_refs=tuple(str(actor) for actor in data.get("actor_refs", ())),
            path_ref=str(data["path_ref"]) if data.get("path_ref") is not None else None,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class StoryboardEventSpec:
    id: str
    priority: str
    start_trigger_ref: str
    action_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "storyboard.event.id")
        _require_non_empty(self.priority, f"storyboard.event[{self.id}].priority")
        _require_non_empty(self.start_trigger_ref, f"storyboard.event[{self.id}].start_trigger_ref")
        if not self.action_refs:
            raise ScenarioSpecError(f"storyboard.event[{self.id}].action_refs must not be empty.")
        for action_ref in self.action_refs:
            _require_non_empty(action_ref, f"storyboard.event[{self.id}].action_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority,
            "start_trigger_ref": self.start_trigger_ref,
            "action_refs": list(self.action_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardEventSpec":
        return cls(
            id=str(data["id"]),
            priority=str(data["priority"]),
            start_trigger_ref=str(data["start_trigger_ref"]),
            action_refs=tuple(str(action) for action in data["action_refs"]),
        )


@dataclass(frozen=True)
class StoryboardManeuverGroupSpec:
    id: str
    actor_refs: tuple[str, ...]
    event_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "storyboard.maneuver_group.id")
        if not self.actor_refs:
            raise ScenarioSpecError(f"storyboard.maneuver_group[{self.id}].actor_refs must not be empty.")
        if not self.event_refs:
            raise ScenarioSpecError(f"storyboard.maneuver_group[{self.id}].event_refs must not be empty.")
        for actor_ref in self.actor_refs:
            _require_non_empty(actor_ref, f"storyboard.maneuver_group[{self.id}].actor_refs")
        for event_ref in self.event_refs:
            _require_non_empty(event_ref, f"storyboard.maneuver_group[{self.id}].event_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "actor_refs": list(self.actor_refs),
            "event_refs": list(self.event_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardManeuverGroupSpec":
        return cls(
            id=str(data["id"]),
            actor_refs=tuple(str(actor) for actor in data["actor_refs"]),
            event_refs=tuple(str(event) for event in data["event_refs"]),
        )


@dataclass(frozen=True)
class StoryboardActSpec:
    id: str
    maneuver_group_refs: tuple[str, ...]
    stop_trigger_ref: str | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "storyboard.act.id")
        if not self.maneuver_group_refs:
            raise ScenarioSpecError(f"storyboard.act[{self.id}].maneuver_group_refs must not be empty.")
        for maneuver_group_ref in self.maneuver_group_refs:
            _require_non_empty(maneuver_group_ref, f"storyboard.act[{self.id}].maneuver_group_refs")
        if self.stop_trigger_ref is not None:
            _require_non_empty(self.stop_trigger_ref, f"storyboard.act[{self.id}].stop_trigger_ref")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "maneuver_group_refs": list(self.maneuver_group_refs),
        }
        if self.stop_trigger_ref is not None:
            data["stop_trigger_ref"] = self.stop_trigger_ref
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardActSpec":
        return cls(
            id=str(data["id"]),
            maneuver_group_refs=tuple(str(group) for group in data["maneuver_group_refs"]),
            stop_trigger_ref=str(data["stop_trigger_ref"]) if data.get("stop_trigger_ref") is not None else None,
        )


@dataclass(frozen=True)
class StoryboardStorySpec:
    id: str
    act_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_non_empty(self.id, "storyboard.story.id")
        if not self.act_refs:
            raise ScenarioSpecError(f"storyboard.story[{self.id}].act_refs must not be empty.")
        for act_ref in self.act_refs:
            _require_non_empty(act_ref, f"storyboard.story[{self.id}].act_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "act_refs": list(self.act_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardStorySpec":
        return cls(
            id=str(data["id"]),
            act_refs=tuple(str(act) for act in data["act_refs"]),
        )


@dataclass(frozen=True)
class StoryboardSpec:
    stories: tuple[StoryboardStorySpec, ...]
    acts: tuple[StoryboardActSpec, ...]
    maneuver_groups: tuple[StoryboardManeuverGroupSpec, ...]
    events: tuple[StoryboardEventSpec, ...]
    actions: tuple[StoryboardActionSpec, ...]

    def __post_init__(self) -> None:
        _require_unique_ids("storyboard.stories", self.stories)
        _require_unique_ids("storyboard.acts", self.acts)
        _require_unique_ids("storyboard.maneuver_groups", self.maneuver_groups)
        _require_unique_ids("storyboard.events", self.events)
        _require_unique_ids("storyboard.actions", self.actions)
        action_ids = {action.id for action in self.actions}
        event_ids = {event.id for event in self.events}
        maneuver_group_ids = {group.id for group in self.maneuver_groups}
        act_ids = {act.id for act in self.acts}
        for event in self.events:
            for action_ref in event.action_refs:
                if action_ref not in action_ids:
                    raise ScenarioSpecError(f"storyboard.event[{event.id}] references unknown action {action_ref}.")
        for group in self.maneuver_groups:
            for event_ref in group.event_refs:
                if event_ref not in event_ids:
                    raise ScenarioSpecError(f"storyboard.maneuver_group[{group.id}] references unknown event {event_ref}.")
        for act in self.acts:
            for group_ref in act.maneuver_group_refs:
                if group_ref not in maneuver_group_ids:
                    raise ScenarioSpecError(f"storyboard.act[{act.id}] references unknown maneuver group {group_ref}.")
        for story in self.stories:
            for act_ref in story.act_refs:
                if act_ref not in act_ids:
                    raise ScenarioSpecError(f"storyboard.story[{story.id}] references unknown act {act_ref}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stories": [story.to_dict() for story in self.stories],
            "acts": [act.to_dict() for act in self.acts],
            "maneuver_groups": [group.to_dict() for group in self.maneuver_groups],
            "events": [event.to_dict() for event in self.events],
            "actions": [action.to_dict() for action in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardSpec":
        return cls(
            stories=tuple(StoryboardStorySpec.from_dict(story) for story in data.get("stories", ())),
            acts=tuple(StoryboardActSpec.from_dict(act) for act in data.get("acts", ())),
            maneuver_groups=tuple(
                StoryboardManeuverGroupSpec.from_dict(group)
                for group in data.get("maneuver_groups", ())
            ),
            events=tuple(StoryboardEventSpec.from_dict(event) for event in data.get("events", ())),
            actions=tuple(StoryboardActionSpec.from_dict(action) for action in data.get("actions", ())),
        )


def _require_unique_ids(field_name: str, items: tuple[object, ...]) -> None:
    ids = [getattr(item, "id", None) for item in items]
    if len(ids) != len(set(ids)):
        raise ScenarioSpecError(f"{field_name} ids must be unique.")


@dataclass(frozen=True)
class ScenarioSpec:
    scenario_name: str
    scenario_type: str
    road: RoadSpec
    weather: WeatherSpec
    actors: list[ActorSpec]
    trigger: TriggerSpec
    intended_criticality: CriticalitySpec
    metadata: dict[str, Any] = field(default_factory=dict)
    layout: LayoutSpec | None = None
    spatial_relations: tuple[SpatialRelationSpec, ...] = ()
    timing: ScenarioTimingSpec | None = None
    storyboard: StoryboardSpec | None = None

    def __post_init__(self) -> None:
        _require_non_empty(self.scenario_name, "scenario_name")
        _require_non_empty(self.scenario_type, "scenario_type")
        if not self.actors:
            raise ScenarioSpecError("actors must contain at least one actor.")
        ids = [actor.id for actor in self.actors]
        if len(ids) != len(set(ids)):
            raise ScenarioSpecError("actor ids must be unique.")
        if self.layout is not None and not isinstance(self.layout, LayoutSpec):
            raise ScenarioSpecError("layout must be a LayoutSpec or None.")
        if self.timing is not None and not isinstance(self.timing, ScenarioTimingSpec):
            raise ScenarioSpecError("timing must be a ScenarioTimingSpec or None.")
        if self.storyboard is not None and not isinstance(self.storyboard, StoryboardSpec):
            raise ScenarioSpecError("storyboard must be a StoryboardSpec or None.")
        for index, relation in enumerate(self.spatial_relations):
            if not isinstance(relation, SpatialRelationSpec):
                raise ScenarioSpecError(f"spatial_relations[{index}] must be a SpatialRelationSpec.")

    def actor_by_role(self, role: str) -> ActorSpec | None:
        return next((actor for actor in self.actors if actor.role == role), None)

    def actor_by_id(self, actor_id: str) -> ActorSpec | None:
        return next((actor for actor in self.actors if actor.id == actor_id), None)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "scenario_name": self.scenario_name,
            "scenario_type": self.scenario_type,
            "road": self.road.to_dict(),
            "weather": self.weather.to_dict(),
            "actors": [actor.to_dict() for actor in self.actors],
            "trigger": self.trigger.to_dict(),
            "intended_criticality": self.intended_criticality.to_dict(),
        }
        if self.metadata:
            data["metadata"] = self.metadata
        if self.layout is not None:
            data["layout"] = self.layout.to_dict()
        if self.spatial_relations:
            data["spatial_relations"] = [relation.to_dict() for relation in self.spatial_relations]
        if self.timing is not None:
            data["timing"] = self.timing.to_dict()
        if self.storyboard is not None:
            data["storyboard"] = self.storyboard.to_dict()
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioSpec":
        return cls(
            scenario_name=str(data["scenario_name"]),
            scenario_type=str(data["scenario_type"]),
            road=RoadSpec.from_dict(data["road"]),
            weather=WeatherSpec.from_dict(data["weather"]),
            actors=[ActorSpec.from_dict(actor) for actor in data["actors"]],
            trigger=TriggerSpec.from_dict(data["trigger"]),
            intended_criticality=CriticalitySpec.from_dict(data["intended_criticality"]),
            metadata=dict(data.get("metadata", {})),
            layout=LayoutSpec.from_dict(data["layout"]) if data.get("layout") is not None else None,
            spatial_relations=tuple(
                SpatialRelationSpec.from_dict(relation)
                for relation in data.get("spatial_relations", ())
            ),
            timing=ScenarioTimingSpec.from_dict(data["timing"]) if data.get("timing") is not None else None,
            storyboard=StoryboardSpec.from_dict(data["storyboard"]) if data.get("storyboard") is not None else None,
        )

    @classmethod
    def from_json(cls, raw: str) -> "ScenarioSpec":
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ScenarioSpecError("ScenarioSpec JSON must be an object.")
        return cls.from_dict(loaded)
