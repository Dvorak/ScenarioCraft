from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class ScenarioSpecError(ValueError):
    """Raised when a ScenarioSpec cannot be validated."""


def _require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioSpecError(f"{field_name} must be a non-empty string.")
    return value


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
class ScenarioSpec:
    scenario_name: str
    scenario_type: str
    road: RoadSpec
    weather: WeatherSpec
    actors: list[ActorSpec]
    trigger: TriggerSpec
    intended_criticality: CriticalitySpec
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_non_empty(self.scenario_name, "scenario_name")
        _require_non_empty(self.scenario_type, "scenario_type")
        if not self.actors:
            raise ScenarioSpecError("actors must contain at least one actor.")
        ids = [actor.id for actor in self.actors]
        if len(ids) != len(set(ids)):
            raise ScenarioSpecError("actor ids must be unique.")

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
        )

    @classmethod
    def from_json(cls, raw: str) -> "ScenarioSpec":
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ScenarioSpecError("ScenarioSpec JSON must be an object.")
        return cls.from_dict(loaded)
