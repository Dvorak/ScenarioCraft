from scenariocraft.core.checks import run_family_checks
from scenariocraft.core.schemas import (
    ActorSpec,
    CriticalitySpec,
    RoadSpec,
    ScenarioIntent,
    ScenarioSpec,
    TriggerSpec,
    WeatherSpec,
)
from scenariocraft.core.templates import resolve_scenario_intent


def test_run_family_checks_dispatches_golden_family_checks() -> None:
    expected = {
        "pedestrian_occlusion": "ego_footprint_in_ego_lane",
        "lead_vehicle_braking": "lead_vehicle_same_lane_following",
        "cut_in": "cut_in_starts_in_adjacent_lane",
        "crossing_vehicle": "crossing_vehicle_path_crosses_ego_path",
        "oncoming_turn_across_path": "oncoming_turn_starts_opposite_ego",
    }

    for template_id, expected_check in expected.items():
        spec = resolve_scenario_intent(ScenarioIntent(template_id=template_id))
        result_names = {result.name for result in run_family_checks(spec)}

        assert expected_check in result_names


def test_run_family_checks_can_include_pedestrian_timing_checks() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="pedestrian_occlusion"))
    result_names = {result.name for result in run_family_checks(spec, include_timing=True)}

    assert "ego_lead_time_to_conflict_positive" in result_names


def test_run_family_checks_does_not_apply_pedestrian_checks_to_unknown_family() -> None:
    spec = ScenarioSpec(
        scenario_name="future_family",
        scenario_type="future_family",
        road=RoadSpec("urban_straight", 1, 50),
        weather=WeatherSpec(False, "dry"),
        actors=[ActorSpec("ego", "car", "ego", initial_speed_kph=35)],
        trigger=TriggerSpec("relative_distance", "ego", "ego", 18),
        intended_criticality=CriticalitySpec("near_miss", 1.5),
    )

    assert run_family_checks(spec) == ()
