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
class TriggerSpec:
    type: str
    source: str
    target: str
    distance_m: float

    def __post_init__(self) -> None:
        _require_non_empty(self.type, "trigger.type")
        _require_non_empty(self.source, "trigger.source")
        _require_non_empty(self.target, "trigger.target")
        if not 0.5 <= self.distance_m <= 500:
            raise ScenarioSpecError("trigger.distance_m must be between 0.5 and 500.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "source": self.source,
            "target": self.target,
            "distance_m": self.distance_m,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TriggerSpec":
        return cls(
            type=str(data["type"]),
            source=str(data["source"]),
            target=str(data["target"]),
            distance_m=float(data["distance_m"]),
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
        )

    @classmethod
    def from_json(cls, raw: str) -> "ScenarioSpec":
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ScenarioSpecError("ScenarioSpec JSON must be an object.")
        return cls.from_dict(loaded)
