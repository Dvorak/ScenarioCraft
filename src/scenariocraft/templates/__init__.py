from scenariocraft.templates.base import ScenarioTemplate
from scenariocraft.templates.pedestrian_occlusion import PedestrianOcclusionTemplate
from scenariocraft.templates.registry import get_template, registered_templates

__all__ = [
    "PedestrianOcclusionTemplate",
    "ScenarioTemplate",
    "get_template",
    "registered_templates",
]
