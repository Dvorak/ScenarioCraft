from dataclasses import replace

from scenariocraft.core.generators import MockScenarioGenerator
from scenariocraft.core.probes import run_time_headway_probes
from scenariocraft.core.schemas import ActorSpec, Pose2D, TriggerConditionSpec, TriggerSpec
from scenariocraft.core.metrics import compute_timing_metrics, time_headway_s


def test_time_headway_metric_computes_for_same_lane_lead_actor() -> None:
    spec = _time_headway_spec(lead_x_m=25.0, lead_y_m=0.0, rule="greaterThan", threshold_s=2.0)

    metrics = compute_timing_metrics(spec)
    results = run_time_headway_probes(spec)

    assert metrics.time_headway_s == 25.0 / (35.0 / 3.6)
    assert time_headway_s(spec) == metrics.time_headway_s
    assert [result.name for result in results] == [
        "time_headway_computable",
        "time_headway_condition_matches_rule",
        "time_headway_metric_not_ttc",
    ]
    assert all(result.passed for result in results)
    assert results[0].measured["source_actor_id"] == "ego"
    assert results[0].measured["target_actor_id"] == "lead_vehicle"


def test_time_headway_probe_reports_condition_rule_mismatch() -> None:
    spec = _time_headway_spec(lead_x_m=25.0, lead_y_m=0.0, rule="lessThan", threshold_s=2.0)

    by_name = {result.name: result for result in run_time_headway_probes(spec)}

    assert by_name["time_headway_computable"].passed is True
    assert by_name["time_headway_condition_matches_rule"].passed is False
    assert by_name["time_headway_condition_matches_rule"].severity == "warning"
    assert by_name["time_headway_condition_matches_rule"].measured["time_headway_s"] > 2.0


def test_time_headway_requires_same_lane_positive_lead_gap() -> None:
    lateral_spec = _time_headway_spec(lead_x_m=25.0, lead_y_m=3.25, rule="greaterThan", threshold_s=2.0)
    behind_spec = _time_headway_spec(lead_x_m=-5.0, lead_y_m=0.0, rule="greaterThan", threshold_s=2.0)

    lateral = {result.name: result for result in run_time_headway_probes(lateral_spec)}
    behind = {result.name: result for result in run_time_headway_probes(behind_spec)}

    assert lateral["time_headway_computable"].passed is False
    assert lateral["time_headway_computable"].measured["lateral_offset_m"] == 3.25
    assert behind["time_headway_computable"].passed is False
    assert behind["time_headway_computable"].measured["longitudinal_gap_m"] == -5.0


def test_time_headway_probes_are_absent_for_non_thw_trigger_conditions() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    assert run_time_headway_probes(spec) == ()


def test_time_headway_layout_free_spec_reports_unavailable_without_crashing() -> None:
    spec = replace(_time_headway_spec(lead_x_m=25.0, lead_y_m=0.0), layout=None, spatial_relations=())

    by_name = {result.name: result for result in run_time_headway_probes(spec)}

    assert by_name["time_headway_computable"].passed is False
    assert by_name["time_headway_computable"].measured["time_headway_s"] is None


def _time_headway_spec(
    *,
    lead_x_m: float,
    lead_y_m: float,
    rule: str = "greaterThan",
    threshold_s: float = 2.0,
):
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    lead_actor = ActorSpec("lead_vehicle", "car", "lead_vehicle", initial_speed_kph=25.0)
    actors = tuple(spec.actors) + (lead_actor,)
    actor_poses = {
        **spec.layout.actor_poses,
        "lead_vehicle": Pose2D(lead_x_m, lead_y_m, 0.0),
    }
    layout = replace(spec.layout, actor_poses=actor_poses)
    trigger = TriggerSpec(
        type="time_headway",
        source="ego",
        target="lead_vehicle",
        distance_m=spec.trigger.distance_m,
        condition=TriggerConditionSpec(
            id="ego_time_headway_to_lead_vehicle",
            metric="time_headway",
            source="ego",
            target="lead_vehicle",
            rule=rule,
            value=threshold_s,
            unit="s",
            target_kind="entity",
        ),
    )
    return replace(spec, actors=actors, layout=layout, trigger=trigger, scenario_type="car_following")
