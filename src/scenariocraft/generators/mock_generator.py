from __future__ import annotations

from scenariocraft.generators.base import ScenarioGenerator
from scenariocraft.schemas import ScenarioSpec
from scenariocraft.templates import get_template


class MockScenarioGenerator(ScenarioGenerator):
    """Deterministic generator for the pedestrian occlusion scenario."""

    def generate_spec(self, scenario_text: str) -> ScenarioSpec:
        template = get_template("pedestrian_occlusion")
        return template.instantiate(source_text=scenario_text)
