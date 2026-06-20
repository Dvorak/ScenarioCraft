from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypeAlias
from xml.etree import ElementTree as ET

from scenariocraft.loop import RepairRunResult, run_bounded_repair_loop
from scenariocraft.probes import run_artifact_consistency_probes, run_pedestrian_occlusion_probes
from scenariocraft.repair import apply_patch
from scenariocraft.repair.providers import FakeRepairProvider
from scenariocraft.schemas import (
    PatchSpec,
    ProbeResult,
    ScenarioSpec,
    SetActorPoseOperation,
    SetNamedPointOperation,
)
from scenariocraft.tools import build_openscenario


FaultDomain: TypeAlias = Literal["none", "geometry", "artifact"]
RepairExpectation: TypeAlias = Literal[
    "not_needed",
    "repairable_with_fake_provider",
    "detection_only",
]

_FAULT_DOMAINS = {"none", "geometry", "artifact"}
_REPAIR_EXPECTATIONS = {
    "not_needed",
    "repairable_with_fake_provider",
    "detection_only",
}


@dataclass(frozen=True)
class DemoCase:
    case_id: str
    display_name: str
    description: str
    fault_domain: FaultDomain
    repair_expectation: RepairExpectation

    def __post_init__(self) -> None:
        for field_name in ("case_id", "display_name", "description"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} must be a non-empty string.")
        if self.fault_domain not in _FAULT_DOMAINS:
            raise ValueError(f"Unsupported fault_domain: {self.fault_domain}.")
        if self.repair_expectation not in _REPAIR_EXPECTATIONS:
            raise ValueError(f"Unsupported repair_expectation: {self.repair_expectation}.")

    @property
    def uses_provider(self) -> bool:
        return self.repair_expectation == "repairable_with_fake_provider"


@dataclass(frozen=True)
class DemoCaseExecution:
    case: DemoCase
    original_spec: ScenarioSpec
    experiment_spec: ScenarioSpec
    setup_description: str
    setup_values: dict[str, object]
    injected_patch: PatchSpec | None
    initial_geometry_probe_results: tuple[ProbeResult, ...]
    final_geometry_probe_results: tuple[ProbeResult, ...]
    artifact_probe_results: tuple[ProbeResult, ...]
    provider_requested: bool
    provider_name: str | None
    provider_rationale: str
    proposed_patch: PatchSpec | None
    patch_applied: bool
    application_error: str | None
    terminal_status: str
    terminal_reason: str
    artifact_paths: tuple[Path, ...]
    repair_run_result: RepairRunResult | None = None


@dataclass(frozen=True)
class PreparedDemoCase:
    case: DemoCase
    original_spec: ScenarioSpec
    experiment_spec: ScenarioSpec
    setup_description: str
    setup_values: dict[str, object]
    injected_patch: PatchSpec | None
    initial_geometry_probe_results: tuple[ProbeResult, ...]
    artifact_probe_results: tuple[ProbeResult, ...]
    terminal_status: str
    terminal_reason: str
    artifact_paths: tuple[Path, ...] = ()

    @property
    def geometry_failures(self) -> tuple[ProbeResult, ...]:
        return tuple(result for result in self.initial_geometry_probe_results if not result.passed)

    @property
    def artifact_failures(self) -> tuple[ProbeResult, ...]:
        return tuple(result for result in self.artifact_probe_results if not result.passed)

    @property
    def repair_required(self) -> bool:
        return self.case.fault_domain == "geometry" and bool(self.geometry_failures)

    @property
    def detection_only(self) -> bool:
        return self.case.fault_domain == "artifact" and bool(self.artifact_failures)


DEMO_CASES = (
    DemoCase(
        case_id="normal_good_scenario",
        display_name="Normal Good Scenario",
        description="Canonical layout-backed pedestrian occlusion with no injected fault.",
        fault_domain="none",
        repair_expectation="not_needed",
    ),
    DemoCase(
        case_id="geometry_van_in_ego_lane",
        display_name="Repairable Geometry Fault: Parked Van in Ego Lane",
        description="Move parked_van laterally into ego_driving_lane while preserving x and heading.",
        fault_domain="geometry",
        repair_expectation="repairable_with_fake_provider",
    ),
    DemoCase(
        case_id="geometry_trigger_after_conflict",
        display_name="Repairable Geometry Fault: Trigger after Conflict Point",
        description="Move trigger_point after conflict_point while keeping it inside the ego lane.",
        fault_domain="geometry",
        repair_expectation="repairable_with_fake_provider",
    ),
    DemoCase(
        case_id="artifact_xosc_actor_pose_drift",
        display_name="Non-Repairable Artifact Fault: XOSC Actor Pose Drift",
        description="Drift only the generated XOSC parked_van initial y position.",
        fault_domain="artifact",
        repair_expectation="detection_only",
    ),
)

_DEMO_CASES_BY_ID = {case.case_id: case for case in DEMO_CASES}


def get_demo_case(case_id: str) -> DemoCase:
    try:
        return _DEMO_CASES_BY_ID[case_id]
    except KeyError as exc:
        raise ValueError(f"Unknown demo case: {case_id}.") from exc


def run_demo_case(
    case_id: str,
    spec: ScenarioSpec,
    current_run_dir: Path,
) -> DemoCaseExecution:
    prepared = prepare_demo_case(case_id, spec, current_run_dir)
    if prepared.case.fault_domain == "artifact":
        return _execution_from_prepared_artifact(prepared)
    return execute_prepared_demo_case(prepared, current_run_dir)


def prepare_demo_case(
    case_id: str,
    spec: ScenarioSpec,
    current_run_dir: Path,
) -> PreparedDemoCase:
    case = get_demo_case(case_id)
    canonical = _snapshot_supported_spec(spec)
    case_dir = _case_output_dir(current_run_dir, case.case_id)
    if case.fault_domain == "artifact":
        execution = _run_artifact_drift_case(case, canonical, case_dir)
        return PreparedDemoCase(
            case=case,
            original_spec=execution.original_spec,
            experiment_spec=execution.experiment_spec,
            setup_description=execution.setup_description,
            setup_values=execution.setup_values,
            injected_patch=None,
            initial_geometry_probe_results=execution.initial_geometry_probe_results,
            artifact_probe_results=execution.artifact_probe_results,
            terminal_status=execution.terminal_status,
            terminal_reason=execution.terminal_reason,
            artifact_paths=execution.artifact_paths,
        )

    experiment_spec, injected_patch, setup_description, setup_values = _geometry_case_setup(case, canonical)
    geometry_results = run_pedestrian_occlusion_probes(experiment_spec)
    failures = tuple(result for result in geometry_results if not result.passed)
    terminal_status = "repair_required" if failures else "geometry_passed"
    terminal_reason = (
        "ScenarioSpec geometry requires deterministic repair."
        if failures
        else "ScenarioSpec geometry passed; no repair proposal is required."
    )
    return PreparedDemoCase(
        case=case,
        original_spec=canonical,
        experiment_spec=experiment_spec,
        setup_description=setup_description,
        setup_values=setup_values,
        injected_patch=injected_patch,
        initial_geometry_probe_results=geometry_results,
        artifact_probe_results=(),
        terminal_status=terminal_status,
        terminal_reason=terminal_reason,
    )


def execute_prepared_demo_case(
    prepared: PreparedDemoCase,
    current_run_dir: Path,
) -> DemoCaseExecution:
    if prepared.case.fault_domain == "artifact":
        return _execution_from_prepared_artifact(prepared)
    case_dir = _case_output_dir(current_run_dir, prepared.case.case_id)
    run_result = run_bounded_repair_loop(
        prepared.experiment_spec,
        provider=FakeRepairProvider(),
        output_dir=case_dir,
        user_intent=_case_user_intent(prepared.case),
    )
    first_round = run_result.rounds[0] if run_result.rounds else None
    completed_setup_values = {
        **prepared.setup_values,
        **_repair_outcome_values(prepared.case, run_result),
    }
    return DemoCaseExecution(
        case=prepared.case,
        original_spec=prepared.original_spec,
        experiment_spec=prepared.experiment_spec,
        setup_description=prepared.setup_description,
        setup_values=completed_setup_values,
        injected_patch=prepared.injected_patch,
        initial_geometry_probe_results=prepared.initial_geometry_probe_results,
        final_geometry_probe_results=run_result.final_geometry_probe_results,
        artifact_probe_results=run_result.final_artifact_probe_results,
        provider_requested=first_round is not None,
        provider_name=first_round.provider_name if first_round is not None else None,
        provider_rationale=(
            first_round.proposal_rationale
            if first_round is not None
            else _provider_not_needed_reason(prepared.case)
        ),
        proposed_patch=first_round.proposed_patch if first_round is not None else None,
        patch_applied=first_round.patch_applied if first_round is not None else False,
        application_error=first_round.application_error if first_round is not None else None,
        terminal_status=run_result.terminal_status,
        terminal_reason=run_result.terminal_reason,
        artifact_paths=tuple(
            path for path in (run_result.xosc_path, run_result.xodr_path) if path is not None
        ),
        repair_run_result=run_result,
    )


def _execution_from_prepared_artifact(prepared: PreparedDemoCase) -> DemoCaseExecution:
    return DemoCaseExecution(
        case=prepared.case,
        original_spec=prepared.original_spec,
        experiment_spec=prepared.experiment_spec,
        setup_description=prepared.setup_description,
        setup_values=prepared.setup_values,
        injected_patch=None,
        initial_geometry_probe_results=prepared.initial_geometry_probe_results,
        final_geometry_probe_results=prepared.initial_geometry_probe_results,
        artifact_probe_results=prepared.artifact_probe_results,
        provider_requested=False,
        provider_name=None,
        provider_rationale=_provider_not_needed_reason(prepared.case),
        proposed_patch=None,
        patch_applied=False,
        application_error=None,
        terminal_status=prepared.terminal_status,
        terminal_reason=prepared.terminal_reason,
        artifact_paths=prepared.artifact_paths,
        repair_run_result=None,
    )


def _case_output_dir(current_run_dir: Path, case_id: str) -> Path:
    return Path(current_run_dir) / "demo_experiments" / case_id


def _geometry_case_setup(
    case: DemoCase,
    canonical: ScenarioSpec,
) -> tuple[ScenarioSpec, PatchSpec | None, str, dict[str, object]]:
    if case.case_id == "normal_good_scenario":
        return (
            ScenarioSpec.from_dict(canonical.to_dict()),
            None,
            "Canonical ScenarioSpec used unchanged; no fault was injected.",
            {"fault_injected": False},
        )
    assert canonical.layout is not None
    if case.case_id == "geometry_van_in_ego_lane":
        van_pose = canonical.layout.actor_poses["parked_van"]
        ego_lane = next(band for band in canonical.layout.road_bands if band.id == "ego_driving_lane")
        faulty_y_m = (ego_lane.y_min_m + ego_lane.y_max_m) / 2.0
        patch = PatchSpec((
            SetActorPoseOperation(
                actor_id="parked_van",
                x_m=van_pose.x_m,
                y_m=faulty_y_m,
                heading_rad=van_pose.heading_rad,
            ),
        ))
        return (
            apply_patch(canonical, patch),
            patch,
            "Injected ScenarioSpec geometry fault: parked_van moved into ego_driving_lane.",
            {
                "actor_id": "parked_van",
                "before": {"x_m": van_pose.x_m, "y_m": van_pose.y_m, "heading_rad": van_pose.heading_rad},
                "after": {"x_m": van_pose.x_m, "y_m": faulty_y_m, "heading_rad": van_pose.heading_rad},
            },
        )
    if case.case_id == "geometry_trigger_after_conflict":
        trigger = canonical.layout.points["trigger_point"]
        conflict = canonical.layout.points["conflict_point"]
        faulty_x_m = conflict.x_m + 1.0
        patch = PatchSpec((
            SetNamedPointOperation(
                point_id="trigger_point",
                x_m=faulty_x_m,
                y_m=trigger.y_m,
            ),
        ))
        return (
            apply_patch(canonical, patch),
            patch,
            "Injected ScenarioSpec geometry fault: trigger_point moved after conflict_point.",
            {
                "point_id": "trigger_point",
                "conflict_x_m": conflict.x_m,
                "before": {"x_m": trigger.x_m, "y_m": trigger.y_m},
                "after": {"x_m": faulty_x_m, "y_m": trigger.y_m},
            },
        )
    raise ValueError(f"Unsupported geometry demo case: {case.case_id}.")


def _run_artifact_drift_case(
    case: DemoCase,
    canonical: ScenarioSpec,
    case_dir: Path,
) -> DemoCaseExecution:
    geometry_results = run_pedestrian_occlusion_probes(canonical)
    build_result = build_openscenario(canonical, case_dir)
    expected_y_m, observed_y_m = _drift_parked_van_xosc_y(build_result.xosc_path)
    artifact_results = run_artifact_consistency_probes(
        canonical,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )
    artifact_failed = any(not result.passed for result in artifact_results)
    terminal_status = "artifact_validation_failed" if artifact_failed else "passed"
    terminal_reason = (
        "The ScenarioSpec remains valid, but the generated artifact no longer matches it. "
        "This builder/materialization consistency failure is intentionally detection-only."
        if artifact_failed
        else "The controlled artifact drift was not detected."
    )
    return DemoCaseExecution(
        case=case,
        original_spec=canonical,
        experiment_spec=ScenarioSpec.from_dict(canonical.to_dict()),
        setup_description="Injected artifact fault: changed only parked_van initial WorldPosition y in isolated XOSC.",
        setup_values={
            "actor_id": "parked_van",
            "expected_y_m": expected_y_m,
            "observed_xosc_y_m": observed_y_m,
            "drift_y_m": observed_y_m - expected_y_m,
            "scenario_spec_changed": False,
        },
        injected_patch=None,
        initial_geometry_probe_results=geometry_results,
        final_geometry_probe_results=geometry_results,
        artifact_probe_results=artifact_results,
        provider_requested=False,
        provider_name=None,
        provider_rationale=_provider_not_needed_reason(case),
        proposed_patch=None,
        patch_applied=False,
        application_error=None,
        terminal_status=terminal_status,
        terminal_reason=terminal_reason,
        artifact_paths=tuple(build_result.artifact_paths()),
        repair_run_result=None,
    )


def _drift_parked_van_xosc_y(xosc_path: Path) -> tuple[float, float]:
    tree = ET.parse(xosc_path)
    world_position = tree.getroot().find(
        ".//Init/Actions/Private[@entityRef='parked_van']"
        "//TeleportAction/Position/WorldPosition"
    )
    if world_position is None:
        raise ValueError("Generated XOSC does not contain parked_van initial WorldPosition.")
    expected_y_m = float(world_position.attrib["y"])
    observed_y_m = expected_y_m + 0.75
    world_position.attrib["y"] = str(observed_y_m)
    tree.write(xosc_path, encoding="utf-8", xml_declaration=True)
    return expected_y_m, observed_y_m


def _snapshot_supported_spec(spec: ScenarioSpec) -> ScenarioSpec:
    if not isinstance(spec, ScenarioSpec):
        raise TypeError("spec must be a ScenarioSpec.")
    if spec.scenario_type != "pedestrian_occlusion" or spec.layout is None:
        raise ValueError("Demo cases require a layout-backed pedestrian_occlusion ScenarioSpec.")
    return ScenarioSpec.from_dict(spec.to_dict())


def _case_user_intent(case: DemoCase) -> str | None:
    intents = {
        "geometry_van_in_ego_lane": "Restore parked_van to the ego-side parking strip.",
        "geometry_trigger_after_conflict": "Move trigger_point before conflict_point inside the ego lane.",
    }
    return intents.get(case.case_id)


def _repair_outcome_values(
    case: DemoCase,
    result: RepairRunResult,
) -> dict[str, object]:
    layout = result.final_spec.layout
    if layout is None:
        return {}
    if case.case_id == "geometry_van_in_ego_lane":
        pose = layout.actor_poses["parked_van"]
        return {
            "after_repair": {
                "x_m": pose.x_m,
                "y_m": pose.y_m,
                "heading_rad": pose.heading_rad,
            }
        }
    if case.case_id == "geometry_trigger_after_conflict":
        point = layout.points["trigger_point"]
        return {"after_repair": {"x_m": point.x_m, "y_m": point.y_m}}
    return {}


def _provider_not_needed_reason(case: DemoCase) -> str:
    if case.fault_domain == "artifact":
        return (
            "No repair proposal requested because this is an artifact consistency failure, "
            "not a ScenarioSpec geometry repair candidate."
        )
    return "No repair proposal requested because geometry already passed."
