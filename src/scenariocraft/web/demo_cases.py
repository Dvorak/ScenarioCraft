"""Compatibility exports for controlled demo cases.

The controlled demo-case workflow is application-owned. Keep this module as a
small Web-facing import shim for existing UI and tests.
"""

from scenariocraft.application.demo_cases import (
    DEMO_CASES,
    DemoCase,
    DemoCaseExecution,
    FaultDomain,
    PreparedDemoCase,
    RepairExpectation,
    execute_prepared_demo_case,
    get_demo_case,
    prepare_demo_case,
    run_demo_case,
)

__all__ = [
    "DEMO_CASES",
    "DemoCase",
    "DemoCaseExecution",
    "FaultDomain",
    "PreparedDemoCase",
    "RepairExpectation",
    "execute_prepared_demo_case",
    "get_demo_case",
    "prepare_demo_case",
    "run_demo_case",
]
