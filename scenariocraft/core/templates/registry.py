from __future__ import annotations

from scenariocraft.core.templates.base import ScenarioTemplate
from scenariocraft.core.templates.crossing_vehicle import CrossingVehicleTemplate
from scenariocraft.core.templates.cut_in import CutInTemplate
from scenariocraft.core.templates.lead_vehicle_braking import LeadVehicleBrakingTemplate
from scenariocraft.core.templates.oncoming_turn_across_path import OncomingTurnAcrossPathTemplate
from scenariocraft.core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate


_TEMPLATES: dict[str, ScenarioTemplate] = {
    PedestrianOcclusionTemplate.template_id: PedestrianOcclusionTemplate(),
    LeadVehicleBrakingTemplate.template_id: LeadVehicleBrakingTemplate(),
    CutInTemplate.template_id: CutInTemplate(),
    CrossingVehicleTemplate.template_id: CrossingVehicleTemplate(),
    OncomingTurnAcrossPathTemplate.template_id: OncomingTurnAcrossPathTemplate(),
}


def registered_templates() -> dict[str, ScenarioTemplate]:
    return dict(_TEMPLATES)


def get_template(template_id: str) -> ScenarioTemplate:
    try:
        return _TEMPLATES[template_id]
    except KeyError as exc:
        raise ValueError(f"Unknown scenario template: {template_id}") from exc
