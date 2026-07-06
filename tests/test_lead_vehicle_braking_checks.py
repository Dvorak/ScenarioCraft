from dataclasses import replace

from scenariocraft.core.checks import run_lead_vehicle_braking_checks
from scenariocraft.core.schemas import Point2D, Pose2D, ScenarioIntent
from scenariocraft.core.templates import resolve_scenario_intent


def test_lead_vehicle_braking_checks_pass_for_default_family_instance() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))

    by_name = {result.name: result for result in run_lead_vehicle_braking_checks(spec)}

    assert by_name["lead_vehicle_same_lane_following"].passed is True
    assert by_name["lead_vehicle_initial_gap_in_domain"].passed is True
    assert by_name["lead_vehicle_braking_trigger_timing"].passed is True
    assert by_name["lead_vehicle_braking_semantics"].passed is True
    assert by_name["lead_vehicle_initial_gap_in_domain"].measured["initial_gap_m"] == 28.0
    assert by_name["lead_vehicle_braking_trigger_timing"].measured["trigger_time_s"] > 0.0


def test_lead_vehicle_braking_checks_report_lateral_or_behind_actor_mismatch() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="lead_vehicle_braking"))
    assert spec.layout is not None
    lateral_layout = replace(
        spec.layout,
        actor_poses={**spec.layout.actor_poses, "lead_vehicle": Pose2D(20.0, 3.5, 0.0)},
    )
    behind_layout = replace(
        spec.layout,
        actor_poses={**spec.layout.actor_poses, "lead_vehicle": Pose2D(-5.0, 0.0, 0.0)},
    )

    lateral = {result.name: result for result in run_lead_vehicle_braking_checks(replace(spec, layout=lateral_layout))}
    behind = {result.name: result for result in run_lead_vehicle_braking_checks(replace(spec, layout=behind_layout))}

    assert lateral["lead_vehicle_same_lane_following"].passed is False
    assert lateral["lead_vehicle_same_lane_following"].measured["lateral_offset_m"] == 3.5
    assert behind["lead_vehicle_same_lane_following"].passed is False
    assert behind["lead_vehicle_same_lane_following"].measured["longitudinal_gap_m"] == -5.0


def test_lead_vehicle_braking_checks_report_trigger_after_stop_window() -> None:
    spec = resolve_scenario_intent(
        ScenarioIntent(
            template_id="lead_vehicle_braking",
            parameters={"initial_gap_m": 35.0, "reaction_point_x_m": 8.0},
        )
    )
    assert spec.layout is not None
    layout = replace(
        spec.layout,
        points={**spec.layout.points, "reaction_point": Point2D(120.0, 0.0)},
    )

    by_name = {result.name: result for result in run_lead_vehicle_braking_checks(replace(spec, layout=layout))}

    assert by_name["lead_vehicle_braking_trigger_timing"].passed is False
    assert by_name["lead_vehicle_braking_trigger_timing"].measured["trigger_time_s"] > spec.timing.total_duration_s


def test_lead_vehicle_braking_checks_ignore_other_scenario_types() -> None:
    spec = resolve_scenario_intent(ScenarioIntent(template_id="pedestrian_occlusion"))

    assert run_lead_vehicle_braking_checks(spec) == ()
