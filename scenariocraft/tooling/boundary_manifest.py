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
    "scenariocraft._legacy_streamlit",
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
        "scenariocraft.core.build.fallback_xml_writer",
        "scenariocraft.core.build.layout_adapter",
        "scenariocraft.core.build.road_binding",
        "scenariocraft.core.build.scenario_builder",
        "scenariocraft.core.build.storyboard_compiler",
        "scenariocraft.core.build.trajectory_compiler",
        "scenariocraft.core.build.trigger_compiler",
    ),
    "metrics": (
        "scenariocraft.core.metrics.timing",
    ),
    "rendering": (
        "scenariocraft.rendering.preview_2d",
        "scenariocraft.rendering.preview_style",
        "scenariocraft.rendering.report",
    ),
    "checks": (
        "scenariocraft.core.checks.artifact_consistency",
        "scenariocraft.core.checks.crossing_vehicle",
        "scenariocraft.core.checks.cut_in",
        "scenariocraft.core.checks.family",
        "scenariocraft.core.checks.lead_vehicle_braking",
        "scenariocraft.core.checks.oncoming_turn_across_path",
        "scenariocraft.core.checks.pedestrian_occlusion",
        "scenariocraft.core.checks.runtime_consistency",
        "scenariocraft.core.checks.runtime_pipeline",
        "scenariocraft.core.checks.structural",
        "scenariocraft.core.checks.time_headway",
        "scenariocraft.core.checks.xosc_artifact_reader",
    ),
    "external_tools": (
        "scenariocraft.external_tools.asam_qc",
        "scenariocraft.external_tools.esmini",
    ),
    "providers": (
        "scenariocraft.providers.intent",
        "scenariocraft.providers.intent_eval",
        "scenariocraft.providers.openai_intent",
        "scenariocraft.providers.openai_repair",
    ),
    "roads": (
        "scenariocraft.core.roads.capability",
        "scenariocraft.core.roads.multi_lane_same_direction",
        "scenariocraft.core.roads.urban_four_way_intersection",
        "scenariocraft.core.roads.urban_two_way_parking",
    ),
    "templates": (
        "scenariocraft.core.templates.capability",
        "scenariocraft.core.templates.crossing_vehicle",
        "scenariocraft.core.templates.cut_in",
        "scenariocraft.core.templates.family_assets",
        "scenariocraft.core.templates.family_taxonomy",
        "scenariocraft.core.templates.lead_vehicle_braking",
        "scenariocraft.core.templates.oncoming_turn_across_path",
        "scenariocraft.core.templates.pedestrian_occlusion",
        "scenariocraft.core.templates.registry",
        "scenariocraft.core.templates.resolver",
    ),
}

FORBIDDEN_CORE_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft._legacy_streamlit",
    "scenariocraft.application",
    "scenariocraft.providers",
    "scenariocraft.external_tools",
    "from openai import",
    "import openai",
    "import subprocess",
    "run_esmini",
    "run_asam_qc",
)

FORBIDDEN_PROVIDER_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft._legacy_streamlit",
    "scenariocraft.external_tools",
    "scenariocraft.rendering",
    "scenariocraft.core.build",
)

FORBIDDEN_EXTERNAL_TOOL_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft._legacy_streamlit",
    "scenariocraft.providers",
    "scenariocraft.core.templates",
)

FORBIDDEN_RENDERING_IMPORT_PATTERNS = (
    "import streamlit",
    "from streamlit",
    "scenariocraft._legacy_streamlit",
    "scenariocraft.providers",
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
    "FORBIDDEN_EXTERNAL_TOOL_IMPORT_PATTERNS",
    "FORBIDDEN_CORE_IMPORT_PATTERNS",
    "FORBIDDEN_PROVIDER_IMPORT_PATTERNS",
    "FORBIDDEN_RENDERING_IMPORT_PATTERNS",
    "EXTERNAL_TOOL_MODULES",
    "TOOL_SEMANTIC_GROUPS",
    "current_boundary_modules",
]
