from __future__ import annotations

import argparse
from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
from scenariocraft.probes import run_pedestrian_occlusion_probes
from scenariocraft.references import XoscMetadata, extract_xosc_metadata
from scenariocraft.schemas import ProbeResult, ScenarioSpec
from scenariocraft.schemas.scenario_spec import ScenarioSpecError
from scenariocraft.tools import (
    EsminiResult,
    build_openscenario,
    generate_2d_preview,
    generate_validation_report,
    run_asam_qc,
    run_esmini,
    validate_semantics,
)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.out)
    if args.load_xosc is not None:
        return _run_loaded_xosc(args, output_dir)

    input_path = Path(args.input)
    scenario_text = input_path.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "input.txt").write_text(scenario_text, encoding="utf-8")

    generator = _get_generator(args.provider)
    try:
        spec = _generate_spec(generator, scenario_text, args)
    except (ScenarioSpecError, TypeError, ValueError) as exc:
        (output_dir / "generation_error.txt").write_text(f"{exc}\n", encoding="utf-8")
        print(f"Scenario generation failed: {exc}")
        return 2
    (output_dir / "scenario_spec.json").write_text(spec.to_json() + "\n", encoding="utf-8")

    preview_path = generate_2d_preview(spec, output_dir / "preview_2d.png")
    build_result = build_openscenario(spec, output_dir)
    qc_result = run_asam_qc(build_result.xosc_path, output_dir)
    esmini_result = run_esmini(
        build_result.xosc_path,
        output_dir,
        required=args.require_esmini,
        binary=args.esmini_bin,
        timeout_s=args.esmini_timeout,
    )
    semantic_result = validate_semantics(spec)
    probe_results = _run_template_probes(spec)
    report_path = generate_validation_report(
        scenario_text,
        spec,
        build_result,
        qc_result,
        esmini_result,
        semantic_result,
        output_dir,
        probe_results=probe_results,
    )
    print(f"Wrote ScenarioSpec: {output_dir / 'scenario_spec.json'}")
    print(f"Wrote 2D preview: {preview_path}")
    print(f"Wrote OpenSCENARIO: {build_result.xosc_path}")
    print(f"Wrote validation report: {report_path}")
    if args.require_esmini and not esmini_result.esmini_available:
        print("Required esmini binary was not found. Set ESMINI_BIN or add esmini to PATH.")
        return 2
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and validate a deterministic scenarioCraft scenario.")
    parser.add_argument("--input", default="examples/pedestrian_occlusion.txt", help="Path to natural-language scenario text.")
    parser.add_argument("--out", default="outputs/demo", help="Output artifact directory.")
    parser.add_argument("--provider", default="mock", choices=["mock"], help="Scenario generator provider.")
    parser.add_argument(
        "--load-xosc",
        default=None,
        help="Run checks against an existing OpenSCENARIO .xosc file without generating a ScenarioSpec.",
    )
    parser.add_argument(
        "--run-esmini",
        action="store_true",
        help="Run the optional esmini load/execution check for --load-xosc.",
    )
    parser.add_argument(
        "--xosc-working-dir",
        default=None,
        help="Working directory for --load-xosc. Defaults to the loaded .xosc file's parent directory.",
    )
    parser.add_argument(
        "--esmini-bin",
        default=None,
        help="Path to an esmini executable. Overrides ESMINI_BIN, PATH, and local third_party/tools lookup.",
    )
    parser.add_argument(
        "--require-esmini",
        action="store_true",
        help="Return a non-zero exit code if esmini is not available.",
    )
    parser.add_argument(
        "--esmini-timeout",
        type=float,
        default=20.0,
        help="Maximum seconds to wait for the esmini load/run check.",
    )
    parser.add_argument(
        "--duration-s",
        type=float,
        default=None,
        help="Override mock pedestrian-occlusion ScenarioTimingSpec total duration.",
    )
    parser.add_argument(
        "--trigger-window-earliest-s",
        type=float,
        default=None,
        help="Override mock pedestrian-occlusion preferred trigger window start.",
    )
    parser.add_argument(
        "--trigger-window-latest-s",
        type=float,
        default=None,
        help="Override mock pedestrian-occlusion preferred trigger window end.",
    )
    return parser.parse_args(argv)


def _run_loaded_xosc(args: argparse.Namespace, output_dir: Path) -> int:
    xosc_path = Path(args.load_xosc).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not xosc_path.exists():
        print(f"OpenSCENARIO file was not found: {xosc_path}")
        return 2
    working_dir = Path(args.xosc_working_dir).expanduser() if args.xosc_working_dir else None
    if args.run_esmini:
        esmini_result = run_esmini(
            xosc_path,
            output_dir,
            working_dir=working_dir,
            required=args.require_esmini,
            binary=args.esmini_bin,
            timeout_s=args.esmini_timeout,
        )
    else:
        resolved_xosc = xosc_path.resolve()
        resolved_working_dir = working_dir.resolve() if working_dir else resolved_xosc.parent
        esmini_result = EsminiResult(
            esmini_available=False,
            command=[],
            working_dir=_display_path(resolved_working_dir),
            return_code=None,
            stdout="",
            stderr="esmini check was not requested.",
            executed=None,
            error_message="esmini check was not requested.",
            playback_path=None,
            required=args.require_esmini,
            timeout_s=args.esmini_timeout,
        )
        (output_dir / "esmini_log.txt").write_text("esmini check was not requested.\n", encoding="utf-8")
        (output_dir / "esmini_stdout.txt").write_text("", encoding="utf-8")
        (output_dir / "esmini_stderr.txt").write_text(esmini_result.stderr, encoding="utf-8")
    metadata = extract_xosc_metadata(xosc_path)
    report_path = _write_loaded_xosc_report(xosc_path, metadata, esmini_result, output_dir)
    print(f"Loaded OpenSCENARIO: {xosc_path}")
    print(f"Wrote esmini log: {output_dir / 'esmini_log.txt'}")
    print(f"Wrote validation report: {report_path}")
    if args.require_esmini and not esmini_result.esmini_available:
        print("Required esmini binary was not found. Set ESMINI_BIN or add esmini to PATH.")
        return 2
    return 0


def _write_loaded_xosc_report(
    xosc_path: Path,
    metadata: XoscMetadata,
    result: EsminiResult,
    output_dir: Path,
) -> Path:
    report_path = output_dir / "validation_report.md"
    if not result.esmini_available:
        esmini_section = "\n".join([
            "esmini was not found. Scenario playback/execution check was skipped."
            if result.command
            else "esmini execution check was not requested.",
            f"- Working directory: `{result.working_dir}`",
            f"- Error message: `{result.error_message}`",
        ])
    else:
        esmini_section = "\n".join([
            f"- Command: `{' '.join(result.command)}`",
            f"- Working directory: `{result.working_dir}`",
            f"- Timeout seconds: `{result.timeout_s}`",
            f"- Timed out: `{result.timed_out}`",
            f"- Return code: `{result.return_code}`",
            f"- Executed: `{result.executed}`",
            f"- Error message: `{result.error_message}`",
        ])
    report_path.write_text(
        f"""# scenarioCraft Loaded OpenSCENARIO Report

## Loaded OpenSCENARIO

- Source file: `{xosc_path}`
- The file was executed in place; it was not copied into the output directory.

## Extracted Metadata

{_metadata_section(metadata)}

## esmini Execution / Playback

{esmini_section}

## Generated Artifacts

- `esmini_log.txt`
- `esmini_stdout.txt`
- `esmini_stderr.txt`
- `validation_report.md`

## Known Limitations

- This mode does not parse external OpenSCENARIO files into ScenarioSpec.
- esmini is used only as an optional load/execution check; MP4/GIF rendering is not implemented.
""",
        encoding="utf-8",
    )
    return report_path


def _metadata_section(metadata: XoscMetadata) -> str:
    if not metadata.file_exists:
        return "OpenSCENARIO file does not exist."
    if not metadata.parse_success:
        return f"OpenSCENARIO XML parsing failed: `{metadata.parse_error}`"
    lines = [
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
    ]
    return "\n".join(lines)


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


def _get_generator(provider: str) -> ScenarioGenerator:
    if provider == "mock":
        return MockScenarioGenerator()
    raise ValueError(f"Unsupported provider: {provider}")


def _generate_spec(generator: ScenarioGenerator, scenario_text: str, args: argparse.Namespace) -> ScenarioSpec:
    template_parameters: dict[str, object] = {}
    if args.duration_s is not None:
        template_parameters["total_duration_s"] = args.duration_s
    if args.trigger_window_earliest_s is not None:
        template_parameters["preferred_trigger_earliest_s"] = args.trigger_window_earliest_s
    if args.trigger_window_latest_s is not None:
        template_parameters["preferred_trigger_latest_s"] = args.trigger_window_latest_s
    if template_parameters and isinstance(generator, MockScenarioGenerator):
        return generator.generate_spec(scenario_text, **template_parameters)
    return generator.generate_spec(scenario_text)


def _run_template_probes(spec: ScenarioSpec) -> tuple[ProbeResult, ...]:
    if spec.scenario_type == "pedestrian_occlusion" and spec.layout is not None:
        return run_pedestrian_occlusion_probes(spec)
    return ()


if __name__ == "__main__":
    raise SystemExit(main())
