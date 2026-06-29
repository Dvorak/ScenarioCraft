from __future__ import annotations

from pathlib import Path


def test_core_boundary_manifest_names_stable_extraction_groups() -> None:
    from scenariocraft.core_boundary import (
        CORE_CANDIDATE_MODULES,
        DELIVERY_ADAPTER_MODULES,
        RUNTIME_ADAPTER_MODULES,
        TOOL_SEMANTIC_GROUPS,
    )

    assert "scenariocraft.schemas" in CORE_CANDIDATE_MODULES
    assert "scenariocraft.templates" in CORE_CANDIDATE_MODULES
    assert "scenariocraft.probes" in CORE_CANDIDATE_MODULES
    assert "scenariocraft.repair.patcher" in CORE_CANDIDATE_MODULES
    assert "scenariocraft.web" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.application" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.tools.esmini_tool" in RUNTIME_ADAPTER_MODULES
    assert "scenariocraft.tools.asam_qc_tool" in RUNTIME_ADAPTER_MODULES
    assert TOOL_SEMANTIC_GROUPS["build"] == (
        "scenariocraft.tools.layout_adapter",
        "scenariocraft.tools.scenario_builder",
    )
    assert "scenariocraft.tools.preview_2d" in TOOL_SEMANTIC_GROUPS["presentation"]
    assert "scenariocraft.tools.timing_metrics" in TOOL_SEMANTIC_GROUPS["metrics"]


def test_core_boundary_manifest_has_no_missing_current_modules() -> None:
    from scenariocraft.core_boundary import current_boundary_modules

    missing = []
    for module_name in current_boundary_modules():
        relative = Path("src") / Path(*module_name.split("."))
        if not relative.with_suffix(".py").exists() and not (relative / "__init__.py").exists():
            missing.append(module_name)

    assert missing == []


def test_core_candidates_remain_free_of_delivery_runtime_and_provider_imports() -> None:
    from scenariocraft.core_boundary import CORE_CANDIDATE_MODULES, FORBIDDEN_CORE_IMPORT_PATTERNS

    offenders: dict[str, list[str]] = {}
    for module_name in CORE_CANDIDATE_MODULES:
        relative = Path("src") / Path(*module_name.split("."))
        paths = [relative.with_suffix(".py")] if relative.with_suffix(".py").exists() else list(relative.glob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            matches = [pattern for pattern in FORBIDDEN_CORE_IMPORT_PATTERNS if pattern in source]
            if matches:
                offenders[str(path)] = matches

    assert offenders == {}
