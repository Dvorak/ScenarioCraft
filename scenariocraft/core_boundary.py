"""Code-level package boundary manifest for ScenarioCraft.

The reusable domain package is `scenariocraft.core`. The `scenariocraft`
package contains delivery surfaces and optional external adapters.
"""

from __future__ import annotations

from itertools import chain

CORE_PACKAGE_MODULES = (
    "scenariocraft.core.build",
    "scenariocraft.core.generators",
    "scenariocraft.core.loop",
    "scenariocraft.core.metrics",
    "scenariocraft.core.probes",
    "scenariocraft.core.repair",
    "scenariocraft.core.roads",
    "scenariocraft.core.schemas",
    "scenariocraft.core.templates",
    "scenariocraft.core.validation",
)

DELIVERY_ADAPTER_MODULES = (
    "scenariocraft.application",
    "scenariocraft.main",
    "scenariocraft.orchestration",
    "scenariocraft.web",
)

RUNTIME_ADAPTER_MODULES = (
    "scenariocraft.integrations",
    "scenariocraft.integrations.openai_repair",
    "scenariocraft.references",
    "scenariocraft.presentation",
    "scenariocraft.runtime",
)

TOOL_SEMANTIC_GROUPS = {
    "build": (
        "scenariocraft.core.build.layout_adapter",
        "scenariocraft.core.build.scenario_builder",
    ),
    "metrics": (
        "scenariocraft.core.metrics.timing",
    ),
    "presentation": (
        "scenariocraft.presentation.preview_2d",
        "scenariocraft.presentation.report",
    ),
    "validation": (
        "scenariocraft.core.validation.semantic",
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
    "scenariocraft.integrations",
    "scenariocraft.runtime",
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
