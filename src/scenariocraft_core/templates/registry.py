from __future__ import annotations

from scenariocraft_core.templates.base import ScenarioTemplate
from scenariocraft_core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate


_TEMPLATES: dict[str, ScenarioTemplate] = {
    PedestrianOcclusionTemplate.template_id: PedestrianOcclusionTemplate(),
}


def registered_templates() -> dict[str, ScenarioTemplate]:
    return dict(_TEMPLATES)


def get_template(template_id: str) -> ScenarioTemplate:
    try:
        return _TEMPLATES[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario template: {template_id}") from exc
