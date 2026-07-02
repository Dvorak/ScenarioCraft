from __future__ import annotations

"""Structured scenario intent before deterministic template expansion.

LLM or local providers may propose this contract, but templates remain
responsible for producing complete ScenarioSpec objects.
"""

import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from scenariocraft.core.schemas.common import require_non_empty


class ScenarioIntentError(ValueError):
    """Raised when a ScenarioIntent payload cannot be validated."""


_ALLOWED_FIELDS = {"template_id", "road_context", "weather", "actors", "criticality", "parameters", "metadata"}


def _require_mapping(value: object, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ScenarioIntentError(f"{field_name} must be an object.")
    return dict(value)


def _json_compatible(value: object, field_name: str) -> object:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ScenarioIntentError(f"{field_name} must be JSON-compatible.") from exc
    return value


@dataclass(frozen=True)
class ScenarioIntent:
    template_id: str
    road_context: dict[str, Any] = field(default_factory=dict)
    weather: dict[str, Any] = field(default_factory=dict)
    actors: dict[str, dict[str, Any]] = field(default_factory=dict)
    criticality: dict[str, Any] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            require_non_empty(self.template_id, "template_id")
        except ValueError as exc:
            raise ScenarioIntentError(str(exc)) from exc
        object.__setattr__(self, "road_context", _require_mapping(self.road_context, "road_context"))
        object.__setattr__(self, "weather", _require_mapping(self.weather, "weather"))
        object.__setattr__(self, "criticality", _require_mapping(self.criticality, "criticality"))
        object.__setattr__(self, "parameters", _require_mapping(self.parameters, "parameters"))
        object.__setattr__(self, "metadata", _require_mapping(self.metadata, "metadata"))
        actors = _require_mapping(self.actors, "actors")
        normalized_actors: dict[str, dict[str, Any]] = {}
        for actor_role, actor_payload in actors.items():
            try:
                role = require_non_empty(str(actor_role), "actors key")
            except ValueError as exc:
                raise ScenarioIntentError(str(exc)) from exc
            normalized_actors[role] = _require_mapping(actor_payload, f"actors[{role}]")
        object.__setattr__(self, "actors", normalized_actors)
        _json_compatible(self.to_dict(), "ScenarioIntent")

    def actor(self, role: str) -> dict[str, Any]:
        return dict(self.actors.get(role, {}))

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {"template_id": self.template_id}
        if self.road_context:
            data["road_context"] = dict(self.road_context)
        if self.weather:
            data["weather"] = dict(self.weather)
        if self.actors:
            data["actors"] = {role: dict(payload) for role, payload in self.actors.items()}
        if self.criticality:
            data["criticality"] = dict(self.criticality)
        if self.parameters:
            data["parameters"] = dict(self.parameters)
        if self.metadata:
            data["metadata"] = dict(self.metadata)
        return data

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioIntent":
        if not isinstance(data, Mapping):
            raise ScenarioIntentError("ScenarioIntent must be an object.")
        unknown = set(data) - _ALLOWED_FIELDS
        if unknown:
            raise ScenarioIntentError(f"Unknown ScenarioIntent field(s): {', '.join(sorted(unknown))}.")
        if "template_id" not in data:
            raise ScenarioIntentError("template_id is required.")
        return cls(
            template_id=str(data["template_id"]),
            road_context=_require_mapping(data.get("road_context", {}), "road_context"),
            weather=_require_mapping(data.get("weather", {}), "weather"),
            actors=_require_mapping(data.get("actors", {}), "actors"),
            criticality=_require_mapping(data.get("criticality", {}), "criticality"),
            parameters=_require_mapping(data.get("parameters", {}), "parameters"),
            metadata=_require_mapping(data.get("metadata", {}), "metadata"),
        )

    @classmethod
    def from_json(cls, raw: str) -> "ScenarioIntent":
        loaded = json.loads(raw)
        if not isinstance(loaded, dict):
            raise ScenarioIntentError("ScenarioIntent JSON must be an object.")
        return cls.from_dict(loaded)
