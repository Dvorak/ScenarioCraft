from scenariocraft.core.templates.base import ScenarioTemplate
from scenariocraft.core.templates.capability import (
    ParameterDomain,
    ResolvedParameter,
    ResolvedTemplateParameters,
    TemplateCapability,
)
from scenariocraft.core.templates.defaults import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.templates.family_taxonomy import (
    FamilyDeclaration,
    FamilyStatus,
    executable_family_ids,
    family_declaration,
    family_declarations,
    planned_family_ids,
)
from scenariocraft.core.templates.lead_vehicle_braking import LeadVehicleBrakingTemplate
from scenariocraft.core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate
from scenariocraft.core.templates.registry import get_template, registered_templates
from scenariocraft.core.templates.resolver import resolve_scenario_intent, resolve_template_parameters

__all__ = [
    "LeadVehicleBrakingTemplate",
    "ParameterDomain",
    "PedestrianOcclusionTemplate",
    "ResolvedParameter",
    "ResolvedTemplateParameters",
    "ScenarioTemplate",
    "TemplateCapability",
    "FamilyDeclaration",
    "FamilyStatus",
    "executable_family_ids",
    "family_declaration",
    "family_declarations",
    "generate_default_pedestrian_occlusion_spec",
    "get_template",
    "planned_family_ids",
    "registered_templates",
    "resolve_scenario_intent",
    "resolve_template_parameters",
]
