from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.loop import run_bounded_orchestrator
from scenariocraft.repair.providers import FakeRepairProvider
from scenariocraft.schemas import Point2D, Pose2D


def test_orchestrator_passes_canonical_scenario_and_writes_artifacts(monkeypatch, tmp_path: Path) -> None:
    _disable_external_tools(monkeypatch, tmp_path)

    result = run_bounded_orchestrator(
        _canonical_spec(),
        output_dir=tmp_path,
        scenario_text="rainy pedestrian occlusion",
        repair_provider=FakeRepairProvider(),
    )

    assert result.terminal_status == "passed"
    assert result.repair_run_result is not None
    assert result.repair_run_result.rounds == ()
    assert result.build_result is not None
    assert result.final_geometry_probe_results
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert result.final_artifact_probe_results
    assert all(probe.passed for probe in result.final_artifact_probe_results)
    assert result.runtime_probe_results
    assert any(probe.name == "runtime_motion_verifiable" for probe in result.runtime_probe_results)
    assert (tmp_path / "orchestrator_result.json").exists()
    assert (tmp_path / "runtime_probe_results.json").exists()
    assert (tmp_path / "validation_report.md").exists()
    assert "## Runtime Consistency Probes" in (tmp_path / "validation_report.md").read_text(encoding="utf-8")
    json.loads((tmp_path / "orchestrator_result.json").read_text(encoding="utf-8"))


def test_orchestrator_repairs_van_fault_before_building(monkeypatch, tmp_path: Path) -> None:
    _disable_external_tools(monkeypatch, tmp_path)

    result = run_bounded_orchestrator(
        _van_outside_parking_strip(),
        output_dir=tmp_path,
        repair_provider=FakeRepairProvider(),
    )

    assert result.terminal_status == "passed"
    assert result.repair_run_result is not None
    assert len(result.repair_run_result.rounds) == 1
    patch = result.repair_run_result.rounds[0].proposed_patch
    assert patch is not None
    assert patch.operations[0].to_dict()["op"] == "reposition_actor_to_band"
    assert all(probe.passed for probe in result.final_geometry_probe_results)
    assert result.build_result is not None and result.build_result.xosc_path.exists()


def test_orchestrator_repairs_trigger_after_conflict(monkeypatch, tmp_path: Path) -> None:
    _disable_external_tools(monkeypatch, tmp_path)

    result = run_bounded_orchestrator(
        _trigger_after_conflict(),
        output_dir=tmp_path,
        repair_provider=FakeRepairProvider(),
    )

    assert result.terminal_status == "passed"
    assert result.repair_run_result is not None
    assert len(result.repair_run_result.rounds) == 1
    patch = result.repair_run_result.rounds[0].proposed_patch
    assert patch is not None
    assert [operation.to_dict()["op"] for operation in patch.operations] == [
        "set_named_point",
        "set_trigger_point_by_lead_time",
    ]
    assert all(probe.passed for probe in result.final_geometry_probe_results)


def test_orchestrator_without_provider_reports_repair_required(tmp_path: Path) -> None:
    result = run_bounded_orchestrator(
        _van_outside_parking_strip(),
        output_dir=tmp_path,
        repair_provider=None,
    )

    assert result.terminal_status == "repair_required"
    assert result.build_result is None
    assert result.runtime_probe_results == ()
    assert any(not probe.passed for probe in result.final_geometry_probe_results)
    assert (tmp_path / "orchestrator_result.json").exists()


def test_orchestrator_preserves_provider_refusal_as_terminal(monkeypatch, tmp_path: Path) -> None:
    provider = FakeRepairProvider()
    provider.propose_patch = Mock(wraps=provider.propose_patch)

    result = run_bounded_orchestrator(
        _pedestrian_outside_sidewalk(),
        output_dir=tmp_path,
        repair_provider=provider,
    )

    assert result.terminal_status == "provider_refused"
    assert provider.propose_patch.call_count == 1
    assert result.build_result is None
    assert result.runtime_probe_results == ()
    assert result.report_path is None


def test_cli_orchestrator_path_writes_unified_result(monkeypatch, tmp_path: Path) -> None:
    from scenariocraft.main import main

    _disable_external_tools(monkeypatch, tmp_path)
    input_path = tmp_path / "input.txt"
    output_dir = tmp_path / "out"
    input_path.write_text("rainy pedestrian occlusion", encoding="utf-8")

    exit_code = main([
        "--input",
        str(input_path),
        "--out",
        str(output_dir),
        "--provider",
        "mock",
        "--use-orchestrator",
    ])

    assert exit_code == 0
    result = json.loads((output_dir / "orchestrator_result.json").read_text(encoding="utf-8"))
    assert result["terminal_status"] == "passed"
    assert (output_dir / "runtime_probe_results.json").exists()
    assert (output_dir / "validation_report.md").exists()


def _disable_external_tools(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ESMINI_BIN", "missing-esmini")
    monkeypatch.setenv("ASAM_QC_OPENSCENARIOXML_BIN", "missing-qc")
    monkeypatch.setattr("shutil.which", lambda _binary: None)


def _canonical_spec():
    return MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")


def _van_outside_parking_strip():
    spec = _canonical_spec()
    assert spec.layout is not None
    pose = spec.layout.actor_poses["parked_van"]
    actor_poses = {
        **spec.layout.actor_poses,
        "parked_van": Pose2D(pose.x_m, 0.0, pose.heading_rad),
    }
    return replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))


def _trigger_after_conflict():
    spec = _canonical_spec()
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    trigger = spec.layout.points["trigger_point"]
    points = {
        **spec.layout.points,
        "trigger_point": Point2D(conflict.x_m + 5.0, trigger.y_m),
    }
    return replace(spec, layout=replace(spec.layout, points=points))


def _pedestrian_outside_sidewalk():
    spec = _canonical_spec()
    assert spec.layout is not None
    pose = spec.layout.actor_poses["pedestrian"]
    actor_poses = {
        **spec.layout.actor_poses,
        "pedestrian": Pose2D(pose.x_m, 0.0, pose.heading_rad),
    }
    return replace(spec, layout=replace(spec.layout, actor_poses=actor_poses))
