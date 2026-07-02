from __future__ import annotations

"""Base protocol for deterministic ScenarioSpec probes.

Probe runners collect evidence only; mutation and provider calls belong to
repair loops and repair providers.
"""

from typing import Protocol, Sequence

from scenariocraft.core.schemas import ProbeResult, ScenarioSpec


class ScenarioProbe(Protocol):
    name: str

    def run(self, spec: ScenarioSpec) -> ProbeResult:
        """Run a deterministic check against a ScenarioSpec."""


def run_probes(spec: ScenarioSpec, probes: Sequence[ScenarioProbe]) -> tuple[ProbeResult, ...]:
    return tuple(probe.run(spec) for probe in probes)
