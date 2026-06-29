import subprocess

from scenariocraft.runtime.asam_qc import run_asam_qc


def test_asam_qc_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ASAM_QC_OPENSCENARIOXML_BIN", "missing-qc-openscenario")
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    result = run_asam_qc(tmp_path / "scenario.xosc", tmp_path)

    assert result.checker_available is False
    assert result.passed is None
    assert "not found" in result.stderr
    assert result.command == ["missing-qc-openscenario", "-c", str(tmp_path / "qc_config.xml")]
    assert result.config_path == str(tmp_path / "qc_config.xml")
    assert result.result_path == str(tmp_path / "qc_result.xqar")
    assert (tmp_path / "qc_config.xml").exists()
    assert (tmp_path / "qc_report.json").exists()


def test_asam_qc_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/asam")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "ok", ""),
    )

    result = run_asam_qc(tmp_path / "scenario.xosc")

    assert result.checker_available is True
    assert result.passed is True
    assert result.return_code == 0
    assert result.command == ["qc_openscenario", "-c", str(tmp_path / "qc_config.xml")]


def test_asam_qc_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/asam")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "invalid"),
    )

    result = run_asam_qc(tmp_path / "scenario.xosc")

    assert result.checker_available is True
    assert result.passed is False
    assert result.return_code == 2
