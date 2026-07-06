from __future__ import annotations

"""Resolve ScenarioIntent into ScenarioSpec through registered templates.

This module selects deterministic templates. It does not call providers,
generate XML, run checks, or validate repair success.
"""

from dataclasses import replace
from typing import Any

from scenariocraft.core.schemas import ScenarioIntent, ScenarioSpec
from scenariocraft.core.templates.capability import ResolvedParameter, ResolvedTemplateParameters
from scenariocraft.core.templates.registry import get_template


_SPECIAL_PARAMETER_KEYS = {"scenario_name", "source_text", "seed", "variant_index"}


def resolve_scenario_intent(
    intent: ScenarioIntent | dict[str, Any],
    *,
    seed: int | None = None,
    variant_index: int = 0,
) -> ScenarioSpec:
    scenario_intent = intent if isinstance(intent, ScenarioIntent) else ScenarioIntent.from_dict(intent)
    template = get_template(scenario_intent.template_id)
    resolved = resolve_template_parameters(
        scenario_intent,
        seed=seed,
        variant_index=variant_index,
    )
    parameters = {
        **resolved.values,
        "intent": scenario_intent,
    }
    for key in ("scenario_name", "source_text"):
        if key in scenario_intent.parameters:
            parameters[key] = scenario_intent.parameters[key]
    if "source_text" not in parameters and "source_text" in scenario_intent.metadata:
        parameters["source_text"] = scenario_intent.metadata["source_text"]
    spec = template.instantiate(**parameters)
    metadata = {
        **spec.metadata,
        "template_resolution": resolved.to_dict(),
        "template_capability": template.capability.to_dict(),
    }
    return replace(spec, metadata=metadata)


def resolve_template_parameters(
    intent: ScenarioIntent | dict[str, Any],
    *,
    seed: int | None = None,
    variant_index: int = 0,
) -> ResolvedTemplateParameters:
    scenario_intent = intent if isinstance(intent, ScenarioIntent) else ScenarioIntent.from_dict(intent)
    template = get_template(scenario_intent.template_id)
    domains = template.capability.domain_map()
    effective_seed = _effective_seed(scenario_intent, seed)
    sampled = effective_seed is not None
    values: dict[str, object] = {}
    resolved_parameters: list[ResolvedParameter] = []
    unsupported_fields = tuple(
        sorted(key for key in scenario_intent.parameters if key not in domains and key not in _SPECIAL_PARAMETER_KEYS)
    )

    for name, domain in domains.items():
        if name in scenario_intent.parameters:
            value = domain.validate(scenario_intent.parameters[name])
            source = "user"
        else:
            intent_value = _intent_value_for_parameter(scenario_intent, name)
            if intent_value is not None:
                value = domain.validate(intent_value)
                source = "intent"
            elif sampled:
                value = domain.validate(
                    domain.sample(seed=effective_seed, variant_index=variant_index, template_id=template.template_id)
                )
                source = "sampled"
            else:
                value = domain.validate(domain.default)
                source = "default"
        values[name] = value
        resolved_parameters.append(ResolvedParameter(name=name, value=value, source=source, unit=domain.unit))

    return ResolvedTemplateParameters(
        template_id=template.template_id,
        seed=effective_seed,
        variant_index=variant_index,
        sampled=sampled,
        values=values,
        parameters=tuple(resolved_parameters),
        unsupported_fields=unsupported_fields,
    )


def _effective_seed(intent: ScenarioIntent, seed: int | None) -> int | None:
    if seed is not None:
        return int(seed)
    if "seed" in intent.parameters:
        return int(intent.parameters["seed"])
    if "seed" in intent.metadata:
        return int(intent.metadata["seed"])
    return None


def _intent_value_for_parameter(intent: ScenarioIntent, name: str) -> object | None:
    if name == "ego_speed_kph":
        return intent.actor("ego").get("speed_kph")
    if name == "pedestrian_speed_mps":
        return (intent.actor("pedestrian") or intent.actor("crossing_actor")).get("speed_mps")
    if name == "lead_vehicle_speed_kph":
        return intent.actor("lead_vehicle").get("speed_kph")
    if name == "target_min_ttc_s":
        return intent.criticality.get("target_ttc_s")
    if name == "weather":
        return intent.weather.get("condition")
    return None
