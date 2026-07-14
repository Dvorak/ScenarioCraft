from __future__ import annotations

"""OpenAI-compatible provider for ScenarioIntent extraction."""

import json
import os
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from scenariocraft.core.schemas import ScenarioIntent, ScenarioIntentError
from scenariocraft.providers.intent import (
    IntentProposal,
    IntentProposalStatus,
    IntentRequest,
    RefinementSuggestion,
)


class OpenAIIntentProviderConfigurationError(RuntimeError):
    """Raised when the OpenAI-compatible intent provider cannot be configured."""


class OpenAIIntentProviderExecutionError(RuntimeError):
    """Raised when a configured provider cannot complete an intent request."""


@dataclass(frozen=True)
class LocalLlmConfigurationHint:
    server_url: str
    reachable: bool
    model_names: tuple[str, ...]
    message: str


DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_S = 20.0


def local_openai_compatible_env() -> dict[str, str | None]:
    """Read hosted/local OpenAI-compatible intent provider environment.

    `SCENARIOCRAFT_LOCAL_LLM_*` names are the user-facing local-model aliases.
    Existing `SCENARIOCRAFT_OPENAI_*` names remain supported for compatibility.
    """

    base_url = (
        os.environ.get("SCENARIOCRAFT_LOCAL_LLM_BASE_URL")
        or os.environ.get("SCENARIOCRAFT_OPENAI_BASE_URL")
    )
    model = (
        os.environ.get("SCENARIOCRAFT_LOCAL_LLM_MODEL")
        or os.environ.get("SCENARIOCRAFT_INTENT_MODEL")
        or os.environ.get("OPENAI_MODEL")
    )
    api_key = (
        os.environ.get("SCENARIOCRAFT_LOCAL_LLM_API_KEY")
        or os.environ.get("SCENARIOCRAFT_OPENAI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ("local" if base_url else None)
    )
    timeout_s = (
        os.environ.get("SCENARIOCRAFT_LOCAL_LLM_TIMEOUT_S")
        or os.environ.get("SCENARIOCRAFT_OPENAI_TIMEOUT_S")
    )
    return {"base_url": base_url, "model": model, "api_key": api_key, "timeout_s": timeout_s}


def local_llm_configuration_hint(*, timeout_s: float = 0.35) -> LocalLlmConfigurationHint:
    """Return a user-facing configuration hint for local OpenAI-compatible LLMs."""

    env = local_openai_compatible_env()
    server_url = env["base_url"] or "http://localhost:11434/v1"
    model = env["model"]
    if model:
        return LocalLlmConfigurationHint(
            server_url=server_url,
            reachable=True,
            model_names=(model,),
            message=f"Local LLM model is configured as `{model}`.",
        )
    ollama_url = _ollama_base_from_openai_url(server_url)
    model_names = _ollama_model_names(ollama_url, timeout_s=timeout_s)
    if model_names:
        suggested_model = model_names[0]
        return LocalLlmConfigurationHint(
            server_url=f"{ollama_url}/v1",
            reachable=True,
            model_names=model_names,
            message=(
                "Ollama appears to be running locally. Set the Local LLM environment variables, then restart "
                "the Streamlit app:\n\n"
                "```bash\n"
                f"export SCENARIOCRAFT_LOCAL_LLM_BASE_URL={ollama_url}/v1\n"
                "export SCENARIOCRAFT_LOCAL_LLM_API_KEY=local\n"
                f"export SCENARIOCRAFT_LOCAL_LLM_MODEL={suggested_model}\n"
                ".venv/bin/just web\n"
                "```"
            ),
        )
    return LocalLlmConfigurationHint(
        server_url=f"{ollama_url}/v1",
        reachable=False,
        model_names=(),
        message=(
            "No configured local model was found. If you use Ollama, start it and pull a model, then restart "
            "the Streamlit app:\n\n"
            "```bash\n"
            "ollama pull qwen2.5:7b\n"
            "ollama serve\n"
            "export SCENARIOCRAFT_LOCAL_LLM_BASE_URL=http://localhost:11434/v1\n"
            "export SCENARIOCRAFT_LOCAL_LLM_API_KEY=local\n"
            "export SCENARIOCRAFT_LOCAL_LLM_MODEL=qwen2.5:7b\n"
            ".venv/bin/just web\n"
            "```\n\n"
            "See README.md -> Tool Setup Details -> Local LLM."
        ),
    )


def _ollama_base_from_openai_url(server_url: str) -> str:
    return server_url.removesuffix("/v1").rstrip("/")


def _ollama_model_names(base_url: str, *, timeout_s: float) -> tuple[str, ...]:
    try:
        with urlopen(f"{base_url}/api/tags", timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError, TimeoutError):
        return ()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return ()
    names = []
    for model in models:
        if isinstance(model, dict) and isinstance(model.get("name"), str):
            names.append(model["name"])
    return tuple(names)


def _provider_timeout(value: object) -> float:
    if value is None or value == "":
        return DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_S
    try:
        timeout_s = float(value)
    except (TypeError, ValueError):
        return DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_S
    return timeout_s if timeout_s > 0.0 else DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_S


_SYSTEM_PROMPT = """Return only a structured ScenarioIntent proposal.
You are a semantic router onto ScenarioCraft's registered template capability
tree. Use the supplied template descriptions, aliases, semantic slots, supported
variants, unsupported boundary examples, and parameter domains.
If request.metadata.revision_request is non-empty, treat the prompt as a
Scenario Revision Loop request. Use request.metadata.base_scenario_type as the
preferred existing family when the revision still fits that registered family.
Do not return unsupported merely because a supported revision asks for a
different parameter value; deterministic ScenarioCraft resolvers will clamp,
default, sample, or reject concrete parameter candidates.
Choose one available template when the request clearly matches that scenario
family, even if optional parameters are missing. Deterministic resolvers will
fill safe defaults or seeded samples.
Same-lane following with a lead/front vehicle that brakes maps to
lead_vehicle_braking. Only choose cut_in when the request describes an adjacent
lane vehicle cutting in, merging, or changing lanes into the ego lane.
Do not choose the nearest template when the interaction family is unsupported.
For vague but potentially supportable requests, return clarification_required
and include refinement_suggestions that rewrite the user request into concrete
supported template-family requests.
Allowed output:
- status: "supported", "clarification_required", or "unsupported";
- intent: ScenarioIntent JSON using one available template_id when supported,
  otherwise null;
- rationale: short explanation;
- refusal_reason: null for success/clarification or a string for unsupported requests;
- clarification_question: null unless status is clarification_required;
- nearest_template_candidates: zero or more available template IDs that are close
  but must not be auto-used for unsupported requests;
- refinement_suggestions: zero to three user-facing request rewrites, each with
  template_id, label, suggested_request, and reason.
Never return raw ScenarioSpec, OpenSCENARIO XML, OpenDRIVE XML, code, Markdown,
or claims that the scenario is valid. Deterministic ScenarioCraft tools will
resolve, build, check, and report the scenario."""


class OpenAIIntentProvider:
    """Hosted or local OpenAI-compatible ScenarioIntent proposal provider."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        model: str,
        client: object | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_s: float = DEFAULT_OPENAI_COMPATIBLE_TIMEOUT_S,
    ) -> None:
        if not isinstance(model, str) or not model.strip():
            raise OpenAIIntentProviderConfigurationError("model must be a non-empty string.")
        self.model = model.strip()
        self.base_url = base_url.strip() if isinstance(base_url, str) and base_url.strip() else None
        self.timeout_s = _provider_timeout(timeout_s)
        self._api_key = api_key
        self._client = client if client is not None else self._create_client(
            api_key=api_key,
            base_url=base_url,
            timeout_s=self.timeout_s,
        )

    @classmethod
    def from_env(cls, *, client: object | None = None) -> "OpenAIIntentProvider":
        env = local_openai_compatible_env()
        model = env["model"]
        api_key = env["api_key"]
        base_url = env["base_url"]
        timeout_s = _provider_timeout(env.get("timeout_s"))
        if not model:
            hint = local_llm_configuration_hint(timeout_s=0.75)
            if hint.reachable and hint.model_names:
                model = hint.model_names[0]
                base_url = base_url or hint.server_url
                api_key = api_key or "local"
            else:
                raise OpenAIIntentProviderConfigurationError(
                    "SCENARIOCRAFT_LOCAL_LLM_MODEL or SCENARIOCRAFT_INTENT_MODEL is required for the "
                    "OpenAI-compatible intent provider when Ollama auto-discovery is unavailable."
                )
        return cls(model=model, client=client, api_key=api_key, base_url=base_url, timeout_s=timeout_s)

    def propose_intent(self, request: IntentRequest) -> IntentProposal:
        if not isinstance(request, IntentRequest):
            raise TypeError("request must be an IntentRequest.")
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(request.to_dict(), sort_keys=True)},
        ]
        try:
            response = self._create_response(messages)
        except Exception as exc:
            raise OpenAIIntentProviderExecutionError(
                f"OpenAI-compatible intent request failed with {type(exc).__name__}."
            ) from exc

        raw = self._response_payload(response)
        if raw is None:
            return self._decline("OpenAI-compatible response did not contain a structured JSON payload.")
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            return self._decline("OpenAI-compatible response was not valid JSON.")
        if not isinstance(payload, Mapping):
            return self._decline("OpenAI-compatible response JSON was not an object.")

        rationale = payload.get("rationale")
        if not isinstance(rationale, str) or not rationale.strip():
            return self._decline("OpenAI-compatible response omitted a non-empty rationale.")
        status = _proposal_status(payload)
        refusal_reason = _optional_string(payload.get("refusal_reason"))
        clarification_question = _optional_string(payload.get("clarification_question"))
        nearest_template_candidates = _nearest_candidates(payload.get("nearest_template_candidates"), request)
        refinement_suggestions = _refinement_suggestions(payload.get("refinement_suggestions"), request)
        if status == "unsupported":
            return IntentProposal(
                intent=None,
                rationale=rationale.strip(),
                provider_name=self.provider_name,
                status="unsupported",
                refusal_reason=refusal_reason or rationale.strip(),
                nearest_template_candidates=nearest_template_candidates,
                refinement_suggestions=refinement_suggestions,
            )
        if status == "clarification_required":
            return IntentProposal(
                intent=None,
                rationale=rationale.strip(),
                provider_name=self.provider_name,
                status="clarification_required",
                clarification_question=clarification_question or rationale.strip(),
                nearest_template_candidates=nearest_template_candidates,
                refinement_suggestions=refinement_suggestions,
            )

        intent_payload = payload.get("intent")
        if not isinstance(intent_payload, Mapping):
            return self._decline("OpenAI-compatible response omitted ScenarioIntent.")
        intent_payload = dict(intent_payload)
        raw_template_id = str(intent_payload.get("template_id", ""))
        coerced_template_id = _coerced_template_id(raw_template_id, request)
        if coerced_template_id is None:
            return self._decline(
                f"OpenAI-compatible response used unknown template_id: {raw_template_id}.",
                nearest_template_candidates=nearest_template_candidates,
            )
        request_consistent_template_id = _request_consistent_template_id(
            coerced_template_id,
            request,
        )
        if request_consistent_template_id is not None:
            coerced_template_id = request_consistent_template_id
        if coerced_template_id != raw_template_id:
            metadata = intent_payload.get("metadata")
            metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
            metadata["provider_template_id"] = raw_template_id
            intent_payload["metadata"] = metadata
            intent_payload["template_id"] = coerced_template_id
        try:
            intent = ScenarioIntent.from_dict(intent_payload)
        except (ScenarioIntentError, TypeError, ValueError) as exc:
            return self._decline(f"ScenarioIntent validation failed: {exc}")
        return IntentProposal(intent=intent, rationale=rationale.strip(), provider_name=self.provider_name)

    @staticmethod
    def _create_client(*, api_key: str | None, base_url: str | None, timeout_s: float) -> object:
        if not api_key:
            raise OpenAIIntentProviderConfigurationError(
                "OPENAI_API_KEY or SCENARIOCRAFT_OPENAI_API_KEY is required unless a client is injected."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise OpenAIIntentProviderConfigurationError(
                'The OpenAI SDK is not installed; install the "openai" optional dependency.'
            ) from exc
        kwargs: dict[str, object] = {"api_key": api_key, "timeout": timeout_s}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    def _create_response(self, messages: list[dict[str, str]]) -> object:
        try:
            return self._client.responses.create(
                model=self.model,
                input=messages,
                text={"format": self._response_format()},
                temperature=0,
            )
        except Exception:
            chat = getattr(self._client, "chat", None)
            completions = getattr(chat, "completions", None)
            if completions is None:
                raise
            return completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
            )

    @staticmethod
    def _response_format() -> dict[str, object]:
        return {
            "type": "json_schema",
            "name": "scenario_intent_proposal",
            "strict": False,
            "schema": {
                "type": "object",
                "properties": {
                    "intent": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "template_id": {"type": "string"},
                                    "road_context": {"type": "object", "additionalProperties": True},
                                    "weather": {"type": "object", "additionalProperties": True},
                                    "actors": {
                                        "type": "object",
                                        "additionalProperties": {
                                            "type": "object",
                                            "additionalProperties": True,
                                        },
                                    },
                                    "criticality": {"type": "object", "additionalProperties": True},
                                    "parameters": {"type": "object", "additionalProperties": True},
                                    "metadata": {"type": "object", "additionalProperties": True},
                                },
                                "required": ["template_id"],
                                "additionalProperties": False,
                            },
                            {"type": "null"},
                        ]
                    },
                    "rationale": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["supported", "clarification_required", "unsupported"],
                    },
                    "refusal_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "clarification_question": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "nearest_template_candidates": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "refinement_suggestions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "template_id": {"type": "string"},
                                "label": {"type": "string"},
                                "suggested_request": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                            "required": ["template_id", "label", "suggested_request"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["intent", "rationale"],
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
        choices = getattr(response, "choices", None)
        if choices:
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None)
            if isinstance(content, str) and content.strip():
                return content
        return None

    def _decline(
        self,
        rationale: str,
        *,
        nearest_template_candidates: tuple[str, ...] = (),
    ) -> IntentProposal:
        return IntentProposal(
            intent=None,
            rationale=rationale,
            provider_name=self.provider_name,
            status="unsupported",
            refusal_reason=rationale,
            nearest_template_candidates=nearest_template_candidates,
        )


def _proposal_status(payload: Mapping[str, Any]) -> IntentProposalStatus:
    raw = payload.get("status")
    if raw in {"supported", "clarification_required", "unsupported"}:
        return raw  # type: ignore[return-value]
    refusal_reason = payload.get("refusal_reason")
    if isinstance(refusal_reason, str) and refusal_reason.strip():
        return "unsupported"
    return "supported"


def _optional_string(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _nearest_candidates(value: object, request: IntentRequest) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    available = set(request.available_templates)
    return tuple(str(candidate) for candidate in value if str(candidate) in available)


def _coerced_template_id(raw_template_id: str, request: IntentRequest) -> str | None:
    raw = _normalized_tokens(raw_template_id)
    if not raw:
        return None
    exact = {_normalized_key(template_id): template_id for template_id in request.available_templates}
    raw_key = _normalized_key(raw_template_id)
    if raw_key in exact:
        return exact[raw_key]

    best_template: str | None = None
    best_score = 0
    for template_id in request.available_templates:
        summary = request.template_contract_summary.get(template_id, {})
        candidates = [template_id]
        if isinstance(summary, Mapping):
            description = summary.get("description")
            if isinstance(description, str):
                candidates.append(description)
            capability = summary.get("capability")
            if isinstance(capability, Mapping):
                for key in ("interaction_family", "description"):
                    value = capability.get(key)
                    if isinstance(value, str):
                        candidates.append(value)
                for key in ("aliases", "semantic_slots", "supported_variants"):
                    values = capability.get(key)
                    if isinstance(values, list):
                        candidates.extend(str(value) for value in values)
        score = max((_token_overlap_score(raw, _normalized_tokens(candidate)) for candidate in candidates), default=0)
        if score > best_score:
            best_score = score
            best_template = template_id
    return best_template if best_score >= 2 else None


def _request_consistent_template_id(template_id: str, request: IntentRequest) -> str | None:
    """Correct clear provider/template mismatches against the capability tree.

    Small local models can occasionally select a known but semantically wrong
    template. This guard is intentionally conservative: it only changes the
    selected template when the user text has a substantially stronger token
    overlap with another registered capability.
    """

    if template_id not in request.available_templates:
        return None
    request_tokens = _normalized_tokens(request.user_text)
    if not request_tokens:
        return None
    scores = {
        candidate: _template_match_score(request_tokens, candidate, request)
        for candidate in request.available_templates
    }
    selected_score = scores.get(template_id, 0)
    best_template, best_score = max(scores.items(), key=lambda item: item[1])
    if best_template == template_id:
        return None
    if best_score >= 3 and best_score >= selected_score + 2:
        return best_template
    return None


def _template_match_score(
    request_tokens: set[str],
    template_id: str,
    request: IntentRequest,
) -> int:
    summary = request.template_contract_summary.get(template_id, {})
    candidates = [template_id]
    if isinstance(summary, Mapping):
        description = summary.get("description")
        if isinstance(description, str):
            candidates.append(description)
        capability = summary.get("capability")
        if isinstance(capability, Mapping):
            for key in ("interaction_family", "description"):
                value = capability.get(key)
                if isinstance(value, str):
                    candidates.append(value)
            for key in ("aliases", "semantic_slots", "supported_variants"):
                values = capability.get(key)
                if isinstance(values, list):
                    candidates.extend(str(value) for value in values)
    return max(
        (_token_overlap_score(request_tokens, _normalized_tokens(candidate)) for candidate in candidates),
        default=0,
    )


def _normalized_key(value: str) -> str:
    return "".join(_normalized_tokens(value))


def _normalized_tokens(value: str) -> set[str]:
    token = []
    tokens: set[str] = set()
    for char in value.lower():
        if char.isalnum():
            token.append(char)
        else:
            if token:
                tokens.add(_stem_token("".join(token)))
                token.clear()
    if token:
        tokens.add(_stem_token("".join(token)))
    return {item for item in tokens if item not in {"scenario", "vehicle", "car", "urban"}}


def _stem_token(token: str) -> str:
    if token.endswith("ing") and len(token) > 5:
        return token[:-3]
    if token.endswith("ed") and len(token) > 4:
        return token[:-2]
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _token_overlap_score(left: set[str], right: set[str]) -> int:
    return len(left & right)


def _refinement_suggestions(value: object, request: IntentRequest) -> tuple[RefinementSuggestion, ...]:
    if not isinstance(value, list):
        return ()
    available = set(request.available_templates)
    suggestions: list[RefinementSuggestion] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        template_id = _optional_string(item.get("template_id"))
        label = _optional_string(item.get("label"))
        suggested_request = _optional_string(item.get("suggested_request"))
        reason = _optional_string(item.get("reason")) or ""
        if template_id not in available or label is None or suggested_request is None:
            continue
        if _looks_like_artifact(suggested_request):
            continue
        try:
            suggestions.append(
                RefinementSuggestion(
                    template_id=template_id,
                    label=label,
                    suggested_request=suggested_request,
                    reason=reason,
                )
            )
        except ValueError:
            continue
        if len(suggestions) >= 3:
            break
    return tuple(suggestions)


def _looks_like_artifact(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in ("<openscenario", "<opendrive", "<?xml", "<scenario"))
