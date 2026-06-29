from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from scenariocraft.repair.providers.types import RepairProposal, RepairRequest
from scenariocraft.schemas import PatchSpec, PatchSpecError


class OpenAIRepairProviderConfigurationError(RuntimeError):
    """Raised when the OpenAI repair provider cannot be configured locally."""


_OPERATION_SCHEMAS: dict[str, dict[str, object]] = {
    "set_actor_pose": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set_actor_pose"]},
            "actor_id": {"type": "string"},
            "x_m": {"type": "number"},
            "y_m": {"type": "number"},
            "heading_rad": {"type": "number"},
        },
        "required": ["op", "actor_id", "x_m", "y_m", "heading_rad"],
        "additionalProperties": False,
    },
    "reposition_actor_to_band": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["reposition_actor_to_band"]},
            "actor_id": {"type": "string"},
            "target_band_id": {"type": "string"},
        },
        "required": ["op", "actor_id", "target_band_id"],
        "additionalProperties": False,
    },
    "set_path_points": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set_path_points"]},
            "path_id": {"type": "string"},
            "points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "x_m": {"type": "number"},
                        "y_m": {"type": "number"},
                    },
                    "required": ["x_m", "y_m"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["op", "path_id", "points"],
        "additionalProperties": False,
    },
    "set_named_point": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set_named_point"]},
            "point_id": {"type": "string"},
            "x_m": {"type": "number"},
            "y_m": {"type": "number"},
        },
        "required": ["op", "point_id", "x_m", "y_m"],
        "additionalProperties": False,
    },
    "set_trigger_point_by_lead_time": {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": ["set_trigger_point_by_lead_time"]},
            "point_id": {"type": "string"},
            "reference_point_id": {"type": "string"},
            "speed_source_actor_id": {"type": "string"},
            "lead_time_s": {"type": "number"},
        },
        "required": ["op", "point_id", "reference_point_id", "speed_source_actor_id", "lead_time_s"],
        "additionalProperties": False,
    },
}

_SYSTEM_PROMPT = """Return only a structured repair proposal.
Allowed outcomes:
1. A valid PatchSpec proposal using allowed operations only.
2. An explicit refusal with rationale.
Never return:
- raw OpenSCENARIO XML;
- raw OpenDRIVE XML;
- code;
- Markdown;
- direct ScenarioSpec mutation instructions;
- claims that the repair is successful.
Use only the supplied structured evidence. A proposal is not proof that a repair succeeds."""


class OpenAIRepairProvider:
    """OpenAI-backed proposal-only provider with deterministic local validation."""

    provider_name = "openai"

    def __init__(self, *, model: str, client: object | None = None) -> None:
        if not isinstance(model, str) or not model.strip():
            raise OpenAIRepairProviderConfigurationError("model must be a non-empty string.")
        self.model = model.strip()
        self._client = client if client is not None else self._create_client()

    def propose_patch(self, request: RepairRequest) -> RepairProposal:
        if not isinstance(request, RepairRequest):
            raise TypeError("request must be a RepairRequest.")

        try:
            response = self._client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(self._request_payload(request), sort_keys=True),
                    },
                ],
                text={"format": self._response_format()},
            )
        except Exception as exc:  # The SDK exposes several transport-specific exception types.
            return self._decline(f"OpenAI request failed with {type(exc).__name__}.")

        refusal = self._response_refusal(response)
        if refusal is not None:
            return self._decline(f"OpenAI refused the repair request: {refusal}")
        raw = self._response_payload(response)
        if raw is None:
            return self._decline("OpenAI response did not contain a structured JSON payload.")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return self._decline("OpenAI response was not valid JSON.")
        if not isinstance(payload, Mapping):
            return self._decline("OpenAI response JSON was not an object.")
        actual_fields = set(payload)
        if actual_fields != {"patch", "rationale"}:
            return self._decline("OpenAI response did not match the repair proposal structure.")

        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            return self._decline("OpenAI response omitted a non-empty rationale.")
        patch_payload = payload.get("patch")
        if patch_payload is None:
            return self._decline(rationale.strip())
        if not isinstance(patch_payload, Mapping):
            return self._decline("OpenAI patch payload was not an object.")

        try:
            patch = PatchSpec.from_dict(patch_payload)
        except (PatchSpecError, KeyError, TypeError, ValueError) as exc:
            return self._decline(f"OpenAI patch failed PatchSpec validation: {exc}")

        allowed = set(request.allowed_operation_types)
        disallowed = sorted({operation.to_dict()["op"] for operation in patch.operations} - allowed)
        if disallowed:
            return self._decline(
                "OpenAI patch used disallowed operation types: " + ", ".join(disallowed) + "."
            )
        return RepairProposal(patch=patch, rationale=rationale.strip(), provider_name=self.provider_name)

    @staticmethod
    def _create_client() -> object:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OpenAIRepairProviderConfigurationError(
                "OPENAI_API_KEY is required when no OpenAI client is injected."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIRepairProviderConfigurationError(
                'The OpenAI SDK is not installed; install the "openai" optional dependency.'
            ) from exc
        return OpenAI(api_key=api_key)

    @staticmethod
    def _request_payload(request: RepairRequest) -> dict[str, object]:
        allowed_contract = {
            operation_type: _OPERATION_SCHEMAS[operation_type]
            for operation_type in request.allowed_operation_types
            if operation_type in _OPERATION_SCHEMAS
        }
        return {
            "user_intent": request.user_intent,
            "scenario_spec": request.scenario_spec.to_dict(),
            "failed_probe_results": [result.to_dict() for result in request.failed_probe_results],
            "allowed_operation_types": list(request.allowed_operation_types),
            "allowed_operation_contract": allowed_contract,
            "repair_authority": {
                "provider_role": "proposal_only",
                "output_contract": "PatchSpec JSON or refusal",
                "success_authority": "deterministic probes/build/runtime evidence",
                "may_mutate_xml": False,
                "may_claim_repair_success": False,
            },
        }

    @staticmethod
    def _response_format() -> dict[str, object]:
        return {
            "type": "json_schema",
            "name": "repair_proposal",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "patch": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "operations": {
                                        "type": "array",
                                        "items": {"anyOf": list(_OPERATION_SCHEMAS.values())},
                                    }
                                },
                                "required": ["operations"],
                                "additionalProperties": False,
                            },
                            {"type": "null"},
                        ]
                    },
                    "rationale": {"type": "string"},
                },
                "required": ["patch", "rationale"],
                "additionalProperties": False,
            },
        }

    @staticmethod
    def _response_payload(response: object) -> str | Mapping[str, Any] | None:
        parsed = getattr(response, "output_parsed", None)
        if isinstance(parsed, Mapping):
            return parsed
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str) and output_text.strip():
            return output_text
        return None

    @staticmethod
    def _response_refusal(response: object) -> str | None:
        for output in getattr(response, "output", ()) or ():
            for content in getattr(output, "content", ()) or ():
                refusal = getattr(content, "refusal", None)
                if isinstance(refusal, str) and refusal.strip():
                    return refusal.strip()
        return None

    def _decline(self, rationale: str) -> RepairProposal:
        return RepairProposal(patch=None, rationale=rationale, provider_name=self.provider_name)
