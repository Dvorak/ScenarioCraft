"""Code-level package boundary manifest for future core extraction.

This module is intentionally descriptive: it records stable extraction
boundaries without moving directories or changing runtime behavior.
"""

from __future__ import annotations

from itertools import chain

CORE_CANDIDATE_MODULES = (
    "scenariocraft.schemas",
    "scenariocraft.templates",
    "scenariocraft.probes",
    "scenariocraft.repair.patcher",
    "scenariocraft.repair.providers.base",
    "scenariocraft.repair.providers.fake",
    "scenariocraft.repair.providers.types",
    "scenariocraft.generators.base",
    "scenariocraft.generators.mock_generator",
    "scenariocraft.roads",
)

DELIVERY_ADAPTER_MODULES = (
    "scenariocraft.application",
    "scenariocraft.main",
    "scenariocraft.web",
)

RUNTIME_ADAPTER_MODULES = (
    "scenariocraft.references",
    "scenariocraft.repair.providers.openai",
    "scenariocraft.tools.asam_qc_tool",
    "scenariocraft.tools.esmini_tool",
)

TOOL_SEMANTIC_GROUPS = {
    "build": (
        "scenariocraft.tools.layout_adapter",
        "scenariocraft.tools.scenario_builder",
    ),
    "metrics": (
        "scenariocraft.tools.timing_metrics",
    ),
    "presentation": (
        "scenariocraft.tools.preview_2d",
        "scenariocraft.tools.report_tool",
    ),
    "validation": (
        "scenariocraft.tools.semantic_validator",
    ),
    "runtime": (
        "scenariocraft.tools.asam_qc_tool",
        "scenariocraft.tools.esmini_tool",
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
                CORE_CANDIDATE_MODULES,
                DELIVERY_ADAPTER_MODULES,
                RUNTIME_ADAPTER_MODULES,
                *TOOL_SEMANTIC_GROUPS.values(),
            )
        )
    )


__all__ = [
    "CORE_CANDIDATE_MODULES",
    "DELIVERY_ADAPTER_MODULES",
    "FORBIDDEN_CORE_IMPORT_PATTERNS",
    "RUNTIME_ADAPTER_MODULES",
    "TOOL_SEMANTIC_GROUPS",
    "current_boundary_modules",
]
