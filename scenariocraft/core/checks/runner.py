from __future__ import annotations

"""Base protocol for deterministic ScenarioSpec checks.

Check runners collect evidence only; mutation and provider calls belong to
repair loops and repair providers.
"""

from typing import Protocol, Sequence

from scenariocraft.core.schemas import CheckResult, ScenarioSpec


class ScenarioCheck(Protocol):
    name: str

    def run(self, spec: ScenarioSpec) -> CheckResult:
        """Run a deterministic check against a ScenarioSpec."""


def run_checks(spec: ScenarioSpec, checks: Sequence[ScenarioCheck]) -> tuple[CheckResult, ...]:
    return tuple(check.run(spec) for check in checks)
