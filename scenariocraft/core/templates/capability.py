from __future__ import annotations

"""Template capability manifests and deterministic parameter resolution.

Capabilities describe a scenario family parameter space. They let providers
and resolvers vary a template without turning templates into fixed examples or
free-form XML generators.
"""

from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

ParameterKind = Literal["float", "int", "str", "bool"]
ResolvedParameterSource = Literal["user", "intent", "sampled", "default"]


@dataclass(frozen=True)
class ParameterDomain:
    name: str
    kind: ParameterKind
    default: object
    unit: str | None = None
    min_value: float | None = None
    max_value: float | None = None
    allowed_values: tuple[object, ...] = ()
    user_settable: bool = True
    sampleable: bool = True
    description: str = ""

    def validate(self, value: object) -> object:
        if self.kind == "float":
            value = float(value)
            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"{self.name} must be >= {self.min_value:g}.")
            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"{self.name} must be <= {self.max_value:g}.")
            return value
        if self.kind == "int":
            value = int(value)
            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"{self.name} must be >= {self.min_value:g}.")
            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"{self.name} must be <= {self.max_value:g}.")
            return value
        if self.kind == "bool":
            if isinstance(value, bool):
                return value
            raise ValueError(f"{self.name} must be a bool.")
        if self.kind == "str":
            value = str(value)
            if self.allowed_values and value not in self.allowed_values:
                allowed = ", ".join(str(item) for item in self.allowed_values)
                raise ValueError(f"{self.name} must be one of: {allowed}.")
            return value
        raise ValueError(f"Unsupported parameter kind: {self.kind}.")

    def sample(self, *, seed: int, variant_index: int, template_id: str) -> object:
        if not self.sampleable:
            return self.validate(self.default)
        fraction = _stable_fraction(f"{template_id}:{seed}:{variant_index}:{self.name}")
        if self.kind == "float":
            low = self.min_value if self.min_value is not None else float(self.default)
            high = self.max_value if self.max_value is not None else float(self.default)
            return round(low + (high - low) * fraction, 3)
        if self.kind == "int":
            low = int(self.min_value if self.min_value is not None else self.default)
            high = int(self.max_value if self.max_value is not None else self.default)
            return low + int(fraction * ((high - low) + 1))
        if self.kind == "str" and self.allowed_values:
            index = min(int(fraction * len(self.allowed_values)), len(self.allowed_values) - 1)
            return self.allowed_values[index]
        if self.kind == "bool":
            return fraction >= 0.5
        return self.validate(self.default)

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "kind": self.kind,
            "default": self.default,
            "user_settable": self.user_settable,
            "sampleable": self.sampleable,
        }
        if self.unit is not None:
            data["unit"] = self.unit
        if self.min_value is not None:
            data["min_value"] = self.min_value
        if self.max_value is not None:
            data["max_value"] = self.max_value
        if self.allowed_values:
            data["allowed_values"] = list(self.allowed_values)
        if self.description:
            data["description"] = self.description
        return data


@dataclass(frozen=True)
class TemplateCapability:
    template_id: str
    interaction_family: str
    description: str
    actor_roles: tuple[str, ...]
    road_contexts: tuple[str, ...]
    topologies: tuple[str, ...]
    parameter_domains: tuple[ParameterDomain, ...]
    aliases: tuple[str, ...] = ()
    semantic_slots: tuple[str, ...] = ()
    supported_variants: tuple[str, ...] = ()
    unsupported_boundary_examples: tuple[str, ...] = ()
    default_seed: int = 0
    sampling_policy: str = "deterministic_seeded"

    def domain_map(self) -> dict[str, ParameterDomain]:
        return {domain.name: domain for domain in self.parameter_domains}

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "interaction_family": self.interaction_family,
            "description": self.description,
            "actor_roles": list(self.actor_roles),
            "road_contexts": list(self.road_contexts),
            "topologies": list(self.topologies),
            "aliases": list(self.aliases),
            "semantic_slots": list(self.semantic_slots),
            "supported_variants": list(self.supported_variants),
            "unsupported_boundary_examples": list(self.unsupported_boundary_examples),
            "parameter_domains": [domain.to_dict() for domain in self.parameter_domains],
            "default_seed": self.default_seed,
            "sampling_policy": self.sampling_policy,
        }


@dataclass(frozen=True)
class ResolvedParameter:
    name: str
    value: object
    source: ResolvedParameterSource
    unit: str | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "value": self.value,
            "source": self.source,
        }
        if self.unit is not None:
            data["unit"] = self.unit
        return data


@dataclass(frozen=True)
class ResolvedTemplateParameters:
    template_id: str
    seed: int | None
    variant_index: int
    sampled: bool
    values: dict[str, object]
    parameters: tuple[ResolvedParameter, ...]
    unsupported_fields: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "seed": self.seed,
            "variant_index": self.variant_index,
            "sampled": self.sampled,
            "values": dict(self.values),
            "parameters": [parameter.to_dict() for parameter in self.parameters],
            "unsupported_fields": list(self.unsupported_fields),
        }


def _stable_fraction(key: str) -> float:
    digest = sha256(key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64
