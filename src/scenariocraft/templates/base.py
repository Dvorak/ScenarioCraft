from __future__ import annotations

from typing import Mapping, Protocol

from scenariocraft.schemas import ScenarioSpec


class ScenarioTemplate(Protocol):
    template_id: str
    description: str
    required_actors: tuple[str, ...]
    default_parameters: Mapping[str, object]
    supported_operations: tuple[str, ...]

    def instantiate(self, **parameters: object) -> ScenarioSpec:
        """Instantiate this deterministic template as a ScenarioSpec."""
