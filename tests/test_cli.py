from pathlib import Path
import subprocess
from dataclasses import replace

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.main import main


def test_cli_happy_path_with_mock_provider(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    output_dir = tmp_path / "out"
    input_path.write_text("rainy pedestrian occlusion", encoding="utf-8")
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    exit_code = main(["--input", str(input_path), "--out", str(output_dir), "--provider", "mock"])

    assert exit_code == 0
    assert (output_dir / "input.txt").exists()
    assert (output_dir / "scenario_spec.json").exists()
    assert (output_dir / "preview_2d.png").exists()
    assert (output_dir / "scenario.xosc").exists()
    assert (output_dir / "qc_report.json").exists()
    assert (output_dir / "esmini_log.txt").exists()
    assert "Scenario playback/execution check was skipped" in (output_dir / "validation_report.md").read_text(
        encoding="utf-8"
    )
    report = (output_dir / "validation_report.md").read_text(encoding="utf-8")
    assert "## Template-Aware Probes" in report
    assert "`ego_footprint_in_ego_lane`" in report
    assert "`trigger_point_before_conflict_and_in_ego_lane`" in report


def test_cli_layout_free_spec_succeeds_without_template_aware_probes(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    output_dir = tmp_path / "out"
    input_path.write_text("rainy pedestrian occlusion", encoding="utf-8")
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    class LayoutFreeGenerator:
        def generate_spec(self, scenario_text: str):
            spec = MockScenarioGenerator().generate_spec(scenario_text)
            return replace(spec, layout=None, spatial_relations=())

    monkeypatch.setattr("scenariocraft.main.MockScenarioGenerator", LayoutFreeGenerator)

    exit_code = main(["--input", str(input_path), "--out", str(output_dir), "--provider", "mock"])

    assert exit_code == 0
    assert (output_dir / "scenario_spec.json").exists()
    assert (output_dir / "scenario.xosc").exists()
    report = (output_dir / "validation_report.md").read_text(encoding="utf-8")
    assert "## Template-Aware Probes" not in report


def test_cli_require_esmini_returns_nonzero_when_missing(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    output_dir = tmp_path / "out"
    input_path.write_text("rainy pedestrian occlusion", encoding="utf-8")
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    exit_code = main([
        "--input",
        str(input_path),
        "--out",
        str(output_dir),
        "--provider",
        "mock",
        "--require-esmini",
    ])

    assert exit_code == 2
    assert (output_dir / "validation_report.md").exists()


def test_cli_uses_explicit_esmini_binary(monkeypatch, tmp_path: Path) -> None:
    input_path = tmp_path / "input.txt"
    output_dir = tmp_path / "out"
    esmini_bin = tmp_path / "esmini"
    input_path.write_text("rainy pedestrian occlusion", encoding="utf-8")
    esmini_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr("shutil.which", lambda binary: str(esmini_bin) if binary == str(esmini_bin) else None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "loaded", ""),
    )

    exit_code = main([
        "--input",
        str(input_path),
        "--out",
        str(output_dir),
        "--provider",
        "mock",
        "--esmini-bin",
        str(esmini_bin),
        "--require-esmini",
    ])

    assert exit_code == 0
    assert "available: True" in (output_dir / "esmini_log.txt").read_text(encoding="utf-8")


def test_cli_load_xosc_runs_esmini_from_xosc_parent(monkeypatch, tmp_path: Path) -> None:
    reference_dir = tmp_path / "reference"
    output_dir = tmp_path / "out"
    xosc_path = reference_dir / "reference.xosc"
    reference_dir.mkdir()
    xosc_path.write_text(
        """<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="3" description="reference"/>
  <Entities><ScenarioObject name="ego"/></Entities>
  <Storyboard/>
</OpenSCENARIO>
""",
        encoding="utf-8",
    )
    captured = {}
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def fake_run(*args, **kwargs):
        captured["command"] = args[0]
        captured["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(args[0], 0, "loaded", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code = main([
        "--load-xosc",
        str(xosc_path),
        "--out",
        str(output_dir),
        "--run-esmini",
    ])

    assert exit_code == 0
    assert captured["cwd"] == reference_dir
    assert captured["command"][2] == "reference.xosc"
    assert not (output_dir / "reference.xosc").exists()
    assert not (output_dir / "scenario_spec.json").exists()
    assert (output_dir / "esmini_log.txt").exists()
    assert (output_dir / "esmini_stdout.txt").read_text(encoding="utf-8") == "loaded"
    report = (output_dir / "validation_report.md").read_text(encoding="utf-8")
    assert "Loaded OpenSCENARIO" in report
    assert "Extracted Metadata" in report
    assert "ego" in report
