from __future__ import annotations

from scenariocraft.repair.providers.types import RepairProposal, RepairRequest
from scenariocraft.schemas import (
    PatchSpec,
    RepositionActorToBandOperation,
    SetNamedPointOperation,
    SetTriggerPointByLeadTimeOperation,
)
from scenariocraft.tools.timing_metrics import compute_timing_metrics

PARKING_PROBE = "parked_van_footprint_in_parking_strip"
TRIGGER_PROBE = "trigger_point_before_conflict_and_in_ego_lane"
TIMING_TRIGGER_PROBES = {
    "ego_lead_time_to_conflict_positive",
    "ego_lead_time_within_timing_policy",
    "pedestrian_conflict_timing_alignment",
}
TIMING_REPAIR_LEAD_TIME_MARGIN_S = 0.001


class FakeRepairProvider:
    """Deterministic PatchSpec proposal provider for tests and local development."""

    provider_name = "deterministic_fake"

    def propose_patch(self, request: RepairRequest) -> RepairProposal:
        if not isinstance(request, RepairRequest):
            raise TypeError("request must be a RepairRequest.")

        failed_names = {result.name for result in request.failed_probe_results}
        allowed = set(request.allowed_operation_types)
        operations = []
        blocked_operations: list[str] = []

        if PARKING_PROBE in failed_names:
            operation_type = RepositionActorToBandOperation.op
            if operation_type in allowed:
                operations.append(
                    RepositionActorToBandOperation(
                        actor_id="parked_van",
                        target_band_id="ego_side_parking_strip",
                    )
                )
            else:
                blocked_operations.append(operation_type)

        if TRIGGER_PROBE in failed_names:
            operation_type = SetNamedPointOperation.op
            if operation_type in allowed:
                layout = request.scenario_spec.layout
                if layout is None:
                    return self._decline("ScenarioSpec.layout is required for trigger-point repair.")
                conflict = layout.points.get("conflict_point")
                trigger = layout.points.get("trigger_point")
                if conflict is None or trigger is None:
                    return self._decline("Named conflict_point and trigger_point are required for trigger repair.")
                operations.append(
                    SetNamedPointOperation(
                        point_id="trigger_point",
                        x_m=conflict.x_m - 1.0,
                        y_m=trigger.y_m,
                    )
                )
            else:
                blocked_operations.append(operation_type)

        if failed_names & TIMING_TRIGGER_PROBES:
            operation_type = SetTriggerPointByLeadTimeOperation.op
            if operation_type in allowed:
                lead_time_s = _required_lead_time_s(request)
                if lead_time_s is None:
                    return self._decline("Timing repair requires a computable positive lead time.")
                operations.append(
                    SetTriggerPointByLeadTimeOperation(
                        point_id="trigger_point",
                        reference_point_id="conflict_point",
                        speed_source_actor_id=request.scenario_spec.trigger.source,
                        lead_time_s=lead_time_s,
                    )
                )
            else:
                blocked_operations.append(operation_type)

        if operations:
            return RepairProposal(
                patch=PatchSpec(tuple(operations)),
                rationale="Proposed deterministic operations for supported failed probes.",
                provider_name=self.provider_name,
            )
        if blocked_operations:
            blocked = ", ".join(sorted(set(blocked_operations)))
            return self._decline(f"Required operation types are not allowed: {blocked}.")
        unsupported = ", ".join(sorted(failed_names)) or "none"
        return self._decline(f"No supported deterministic repair for failed probes: {unsupported}.")

    def _decline(self, rationale: str) -> RepairProposal:
        return RepairProposal(
            patch=None,
            rationale=rationale,
            provider_name=self.provider_name,
        )


def _required_lead_time_s(request: RepairRequest) -> float | None:
    candidates: list[float] = []
    for result in request.failed_probe_results:
        value = result.measured.get("required_minimum_lead_time_s")
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0.0:
            candidates.append(float(value))
    if request.scenario_spec.intended_criticality.target_min_ttc_s is not None:
        candidates.append(request.scenario_spec.intended_criticality.target_min_ttc_s)
    if request.scenario_spec.timing is not None:
        candidates.append(request.scenario_spec.timing.minimum_pre_trigger_context_s)
    metrics = compute_timing_metrics(request.scenario_spec)
    if metrics.pedestrian_time_to_conflict_s is not None and metrics.target_ttc_s is not None:
        candidates.append(metrics.pedestrian_time_to_conflict_s - metrics.target_ttc_s)
    return max(candidates) + TIMING_REPAIR_LEAD_TIME_MARGIN_S if candidates else None
