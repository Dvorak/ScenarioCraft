from __future__ import annotations

from pathlib import Path


def test_core_boundary_manifest_names_stable_extraction_groups() -> None:
    from scenariocraft.tooling.boundary_manifest import (
        CORE_PACKAGE_MODULES,
        DELIVERY_ADAPTER_MODULES,
        EXTERNAL_TOOL_MODULES,
        TOOL_SEMANTIC_GROUPS,
    )

    assert "scenariocraft.core.schemas" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.templates" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.probes" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.repair" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.loop" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.build" in CORE_PACKAGE_MODULES
    assert "scenariocraft.core.validation" in CORE_PACKAGE_MODULES
    assert "scenariocraft.web" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.application" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.application.orchestrator" in DELIVERY_ADAPTER_MODULES
    assert "scenariocraft.external_tools" in EXTERNAL_TOOL_MODULES
    assert "scenariocraft.rendering" in EXTERNAL_TOOL_MODULES
    assert "scenariocraft.providers.openai_repair" in EXTERNAL_TOOL_MODULES
    assert TOOL_SEMANTIC_GROUPS["build"] == (
        "scenariocraft.core.build.layout_adapter",
        "scenariocraft.core.build.scenario_builder",
    )
    assert "scenariocraft.rendering.preview_2d" in TOOL_SEMANTIC_GROUPS["rendering"]
    assert "scenariocraft.rendering.report" in TOOL_SEMANTIC_GROUPS["rendering"]
    assert "scenariocraft.core.metrics.timing" in TOOL_SEMANTIC_GROUPS["metrics"]
    assert TOOL_SEMANTIC_GROUPS["validation"] == ("scenariocraft.core.validation.semantic",)
    assert TOOL_SEMANTIC_GROUPS["external_tools"] == (
        "scenariocraft.external_tools.asam_qc",
        "scenariocraft.external_tools.esmini",
    )


def test_core_boundary_manifest_has_no_missing_current_modules() -> None:
    from scenariocraft.tooling.boundary_manifest import current_boundary_modules

    missing = []
    for module_name in current_boundary_modules():
        relative = Path(*module_name.split("."))
        if not relative.with_suffix(".py").exists() and not (relative / "__init__.py").exists():
            missing.append(module_name)

    assert missing == []


def test_core_candidates_remain_free_of_delivery_runtime_and_provider_imports() -> None:
    from scenariocraft.tooling.boundary_manifest import CORE_PACKAGE_MODULES, FORBIDDEN_CORE_IMPORT_PATTERNS

    offenders: dict[str, list[str]] = {}
    for module_name in CORE_PACKAGE_MODULES:
        relative = Path(*module_name.split("."))
        paths = [relative.with_suffix(".py")] if relative.with_suffix(".py").exists() else list(relative.glob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            matches = [pattern for pattern in FORBIDDEN_CORE_IMPORT_PATTERNS if pattern in source]
            if matches:
                offenders[str(path)] = matches

    assert offenders == {}


def test_canonical_semantic_package_imports_are_available() -> None:
    from scenariocraft.application import run_bounded_orchestrator
    from scenariocraft.application.orchestrator import run_bounded_orchestrator as run_orchestrator_direct
    from scenariocraft.core.build import build_openscenario
    from scenariocraft.core.build.scenario_builder import BuildResult
    from scenariocraft.core.metrics import compute_timing_metrics
    from scenariocraft.core.metrics.timing import time_headway_s
    from scenariocraft.core.schemas import ScenarioIntent
    from scenariocraft.core.templates import LeadVehicleBrakingTemplate, resolve_scenario_intent
    from scenariocraft.external_tools import AsamQcResult, EsminiResult, run_asam_qc, run_esmini
    from scenariocraft.external_tools.esmini import run_esmini_playback
    from scenariocraft.providers.openai_repair import OpenAIRepairProvider
    from scenariocraft.rendering import generate_2d_preview, generate_validation_report
    from scenariocraft.rendering.preview_2d import estimate_ttc_s
    from scenariocraft.tooling.boundary_manifest import current_boundary_modules
    from scenariocraft.core.validation import validate_semantics

    assert AsamQcResult.__name__ == "AsamQcResult"
    assert BuildResult.__name__ == "BuildResult"
    assert EsminiResult.__name__ == "EsminiResult"
    assert LeadVehicleBrakingTemplate.template_id == "lead_vehicle_braking"
    assert ScenarioIntent.__name__ == "ScenarioIntent"
    assert callable(estimate_ttc_s)
    assert callable(build_openscenario)
    assert callable(compute_timing_metrics)
    assert callable(generate_2d_preview)
    assert callable(generate_validation_report)
    assert callable(current_boundary_modules)
    assert OpenAIRepairProvider.__name__ == "OpenAIRepairProvider"
    assert callable(run_asam_qc)
    assert callable(run_bounded_orchestrator)
    assert run_bounded_orchestrator is run_orchestrator_direct
    assert callable(run_esmini)
    assert callable(run_esmini_playback)
    assert callable(resolve_scenario_intent)
    assert callable(time_headway_s)
    assert callable(validate_semantics)


def test_pre_release_compatibility_facades_are_not_used_by_source() -> None:
    checked_paths = [
        path
        for root in (Path("scenariocraft"), Path("scenariocraft/core"), Path("tests"))
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    forbidden = (
        "scenariocraft.loop",
        "scenariocraft.repair",
        "scenariocraft.runtime",
        "scenariocraft.tools",
        "scenariocraft.presentation",
        "scenariocraft.integrations",
        "scenariocraft.orchestration",
        "scenariocraft.setup",
        "scenariocraft.core_boundary",
        "scenariocraft.core.schemas.scenario_spec",
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
        "repair",
        "roads",
        "schemas",
        "templates",
        "tools",
        "runtime",
        "validation",
    )

    offenders = [name for name in removed_core_dirs if (Path("scenariocraft") / name).exists()]

    assert offenders == []


def test_canonical_source_package_directories_are_present() -> None:
    expected_dirs = (
        "core",
        "application",
        "web",
        "external_tools",
        "providers",
        "rendering",
        "tooling",
        "references",
    )

    missing = [name for name in expected_dirs if not (Path("scenariocraft") / name).is_dir()]

    assert missing == []


def test_retired_source_layout_paths_are_absent() -> None:
    retired_paths = (
        Path("scenariocraft/presentation"),
        Path("scenariocraft/integrations"),
        Path("scenariocraft/orchestration"),
        Path("scenariocraft/setup.py"),
        Path("scenariocraft/core_boundary.py"),
    )

    offenders = [str(path) for path in retired_paths if path.exists()]

    assert offenders == []


def test_core_generators_facade_is_retired() -> None:
    assert not Path("scenariocraft/core/generators").exists()
