from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scenariocraft_core.schemas.common import ScenarioSpecError, require_non_empty


@dataclass(frozen=True)
class RoadSpec:
    type: str
    lanes_per_direction: int
    speed_limit_kph: float

    def __post_init__(self) -> None:
        require_non_empty(self.type, "road.type")
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
        require_non_empty(self.road_condition, "weather.road_condition")

    def to_dict(self) -> dict[str, Any]:
        return {"rain": self.rain, "road_condition": self.road_condition}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeatherSpec":
        return cls(rain=bool(data["rain"]), road_condition=str(data["road_condition"]))
