from __future__ import annotations

from pathlib import Path

from scenariocraft.tooling import setup_tools as setup_tool


def test_setup_tool_runs_optional_tool_installers(monkeypatch, tmp_path: Path, capsys) -> None:
    calls: list[tuple[str, list[str]]] = []

    monkeypatch.setattr(
        setup_tool.install_esmini,
        "main",
        lambda argv: calls.append(("esmini", list(argv or []))) or 0,
    )
    monkeypatch.setattr(
        setup_tool.install_asamqc,
        "main",
        lambda argv: calls.append(("asamqc", list(argv or []))) or 0,
    )

    exit_code = setup_tool.main(["--project-root", str(tmp_path)])

    assert exit_code == 0
    assert calls == [
        ("esmini", ["--install-dir", str(tmp_path / "third_party/esmini"), "--package", "bin"]),
        ("asamqc", ["--project-root", str(tmp_path)]),
    ]
    stdout = capsys.readouterr().out
    assert "http://localhost:8501" in stdout
    assert ".venv/bin/just web" in stdout


def test_setup_tool_can_skip_optional_installers(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(setup_tool.install_esmini, "main", lambda argv: (_ for _ in ()).throw(AssertionError))
    monkeypatch.setattr(setup_tool.install_asamqc, "main", lambda argv: (_ for _ in ()).throw(AssertionError))

    exit_code = setup_tool.main(["--project-root", str(tmp_path), "--skip-esmini", "--skip-asam-qc"])

    assert exit_code == 0
