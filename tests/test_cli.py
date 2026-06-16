from pathlib import Path
import subprocess

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
    assert (output_dir / "scenario.xosc").exists()
    assert (output_dir / "qc_report.json").exists()
    assert (output_dir / "esmini_log.txt").exists()
    assert "Scenario playback/execution check was skipped" in (output_dir / "validation_report.md").read_text(
        encoding="utf-8"
    )


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
