from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from scenariocraft_core.schemas import ScenarioSpec


@dataclass(frozen=True)
class SemanticCheck:
    name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class SemanticValidationResult:
    passed: bool
    checks: list[SemanticCheck]

    def to_dict(self) -> dict[str, object]:
        return {"passed": self.passed, "checks": [asdict(check) for check in self.checks]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def validate_semantics(spec: ScenarioSpec) -> SemanticValidationResult:
    ego = spec.actor_by_role("ego")
    occluder = spec.actor_by_role("occluder")
    pedestrian = spec.actor_by_role("crossing_actor")
    checks = [
        SemanticCheck("ego_vehicle_exists", ego is not None, "Ego vehicle is defined." if ego else "Ego vehicle is missing."),
        SemanticCheck(
            "occluding_vehicle_exists",
            occluder is not None,
            "Occluding vehicle is defined." if occluder else "Occluding vehicle is missing.",
        ),
        SemanticCheck(
            "pedestrian_exists",
            pedestrian is not None,
            "Pedestrian crossing actor is defined." if pedestrian else "Pedestrian crossing actor is missing.",
        ),
        SemanticCheck(
            "rainy_wet_weather",
            spec.weather.rain and spec.weather.road_condition.lower() == "wet",
            "Rainy wet weather is defined.",
        ),
        SemanticCheck("trigger_defined", spec.trigger is not None, "Trigger condition is defined."),
        SemanticCheck(
            "ego_speed_plausible",
            ego is not None and ego.initial_speed_kph is not None and 5 <= ego.initial_speed_kph <= spec.road.speed_limit_kph,
            "Ego speed is plausible for the road speed limit.",
        ),
        SemanticCheck(
            "pedestrian_speed_plausible",
            pedestrian is not None and pedestrian.speed_mps is not None and 0.5 <= pedestrian.speed_mps <= 3.0,
            "Pedestrian speed is plausible.",
        ),
        SemanticCheck(
            "intended_criticality_defined",
            spec.intended_criticality.target_min_ttc_s > 0,
            "Intended criticality is defined.",
        ),
        SemanticCheck(
            "trigger_actor_references_exist",
            spec.actor_by_id(spec.trigger.source) is not None and spec.actor_by_id(spec.trigger.target) is not None,
            "Trigger source and target actors exist.",
        ),
    ]
    return SemanticValidationResult(passed=all(check.passed for check in checks), checks=checks)
