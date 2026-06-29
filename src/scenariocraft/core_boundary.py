"""Code-level package boundary manifest for ScenarioCraft.

The reusable domain package is `scenariocraft_core`. The `scenariocraft`
package contains delivery surfaces and optional external adapters.
"""

from __future__ import annotations

from itertools import chain

CORE_PACKAGE_MODULES = (
    "scenariocraft_core.build",
    "scenariocraft_core.generators",
    "scenariocraft_core.loop",
    "scenariocraft_core.metrics",
    "scenariocraft_core.probes",
    "scenariocraft_core.repair",
    "scenariocraft_core.roads",
    "scenariocraft_core.schemas",
    "scenariocraft_core.templates",
    "scenariocraft_core.validation",
)

DELIVERY_ADAPTER_MODULES = (
    "scenariocraft.application",
    "scenariocraft.main",
    "scenariocraft.web",
)

RUNTIME_ADAPTER_MODULES = (
    "scenariocraft.references",
    "scenariocraft.presentation",
    "scenariocraft.references",
    "scenariocraft.repair.providers.openai",
    "scenariocraft.runtime",
)

TOOL_SEMANTIC_GROUPS = {
    "build": (
        "scenariocraft_core.build.layout_adapter",
        "scenariocraft_core.build.scenario_builder",
    ),
    "metrics": (
        "scenariocraft_core.metrics.timing",
    ),
    "presentation": (
        "scenariocraft.presentation.preview_2d",
        "scenariocraft.presentation.report",
    ),
    "validation": (
        "scenariocraft_core.validation.semantic",
    ),
    "runtime": (
        "scenariocraft.runtime.asam_qc",
        "scenariocraft.runtime.esmini",
    ),
}

FORBIDDEN_CORE_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft.web",
    "scenariocraft.application",
    "from openai import",
    "import openai",
    "import subprocess",
    "run_esmini",
    "run_asam_qc",
)


def current_boundary_modules() -> tuple[str, ...]:
    """Return all current modules named by the extraction boundary manifest."""

    return tuple(
        dict.fromkeys(
            chain(
                CORE_PACKAGE_MODULES,
                DELIVERY_ADAPTER_MODULES,
                RUNTIME_ADAPTER_MODULES,
                *TOOL_SEMANTIC_GROUPS.values(),
            )
        )
    )


__all__ = [
    "CORE_PACKAGE_MODULES",
    "DELIVERY_ADAPTER_MODULES",
    "FORBIDDEN_CORE_IMPORT_PATTERNS",
    "RUNTIME_ADAPTER_MODULES",
    "TOOL_SEMANTIC_GROUPS",
    "current_boundary_modules",
]
