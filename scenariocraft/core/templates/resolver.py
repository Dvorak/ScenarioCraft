from __future__ import annotations

"""Resolve ScenarioIntent into ScenarioSpec through registered templates.

This module selects deterministic templates. It does not call providers,
generate XML, run probes, or validate repair success.
"""

from typing import Any

from scenariocraft.core.schemas import ScenarioIntent, ScenarioSpec
from scenariocraft.core.templates.registry import get_template


def resolve_scenario_intent(intent: ScenarioIntent | dict[str, Any]) -> ScenarioSpec:
    scenario_intent = intent if isinstance(intent, ScenarioIntent) else ScenarioIntent.from_dict(intent)
    template = get_template(scenario_intent.template_id)
    parameters = {
        **scenario_intent.parameters,
        "intent": scenario_intent,
    }
    if "source_text" not in parameters and "source_text" in scenario_intent.metadata:
        parameters["source_text"] = scenario_intent.metadata["source_text"]
    return template.instantiate(**parameters)
