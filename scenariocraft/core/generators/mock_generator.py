from __future__ import annotations

from scenariocraft.core.generators.base import ScenarioGenerator
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.core.templates import get_template


class MockScenarioGenerator(ScenarioGenerator):
    """Deterministic generator for the pedestrian occlusion scenario."""

    def generate_spec(self, scenario_text: str, **template_parameters: object) -> ScenarioSpec:
        template = get_template("pedestrian_occlusion")
        return template.instantiate(source_text=scenario_text, **template_parameters)
