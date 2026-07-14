from __future__ import annotations

"""Deterministic controlled scenario cases for Web and CLI smoke paths.

Controlled cases are normal golden-family examples. They are intentionally
separate from repair experiments, which inject faults and exercise PatchSpec.
"""

from dataclasses import dataclass

from scenariocraft.core.schemas import ScenarioIntent, ScenarioSpec
from scenariocraft.core.templates import resolve_scenario_intent


@dataclass(frozen=True)
class ControlledCase:
    case_id: str
    template_id: str
    display_name: str
    description: str
    seed: int
    source_text_variants: tuple[str, ...]

    @property
    def source_text(self) -> str:
        return self.source_text_variants[0]


CONTROLLED_CASES: tuple[ControlledCase, ...] = (
    ControlledCase(
        case_id="pedestrian_occlusion",
        template_id="pedestrian_occlusion",
        display_name="Pedestrian occlusion",
        description="Urban ego vehicle approaches an occluding parked van and a pedestrian crosses.",
        seed=101,
        source_text_variants=(
            "An urban pedestrian occlusion scenario with a pedestrian emerging from behind a parked van.",
            "Create a rainy city street scene where ego approaches a parked delivery van and a pedestrian steps out from behind it.",
            "A wet urban road with ego traveling past curbside parking while a hidden pedestrian crosses from the sidewalk.",
        ),
    ),
    ControlledCase(
        case_id="lead_vehicle_braking",
        template_id="lead_vehicle_braking",
        display_name="Lead vehicle braking",
        description="Urban same-lane following scenario where a lead vehicle brakes sharply.",
        seed=102,
        source_text_variants=(
            "An ego vehicle follows a lead vehicle in the city and the lead vehicle suddenly brakes.",
            "Create an urban same-lane following scenario where the car ahead brakes hard in front of ego.",
            "A straight urban road scenario with ego closing on a slower lead vehicle that performs a sharp braking maneuver.",
        ),
    ),
    ControlledCase(
        case_id="cut_in",
        template_id="cut_in",
        display_name="Cut-in",
        description="Multi-lane same-direction traffic with a vehicle cutting into the ego lane.",
        seed=103,
        source_text_variants=(
            "A vehicle in the adjacent lane cuts into the ego vehicle lane on an urban multilane road.",
            "Create a multilane urban traffic scene where another car merges sharply into ego's lane ahead.",
            "An adjacent vehicle moves laterally into the ego lane, creating a short-gap cut-in conflict.",
        ),
    ),
    ControlledCase(
        case_id="crossing_vehicle",
        template_id="crossing_vehicle",
        display_name="Crossing vehicle",
        description="Intersection scenario where cross traffic enters the ego path.",
        seed=104,
        source_text_variants=(
            "An ego vehicle approaches an intersection while a crossing vehicle enters its path.",
            "Create an urban intersection scenario where cross traffic drives through ego's intended path.",
            "A side vehicle crosses the conflict point at a four-way intersection as ego approaches.",
        ),
    ),
    ControlledCase(
        case_id="oncoming_turn_across_path",
        template_id="oncoming_turn_across_path",
        display_name="Oncoming turn across path",
        description="Intersection scenario where an oncoming vehicle turns across the ego path.",
        seed=1,
        source_text_variants=(
            "An oncoming vehicle turns left across the ego vehicle path at an urban intersection.",
            "Create a city intersection scenario where an oncoming car turns across ego's lane.",
            "An oncoming vehicle initiates a turn across the ego path near the intersection conflict point.",
        ),
    ),
)

_CONTROLLED_CASES_BY_ID = {case.case_id: case for case in CONTROLLED_CASES}


def controlled_case_options() -> tuple[tuple[str, str], ...]:
    return tuple((case.case_id, case.display_name) for case in CONTROLLED_CASES)


def controlled_case_prompt_variant(case_id: str, variant_index: int) -> str:
    case = get_controlled_case(case_id)
    variants = case.source_text_variants
    return variants[int(variant_index) % len(variants)]


def get_controlled_case(case_id: str) -> ControlledCase:
    try:
        return _CONTROLLED_CASES_BY_ID[case_id]
    except KeyError as exc:
        raise ValueError(f"Unknown controlled case: {case_id}.") from exc


def controlled_case_intent(case_id: str) -> ScenarioIntent:
    case = get_controlled_case(case_id)
    return ScenarioIntent(
        template_id=case.template_id,
        parameters={
            "seed": case.seed,
            "scenario_name": case.case_id,
            "source_text": case.source_text,
        },
        metadata={
            "source_text": case.source_text,
            "controlled_case_id": case.case_id,
            "controlled_case_display_name": case.display_name,
        },
    )


def instantiate_controlled_case(case_id: str) -> ScenarioSpec:
    return resolve_scenario_intent(controlled_case_intent(case_id))
