from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scenariocraft.schemas.common import ScenarioSpecError, require_finite_number, require_non_empty


@dataclass(frozen=True)
class Point2D:
    x_m: float
    y_m: float

    def __post_init__(self) -> None:
        require_finite_number(self.x_m, "point.x_m")
        require_finite_number(self.y_m, "point.y_m")

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
        require_finite_number(self.x_m, "pose.x_m")
        require_finite_number(self.y_m, "pose.y_m")
        require_finite_number(self.heading_rad, "pose.heading_rad")

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
        require_non_empty(self.name, "path.name")
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
        length = require_finite_number(self.length_m, "footprint.length_m")
        width = require_finite_number(self.width_m, "footprint.width_m")
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
        require_non_empty(self.id, "road_band.id")
        require_non_empty(self.kind, f"road_band[{self.id}].kind")
        if self.kind not in {"sidewalk", "parking_strip", "driving_lane", "center_divider", "shoulder"}:
            raise ScenarioSpecError(f"road_band[{self.id}].kind is not supported.")
        y_min = require_finite_number(self.y_min_m, f"road_band[{self.id}].y_min_m")
        y_max = require_finite_number(self.y_max_m, f"road_band[{self.id}].y_max_m")
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
        require_non_empty(self.coordinate_frame, "layout.coordinate_frame")
        for actor_id, pose in self.actor_poses.items():
            require_non_empty(actor_id, "layout.actor_poses key")
            if not isinstance(pose, Pose2D):
                raise ScenarioSpecError(f"layout.actor_poses[{actor_id}] must be a Pose2D.")
        for path_name, path in self.paths.items():
            require_non_empty(path_name, "layout.paths key")
            if not isinstance(path, PathSpec):
                raise ScenarioSpecError(f"layout.paths[{path_name}] must be a PathSpec.")
        for point_name, point in self.points.items():
            require_non_empty(point_name, "layout.points key")
            if not isinstance(point, Point2D):
                raise ScenarioSpecError(f"layout.points[{point_name}] must be a Point2D.")
        for actor_id, footprint in self.actor_footprints.items():
            require_non_empty(actor_id, "layout.actor_footprints key")
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
        require_non_empty(self.relation_type, "spatial_relation.relation_type")
        require_non_empty(self.subject, "spatial_relation.subject")
        require_non_empty(self.object, "spatial_relation.object")

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
