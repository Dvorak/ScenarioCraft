from __future__ import annotations

"""Readiness contract for turning declared families into executable assets.

This module is intentionally descriptive. It does not register templates or
make planned families executable; it explains which deterministic assets are
present or missing for each declared scenario family.
"""

from dataclasses import dataclass
from typing import Mapping

from scenariocraft.core.templates.family_taxonomy import (
    FamilyStatus,
    family_declaration,
    family_declarations,
)
from scenariocraft.core.templates.registry import registered_templates

SUPPORTED_ROAD_ASSETS: tuple[str, ...] = (
    "urban_two_way_parking",
    "multi_lane_same_direction",
    "urban_four_way_intersection",
)

_REQUIRED_ROAD_ASSETS: Mapping[str, tuple[str, ...]] = {
    "pedestrian_occlusion": ("urban_two_way_parking",),
    "lead_vehicle_braking": ("urban_two_way_parking",),
    "cut_in": ("multi_lane_same_direction",),
    "crossing_vehicle": ("urban_four_way_intersection",),
    "oncoming_turn_across_path": ("urban_four_way_intersection",),
}

_BUILDER_READY_FAMILIES: frozenset[str] = frozenset(
    {
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    }
)
_FAMILY_CHECK_READY_FAMILIES: frozenset[str] = frozenset(
    {
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    }
)
_ARTIFACT_CHECK_READY_FAMILIES: frozenset[str] = frozenset(
    {
        "pedestrian_occlusion",
        "lead_vehicle_braking",
        "cut_in",
        "crossing_vehicle",
        "oncoming_turn_across_path",
    }
)


@dataclass(frozen=True)
class FamilyAssetReadiness:
    """Machine-readable readiness summary for one scenario family."""

    template_id: str
    status: FamilyStatus
    executable: bool
    template_registered: bool
    capability_ready: bool
    road_asset_ready: bool
    builder_ready: bool
    family_checks_ready: bool
    artifact_checks_ready: bool
    required_road_assets: tuple[str, ...]
    missing_assets: tuple[str, ...]
    automatable_scaffold: tuple[str, ...]
    manual_dirty_work: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "template_id": self.template_id,
            "status": self.status,
            "executable": self.executable,
            "template_registered": self.template_registered,
            "capability_ready": self.capability_ready,
            "road_asset_ready": self.road_asset_ready,
            "builder_ready": self.builder_ready,
            "family_checks_ready": self.family_checks_ready,
            "artifact_checks_ready": self.artifact_checks_ready,
            "required_road_assets": list(self.required_road_assets),
            "missing_assets": list(self.missing_assets),
            "automatable_scaffold": list(self.automatable_scaffold),
            "manual_dirty_work": list(self.manual_dirty_work),
        }


def family_asset_readiness(template_id: str) -> FamilyAssetReadiness:
    declaration = family_declaration(template_id)
    templates = registered_templates()
    template = templates.get(template_id)
    template_registered = template is not None

    domain_names = set(template.capability.domain_map()) if template_registered else set()
    capability_ready = bool(declaration.capability_parameter_names) and set(
        declaration.capability_parameter_names
    ) <= domain_names

    required_roads = _REQUIRED_ROAD_ASSETS.get(template_id, declaration.topologies)
    road_asset_ready = all(road in SUPPORTED_ROAD_ASSETS for road in required_roads)
    builder_ready = template_id in _BUILDER_READY_FAMILIES
    family_checks_ready = template_id in _FAMILY_CHECK_READY_FAMILIES
    artifact_checks_ready = template_id in _ARTIFACT_CHECK_READY_FAMILIES
    executable = template_registered and capability_ready and builder_ready

    missing_assets: list[str] = []
    if not template_registered:
        missing_assets.append("executable_template")
    if not capability_ready:
        missing_assets.append("capability_parameter_names")
    for road in required_roads:
        if road not in SUPPORTED_ROAD_ASSETS:
            missing_assets.append(f"road_asset:{road}")
    if not builder_ready:
        missing_assets.append("builder_storyboard_support")
    if not family_checks_ready:
        missing_assets.append("family_check_module")
    if not artifact_checks_ready:
        missing_assets.append("artifact_consistency_checks")

    return FamilyAssetReadiness(
        template_id=template_id,
        status=declaration.status,
        executable=executable,
        template_registered=template_registered,
        capability_ready=capability_ready,
        road_asset_ready=road_asset_ready,
        builder_ready=builder_ready,
        family_checks_ready=family_checks_ready,
        artifact_checks_ready=artifact_checks_ready,
        required_road_assets=required_roads,
        missing_assets=tuple(missing_assets),
        automatable_scaffold=_automatable_scaffold(
            template_registered=template_registered,
            capability_ready=capability_ready,
            family_checks_ready=family_checks_ready,
            artifact_checks_ready=artifact_checks_ready,
        ),
        manual_dirty_work=_manual_dirty_work(
            required_roads=required_roads,
            road_asset_ready=road_asset_ready,
            builder_ready=builder_ready,
            family_checks_ready=family_checks_ready,
            artifact_checks_ready=artifact_checks_ready,
        ),
    )


def family_asset_readiness_report() -> dict[str, FamilyAssetReadiness]:
    return {
        template_id: family_asset_readiness(template_id)
        for template_id in family_declarations()
    }


def _automatable_scaffold(
    *,
    template_registered: bool,
    capability_ready: bool,
    family_checks_ready: bool,
    artifact_checks_ready: bool,
) -> tuple[str, ...]:
    items: list[str] = []
    if not template_registered:
        items.append("template_file_skeleton")
    if not capability_ready:
        items.append("template_capability_skeleton")
    if not family_checks_ready:
        items.append("family_check_test_skeleton")
    if not artifact_checks_ready:
        items.append("artifact_check_test_skeleton")
    return tuple(items)


def _manual_dirty_work(
    *,
    required_roads: tuple[str, ...],
    road_asset_ready: bool,
    builder_ready: bool,
    family_checks_ready: bool,
    artifact_checks_ready: bool,
) -> tuple[str, ...]:
    items: list[str] = []
    if not road_asset_ready:
        items.extend(f"road_asset_design:{road}" for road in required_roads)
    if not builder_ready:
        items.append("builder_storyboard_support")
    if not family_checks_ready:
        items.append("family_specific_geometry_timing_checks")
    if not artifact_checks_ready:
        items.append("artifact_serialization_checks")
    return tuple(items)
