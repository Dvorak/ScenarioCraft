import importlib


def test_build_package_exposes_separate_compiler_boundaries() -> None:
    """Keep ScenarioSpec build responsibilities out of one monolithic module."""

    expected_modules = [
        "scenariocraft.core.build.road_binding",
        "scenariocraft.core.build.storyboard_compiler",
        "scenariocraft.core.build.trajectory_compiler",
        "scenariocraft.core.build.trigger_compiler",
        "scenariocraft.core.build.fallback_xml_writer",
    ]

    for module_name in expected_modules:
        importlib.import_module(module_name)
