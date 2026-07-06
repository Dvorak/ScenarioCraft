from __future__ import annotations

"""Family checks for same-lane lead-vehicle-braking scenarios."""

from scenariocraft.core.schemas import CheckResult, ScenarioSpec


def run_lead_vehicle_braking_checks(spec: ScenarioSpec) -> tuple[CheckResult, ...]:
    if spec.scenario_type != "lead_vehicle_braking":
        return ()
    return (
        _same_lane_following_check(spec),
        _initial_gap_check(spec),
        _braking_trigger_timing_check(spec),
        _braking_semantics_check(spec),
    )


def _same_lane_following_check(spec: ScenarioSpec) -> CheckResult:
    measured = _layout_measured(spec)
    passed = bool(
        measured.get("longitudinal_gap_m") is not None
        and measured.get("longitudinal_gap_m") > 0
        and measured.get("lateral_offset_m") is not None
        and abs(float(measured["lateral_offset_m"])) <= 1.0
    )
    return _result(
        "lead_vehicle_same_lane_following",
        passed,
        "Lead vehicle starts ahead of ego in the same lane.",
        "Lead vehicle must start ahead of ego in the same lane.",
        measured,
    )


def _initial_gap_check(spec: ScenarioSpec) -> CheckResult:
    measured = _layout_measured(spec)
    initial_gap = measured.get("longitudinal_gap_m")
    passed = initial_gap is not None and 18.0 <= float(initial_gap) <= 35.0
    return _result(
        "lead_vehicle_initial_gap_in_domain",
        passed,
        "Lead vehicle initial gap is inside the family-supported domain.",
        "Lead vehicle initial gap is outside the family-supported domain.",
        {**measured, "initial_gap_m": initial_gap, "expected_gap_range_m": [18.0, 35.0]},
    )


def _braking_trigger_timing_check(spec: ScenarioSpec) -> CheckResult:
    trigger_time_s = _trigger_time_s(spec)
    stop_time_s = spec.timing.total_duration_s if spec.timing is not None else None
    passed = trigger_time_s is not None and stop_time_s is not None and 0.0 <= trigger_time_s < stop_time_s
    return _result(
        "lead_vehicle_braking_trigger_timing",
        passed,
        "Lead braking trigger is reachable before the scenario stop time.",
        "Lead braking trigger is not reachable before the scenario stop time.",
        {
            **_layout_measured(spec),
            "trigger_distance_m": spec.trigger.distance_m,
            "trigger_time_s": trigger_time_s,
            "stop_time_s": stop_time_s,
        },
    )


def _braking_semantics_check(spec: ScenarioSpec) -> CheckResult:
    lead_actor = spec.actor_by_id("lead_vehicle")
    relation_types = {relation.relation_type for relation in spec.spatial_relations}
    metadata = spec.metadata.get("lead_vehicle_braking", {})
    deceleration = metadata.get("lead_deceleration_mps2") if isinstance(metadata, dict) else None
    action = _lead_braking_action(spec)
    passed = bool(
        lead_actor is not None
        and lead_actor.state == "braking"
        and "brakes_before" in relation_types
        and deceleration is not None
        and float(deceleration) < 0.0
        and action is not None
        and action.type == "absolute_speed"
    )
    return _result(
        "lead_vehicle_braking_semantics",
        passed,
        "Lead vehicle braking semantics are represented in actors, relations, metadata, and storyboard action.",
        "Lead vehicle braking semantics are incomplete.",
        {
            "lead_actor_state": lead_actor.state if lead_actor is not None else None,
            "spatial_relations": sorted(relation_types),
            "lead_deceleration_mps2": deceleration,
            "storyboard_action_type": action.type if action is not None else None,
        },
    )


def _layout_measured(spec: ScenarioSpec) -> dict[str, object]:
    measured: dict[str, object] = {"source_actor_id": "ego", "target_actor_id": "lead_vehicle"}
    if spec.layout is None:
        measured.update({"longitudinal_gap_m": None, "lateral_offset_m": None})
        return measured
    ego_pose = spec.layout.actor_poses.get("ego")
    lead_pose = spec.layout.actor_poses.get("lead_vehicle")
    if ego_pose is None or lead_pose is None:
        measured.update({"longitudinal_gap_m": None, "lateral_offset_m": None})
        return measured
    measured.update(
        {
            "ego_position": {"x_m": ego_pose.x_m, "y_m": ego_pose.y_m},
            "lead_vehicle_position": {"x_m": lead_pose.x_m, "y_m": lead_pose.y_m},
            "longitudinal_gap_m": lead_pose.x_m - ego_pose.x_m,
            "lateral_offset_m": lead_pose.y_m - ego_pose.y_m,
        }
    )
    return measured


def _trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    ego_pose = spec.layout.actor_poses.get("ego")
    reaction_point = spec.layout.points.get("reaction_point")
    ego = spec.actor_by_id("ego")
    if ego_pose is None or reaction_point is None or ego is None or ego.initial_speed_kph is None:
        return None
    ego_speed_mps = ego.initial_speed_kph / 3.6
    if ego_speed_mps <= 0.0:
        return None
    return (reaction_point.x_m - ego_pose.x_m) / ego_speed_mps


def _lead_braking_action(spec: ScenarioSpec) -> object | None:
    if spec.storyboard is None:
        return None
    for action in spec.storyboard.actions:
        if "lead_vehicle" in action.actor_refs:
            return action
    return None


def _result(
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
) -> CheckResult:
    return CheckResult(
        name=name,
        passed=passed,
        severity="note" if passed else "warning",
        message=pass_message if passed else failure_message,
        category="intent_alignment",
        intent_relation="matches_intent" if passed else "mismatches_intent",
        repair_action="none",
        measured=measured,
    )
