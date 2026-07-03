"""Code-level package boundary manifest for ScenarioCraft.

The reusable domain package is `scenariocraft.core`. The `scenariocraft`
package contains delivery surfaces, rendering, providers, and optional
external-tool adapters.
"""

from __future__ import annotations

from itertools import chain

CORE_PACKAGE_MODULES = (
    "scenariocraft.core.build",
    "scenariocraft.core.checks",
    "scenariocraft.core.loop",
    "scenariocraft.core.metrics",
    "scenariocraft.core.repair",
    "scenariocraft.core.roads",
    "scenariocraft.core.schemas",
    "scenariocraft.core.templates",
)

DELIVERY_ADAPTER_MODULES = (
    "scenariocraft.application",
    "scenariocraft.main",
    "scenariocraft.application.orchestrator",
    "scenariocraft.web",
)

EXTERNAL_TOOL_MODULES = (
    "scenariocraft.providers",
    "scenariocraft.providers.openai_repair",
    "scenariocraft.references",
    "scenariocraft.rendering",
    "scenariocraft.external_tools",
)

TOOL_SEMANTIC_GROUPS = {
    "build": (
        "scenariocraft.core.build.layout_adapter",
        "scenariocraft.core.build.scenario_builder",
    ),
    "metrics": (
        "scenariocraft.core.metrics.timing",
    ),
    "rendering": (
        "scenariocraft.rendering.preview_2d",
        "scenariocraft.rendering.report",
    ),
    "checks": (
        "scenariocraft.core.checks.structural",
    ),
    "external_tools": (
        "scenariocraft.external_tools.asam_qc",
        "scenariocraft.external_tools.esmini",
    ),
}

FORBIDDEN_CORE_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft.web",
    "scenariocraft.application",
    "scenariocraft.providers",
    "scenariocraft.external_tools",
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
                EXTERNAL_TOOL_MODULES,
                *TOOL_SEMANTIC_GROUPS.values(),
            )
        )
    )


__all__ = [
    "CORE_PACKAGE_MODULES",
    "DELIVERY_ADAPTER_MODULES",
    "FORBIDDEN_CORE_IMPORT_PATTERNS",
    "EXTERNAL_TOOL_MODULES",
    "TOOL_SEMANTIC_GROUPS",
    "current_boundary_modules",
]
