import subprocess

from scenariocraft.tools.esmini_tool import resolve_esmini_binary, run_esmini


def test_esmini_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ESMINI_BIN", str(tmp_path / "missing-esmini"))
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


def test_esmini_resolves_local_prebuilt_binary(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ESMINI_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda _binary: None)
    local_bin = tmp_path / "third_party" / "esmini" / "v3.3.0" / "extracted" / "esmini-bin_macOS" / "bin" / "esmini"
    local_bin.parent.mkdir(parents=True)
    local_bin.write_text("#!/bin/sh\n", encoding="utf-8")
    local_bin.chmod(0o755)

    resolved = resolve_esmini_binary(search_root=tmp_path)

    assert resolved == local_bin.resolve()


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


def test_esmini_timeout(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("shutil.which", lambda _binary: "/fake/esmini")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"], output="partial", stderr="still running")

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    result = run_esmini(tmp_path / "scenario.xosc", timeout_s=0.1)

    assert result.esmini_available is True
    assert result.executed is False
    assert result.timed_out is True
    assert result.timeout_s == 0.1
