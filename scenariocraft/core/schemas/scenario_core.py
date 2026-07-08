from __future__ import annotations

"""Core ScenarioSpec contract after template expansion.

ScenarioSpec is the semantic source of truth consumed by builders, previews,
checks, reports, and repair loops.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from scenariocraft.core.schemas.common import ScenarioSpecError, require_non_empty
from scenariocraft.core.schemas.layout_spec import LayoutSpec, SpatialRelationSpec
from scenariocraft.core.schemas.road_spec import RoadSpec, WeatherSpec
from scenariocraft.core.schemas.storyboard_spec import StoryboardSpec
from scenariocraft.core.schemas.timing_spec import ScenarioTimingSpec
from scenariocraft.core.schemas.trigger_spec import CriticalitySpec, TriggerSpec


@dataclass(frozen=True)
class ActorSpec:
    id: str
    type: str
    role: str
    initial_speed_kph: float | None = None
    speed_mps: float | None = None
    state: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.id, "actor.id")
        require_non_empty(self.type, f"actor[{self.id}].type")
        require_non_empty(self.role, f"actor[{self.id}].role")
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
        require_non_empty(self.scenario_name, "scenario_name")
        require_non_empty(self.scenario_type, "scenario_type")
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

    def metadata_section(self, key: str) -> dict[str, Any]:
        """Return a typed copy of a dict-valued metadata section.

        `metadata` remains the additive JSON extension slot for template and
        workflow annotations. Consumers should use this accessor instead of
        scattering shape checks across checks, builders, and renderers.
        """

        value = self.metadata.get(key)
        if isinstance(value, dict):
            return dict(value)
        return {}

    def family_metadata(self) -> dict[str, Any]:
        """Return metadata owned by this spec's scenario family."""

        return self.metadata_section(self.scenario_type)

    def template_resolution_metadata(self) -> dict[str, Any]:
        """Return resolver metadata without exposing raw metadata shape."""

        return self.metadata_section("template_resolution")

    def metadata_float(self, section: str, key: str, default: float | None = None) -> float | None:
        """Return a float from a metadata section, falling back on parse failure."""

        value = self.metadata_section(section).get(key)
        if value is None:
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def road_asset_id(self) -> str | None:
        """Return the canonical road asset id declared by template resolution."""

        value = self.metadata.get("road_asset_id")
        if isinstance(value, str) and value:
            return value
        return None

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
