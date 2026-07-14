from __future__ import annotations

"""Thin localhost HTTP delivery adapter for ScenarioCraft application workflows."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from scenariocraft.application import (
    ScenarioWorkflowResult,
    ScenarioWorkflowOptions,
    ScenarioWorkflowRequest,
    run_bounded_orchestrator,
    run_generated_scenario_workflow,
)
from scenariocraft.application.candidate_generation import IntentGenerationOutcomeError
from scenariocraft.application.controlled_cases import CONTROLLED_CASES
from scenariocraft.core.repair.providers import FakeRepairProvider
from scenariocraft.providers import (
    OpenAIIntentProvider,
    OpenAIIntentProviderConfigurationError,
    OpenAIIntentProviderExecutionError,
)
from scenariocraft.providers.openai_intent import (
    LocalLlmConfigurationHint,
    local_llm_configuration_hint,
    local_openai_compatible_env,
)


ProviderHint = Callable[[], LocalLlmConfigurationHint]


@dataclass(frozen=True)
class _RunRecord:
    result: ScenarioWorkflowResult
    artifacts: dict[str, Path]


def create_http_app(
    *,
    output_root: Path | str = Path("outputs/api"),
    provider_hint: ProviderHint = local_llm_configuration_hint,
) -> Starlette:
    """Create the local ASGI app without owning scenario-domain behavior."""

    root = Path(output_root).resolve()
    runs: dict[str, _RunRecord] = {}

    def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "service": "scenariocraft"})

    def capabilities(_: Request) -> JSONResponse:
        hint = provider_hint()
        configured_model = local_openai_compatible_env().get("model")
        selected_model = configured_model or (hint.model_names[0] if hint.model_names else None)
        return JSONResponse(
            {
                "providers": {
                    "controlled_case": {"configured": True},
                    "local_llm": {
                        "configured": bool(selected_model and hint.reachable),
                        "reachable": hint.reachable,
                        "server_url": hint.server_url,
                        "models": list(hint.model_names),
                        "selected_model": selected_model,
                        "message": hint.message,
                    },
                },
                "controlled_cases": [
                    {
                        "id": case.case_id,
                        "template_id": case.template_id,
                        "display_name": case.display_name,
                        "description": case.description,
                        "prompt_variants": list(case.source_text_variants),
                    }
                    for case in CONTROLLED_CASES
                ],
            }
        )

    async def generate(request: Request) -> JSONResponse:
        return await _run_generation(request, root=root, runs=runs)

    async def revise(request: Request) -> JSONResponse:
        return await _run_generation(request, root=root, runs=runs, require_revision=True)

    async def repair(request: Request) -> JSONResponse:
        return await _run_repair(request, root=root, runs=runs)

    def artifact(request: Request):
        run_id = request.path_params["run_id"]
        artifact_name = request.path_params["artifact_name"]
        record = runs.get(run_id)
        path = record.artifacts.get(artifact_name) if record is not None else None
        if path is None or not path.is_file():
            return JSONResponse({"error": "artifact_not_found"}, status_code=404)
        return FileResponse(path)

    app = Starlette(
        routes=[
            Route("/api/health", health, methods=["GET"]),
            Route("/api/capabilities", capabilities, methods=["GET"]),
            Route("/api/scenarios/generate", generate, methods=["POST"]),
            Route("/api/scenarios/revise", revise, methods=["POST"]),
            Route("/api/scenarios/repair", repair, methods=["POST"]),
            Route("/api/runs/{run_id:str}/artifacts/{artifact_name:str}", artifact, methods=["GET"]),
        ]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["content-type"],
    )
    return app


async def _run_generation(
    request: Request,
    *,
    root: Path,
    runs: dict[str, _RunRecord],
    require_revision: bool = False,
) -> JSONResponse:
    try:
        payload = await request.json()
        if not isinstance(payload, Mapping):
            raise ValueError("Request body must be a JSON object.")
        scenario_text = _required_string(payload, "scenario_text")
        provider = str(payload.get("provider", "controlled_case"))
        controlled_case_id = _optional_string(payload.get("controlled_case_id"))
        revision_request = _optional_string(payload.get("revision_request"))
        if require_revision and not revision_request:
            raise ValueError("revision_request is required for the revision endpoint.")
        intent_provider = None
        if provider == "controlled_case":
            if not controlled_case_id:
                raise ValueError("controlled_case_id is required for provider=controlled_case.")
            provider_name = "controlled_case"
        elif provider in {"local_llm", "openai-compatible", "openai_compatible"}:
            provider_name = "openai-compatible"
            intent_provider = OpenAIIntentProvider.from_env()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        run_id = _new_run_id()
        output_dir = root / run_id
        result = run_generated_scenario_workflow(
            ScenarioWorkflowRequest(
                scenario_text=scenario_text,
                output_dir=output_dir,
                provider_name=provider_name,
                intent_provider=intent_provider,
                controlled_case_id=controlled_case_id,
                revision_request=revision_request,
                base_scenario_type=_optional_string(payload.get("base_scenario_type")),
                options=_workflow_options(payload.get("options")),
            )
        )
    except IntentGenerationOutcomeError as exc:
        return JSONResponse(
            {
                "error": "intent_outcome",
                "message": str(exc),
                "outcome": exc.proposal.to_dict(),
            },
            status_code=422,
        )
    except OpenAIIntentProviderConfigurationError as exc:
        return JSONResponse(
            {"error": "provider_unavailable", "message": str(exc)},
            status_code=503,
        )
    except OpenAIIntentProviderExecutionError as exc:
        return JSONResponse(
            {"error": "provider_failed", "message": str(exc)},
            status_code=502,
        )
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": "invalid_request", "message": str(exc)}, status_code=400)

    artifact_paths = _artifact_paths(result.artifacts)
    runs[run_id] = _RunRecord(result=result, artifacts=artifact_paths)
    return JSONResponse(
        {
            "run_id": run_id,
            "result": result.to_dict(),
            "artifact_urls": {
                name: f"/api/runs/{run_id}/artifacts/{name}" for name in artifact_paths
            },
        }
    )


async def _run_repair(
    request: Request,
    *,
    root: Path,
    runs: dict[str, _RunRecord],
) -> JSONResponse:
    try:
        payload = await request.json()
        if not isinstance(payload, Mapping):
            raise ValueError("Request body must be a JSON object.")
        source_run_id = _required_string(payload, "run_id")
        source = runs.get(source_run_id)
        if source is None:
            return JSONResponse(
                {"error": "run_not_found", "message": "The requested source run was not found."},
                status_code=404,
            )
        failed_checks = tuple(
            check
            for check in (
                *source.result.geometry_check_results,
                *source.result.artifact_check_results,
            )
            if not check.passed
        )
        if not failed_checks:
            return JSONResponse(
                {
                    "error": "repair_not_required",
                    "message": "The source run has no failed repairable checks.",
                },
                status_code=409,
            )
        provider = str(payload.get("provider", "deterministic_demo"))
        if provider != "deterministic_demo":
            return JSONResponse(
                {
                    "error": "repair_provider_unavailable",
                    "message": "Only the existing deterministic demo repair provider is available through this local API.",
                },
                status_code=501,
            )

        run_id = _new_run_id()
        output_dir = root / run_id
        result = run_bounded_orchestrator(
            source.result.spec,
            output_dir=output_dir,
            scenario_text=source.result.request.scenario_text,
            repair_provider=FakeRepairProvider(),
            run_runtime=False,
            run_esmini_check=False,
        )
        artifacts = _repair_artifact_paths(result, output_dir)
        runs[run_id] = _RunRecord(result=source.result, artifacts=artifacts)
    except (ValueError, TypeError) as exc:
        return JSONResponse({"error": "invalid_request", "message": str(exc)}, status_code=400)

    return JSONResponse(
        {
            "run_id": run_id,
            "source_run_id": source_run_id,
            "repair_result": result.to_dict(),
            "artifact_urls": {
                name: f"/api/runs/{run_id}/artifacts/{name}" for name in artifacts
            },
        }
    )


def _workflow_options(value: object) -> ScenarioWorkflowOptions:
    defaults: dict[str, object] = {
        "run_preview": True,
        "run_semantics": True,
        "run_geometry_checks": True,
        "run_artifact_checks": False,
        "run_runtime_checks": True,
        "run_report": True,
        "run_asam_qc": True,
        "run_esmini": False,
        "run_playback": True,
        "preview_display_orientation": "esmini_top_camera_raw",
        "preview_presentation_style": "clean_split",
        "playback_mode": "playback",
    }
    if value is None:
        return ScenarioWorkflowOptions(**defaults)
    if not isinstance(value, Mapping):
        raise ValueError("options must be a JSON object.")
    allowed = {field.name for field in fields(ScenarioWorkflowOptions)}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unknown workflow options: {', '.join(unknown)}")
    if "run_opendrive_mcp" in value and not isinstance(value["run_opendrive_mcp"], bool):
        raise ValueError("run_opendrive_mcp must be a boolean.")
    return ScenarioWorkflowOptions(**{**defaults, **dict(value)})


def _artifact_paths(artifacts: object) -> dict[str, Path]:
    candidates = {
        "preview": getattr(artifacts, "preview_path", None),
        "playback": getattr(artifacts, "playback_path", None),
        "report": getattr(artifacts, "report_path", None),
        "xosc": getattr(artifacts, "xosc_path", None),
        "xodr": getattr(artifacts, "xodr_path", None),
        "scenario_spec": getattr(artifacts, "scenario_spec_path", None),
        "playback_result": getattr(artifacts, "playback_result_path", None),
        "opendrive_mcp_result": getattr(artifacts, "opendrive_mcp_result_path", None),
    }
    return {
        name: Path(path).resolve()
        for name, path in candidates.items()
        if path is not None and Path(path).is_file()
    }


def _repair_artifact_paths(result: object, output_dir: Path) -> dict[str, Path]:
    build_result = getattr(result, "build_result", None)
    candidates = {
        "preview": output_dir / "preview_2d.png",
        "report": getattr(result, "report_path", None),
        "xosc": getattr(build_result, "xosc_path", None),
        "xodr": getattr(build_result, "xodr_path", None),
        "scenario_spec": output_dir / "scenario_spec.json",
        "orchestrator_result": output_dir / "orchestrator_result.json",
    }
    return {
        name: Path(path).resolve()
        for name, path in candidates.items()
        if path is not None and Path(path).is_file()
    }


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{timestamp}-{uuid4().hex[:8]}"


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = _optional_string(payload.get(key))
    if not value:
        raise ValueError(f"{key} must be a non-empty string.")
    return value


def _optional_string(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


app = create_http_app()
