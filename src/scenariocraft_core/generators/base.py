from __future__ import annotations

from abc import ABC, abstractmethod

from scenariocraft_core.schemas import ScenarioSpec


class ScenarioGenerator(ABC):
    @abstractmethod
    def generate_spec(self, scenario_text: str) -> ScenarioSpec:
        """Convert natural-language scenario text into a validated ScenarioSpec."""

    def repair_spec(
        self,
        scenario_text: str,
        current_spec: ScenarioSpec,
        validation_feedback: str,
    ) -> ScenarioSpec:
        return current_spec
