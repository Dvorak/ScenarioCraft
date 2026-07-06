"""OpenSCENARIO trigger compilation helpers."""

from scenariocraft.core.schemas import ScenarioSpec


def xosc_simulation_time_trigger(name: str, value_s: float, xosc: object) -> object:
    return xosc.ValueTrigger(
        name,
        0,
        xosc.ConditionEdge.rising,
        xosc.SimulationTimeCondition(value_s, xosc.Rule.greaterThan),
    )


def xosc_rule(rule: str, xosc: object) -> object:
    return getattr(xosc.Rule, rule, xosc.Rule.lessThan)


def xosc_pedestrian_start_trigger(
    spec: ScenarioSpec,
    xosc: object,
    *,
    trigger_name: str | None = None,
    include_timing_alignment_trigger: bool = True,
) -> object:
    trigger = xosc.Trigger("start")
    relative_group = xosc.ConditionGroup("start")
    relative_group.add_condition(
        xosc_pedestrian_start_condition(spec, xosc, trigger_name=trigger_name)
    )
    trigger.add_conditiongroup(relative_group)
    trigger_time_s = derived_trigger_time_s(spec)
    if uses_relative_distance_start_condition(spec) and include_timing_alignment_trigger and trigger_time_s is not None:
        time_group = xosc.ConditionGroup("start")
        time_group.add_condition(xosc_simulation_time_trigger("relative_distance_time_alignment", trigger_time_s, xosc))
        trigger.add_conditiongroup(time_group)
    return trigger


def xosc_start_trigger(
    spec: ScenarioSpec,
    xosc: object,
    *,
    trigger_name: str | None = None,
    include_timing_alignment_trigger: bool = True,
) -> object:
    return xosc_pedestrian_start_trigger(
        spec,
        xosc,
        trigger_name=trigger_name,
        include_timing_alignment_trigger=include_timing_alignment_trigger,
    )


def xosc_pedestrian_start_condition(spec: ScenarioSpec, xosc: object, *, trigger_name: str | None) -> object:
    condition = spec.trigger.condition
    if condition is not None and condition.metric == "time_to_collision":
        return xosc.EntityTrigger(
            condition.id,
            0,
            xosc.ConditionEdge.rising,
            xosc_time_to_collision_condition(spec, xosc),
            condition.source or spec.trigger.source,
            xosc.TriggeringEntitiesRule.any,
        )
    return xosc.EntityTrigger(
        trigger_name or spec.trigger.type,
        0,
        xosc.ConditionEdge.rising,
        xosc.RelativeDistanceCondition(
            spec.trigger.distance_m,
            xosc.Rule.lessThan,
            xosc.RelativeDistanceType.longitudinal,
            spec.trigger.target,
            freespace=False,
        ),
        spec.trigger.source,
        xosc.TriggeringEntitiesRule.any,
    )


def xosc_time_to_collision_condition(spec: ScenarioSpec, xosc: object) -> object:
    condition = spec.trigger.condition
    if condition is None or condition.metric != "time_to_collision":
        raise ValueError("trigger.condition.metric must be time_to_collision.")
    kwargs: dict[str, object] = {
        "alongroute": True,
        "freespace": condition.freespace if condition.freespace is not None else True,
        "distance_type": getattr(
            xosc.RelativeDistanceType,
            condition.relative_distance_type or "longitudinal",
            xosc.RelativeDistanceType.longitudinal,
        ),
        "coordinate_system": getattr(
            xosc.CoordinateSystem,
            condition.coordinate_system or "road",
            xosc.CoordinateSystem.road,
        ),
    }
    if condition.target_kind == "named_point":
        point = spec.layout.points.get(condition.target) if spec.layout is not None and condition.target is not None else None
        if point is None:
            raise ValueError("time_to_collision named-point target requires a layout point.")
        kwargs["position"] = xosc.WorldPosition(point.x_m, point.y_m, 0.0, 0.0)
    else:
        kwargs["entity"] = condition.target or spec.trigger.target
    return xosc.TimeToCollisionCondition(
        condition.value,
        xosc_rule(condition.rule, xosc),
        **kwargs,
    )


def uses_relative_distance_start_condition(spec: ScenarioSpec) -> bool:
    return spec.trigger.condition is None or spec.trigger.condition.metric == "relative_distance"


def derived_trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    source_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    source_actor = spec.actor_by_id(spec.trigger.source)
    if source_pose is None or target_pose is None or source_actor is None or source_actor.initial_speed_kph is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    trigger_distance_along_x = target_pose.x_m - source_pose.x_m - spec.trigger.distance_m
    if trigger_distance_along_x < 0:
        return 0.0
    return trigger_distance_along_x / speed_mps


def scenario_stop_time_s(spec: ScenarioSpec) -> float:
    return spec.timing.total_duration_s if spec.timing is not None else 8.0


def stop_trigger_name(stop_time_s: float) -> str:
    return f"stop_after_{stop_time_s:g}s"
