"""Compatibility exports for ScenarioSpec-related schema contracts.

New code should prefer semantic modules such as `scenario_core`, `layout_spec`,
`storyboard_spec`, `timing_spec`, `trigger_spec`, and `road_spec`. This module
keeps the historical `scenariocraft.schemas.scenario_spec` import path stable.
"""

from scenariocraft.schemas.common import ScenarioSpecError
from scenariocraft.schemas.layout_spec import (
    FootprintSpec,
    LayoutSpec,
    PathSpec,
    Point2D,
    Pose2D,
    RoadBandSpec,
    SpatialRelationSpec,
)
from scenariocraft.schemas.road_spec import RoadSpec, WeatherSpec
from scenariocraft.schemas.scenario_core import ActorSpec, ScenarioSpec
from scenariocraft.schemas.storyboard_spec import (
    StoryboardActionSpec,
    StoryboardActSpec,
    StoryboardEventSpec,
    StoryboardManeuverGroupSpec,
    StoryboardSpec,
    StoryboardStorySpec,
)
from scenariocraft.schemas.timing_spec import ScenarioTimingSpec
from scenariocraft.schemas.trigger_spec import CriticalitySpec, TriggerConditionSpec, TriggerSpec

__all__ = [
    "ActorSpec",
    "CriticalitySpec",
    "FootprintSpec",
    "LayoutSpec",
    "PathSpec",
    "Point2D",
    "Pose2D",
    "RoadBandSpec",
    "RoadSpec",
    "ScenarioSpec",
    "ScenarioSpecError",
    "ScenarioTimingSpec",
    "SpatialRelationSpec",
    "StoryboardActionSpec",
    "StoryboardActSpec",
    "StoryboardEventSpec",
    "StoryboardManeuverGroupSpec",
    "StoryboardSpec",
    "StoryboardStorySpec",
    "TriggerConditionSpec",
    "TriggerSpec",
    "WeatherSpec",
]
