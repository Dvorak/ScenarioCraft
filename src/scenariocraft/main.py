from __future__ import annotations

import argparse
from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator, ScenarioGenerator
from scenariocraft.tools import build_openscenario, generate_validation_report, run_asam_qc, run_esmini, validate_semantics


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    input_path = Path(args.input)
    output_dir = Path(args.out)
    scenario_text = input_path.read_text(encoding="utf-8")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "input.txt").write_text(scenario_text, encoding="utf-8")

    generator = _get_generator(args.provider)
    spec = generator.generate_spec(scenario_text)
    (output_dir / "scenario_spec.json").write_text(spec.to_json() + "\n", encoding="utf-8")

    build_result = build_openscenario(spec, output_dir)
    qc_result = run_asam_qc(build_result.xosc_path, output_dir)
    esmini_result = run_esmini(build_result.xosc_path, output_dir, required=args.require_esmini)
    semantic_result = validate_semantics(spec)
    report_path = generate_validation_report(
        scenario_text,
        spec,
        build_result,
        qc_result,
        esmini_result,
        semantic_result,
        output_dir,
    )
    print(f"Wrote ScenarioSpec: {output_dir / 'scenario_spec.json'}")
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
        "--require-esmini",
        action="store_true",
        help="Return a non-zero exit code if esmini is not available on PATH or via ESMINI_BIN.",
    )
    return parser.parse_args(argv)


def _get_generator(provider: str) -> ScenarioGenerator:
    if provider == "mock":
        return MockScenarioGenerator()
    raise ValueError(f"Unsupported provider: {provider}")


if __name__ == "__main__":
    raise SystemExit(main())
