from __future__ import annotations

from pathlib import Path

from scenariocraft.application.contracts import (
    ScenarioArtifactPaths,
    ScenarioWorkflowOptions,
    ScenarioWorkflowRequest,
    ScenarioWorkflowResult,
    ScenarioWorkflowStatus,
)
from scenariocraft.application.demo_cases import PreparedDemoCase, prepare_demo_case
from scenariocraft.core.probes import run_artifact_consistency_probes, run_pedestrian_occlusion_probes
from scenariocraft.core.probes.runtime_pipeline import run_and_write_runtime_consistency_probes
from scenariocraft.core.build import BuildResult, build_openscenario
from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.rendering import generate_2d_preview, generate_validation_report
from scenariocraft.external_tools import (
    AsamQcResult,
    EsminiPlaybackResult,
    EsminiResult,
    run_asam_qc,
    run_esmini,
    run_esmini_playback,
)
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.core.validation import SemanticValidationResult
from scenariocraft.core.validation import validate_semantics


def run_generated_scenario_workflow(request: ScenarioWorkflowRequest) -> ScenarioWorkflowResult:
    output_dir = request.output_dir
    options = request.options
    output_dir.mkdir(parents=True, exist_ok=True)

    canonical_spec = _generate_spec(request)
    prepared_case = _prepare_case(request, canonical_spec, output_dir)
    spec = prepared_case.experiment_spec if prepared_case is not None else canonical_spec

    input_path = output_dir / "input.txt"
    spec_path = output_dir / "scenario_spec.json"
    input_path.write_text(request.scenario_text, encoding="utf-8")
    spec_path.write_text(spec.to_json() + "\n", encoding="utf-8")

    build_result = build_openscenario(spec, output_dir)
    xosc_text = build_result.xosc_path.read_text(encoding="utf-8")

    preview_path = _generate_preview(spec, output_dir, options)
    semantic_result = validate_semantics(spec) if options.run_semantics else None
    geometry_results = _geometry_probe_results(spec, options, prepared_case)
    artifact_results = _artifact_probe_results(spec, options, build_result)

    skip_optional = _should_skip_optional_integrations(options, prepared_case)
    qc_result = None
    esmini_result = None
    playback_result = None
    runtime_results = ()
    report_path = None
    report_text = ""

    if options.run_asam_qc and not skip_optional:
        qc_result = run_asam_qc(build_result.xosc_path, output_dir)
    if options.run_esmini and not skip_optional:
        esmini_result = run_esmini(
            build_result.xosc_path,
            output_dir,
            required=options.require_esmini,
            binary=options.esmini_bin,
            timeout_s=options.esmini_timeout_s,
        )
    if options.run_playback and not skip_optional:
        playback_result = run_esmini_playback(
            build_result.xosc_path,
            output_dir,
            working_dir=build_result.xosc_path.parent,
            binary=options.esmini_bin,
            timeout_s=options.playback_timeout_s,
            sim_duration_s=options.esmini_sim_duration_s,
            try_video=options.try_playback_video,
            mode=options.playback_mode,
        )
        esmini_result = _read_esmini_result(output_dir) or esmini_result
    if options.run_runtime_probes and not skip_optional:
        runtime_results = run_and_write_runtime_consistency_probes(
            spec,
            output_dir=output_dir,
            xosc_path=build_result.xosc_path,
            xodr_path=build_result.xodr_path,
        )
    if options.run_report and not skip_optional:
        semantic_for_report = semantic_result or validate_semantics(spec)
        qc_for_report = qc_result or _missing_qc_result(build_result.xosc_path, output_dir)
        esmini_for_report = esmini_result or _missing_esmini_result(build_result.xosc_path)
        report_path = generate_validation_report(
            request.scenario_text,
            spec,
            build_result,
            qc_for_report,
            esmini_for_report,
            semantic_for_report,
            output_dir,
            probe_results=geometry_results,
            playback_result=playback_result,
            artifact_probe_results=artifact_results,
            runtime_probe_results=runtime_results,
        )
        semantic_result = semantic_for_report
        qc_result = qc_for_report
        esmini_result = esmini_for_report
        report_text = report_path.read_text(encoding="utf-8")

    artifacts = ScenarioArtifactPaths(
        output_dir=output_dir,
        input_path=input_path,
        scenario_spec_path=spec_path,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
        preview_path=preview_path,
        report_path=report_path,
        qc_report_path=output_dir / "qc_report.json" if (output_dir / "qc_report.json").exists() else None,
        esmini_result_path=output_dir / "esmini_result.json" if (output_dir / "esmini_result.json").exists() else None,
        playback_result_path=output_dir / "esmini_playback_result.json"
        if (output_dir / "esmini_playback_result.json").exists()
        else None,
        playback_path=Path(playback_result.playback_path) if playback_result and playback_result.playback_path else None,
    )
    status = _workflow_status(prepared_case, semantic_result, geometry_results, artifact_results, skip_optional)
    return ScenarioWorkflowResult(
        request=request,
        status=status,
        artifacts=artifacts,
        spec=spec,
        original_spec=prepared_case.original_spec if prepared_case is not None else canonical_spec,
        prepared_case=prepared_case,
        build_result=build_result,
        semantic_result=semantic_result,
        geometry_probe_results=geometry_results,
        artifact_probe_results=artifact_results,
        runtime_probe_results=runtime_results,
        qc_result=qc_result,
        esmini_result=esmini_result,
        playback_result=playback_result,
        xosc_text=xosc_text,
        report_text=report_text,
    )


def _generate_spec(request: ScenarioWorkflowRequest) -> ScenarioSpec:
    if request.provider_name != "mock":
        raise ValueError(f"Unsupported provider: {request.provider_name}")
    return generate_default_pedestrian_occlusion_spec(
        request.scenario_text,
        **request.template_parameters,
    )


def _prepare_case(
    request: ScenarioWorkflowRequest,
    canonical_spec: ScenarioSpec,
    output_dir: Path,
) -> PreparedDemoCase | None:
    if not request.demo_case_id:
        return None
    return prepare_demo_case(request.demo_case_id, canonical_spec, output_dir)


def _generate_preview(
    spec: ScenarioSpec,
    output_dir: Path,
    options: ScenarioWorkflowOptions,
) -> Path | None:
    if not options.run_preview:
        return None
    return generate_2d_preview(
        spec,
        output_dir / "preview_2d.png",
        display_orientation=options.preview_display_orientation,
        presentation_style=options.preview_presentation_style,
    )


def _geometry_probe_results(
    spec: ScenarioSpec,
    options: ScenarioWorkflowOptions,
    prepared_case: PreparedDemoCase | None,
) -> tuple:
    if prepared_case is not None:
        return prepared_case.initial_geometry_probe_results
    if not options.run_geometry_probes:
        return ()
    return run_pedestrian_occlusion_probes(spec)


def _artifact_probe_results(
    spec: ScenarioSpec,
    options: ScenarioWorkflowOptions,
    build_result: BuildResult,
) -> tuple:
    if not options.run_artifact_probes:
        return ()
    return run_artifact_consistency_probes(
        spec,
        xosc_path=build_result.xosc_path,
        xodr_path=build_result.xodr_path,
    )


def _should_skip_optional_integrations(
    options: ScenarioWorkflowOptions,
    prepared_case: PreparedDemoCase | None,
) -> bool:
    return bool(
        options.stop_optional_integrations_when_demo_repair_required
        and prepared_case is not None
        and prepared_case.case.fault_domain != "none"
    )


def _workflow_status(
    prepared_case: PreparedDemoCase | None,
    semantic_result: SemanticValidationResult | None,
    geometry_results: tuple,
    artifact_results: tuple,
    skipped_optional: bool,
) -> ScenarioWorkflowStatus:
    warnings: list[str] = []
    if skipped_optional:
        warnings.append("Optional QC, runtime, playback, and report steps were skipped for a controlled fault case.")
    if prepared_case is not None and prepared_case.repair_required:
        return ScenarioWorkflowStatus("repair_required", prepared_case.terminal_reason, tuple(warnings))
    if prepared_case is not None and prepared_case.detection_only:
        return ScenarioWorkflowStatus("artifact_mismatch", prepared_case.terminal_reason, tuple(warnings))
    if any(not result.passed for result in geometry_results):
        return ScenarioWorkflowStatus("repair_required", "ScenarioSpec geometry probes failed.", tuple(warnings))
    if any(not result.passed for result in artifact_results):
        return ScenarioWorkflowStatus("artifact_mismatch", "Generated artifact consistency probes failed.", tuple(warnings))
    if semantic_result is not None and not semantic_result.passed:
        return ScenarioWorkflowStatus("validation_failed", "Semantic validation failed.", tuple(warnings))
    return ScenarioWorkflowStatus("passed", "Generated scenario workflow completed.", tuple(warnings))


def _missing_qc_result(xosc_path: Path, output_dir: Path) -> AsamQcResult:
    config_path = output_dir / "qc_config.xml"
    result_path = output_dir / "qc_result.xqar"
    return AsamQcResult(
        checker_available=False,
        command=["qc_openscenario", "-c", str(config_path)],
        return_code=None,
        stdout="",
        stderr="ASAM OpenSCENARIO XML checker has not been run.",
        passed=None,
        config_path=str(config_path),
        result_path=str(result_path),
    )


def _missing_esmini_result(xosc_path: Path) -> EsminiResult:
    return EsminiResult(
        esmini_available=False,
        command=["esmini", "--osc", str(xosc_path), "--headless", "--quit_at_end", "--disable_log"],
        working_dir=str(xosc_path.parent),
        return_code=None,
        stdout="",
        stderr="esmini has not been run.",
        executed=None,
        error_message="esmini has not been run.",
        playback_path=None,
    )


def _read_esmini_result(output_dir: Path) -> EsminiResult | None:
    result_path = output_dir / "esmini_result.json"
    if not result_path.exists():
        return None
    try:
        import json

        return EsminiResult(**json.loads(result_path.read_text(encoding="utf-8")))
    except (TypeError, ValueError):
        return None
