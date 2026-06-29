from __future__ import annotations

from collections.abc import Callable

from scenariocraft.core.probes.base import run_probes
from scenariocraft.core.schemas import ProbeResult, ScenarioSpec
from scenariocraft.core.metrics import time_headway_s


class _TimeHeadwayProbe:
    def __init__(self, name: str, check: Callable[[ScenarioSpec], ProbeResult]) -> None:
        self.name = name
        self._check = check

    def run(self, spec: ScenarioSpec) -> ProbeResult:
        return self._check(spec)


def run_time_headway_probes(spec: ScenarioSpec) -> tuple[ProbeResult, ...]:
    condition = spec.trigger.condition
    if condition is None or condition.metric != "time_headway":
        return ()
    probes = (
        _TimeHeadwayProbe("time_headway_computable", _time_headway_computable),
        _TimeHeadwayProbe("time_headway_condition_matches_rule", _time_headway_condition_matches_rule),
        _TimeHeadwayProbe("time_headway_metric_not_ttc", _time_headway_metric_not_ttc),
    )
    return run_probes(spec, probes)


def _time_headway_computable(spec: ScenarioSpec) -> ProbeResult:
    thw_s = time_headway_s(spec)
    return _result(
        name="time_headway_computable",
        passed=thw_s is not None,
        pass_message="Time headway is computable for the configured source and lead actor.",
        failure_message="Time headway is unavailable; actors must be in the same lane with a positive lead gap and source speed.",
        measured=_measured(spec),
    )


def _time_headway_condition_matches_rule(spec: ScenarioSpec) -> ProbeResult:
    condition = spec.trigger.condition
    thw_s = time_headway_s(spec)
    passed = condition is not None and thw_s is not None and _matches_rule(thw_s, condition.rule, condition.value)
    return _result(
        name="time_headway_condition_matches_rule",
        passed=passed,
        pass_message="Current time headway satisfies the configured trigger condition.",
        failure_message="Current time headway does not satisfy the configured trigger condition.",
        measured=_measured(spec),
    )


def _time_headway_metric_not_ttc(spec: ScenarioSpec) -> ProbeResult:
    condition = spec.trigger.condition
    return _result(
        name="time_headway_metric_not_ttc",
        passed=condition is not None and condition.metric == "time_headway",
        pass_message="Time headway is represented as a distinct metric from TTC.",
        failure_message="Time headway metric is unavailable or conflated with TTC.",
        measured={
            **_measured(spec),
            "time_headway_metric_label": "time_headway_s",
            "target_ttc_metric_label": "target_ttc_s",
        },
    )


def _measured(spec: ScenarioSpec) -> dict[str, object]:
    condition = spec.trigger.condition
    source_id = condition.source if condition is not None and condition.source is not None else spec.trigger.source
    target_id = condition.target if condition is not None and condition.target is not None else spec.trigger.target
    measured: dict[str, object] = {
        "source_actor_id": source_id,
        "target_actor_id": target_id,
        "time_headway_s": time_headway_s(spec),
        "condition_rule": condition.rule if condition is not None else None,
        "condition_value_s": condition.value if condition is not None else None,
    }
    if spec.layout is not None:
        source_pose = spec.layout.actor_poses.get(source_id)
        target_pose = spec.layout.actor_poses.get(target_id)
        if source_pose is not None:
            measured["source_position"] = {"x_m": source_pose.x_m, "y_m": source_pose.y_m}
        if target_pose is not None:
            measured["target_position"] = {"x_m": target_pose.x_m, "y_m": target_pose.y_m}
        if source_pose is not None and target_pose is not None:
            measured["longitudinal_gap_m"] = target_pose.x_m - source_pose.x_m
            measured["lateral_offset_m"] = target_pose.y_m - source_pose.y_m
    return measured


def _matches_rule(value: float, rule: str, threshold: float) -> bool:
    if rule == "lessThan":
        return value < threshold
    if rule == "greaterThan":
        return value > threshold
    return abs(value - threshold) <= 1e-6


def _result(
    *,
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
) -> ProbeResult:
    return ProbeResult(
        name=name,
        passed=passed,
        severity="note" if passed else "warning",
        message=pass_message if passed else failure_message,
        measured=measured,
    )
