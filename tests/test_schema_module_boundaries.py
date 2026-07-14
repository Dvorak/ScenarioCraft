from __future__ import annotations

from pathlib import Path


def test_core_candidate_modules_do_not_import_delivery_or_runtime_adapters() -> None:
    checked_paths = [
        *Path("scenariocraft/core/schemas").glob("*.py"),
        *Path("scenariocraft/core/templates").glob("*.py"),
        *Path("scenariocraft/core/checks").glob("*.py"),
        Path("scenariocraft/core/repair/patcher.py"),
        Path("scenariocraft/core/repair/providers/fake.py"),
    ]
    forbidden = (
        "import streamlit",
        "scenariocraft._legacy_streamlit",
        "scenariocraft.application",
        "from openai import",
        "import openai",
        "run_esmini",
        "run_asam_qc",
    )

    offenders = {
        str(path): [pattern for pattern in forbidden if pattern in path.read_text(encoding="utf-8")]
        for path in checked_paths
        if path.exists()
    }
    offenders = {path: patterns for path, patterns in offenders.items() if patterns}

    assert offenders == {}


def test_schema_public_api_is_backed_by_semantic_submodules() -> None:
    from scenariocraft.core.schemas import (
        ActorSpec,
        CriticalitySpec,
        LayoutSpec,
        RoadSpec,
        ScenarioSpec,
        ScenarioTimingSpec,
        StoryboardSpec,
        TriggerSpec,
    )
    from scenariocraft.core.schemas.layout_spec import LayoutSpec as LayoutSpecFromModule
    from scenariocraft.core.schemas.road_spec import RoadSpec as RoadSpecFromModule
    from scenariocraft.core.schemas.scenario_core import ActorSpec as ActorSpecFromModule
    from scenariocraft.core.schemas.scenario_core import ScenarioSpec as ScenarioSpecFromModule
    from scenariocraft.core.schemas.storyboard_spec import StoryboardSpec as StoryboardSpecFromModule
    from scenariocraft.core.schemas.timing_spec import ScenarioTimingSpec as ScenarioTimingSpecFromModule
    from scenariocraft.core.schemas.trigger_spec import CriticalitySpec as CriticalitySpecFromModule
    from scenariocraft.core.schemas.trigger_spec import TriggerSpec as TriggerSpecFromModule

    assert ActorSpec is ActorSpecFromModule
    assert CriticalitySpec is CriticalitySpecFromModule
    assert LayoutSpec is LayoutSpecFromModule
    assert RoadSpec is RoadSpecFromModule
    assert ScenarioSpec is ScenarioSpecFromModule
    assert ScenarioTimingSpec is ScenarioTimingSpecFromModule
    assert StoryboardSpec is StoryboardSpecFromModule
    assert TriggerSpec is TriggerSpecFromModule
