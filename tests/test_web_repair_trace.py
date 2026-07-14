from __future__ import annotations

from pathlib import Path

import scenariocraft._legacy_streamlit.app as web_app
from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft._legacy_streamlit.app import _run_demo_experiment_if_requested
from scenariocraft._legacy_streamlit.view_models import build_generated_scenario_view_model


def test_demo_experiment_does_nothing_without_explicit_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("Demo experiment executed without explicit user action.")

    monkeypatch.setattr(web_app, "run_demo_case", forbidden)

    result = _run_demo_experiment_if_requested(
        "geometry_van_in_ego_lane",
        _canonical_spec(),
        tmp_path,
        requested=False,
    )

    assert result is None
    assert not (tmp_path / "demo_experiments").exists()


def test_geometry_demo_trace_contains_real_provider_patch_and_revalidation(
    tmp_path: Path,
) -> None:
    spec = _canonical_spec()
    original_json = spec.to_json()

    experiment = _run_demo_experiment_if_requested(
        "geometry_van_in_ego_lane",
        spec,
        tmp_path,
        requested=True,
    )

    assert experiment is not None
    execution, trace = experiment
    assert execution.repair_run_result is not None
    assert trace.case_id == "geometry_van_in_ego_lane"
    assert trace.fault_domain == "geometry"
    assert trace.provider_will_be_used is True
    assert trace.provider_name == "deterministic_fake"
    assert trace.provider_rationale
    assert trace.proposed_operations == (
        {
            "op": "reposition_actor_to_band",
            "actor_id": "parked_van",
            "target_band_id": "ego_side_parking_strip",
        },
    )
    assert trace.patch_applied is True
    assert any(
        check.name == "parked_van_footprint_in_parking_strip" and not check.passed
        for check in trace.initial_geometry_results
    )
    assert trace.geometry_revalidated is True
    assert trace.artifacts_consistent is True
    assert trace.terminal_status == "passed"
    assert spec.to_json() == original_json


def test_artifact_demo_trace_explains_detection_only_boundary(tmp_path: Path) -> None:
    experiment = _run_demo_experiment_if_requested(
        "artifact_xosc_actor_pose_drift",
        _canonical_spec(),
        tmp_path,
        requested=True,
    )

    assert experiment is not None
    _, trace = experiment
    assert trace.fault_domain == "artifact"
    assert trace.provider_will_be_used is False
    assert trace.provider_name is None
    assert trace.proposed_operations == ()
    assert trace.patch_applied is False
    assert trace.geometry_revalidated is True
    assert trace.artifacts_consistent is False
    assert trace.terminal_status == "artifact_validation_failed"
    assert "artifact consistency failure" in trace.provider_decision
    assert "detection-only" in trace.terminal_reason


def test_demo_experiment_preserves_normal_generated_scenario_view(tmp_path: Path) -> None:
    spec = _canonical_spec()
    before = build_generated_scenario_view_model(spec)

    _run_demo_experiment_if_requested(
        "geometry_trigger_after_conflict",
        spec,
        tmp_path,
        requested=True,
    )

    assert build_generated_scenario_view_model(spec) == before


def _canonical_spec():
    return generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
