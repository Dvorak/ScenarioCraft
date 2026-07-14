from __future__ import annotations

from pathlib import Path

import pytest
from starlette.testclient import TestClient

from scenariocraft.api.app import _workflow_options, create_http_app
from scenariocraft.providers.openai_intent import (
    LocalLlmConfigurationHint,
    OpenAIIntentProviderExecutionError,
)


def _provider_hint() -> LocalLlmConfigurationHint:
    return LocalLlmConfigurationHint(
        server_url="http://localhost:11434/v1",
        reachable=True,
        model_names=("qwen2.5:7b",),
        message="Ollama is ready.",
    )


def _fast_options() -> dict[str, bool]:
    return {
        "run_asam_qc": False,
        "run_playback": False,
        "run_runtime_checks": False,
    }


def test_workflow_options_validate_opendrive_mcp_boolean() -> None:
    assert _workflow_options({"run_opendrive_mcp": True}).run_opendrive_mcp is True

    with pytest.raises(ValueError, match="run_opendrive_mcp must be a boolean"):
        _workflow_options({"run_opendrive_mcp": "false"})


def test_health_and_capabilities_expose_delivery_state(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))

    health = client.get("/api/health")
    capabilities = client.get("/api/capabilities")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "scenariocraft"}
    assert capabilities.status_code == 200
    payload = capabilities.json()
    assert [case["id"] for case in payload["controlled_cases"]] == [
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    ]
    assert payload["providers"]["local_llm"] == {
        "configured": True,
        "reachable": True,
        "server_url": "http://localhost:11434/v1",
        "models": ["qwen2.5:7b"],
        "selected_model": "qwen2.5:7b",
        "message": "Ollama is ready.",
    }


def test_local_development_origins_are_allowed(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))

    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/api/scenarios/generate",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_generate_controlled_case_returns_workflow_result_and_artifact_urls(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))

    response = client.post(
        "/api/scenarios/generate",
        json={
            "scenario_text": "A vehicle cuts into the ego lane.",
            "provider": "controlled_case",
            "controlled_case_id": "cut_in",
            "options": {
                "run_asam_qc": False,
                "run_playback": False,
                "run_runtime_checks": False,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"]
    assert payload["result"]["candidate_trace"]["template_id"] == "cut_in"
    assert payload["result"]["status"]["terminal_status"] in {"generated", "passed"}
    assert payload["artifact_urls"]["preview"].endswith("/artifacts/preview")

    preview = client.get(payload["artifact_urls"]["preview"])
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"


def test_artifact_route_rejects_unknown_names(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))
    response = client.get("/api/runs/unknown/artifacts/../../scenario_spec")
    assert response.status_code in {404, 405}


def test_revision_endpoint_reuses_generated_workflow_contract(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))

    response = client.post(
        "/api/scenarios/revise",
        json={
            "scenario_text": "A vehicle cuts in ahead of ego.",
            "provider": "controlled_case",
            "controlled_case_id": "cut_in",
            "revision_request": "Use another deterministic variant.",
            "base_scenario_type": "cut_in",
            "options": _fast_options(),
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["result"]["request"]["revision_request"] == "Use another deterministic variant."
    assert body["result"]["spec"]["scenario_type"] == "cut_in"


def test_repair_endpoint_reports_when_a_passed_run_needs_no_patch(tmp_path: Path) -> None:
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))
    generated = client.post(
        "/api/scenarios/generate",
        json={
            "scenario_text": "A vehicle cuts in ahead of ego.",
            "provider": "controlled_case",
            "controlled_case_id": "cut_in",
            "options": _fast_options(),
        },
    ).json()

    response = client.post(
        "/api/scenarios/repair",
        json={"run_id": generated["run_id"], "provider": "deterministic_demo"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "repair_not_required"


def test_provider_execution_failure_is_not_reported_as_unsupported_intent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class _FailingProvider:
        provider_name = "openai_compatible"

        def propose_intent(self, request):
            raise OpenAIIntentProviderExecutionError("OpenAI-compatible request timed out.")

    monkeypatch.setattr(
        "scenariocraft.api.app.OpenAIIntentProvider.from_env",
        lambda: _FailingProvider(),
    )
    client = TestClient(create_http_app(output_root=tmp_path, provider_hint=_provider_hint))

    response = client.post(
        "/api/scenarios/generate",
        json={
            "scenario_text": "Create a supported scenario.",
            "provider": "local_llm",
            "options": _fast_options(),
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "error": "provider_failed",
        "message": "OpenAI-compatible request timed out.",
    }
