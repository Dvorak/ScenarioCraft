from __future__ import annotations

"""Default deterministic template entry points used by CLI, Web, and tests.

These helpers keep the mock/default path on the canonical ScenarioIntent ->
resolver -> ScenarioTemplate -> ScenarioSpec chain without reintroducing a
provider-style generator facade.
"""

from scenariocraft.core.schemas import ScenarioIntent, ScenarioSpec
from scenariocraft.core.templates.resolver import resolve_scenario_intent


def generate_default_pedestrian_occlusion_spec(
    scenario_text: str,
    **template_parameters: object,
) -> ScenarioSpec:
    return resolve_scenario_intent(
        ScenarioIntent(
            template_id="pedestrian_occlusion",
            metadata={"source_text": scenario_text},
            parameters=dict(template_parameters),
        )
    )
