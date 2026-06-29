from __future__ import annotations

from pathlib import Path

from scenariocraft.application.contracts import (
    ExternalScenarioWorkflowRequest,
    ExternalScenarioWorkflowResult,
    ExternalScenarioWorkflowStatus,
)
from scenariocraft.references import XoscMetadata, extract_xosc_metadata
from scenariocraft.core.build import BuildResult
from scenariocraft.runtime import AsamQcResult, EsminiResult, run_asam_qc, run_esmini


def run_external_scenario_workflow(request: ExternalScenarioWorkflowRequest) -> ExternalScenarioWorkflowResult:
    xosc_path = Path(request.xosc_path).expanduser()
    output_dir = request.output_dir
    options = request.options

    if not xosc_path.exists():
        raise FileNotFoundError(f"OpenSCENARIO file does not exist: {xosc_path}")
    if not xosc_path.is_file():
        raise IsADirectoryError(f"OpenSCENARIO path is not a file: {xosc_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    xosc_text = xosc_path.read_text(encoding="utf-8", errors="replace")
    metadata = extract_xosc_metadata(xosc_path)
    build_result = BuildResult(xosc_path=xosc_path, builder="loaded_xosc")

    qc_result = run_asam_qc(xosc_path, output_dir) if options.run_asam_qc else _missing_qc_result(xosc_path, output_dir)
    esmini_result = (
        run_esmini(
            xosc_path,
            output_dir,
            working_dir=xosc_path.parent,
            required=options.require_esmini,
            binary=options.esmini_bin,
            timeout_s=options.esmini_timeout_s,
            mode=options.esmini_mode,
            sim_duration_s=options.esmini_sim_duration_s,
        )
        if options.run_esmini
        else _missing_esmini_result(xosc_path)
    )
    report_path = None
    report_text = ""
    if options.run_report:
        report_path = _write_loaded_xosc_report(
            output_dir,
            xosc_path,
            metadata,
            qc_result,
            esmini_result,
            source=request.source,
            relative_path=request.relative_path,
        )
        report_text = report_path.read_text(encoding="utf-8")

    return ExternalScenarioWorkflowResult(
        request=request,
        status=_status(metadata, options.run_asam_qc, options.run_esmini),
        xosc_path=xosc_path,
        working_dir=xosc_path.parent,
        metadata=metadata,
        build_result=build_result,
        xosc_text=xosc_text,
        qc_result=qc_result,
        esmini_result=esmini_result,
        report_path=report_path,
        report_text=report_text,
    )


def _status(
    metadata: XoscMetadata,
    ran_qc: bool,
    ran_esmini: bool,
) -> ExternalScenarioWorkflowStatus:
    if not metadata.file_exists or not metadata.parse_success:
        return ExternalScenarioWorkflowStatus("failed", "Loaded OpenSCENARIO metadata extraction failed.")
    if ran_qc or ran_esmini:
        return ExternalScenarioWorkflowStatus("checked", "Loaded OpenSCENARIO checks completed.")
    return ExternalScenarioWorkflowStatus("loaded", "Loaded OpenSCENARIO file.")


def _write_loaded_xosc_report(
    output_dir: Path,
    xosc_path: Path,
    metadata: XoscMetadata | None,
    qc_result: AsamQcResult,
    esmini_result: EsminiResult,
    *,
    source: str,
    relative_path: str,
) -> Path:
    report_path = output_dir / "validation_report.md"
    report_path.write_text(
        "\n".join([
            "# ScenarioCraft Loaded OpenSCENARIO Report",
            "",
            "## Loaded OpenSCENARIO",
            "",
            f"- Source file: `{xosc_path}`",
            f"- Selected source: `{source or 'custom path'}`",
            f"- Selected relative path: `{relative_path or 'n/a'}`",
            f"- esmini working directory: `{xosc_path.parent}`",
            "- The file was inspected in place; ScenarioCraft did not modify it.",
            "",
            "## Extracted Metadata",
            "",
            _metadata_markdown(metadata),
            "",
            "## ASAM Quality Check",
            "",
            _qc_markdown(qc_result),
            "",
            "## esmini Execution / Playback",
            "",
            _esmini_markdown(esmini_result),
            "",
            "## Known Limitations",
            "",
            "- 2D preview is currently available for ScenarioSpec-generated scenarios only.",
            "- External `.xosc` files are not reconstructed as ScenarioSpec.",
            "- Natural-language editing for external `.xosc` is not implemented yet.",
        ]),
        encoding="utf-8",
    )
    return report_path


def _metadata_markdown(metadata: XoscMetadata | None) -> str:
    if metadata is None:
        return "No metadata extracted."
    if not metadata.file_exists:
        return "OpenSCENARIO file does not exist."
    if not metadata.parse_success:
        return f"OpenSCENARIO XML parsing failed: `{metadata.parse_error}`"
    logic_note = ""
    if metadata.logic_file_paths:
        logic_note = (
            "\n- Relative path handling: esmini checks run from the `.xosc` parent directory so "
            "OpenDRIVE LogicFile references remain relative to the source scenario."
        )
    return "\n".join([
        f"- Parse success: `{metadata.parse_success}`",
        f"- OpenSCENARIO version: `{metadata.open_scenario_version}`",
        f"- FileHeader: `{metadata.file_header}`",
        f"- Logic files: `{metadata.logic_file_paths}`",
        f"- Scene graph files: `{metadata.scene_graph_file_paths}`",
        f"- Catalog locations: `{metadata.catalog_locations}`",
        f"- Parameters: `{metadata.parameter_names}`",
        f"- Scenario objects: `{metadata.scenario_object_names}`",
        f"- Has storyboard: `{metadata.has_storyboard}`",
        "- Approximate counts: "
        f"parameters={metadata.parameter_count}, "
        f"scenario_objects={metadata.scenario_object_count}, "
        f"maneuvers={metadata.maneuver_count}, "
        f"events={metadata.event_count}, "
        f"conditions={metadata.condition_count}",
        logic_note,
    ]).strip()


def _qc_markdown(result: AsamQcResult) -> str:
    if not result.checker_available:
        return "ASAM OpenSCENARIO XML checker was not found. Standard-compliance checking was skipped."
    return "\n".join([
        f"- Command: `{' '.join(result.command)}`",
        f"- Return code: `{result.return_code}`",
        f"- Passed: `{result.passed}`",
        f"- Result path: `{result.result_path}`",
    ])


def _esmini_markdown(result: EsminiResult) -> str:
    if not result.esmini_available:
        return "esmini was not found. Scenario playback/execution check was skipped."
    return "\n".join([
        f"- Command: `{' '.join(result.command)}`",
        f"- Working directory: `{result.working_dir}`",
        f"- Return code: `{result.return_code}`",
        f"- Executed: `{result.executed}`",
        f"- Error message: `{result.error_message}`",
    ])


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
