from __future__ import annotations

import math


class ScenarioSpecError(ValueError):
    """Raised when a ScenarioSpec cannot be validated."""


def require_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ScenarioSpecError(f"{field_name} must be a non-empty string.")
    return value


def require_finite_number(value: float, field_name: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ScenarioSpecError(f"{field_name} must be a finite number.")
    return number


def require_positive_number(value: float, field_name: str) -> float:
    number = require_finite_number(value, field_name)
    if number <= 0:
        raise ScenarioSpecError(f"{field_name} must be positive.")
    return number


def require_non_negative_number(value: float, field_name: str) -> float:
    number = require_finite_number(value, field_name)
    if number < 0:
        raise ScenarioSpecError(f"{field_name} must be non-negative.")
    return number


def require_unique_ids(field_name: str, items: tuple[object, ...]) -> None:
    ids = [getattr(item, "id", None) for item in items]
    if len(ids) != len(set(ids)):
        raise ScenarioSpecError(f"{field_name} ids must be unique.")
