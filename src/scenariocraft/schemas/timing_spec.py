from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scenariocraft.schemas.common import (
    ScenarioSpecError,
    require_non_negative_number,
    require_positive_number,
)


@dataclass(frozen=True)
class ScenarioTimingSpec:
    total_duration_s: float = 8.0
    preferred_trigger_earliest_s: float = 1.5
    preferred_trigger_latest_s: float = 3.0
    minimum_pre_trigger_context_s: float = 0.5
    minimum_post_trigger_buffer_s: float = 0.5

    def __post_init__(self) -> None:
        total = require_positive_number(self.total_duration_s, "timing.total_duration_s")
        earliest = require_non_negative_number(
            self.preferred_trigger_earliest_s,
            "timing.preferred_trigger_earliest_s",
        )
        latest = require_non_negative_number(
            self.preferred_trigger_latest_s,
            "timing.preferred_trigger_latest_s",
        )
        pre_context = require_non_negative_number(
            self.minimum_pre_trigger_context_s,
            "timing.minimum_pre_trigger_context_s",
        )
        buffer = require_non_negative_number(
            self.minimum_post_trigger_buffer_s,
            "timing.minimum_post_trigger_buffer_s",
        )
        if earliest > latest:
            raise ScenarioSpecError(
                "timing.preferred_trigger_earliest_s must be less than or equal to preferred_trigger_latest_s."
            )
        if latest >= total:
            raise ScenarioSpecError("timing.preferred_trigger_latest_s must be less than total_duration_s.")
        object.__setattr__(self, "total_duration_s", total)
        object.__setattr__(self, "preferred_trigger_earliest_s", earliest)
        object.__setattr__(self, "preferred_trigger_latest_s", latest)
        object.__setattr__(self, "minimum_pre_trigger_context_s", pre_context)
        object.__setattr__(self, "minimum_post_trigger_buffer_s", buffer)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_duration_s": self.total_duration_s,
            "preferred_trigger_earliest_s": self.preferred_trigger_earliest_s,
            "preferred_trigger_latest_s": self.preferred_trigger_latest_s,
            "minimum_pre_trigger_context_s": self.minimum_pre_trigger_context_s,
            "minimum_post_trigger_buffer_s": self.minimum_post_trigger_buffer_s,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ScenarioTimingSpec":
        return cls(
            total_duration_s=float(data.get("total_duration_s", 8.0)),
            preferred_trigger_earliest_s=float(data.get("preferred_trigger_earliest_s", 1.5)),
            preferred_trigger_latest_s=float(data.get("preferred_trigger_latest_s", 3.0)),
            minimum_pre_trigger_context_s=float(data.get("minimum_pre_trigger_context_s", 0.5)),
            minimum_post_trigger_buffer_s=float(data.get("minimum_post_trigger_buffer_s", 0.5)),
        )
