from __future__ import annotations

from scenariocraft.core.templates.base import ScenarioTemplate
from scenariocraft.core.templates.lead_vehicle_braking import LeadVehicleBrakingTemplate
from scenariocraft.core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate


_TEMPLATES: dict[str, ScenarioTemplate] = {
    PedestrianOcclusionTemplate.template_id: PedestrianOcclusionTemplate(),
    LeadVehicleBrakingTemplate.template_id: LeadVehicleBrakingTemplate(),
}


def registered_templates() -> dict[str, ScenarioTemplate]:
    return dict(_TEMPLATES)


def get_template(template_id: str) -> ScenarioTemplate:
    try:
        return _TEMPLATES[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario template: {template_id}") from exc
