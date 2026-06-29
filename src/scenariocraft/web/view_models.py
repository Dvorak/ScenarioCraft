from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scenariocraft.loop.types import RepairRunResult
from scenariocraft.references import XoscMetadata
from scenariocraft.metrics import compute_timing_metrics
from scenariocraft.runtime import AsamQcResult, EsminiResult
from scenariocraft.schemas import PatchSpec, ProbeResult, ScenarioSpec
from scenariocraft.validation import SemanticValidationResult
from scenariocraft.web.demo_cases import DemoCaseExecution, PreparedDemoCase


@dataclass(frozen=True)
class StatusCardViewModel:
    label: str
    value: str
    detail: str


@dataclass(frozen=True)
class ExternalScenarioViewModel:
    title: str
    source: str
    relative_path: str
    version: str
    entity_count: str
    parameter_count: str
    event_count: str
    condition_count: str
    dependency_count: str
    storyboard_complexity: str
    entity_names: list[str] = field(default_factory=list)
    parameter_names: list[str] = field(default_factory=list)
    logic_file_paths: list[str] = field(default_factory=list)
    catalog_locations: list[str] = field(default_factory=list)
    visual_summary_cards: list[StatusCardViewModel] = field(default_factory=list)
    status_cards: list[StatusCardViewModel] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    recommendation: str = "Load a scenario to start diagnosis."
    compatibility_category: str = "needs_manual_attention"
    parse_message: str = "No metadata extracted."


@dataclass(frozen=True)
class GeneratedScenarioViewModel:
    title: str
    scenario_type: str
    road_summary: str
    weather_summary: str
    actor_summary: list[str]
    trigger_summary: str
    criticality_summary: str
    ego_speed: str
    pedestrian_speed: str
    estimated_ttc: str
    target_ttc: str
    trigger_threshold_time: str
    ego_lead_time: str
    pedestrian_time_to_conflict: str
    trigger_threshold_summary: str
    pedestrian_conflict_summary: str
    status_cards: list[StatusCardViewModel] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)
    recommendation: str = "Generate and validate the scenario."


@dataclass(frozen=True)
class WorkspaceStatusItemViewModel:
    label: str
    value: str
    state: str
    detail: str
    tool_name: str | None = None


@dataclass(frozen=True)
class WorkspaceStatusViewModel:
    items: tuple[WorkspaceStatusItemViewModel, ...]


@dataclass(frozen=True)
class WorkspaceRepairViewModel:
    visible: bool
    detection_only: bool
    provider_name: str | None
    failures: tuple[RepairProbeTraceViewModel, ...]
    suggested_operations: tuple[dict[str, object], ...]
    can_repair: bool


def build_workspace_status_view_model(
    spec: ScenarioSpec | None,
    *,
    prepared_case: PreparedDemoCase | None = None,
    semantic_result: SemanticValidationResult | None = None,
    qc_result: AsamQcResult | None = None,
    esmini_result: EsminiResult | None = None,
) -> WorkspaceStatusViewModel:
    generated = spec is not None
    if prepared_case is not None:
        validation_failed = bool(
            prepared_case.geometry_failures or prepared_case.artifact_failures
        )
        validation_value = "Failed" if validation_failed else "Passed"
        validation_state = "failed" if validation_failed else "passed"
    elif semantic_result is not None:
        validation_value = "Passed" if semantic_result.passed else "Failed"
        validation_state = "passed" if semantic_result.passed else "failed"
    else:
        validation_value = "Waiting" if generated else "Not run"
        validation_state = "waiting" if generated else "neutral"
    return WorkspaceStatusViewModel(items=(
        WorkspaceStatusItemViewModel(
            "Scenario",
            "Generated" if generated else "Not run",
            "passed" if generated else "neutral",
            "Structured source: ScenarioSpec",
            "ScenarioSpec",
        ),
        WorkspaceStatusItemViewModel(
            "Probes",
            validation_value,
            validation_state,
            _workspace_probe_detail(prepared_case, semantic_result),
        ),
        WorkspaceStatusItemViewModel(
            "OSC Quality",
            _workspace_qc_value(qc_result, generated),
            _workspace_qc_state(qc_result, generated),
            _workspace_qc_detail(qc_result),
            "ASAM QC",
        ),
        WorkspaceStatusItemViewModel(
            "Simulation",
            _workspace_esmini_value(esmini_result, generated),
            _workspace_esmini_state(esmini_result, generated),
            _workspace_esmini_detail(esmini_result),
            "esmini",
        ),
    ))


def _workspace_probe_detail(
    prepared_case: PreparedDemoCase | None,
    semantic_result: SemanticValidationResult | None,
) -> str:
    if prepared_case is not None:
        results = (
            prepared_case.initial_geometry_probe_results
            + prepared_case.artifact_probe_results
        )
        if results:
            passed = sum(result.passed for result in results)
            return f"Deterministic validation: {passed}/{len(results)} probes passed"
    if semantic_result is not None and semantic_result.checks:
        passed = sum(check.passed for check in semantic_result.checks)
        return f"Deterministic validation: {passed}/{len(semantic_result.checks)} semantic checks passed"
    return "Deterministic validation: semantic and geometry probes"


def _workspace_qc_detail(result: AsamQcResult | None) -> str:
    if result is None:
        return "Current checker: ASAM QC · not run"
    if not result.checker_available:
        return "Current checker: ASAM QC · unavailable"
    return f"Current checker: ASAM QC · {'passed' if result.passed else 'failed'}"


def _workspace_esmini_detail(result: EsminiResult | None) -> str:
    if result is None:
        return "Current simulator: esmini · not run"
    if not result.esmini_available:
        return "Current simulator: esmini · unavailable"
    if result.executed:
        return "Current simulator: esmini · execution passed"
    if result.executed is False:
        return "Current simulator: esmini · execution failed"
    return "Current simulator: esmini · waiting"


def build_workspace_repair_view_model(
    prepared_case: PreparedDemoCase | None,
) -> WorkspaceRepairViewModel:
    if prepared_case is None:
        return WorkspaceRepairViewModel(False, False, None, (), (), False)
    failures = prepared_case.geometry_failures or prepared_case.artifact_failures
    if not failures:
        return WorkspaceRepairViewModel(False, False, None, (), (), False)
    suggestions: list[dict[str, object]] = []
    for result in failures:
        suggestions.extend(dict(operation) for operation in result.suggested_operations)
    detection_only = prepared_case.detection_only
    return WorkspaceRepairViewModel(
        visible=True,
        detection_only=detection_only,
        provider_name=None if detection_only else "FakeRepairProvider",
        failures=tuple(_repair_probe_view_model(result) for result in failures),
        suggested_operations=tuple(suggestions),
        can_repair=prepared_case.repair_required,
    )


def workspace_section_ids(repair: WorkspaceRepairViewModel) -> tuple[str, ...]:
    sections = ["request", "status"]
    if repair.visible:
        sections.append("repair")
    sections.append("brief")
    return tuple(sections)


def _workspace_qc_value(result: AsamQcResult | None, generated: bool) -> str:
    if result is None:
        return "Waiting" if generated else "Not run"
    if not result.checker_available:
        return "Unavailable"
    return "Passed" if result.passed else "Failed"


def _workspace_qc_state(result: AsamQcResult | None, generated: bool) -> str:
    value = _workspace_qc_value(result, generated)
    return {
        "Passed": "passed",
        "Failed": "failed",
        "Unavailable": "waiting",
        "Waiting": "waiting",
    }.get(value, "neutral")


def _workspace_esmini_value(result: EsminiResult | None, generated: bool) -> str:
    if result is None:
        return "Waiting" if generated else "Not run"
    if not result.esmini_available:
        return "Unavailable"
    if result.executed:
        return "Passed"
    return "Failed" if result.executed is False else "Waiting"


def _workspace_esmini_state(result: EsminiResult | None, generated: bool) -> str:
    value = _workspace_esmini_value(result, generated)
    return {
        "Passed": "passed",
        "Failed": "failed",
        "Unavailable": "waiting",
        "Waiting": "waiting",
    }.get(value, "neutral")


@dataclass(frozen=True)
class RepairProbeTraceViewModel:
    name: str
    passed: bool
    severity: str
    message: str
    measured: dict[str, object]


@dataclass(frozen=True)
class RepairRoundTraceViewModel:
    round_index: int
    provider_name: str
    provider_rationale: str
    proposed_operations: tuple[dict[str, object], ...]
    patch_applied: bool
    application_error: str | None


@dataclass(frozen=True)
class RepairTraceViewModel:
    fault_description: str
    injected_operations: tuple[dict[str, object], ...]
    initial_failures: tuple[RepairProbeTraceViewModel, ...]
    rounds: tuple[RepairRoundTraceViewModel, ...]
    final_geometry_results: tuple[RepairProbeTraceViewModel, ...]
    final_artifact_results: tuple[RepairProbeTraceViewModel, ...]
    geometry_revalidated: bool
    artifacts_consistent: bool
    terminal_status: str
    terminal_reason: str
    artifact_paths: tuple[str, ...]


@dataclass(frozen=True)
class DemoExperimentTraceViewModel:
    case_id: str
    display_name: str
    description: str
    fault_domain: str
    repair_expectation: str
    provider_will_be_used: bool
    setup_description: str
    setup_values: dict[str, object]
    injected_operations: tuple[dict[str, object], ...]
    initial_geometry_results: tuple[RepairProbeTraceViewModel, ...]
    initial_geometry_passed: bool
    provider_decision: str
    provider_name: str | None
    provider_rationale: str
    proposed_operations: tuple[dict[str, object], ...]
    patch_applied: bool
    application_error: str | None
    final_geometry_results: tuple[RepairProbeTraceViewModel, ...]
    geometry_revalidated: bool
    artifact_results: tuple[RepairProbeTraceViewModel, ...]
    artifacts_consistent: bool
    terminal_status: str
    terminal_reason: str
    artifact_paths: tuple[str, ...]


def build_demo_experiment_trace_view_model(
    execution: DemoCaseExecution,
) -> DemoExperimentTraceViewModel:
    initial_geometry = tuple(
        _repair_probe_view_model(probe)
        for probe in execution.initial_geometry_probe_results
    )
    final_geometry = tuple(
        _repair_probe_view_model(probe)
        for probe in execution.final_geometry_probe_results
    )
    artifact_results = tuple(
        _repair_probe_view_model(probe)
        for probe in execution.artifact_probe_results
    )
    return DemoExperimentTraceViewModel(
        case_id=execution.case.case_id,
        display_name=execution.case.display_name,
        description=execution.case.description,
        fault_domain=execution.case.fault_domain,
        repair_expectation=execution.case.repair_expectation,
        provider_will_be_used=execution.case.uses_provider,
        setup_description=execution.setup_description,
        setup_values=dict(execution.setup_values),
        injected_operations=tuple(
            operation.to_dict()
            for operation in (
                execution.injected_patch.operations
                if execution.injected_patch is not None
                else ()
            )
        ),
        initial_geometry_results=initial_geometry,
        initial_geometry_passed=bool(initial_geometry) and all(probe.passed for probe in initial_geometry),
        provider_decision=execution.provider_rationale,
        provider_name=execution.provider_name,
        provider_rationale=execution.provider_rationale,
        proposed_operations=tuple(
            operation.to_dict()
            for operation in (
                execution.proposed_patch.operations
                if execution.proposed_patch is not None
                else ()
            )
        ),
        patch_applied=execution.patch_applied,
        application_error=execution.application_error,
        final_geometry_results=final_geometry,
        geometry_revalidated=bool(final_geometry) and all(probe.passed for probe in final_geometry),
        artifact_results=artifact_results,
        artifacts_consistent=bool(artifact_results) and all(probe.passed for probe in artifact_results),
        terminal_status=execution.terminal_status,
        terminal_reason=execution.terminal_reason,
        artifact_paths=tuple(str(path) for path in execution.artifact_paths),
    )


def build_repair_trace_view_model(
    result: RepairRunResult,
    *,
    fault_description: str,
    injected_patch: PatchSpec,
) -> RepairTraceViewModel:
    first_round_results = result.rounds[0].input_probe_results if result.rounds else ()
    initial_failures = tuple(_repair_probe_view_model(probe) for probe in first_round_results if not probe.passed)
    rounds = tuple(
        RepairRoundTraceViewModel(
            round_index=round_trace.round_index,
            provider_name=round_trace.provider_name,
            provider_rationale=round_trace.proposal_rationale,
            proposed_operations=tuple(
                operation.to_dict()
                for operation in (
                    round_trace.proposed_patch.operations
                    if round_trace.proposed_patch is not None
                    else ()
                )
            ),
            patch_applied=round_trace.patch_applied,
            application_error=round_trace.application_error,
        )
        for round_trace in result.rounds
    )
    geometry_results = tuple(
        _repair_probe_view_model(probe) for probe in result.final_geometry_probe_results
    )
    artifact_results = tuple(
        _repair_probe_view_model(probe) for probe in result.final_artifact_probe_results
    )
    return RepairTraceViewModel(
        fault_description=fault_description,
        injected_operations=tuple(
            operation.to_dict() for operation in injected_patch.operations
        ),
        initial_failures=initial_failures,
        rounds=rounds,
        final_geometry_results=geometry_results,
        final_artifact_results=artifact_results,
        geometry_revalidated=bool(geometry_results) and all(probe.passed for probe in geometry_results),
        artifacts_consistent=bool(artifact_results) and all(probe.passed for probe in artifact_results),
        terminal_status=result.terminal_status,
        terminal_reason=result.terminal_reason,
        artifact_paths=tuple(
            str(path) for path in (result.xosc_path, result.xodr_path) if path is not None
        ),
    )


def _repair_probe_view_model(probe: ProbeResult) -> RepairProbeTraceViewModel:
    return RepairProbeTraceViewModel(
        name=probe.name,
        passed=probe.passed,
        severity=probe.severity,
        message=probe.message,
        measured=dict(probe.measured),
    )


def build_external_scenario_view_model(
    metadata: XoscMetadata | None,
    source: str = "",
    relative_path: str = "",
    qc_result: AsamQcResult | None = None,
    esmini_result: EsminiResult | None = None,
) -> ExternalScenarioViewModel:
    category = external_compatibility_category(metadata, qc_result, esmini_result)
    if metadata is None:
        return ExternalScenarioViewModel(
            title="No scenario loaded",
            source="n/a",
            relative_path="Choose a curated example or custom .xosc path.",
            version="n/a",
            entity_count="0",
            parameter_count="0",
            event_count="0",
            condition_count="0",
            dependency_count="0",
            storyboard_complexity="n/a",
            status_cards=external_status_cards(metadata, qc_result, esmini_result, category),
            diagnostics=external_diagnostics(metadata, qc_result, esmini_result, category),
            recommendation=recommendation_for_external_category(category),
            compatibility_category=category,
        )

    dependency_count = len(metadata.logic_file_paths) + len(metadata.catalog_locations) + len(metadata.scene_graph_file_paths)
    title = Path(metadata.xosc_path).stem if metadata.xosc_path else "external scenario"
    return ExternalScenarioViewModel(
        title=title,
        source=source or "custom path",
        relative_path=relative_path or metadata.xosc_path,
        version=metadata.open_scenario_version or "unknown",
        entity_count=str(metadata.scenario_object_count),
        parameter_count=str(metadata.parameter_count),
        event_count=str(metadata.event_count),
        condition_count=str(metadata.condition_count),
        dependency_count=str(dependency_count),
        storyboard_complexity=storyboard_complexity(metadata),
        entity_names=list(metadata.scenario_object_names[:8]),
        parameter_names=list(metadata.parameter_names[:8]),
        logic_file_paths=list(metadata.logic_file_paths),
        catalog_locations=list(metadata.catalog_locations),
        visual_summary_cards=[
            StatusCardViewModel("OpenDRIVE", list_summary(metadata.logic_file_paths, "No LogicFile reference detected"), "Road dependency"),
            StatusCardViewModel("Catalogs", list_summary(metadata.catalog_locations, "No CatalogLocations detected"), "Asset dependency"),
            StatusCardViewModel("ASAM QC", qc_status_text(qc_result), "Standard compliance"),
            StatusCardViewModel("esmini", esmini_status_text(esmini_result), "Smoke execution"),
        ],
        status_cards=external_status_cards(metadata, qc_result, esmini_result, category),
        diagnostics=external_diagnostics(metadata, qc_result, esmini_result, category)[:3],
        recommendation=recommendation_for_external_category(category),
        compatibility_category=category,
        parse_message="Metadata parsed." if metadata.parse_success else f"Metadata parse failed: {metadata.parse_error or 'unknown error'}",
    )


def build_generated_scenario_view_model(
    spec: ScenarioSpec | None,
    semantic_result: SemanticValidationResult | None = None,
    qc_result: AsamQcResult | None = None,
    esmini_result: EsminiResult | None = None,
    needs_repair: bool = False,
    failure_summary: str = "",
) -> GeneratedScenarioViewModel:
    if spec is None:
        return GeneratedScenarioViewModel(
            title="No generated scenario",
            scenario_type="n/a",
            road_summary="Generate a ScenarioSpec to inspect the scenario brief.",
            weather_summary="n/a",
            actor_summary=[],
            trigger_summary="n/a",
            criticality_summary="n/a",
            ego_speed="missing",
            pedestrian_speed="missing",
            estimated_ttc="n/a",
            target_ttc="n/a",
            trigger_threshold_time="n/a",
            ego_lead_time="n/a",
            pedestrian_time_to_conflict="n/a",
            trigger_threshold_summary="Trigger threshold: n/a",
            pedestrian_conflict_summary="Pedestrian to conflict: n/a",
            status_cards=[
                StatusCardViewModel("ScenarioSpec", "not generated", "Run the mock generator first."),
                StatusCardViewModel("Semantic", "not run", "Validation has not started."),
                StatusCardViewModel("ASAM QC", "not run", "Standard check has not started."),
                StatusCardViewModel("esmini", "not run", "Optional runtime check has not started."),
            ],
        )

    semantic_value = "not run"
    semantic_detail = "Semantic validation has not run."
    if semantic_result is not None:
        semantic_value = "passed" if semantic_result.passed else "failed"
        semantic_detail = "Required scenario intent is present." if semantic_result.passed else "Scenario intent needs repair."
    diagnostics: list[str] = []
    if needs_repair:
        diagnostics.append(failure_summary or "The generated scenario needs repair.")
    elif semantic_result is not None and semantic_result.passed:
        diagnostics.append("Generated scenario is ready for preview and report review.")
    else:
        diagnostics.append("Run Generate & Run to build artifacts and validation results.")

    recommendation = "Repair Scenario" if needs_repair else "Use as generated demo" if semantic_result is not None and semantic_result.passed else "Generate and validate"
    timing_metrics = compute_timing_metrics(spec)
    trigger_threshold = seconds_label(timing_metrics.trigger_threshold_time_s)
    pedestrian_time = seconds_label(timing_metrics.pedestrian_time_to_conflict_s)
    return GeneratedScenarioViewModel(
        title=spec.scenario_name,
        scenario_type=spec.scenario_type,
        road_summary=f"{spec.road.type}, {spec.road.lanes_per_direction} lane(s) per direction, {spec.road.speed_limit_kph:g} km/h limit",
        weather_summary="rain / wet road" if spec.weather.rain else f"dry / {spec.weather.road_condition}",
        actor_summary=[f"{actor.id} ({actor.role})" for actor in spec.actors[:8]],
        trigger_summary=f"{spec.trigger.type}: {spec.trigger.source} to {spec.trigger.target} at {spec.trigger.distance_m:g} m",
        criticality_summary=f"{spec.intended_criticality.type}, target TTC {spec.intended_criticality.target_min_ttc_s:g} s",
        ego_speed=ego_speed_label(spec),
        pedestrian_speed=pedestrian_speed_label(spec),
        estimated_ttc=seconds_label(timing_metrics.target_ttc_s),
        target_ttc=seconds_label(timing_metrics.target_ttc_s),
        trigger_threshold_time=trigger_threshold,
        ego_lead_time=seconds_label(timing_metrics.ego_lead_time_to_conflict_s),
        pedestrian_time_to_conflict=pedestrian_time,
        trigger_threshold_summary=(
            f"Trigger threshold: {trigger_threshold} from {spec.trigger.type.replace('_', '-')} {spec.trigger.distance_m:g} m"
            if timing_metrics.trigger_threshold_time_s is not None
            else "Trigger threshold: n/a"
        ),
        pedestrian_conflict_summary=f"Pedestrian to conflict: {pedestrian_time}",
        status_cards=[
            StatusCardViewModel("ScenarioSpec", "generated", "Structured scenario intent is available."),
            StatusCardViewModel("Semantic", semantic_value, semantic_detail),
            StatusCardViewModel("ASAM QC", qc_status_value(qc_result), qc_status_text(qc_result)),
            StatusCardViewModel("esmini", esmini_status_value(esmini_result), esmini_status_text(esmini_result)),
        ],
        diagnostics=diagnostics[:3],
        recommendation=recommendation,
    )


def external_status_cards(
    metadata: XoscMetadata | None,
    qc_result: AsamQcResult | None,
    esmini_result: EsminiResult | None,
    category: str,
) -> list[StatusCardViewModel]:
    parse_value = "passed" if metadata is not None and metadata.parse_success else "not loaded" if metadata is None else "failed"
    parse_detail = "XML metadata extracted." if parse_value == "passed" else "Load or inspect the XML metadata."
    return [
        StatusCardViewModel("Metadata", metadata_status_label(metadata), parse_detail),
        StatusCardViewModel("ASAM QC", qc_status_label(qc_result), qc_status_text(qc_result)),
        StatusCardViewModel("esmini Smoke", esmini_status_label(esmini_result), esmini_status_text(esmini_result)),
        StatusCardViewModel("Compatibility", compatibility_product_label(category), compatibility_explanation(category)),
    ]


def external_compatibility_category(
    metadata: XoscMetadata | None,
    qc_result: AsamQcResult | None,
    esmini_result: EsminiResult | None,
) -> str:
    if metadata is None:
        return "needs_manual_attention"
    if not metadata.parse_success:
        return "metadata_fail"
    if qc_result is not None and qc_result.passed is False:
        return "qc_fail"
    if esmini_result is None:
        return "tool_skipped"
    if not esmini_result.esmini_available:
        return "tool_skipped"
    if esmini_result.executed:
        return "full_pass"
    if esmini_result.timed_out and esmini_result.timeout_classification in {"timeout_after_start", "timeout_possible_long_scenario"}:
        return "smoke_pass_long_running"
    if esmini_result.executed is False:
        return "esmini_fail"
    return "unknown"


def external_diagnostics(
    metadata: XoscMetadata | None,
    qc_result: AsamQcResult | None,
    esmini_result: EsminiResult | None,
    category: str,
) -> list[str]:
    if metadata is None:
        return ["Choose a curated example or load a local .xosc file to start diagnosis."]
    diagnostics: list[str] = []
    if not metadata.parse_success:
        diagnostics.append(f"XML parsing failed: {metadata.parse_error or 'unknown error'}. Inspect the raw XML in Advanced details.")
        return diagnostics
    if metadata.logic_file_paths:
        diagnostics.append("OpenDRIVE LogicFile references were detected; esmini is run from the .xosc directory to preserve relative paths.")
    if metadata.catalog_locations:
        diagnostics.append("CatalogLocations were detected; missing local catalogs can cause QC or esmini failures.")
    if qc_result is None:
        diagnostics.append("ASAM QC has not run yet. Run checks when the checker is installed or accept a skipped tool state.")
    elif qc_result.passed is False:
        diagnostics.append("ASAM QC failed. Use the QC report in Advanced details to inspect standard-compliance issues.")
    elif not qc_result.checker_available:
        diagnostics.append("ASAM QC is unavailable, so standard-compliance checking is classified as skipped.")
    if esmini_result is None:
        diagnostics.append("esmini smoke check has not run yet.")
    elif not esmini_result.esmini_available:
        diagnostics.append("esmini is unavailable; configure ESMINI_BIN or place esmini on PATH for runtime checks.")
    elif esmini_result.timed_out:
        diagnostics.append(f"esmini timed out with classification `{esmini_result.timeout_classification or 'unknown'}`.")
    elif esmini_result.executed is False:
        diagnostics.append(esmini_result.error_message or "esmini failed without a detailed error message.")
    if category == "full_pass":
        diagnostics.append("This scenario is a stable demo candidate for the current toolchain.")
    elif category == "smoke_pass_long_running":
        diagnostics.append("The scenario appears to load/start in smoke mode but may not terminate naturally in full playback.")
    elif category == "needs_manual_attention":
        diagnostics.append("More checks or manual inspection are needed before using this as a stable demo.")
    return diagnostics or ["No additional diagnostics."]


def recommendation_for_external_category(category: str) -> str:
    recommendations = {
        "full_pass": "Use as a stable demo example.",
        "qc_fail": "Use to demonstrate ASAM QC diagnostics.",
        "esmini_fail": "Use to demonstrate runtime/dependency diagnosis.",
        "smoke_pass_long_running": "Use as a long-running playback example; avoid full mode for demos.",
        "metadata_fail": "Inspect XML formatting before further checks.",
        "tool_skipped": "Install/configure optional tools or treat this as metadata-only.",
        "needs_manual_attention": "Load a scenario and run smoke checks before demo use.",
        "unknown": "Inspect advanced details before using in a demo.",
    }
    return recommendations.get(category, recommendations["unknown"])


def compatibility_product_label(category: str) -> str:
    labels = {
        "full_pass": "Stable demo",
        "qc_fail": "QC issue",
        "esmini_fail": "Runtime diagnostic",
        "smoke_pass_long_running": "Runtime diagnostic",
        "metadata_fail": "Needs attention",
        "tool_skipped": "Needs setup",
        "needs_manual_attention": "Needs attention",
        "unknown": "Needs attention",
    }
    return labels.get(category, labels["unknown"])


def metadata_status_label(metadata: XoscMetadata | None) -> str:
    if metadata is None:
        return "Not loaded"
    return "Ready" if metadata.parse_success else "Needs attention"


def qc_status_label(result: AsamQcResult | None) -> str:
    value = qc_status_value(result)
    labels = {
        "not run": "Not run",
        "skipped": "Needs setup",
        "passed": "Passed",
        "failed": "QC issue",
    }
    return labels.get(value, "Needs attention")


def esmini_status_label(result: EsminiResult | None) -> str:
    value = esmini_status_value(result)
    labels = {
        "not run": "Not run",
        "skipped": "Needs setup",
        "passed": "Smoke pass",
        "timeout": "Runtime diagnostic",
        "failed": "Runtime diagnostic",
    }
    return labels.get(value, "Needs attention")


def storyboard_complexity(metadata: XoscMetadata) -> str:
    if not metadata.has_storyboard:
        return "none"
    total = metadata.event_count + metadata.condition_count + metadata.maneuver_count
    if total >= 30:
        return "high"
    if total >= 8:
        return "medium"
    return "low"


def list_summary(values: list[str], empty: str) -> str:
    if not values:
        return empty
    if len(values) <= 2:
        return ", ".join(values)
    return f"{', '.join(values[:2])} + {len(values) - 2} more"


def qc_status_value(result: AsamQcResult | None) -> str:
    if result is None:
        return "not run"
    if not result.checker_available:
        return "skipped"
    if result.passed:
        return "passed"
    return "failed"


def qc_status_text(result: AsamQcResult | None) -> str:
    if result is None:
        return "ASAM QC has not run."
    if not result.checker_available:
        return "Checker unavailable; standard-compliance check skipped."
    if result.passed:
        return "ASAM QC passed."
    return "ASAM QC failed; inspect the report."


def esmini_status_value(result: EsminiResult | None) -> str:
    if result is None:
        return "not run"
    if not result.esmini_available:
        return "skipped"
    if result.executed:
        return "passed"
    if result.timed_out:
        return "timeout"
    return "failed"


def esmini_status_text(result: EsminiResult | None) -> str:
    if result is None:
        return "esmini smoke check has not run."
    if not result.esmini_available:
        return "esmini unavailable; execution check skipped."
    mode = result.mode or "smoke"
    if result.executed:
        return f"esmini {mode} check passed."
    if result.timed_out:
        return f"esmini {mode} timed out: {result.timeout_classification or 'unknown'}."
    return result.error_message or f"esmini {mode} check failed."


def compatibility_explanation(category: str) -> str:
    explanations = {
        "full_pass": "Metadata parsed and runtime smoke check passed.",
        "qc_fail": "Standard-compliance diagnostics are available.",
        "esmini_fail": "Runtime execution failed or could not start.",
        "smoke_pass_long_running": "Scenario starts, but full playback may run long.",
        "metadata_fail": "XML metadata could not be parsed.",
        "tool_skipped": "One or more optional tools are unavailable or not run.",
        "needs_manual_attention": "Load/check the scenario before demo use.",
        "unknown": "The current state is not classified yet.",
    }
    return explanations.get(category, explanations["unknown"])


def ego_speed_label(spec: ScenarioSpec) -> str:
    ego = spec.actor_by_role("ego")
    if ego is None or ego.initial_speed_kph is None:
        return "missing"
    return f"{ego.initial_speed_kph:g} km/h"


def pedestrian_speed_label(spec: ScenarioSpec) -> str:
    pedestrian = spec.actor_by_role("crossing_actor")
    if pedestrian is None or pedestrian.speed_mps is None:
        return "missing"
    return f"{pedestrian.speed_mps:g} m/s"


def seconds_label(value_s: float | None) -> str:
    if value_s is None:
        return "n/a"
    return f"{value_s:.1f} s"


def ttc_label(spec: ScenarioSpec) -> str:
    return seconds_label(compute_timing_metrics(spec).target_ttc_s)
