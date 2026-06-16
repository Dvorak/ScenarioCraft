import subprocess

from scenariocraft.tools.esmini_tool import run_esmini


def test_esmini_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: None)

    result = run_esmini(tmp_path / "scenario.xosc", tmp_path, required=True)

    assert result.esmini_available is False
    assert result.executed is None
    assert result.required is True
    assert "not found" in result.stderr
    assert (tmp_path / "esmini_log.txt").exists()


def test_esmini_success(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "loaded", ""),
    )

    result = run_esmini(tmp_path / "scenario.xosc")

    assert result.esmini_available is True
    assert result.executed is True
    assert result.return_code == 0


def test_esmini_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "failed"),
    )

    result = run_esmini(tmp_path / "scenario.xosc")

    assert result.esmini_available is True
    assert result.executed is False
    assert result.return_code == 1
