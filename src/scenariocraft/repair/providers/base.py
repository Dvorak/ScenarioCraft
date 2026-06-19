from __future__ import annotations

from typing import Protocol, runtime_checkable

from scenariocraft.repair.providers.types import RepairProposal, RepairRequest


@runtime_checkable
class RepairProvider(Protocol):
    def propose_patch(self, request: RepairRequest) -> RepairProposal:
        """Propose a validated PatchSpec without applying it."""
