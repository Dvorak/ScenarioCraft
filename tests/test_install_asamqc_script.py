from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path


def _load_installer():
    script_path = Path("scripts/install_asamqc.py")
    spec = importlib.util.spec_from_file_location("install_asamqc", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_asamqc_records_explicit_binary_without_install(tmp_path: Path, capsys) -> None:
    installer = _load_installer()
    binary = tmp_path / "qc_openscenario"
    marker = tmp_path / "ASAM_QC_OPENSCENARIOXML_BIN"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")

    exit_code = installer.main([
        "--skip-install",
        "--binary",
        str(binary),
        "--marker",
        str(marker),
    ])

    assert exit_code == 0
    assert marker.read_text(encoding="utf-8").strip() == str(binary)
    stdout = capsys.readouterr().out
    assert "Resolved ASAM QC OpenSCENARIO checker:" in stdout
    assert "export ASAM_QC_OPENSCENARIOXML_BIN=" in stdout
    assert '"$ASAM_QC_OPENSCENARIOXML_BIN" --help' in stdout


def test_install_asamqc_runs_install_from_project_root(monkeypatch, tmp_path: Path) -> None:
    installer = _load_installer()
    project_root = tmp_path / "project"
    binary = tmp_path / "qc_openscenario"
    project_root.mkdir()
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(command, cwd, check):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["check"] = check
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("shutil.which", lambda candidate: str(binary) if candidate == "qc_openscenario" else None)

    exit_code = installer.main([
        "--project-root",
        str(project_root),
        "--marker",
        "third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN",
        "--installer",
        "pip",
    ])

    marker = project_root / "third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN"
    assert exit_code == 0
    assert captured["cwd"] == project_root
    assert captured["check"] is False
    assert captured["command"][:4] == [
        installer.sys.executable,
        "-m",
        "pip",
        "install",
    ]
    assert marker.read_text(encoding="utf-8").strip() == str(binary)
