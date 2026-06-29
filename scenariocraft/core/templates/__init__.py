from scenariocraft.core.templates.base import ScenarioTemplate
from scenariocraft.core.templates.pedestrian_occlusion import PedestrianOcclusionTemplate
from scenariocraft.core.templates.registry import get_template, registered_templates

__all__ = [
    "PedestrianOcclusionTemplate",
    "ScenarioTemplate",
    "get_template",
    "registered_templates",
]
