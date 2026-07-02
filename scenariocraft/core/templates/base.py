from __future__ import annotations

"""ScenarioTemplate protocol for deterministic scenario-family generators.

Templates expand typed intent or parameters into ScenarioSpec objects. They do
not parse natural language or generate XOSC/XODR artifacts.
"""

from typing import Mapping, Protocol

from scenariocraft.core.schemas import ScenarioSpec


class ScenarioTemplate(Protocol):
    template_id: str
    description: str
    required_actors: tuple[str, ...]
    default_parameters: Mapping[str, object]
    supported_operations: tuple[str, ...]

    def instantiate(self, **parameters: object) -> ScenarioSpec:
        """Instantiate this deterministic template as a ScenarioSpec."""
