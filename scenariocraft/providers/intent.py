from __future__ import annotations

"""Provider contracts for natural-language to ScenarioIntent proposals."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Protocol

from scenariocraft.core.schemas import ScenarioIntent

IntentProposalStatus = Literal["supported", "clarification_required", "unsupported"]


@dataclass(frozen=True)
class IntentRequest:
    user_text: str
    available_templates: tuple[str, ...]
    template_contract_summary: dict[str, object]
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "user_text": self.user_text,
            "available_templates": list(self.available_templates),
            "template_contract_summary": _json_value(self.template_contract_summary),
            "metadata": _json_value(self.metadata),
        }


@dataclass(frozen=True)
class RefinementSuggestion:
    template_id: str
    label: str
    suggested_request: str
    reason: str = ""

    def __post_init__(self) -> None:
        if not self.template_id.strip():
            raise ValueError("RefinementSuggestion.template_id must be non-empty.")
        if not self.label.strip():
            raise ValueError("RefinementSuggestion.label must be non-empty.")
        if not self.suggested_request.strip():
            raise ValueError("RefinementSuggestion.suggested_request must be non-empty.")

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "label": self.label,
            "suggested_request": self.suggested_request,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IntentProposal:
    intent: ScenarioIntent | None
    rationale: str
    provider_name: str
    status: IntentProposalStatus = "supported"
    refusal_reason: str | None = None
    clarification_question: str | None = None
    nearest_template_candidates: tuple[str, ...] = ()
    refinement_suggestions: tuple[RefinementSuggestion, ...] = ()

    def __post_init__(self) -> None:
        if self.status == "supported" and self.intent is None and self.refusal_reason:
            object.__setattr__(self, "status", "unsupported")
        if self.status not in {"supported", "clarification_required", "unsupported"}:
            raise ValueError("IntentProposal.status must be supported, clarification_required, or unsupported.")
        if self.status == "supported" and self.intent is None:
            raise ValueError("IntentProposal.intent is required when status is supported.")
        if self.status != "supported" and self.intent is not None:
            raise ValueError("IntentProposal.intent must be None unless status is supported.")
        if self.status == "unsupported" and not self.refusal_reason:
            object.__setattr__(self, "refusal_reason", self.rationale)
        object.__setattr__(
            self,
            "nearest_template_candidates",
            tuple(str(candidate) for candidate in self.nearest_template_candidates),
        )
        object.__setattr__(
            self,
            "refinement_suggestions",
            tuple(
                suggestion
                if isinstance(suggestion, RefinementSuggestion)
                else RefinementSuggestion(**suggestion)
                for suggestion in self.refinement_suggestions
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "intent": self.intent.to_dict() if self.intent is not None else None,
            "rationale": self.rationale,
            "provider_name": self.provider_name,
            "refusal_reason": self.refusal_reason,
            "clarification_question": self.clarification_question,
            "nearest_template_candidates": list(self.nearest_template_candidates),
            "refinement_suggestions": [suggestion.to_dict() for suggestion in self.refinement_suggestions],
        }


class IntentProvider(Protocol):
    provider_name: str

    def propose_intent(self, request: IntentRequest) -> IntentProposal:
        """Return ScenarioIntent proposal or explicit refusal."""


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if hasattr(value, "to_dict"):
        return _json_value(value.to_dict())
    if hasattr(value, "__dataclass_fields__"):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)
