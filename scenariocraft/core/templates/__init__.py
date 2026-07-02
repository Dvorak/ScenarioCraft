from scenariocraft.core.templates.base import ScenarioTemplate
from scenariocraft.core.templates.defaults import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.templates.lead_vehicle_braking import LeadVehicleBrakingTemplate
from scenariocraft.core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate
from scenariocraft.core.templates.registry import get_template, registered_templates
from scenariocraft.core.templates.resolver import resolve_scenario_intent

__all__ = [
    "LeadVehicleBrakingTemplate",
    "PedestrianOcclusionTemplate",
    "ScenarioTemplate",
    "generate_default_pedestrian_occlusion_spec",
    "get_template",
    "registered_templates",
    "resolve_scenario_intent",
]
