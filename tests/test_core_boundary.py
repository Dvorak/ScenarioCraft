from __future__ import annotations

from pathlib import Path


def test_core_boundary_manifest_names_stable_extraction_groups() -> None:
    from scenariocraft.core_boundary import (
        CORE_PACKAGE_MODULES,
        DELIVERY_ADAPTER_MODULES,
        RUNTIME_ADAPTER_MODULES,
        TOOL_SEMANTIC_GROUPS,
    )

    assert "scenariocraft_core.schemas" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.templates" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.probes" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.repair" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.loop" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.build" in CORE_PACKAGE_MODULES
    assert "scenariocraft_core.validation" in CORE_PACKAGE_MODULES
    assert "scenariocraft.web" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.application" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.orchestration" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.runtime" in RUNTIME_ADAPTER_MODULES
    assert "scenariocraft.presentation" in RUNTIME_ADAPTER_MODULES
    assert TOOL_SEMANTIC_GROUPS["build"] == (
        "scenariocraft_core.build.layout_adapter",
        "scenariocraft_core.build.scenario_builder",
    )
    assert "scenariocraft.presentation.preview_2d" in TOOL_SEMANTIC_GROUPS["presentation"]
    assert "scenariocraft.presentation.report" in TOOL_SEMANTIC_GROUPS["presentation"]
    assert "scenariocraft_core.metrics.timing" in TOOL_SEMANTIC_GROUPS["metrics"]
    assert TOOL_SEMANTIC_GROUPS["validation"] == ("scenariocraft_core.validation.semantic",)
    assert TOOL_SEMANTIC_GROUPS["runtime"] == (
        "scenariocraft.runtime.asam_qc",
        "scenariocraft.runtime.esmini",
    )


def test_core_boundary_manifest_has_no_missing_current_modules() -> None:
    from scenariocraft.core_boundary import current_boundary_modules

    missing = []
    for module_name in current_boundary_modules():
        relative = Path("src") / Path(*module_name.split("."))
        if not relative.with_suffix(".py").exists() and not (relative / "__init__.py").exists():
            missing.append(module_name)

    assert missing == []


def test_core_candidates_remain_free_of_delivery_runtime_and_provider_imports() -> None:
    from scenariocraft.core_boundary import CORE_PACKAGE_MODULES, FORBIDDEN_CORE_IMPORT_PATTERNS

    offenders: dict[str, list[str]] = {}
    for module_name in CORE_PACKAGE_MODULES:
        relative = Path("src") / Path(*module_name.split("."))
        paths = [relative.with_suffix(".py")] if relative.with_suffix(".py").exists() else list(relative.glob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            matches = [pattern for pattern in FORBIDDEN_CORE_IMPORT_PATTERNS if pattern in source]
            if matches:
                offenders[str(path)] = matches

    assert offenders == {}


def test_canonical_semantic_package_imports_are_available() -> None:
    from scenariocraft_core.build import build_openscenario
    from scenariocraft_core.build.scenario_builder import BuildResult
    from scenariocraft_core.metrics import compute_timing_metrics
    from scenariocraft_core.metrics.timing import time_headway_s
    from scenariocraft.presentation import generate_2d_preview, generate_validation_report
    from scenariocraft.presentation.preview_2d import estimate_ttc_s
    from scenariocraft.runtime import AsamQcResult, EsminiResult, run_asam_qc, run_esmini
    from scenariocraft.runtime.esmini import run_esmini_playback
    from scenariocraft_core.validation import validate_semantics

    assert AsamQcResult.__name__ == "AsamQcResult"
    assert BuildResult.__name__ == "BuildResult"
    assert EsminiResult.__name__ == "EsminiResult"
    assert callable(estimate_ttc_s)
    assert callable(build_openscenario)
    assert callable(compute_timing_metrics)
    assert callable(generate_2d_preview)
    assert callable(generate_validation_report)
    assert callable(run_asam_qc)
    assert callable(run_esmini)
    assert callable(run_esmini_playback)
    assert callable(time_headway_s)
    assert callable(validate_semantics)


def test_pre_release_compatibility_facades_are_not_used_by_source() -> None:
    checked_paths = [
        path
        for root in (Path("src/scenariocraft"), Path("src/scenariocraft_core"), Path("tests"))
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    forbidden = (
        "scenariocraft.loop",
        "scenariocraft.tools",
        "scenariocraft_core.schemas.scenario_spec",
        "scenariocraft.web.demo_cases",
    )

    offenders = {
        str(path): [pattern for pattern in forbidden if pattern in path.read_text(encoding="utf-8")]
        for path in checked_paths
        if path.name != Path(__file__).name
    }
    offenders = {path: patterns for path, patterns in offenders.items() if patterns}

    assert offenders == {}


def test_scenariocraft_app_no_longer_contains_core_package_directories() -> None:
    removed_core_dirs = (
        "build",
        "generators",
        "loop",
        "metrics",
        "probes",
        "roads",
        "schemas",
        "templates",
        "tools",
        "validation",
    )

    offenders = [name for name in removed_core_dirs if (Path("src/scenariocraft") / name).exists()]

    assert offenders == []
