from __future__ import annotations

from dataclasses import replace

from scenariocraft.schemas import (
    LayoutSpec,
    PatchSpec,
    Point2D,
    Pose2D,
    RepositionActorToBandOperation,
    ScenarioSpec,
    SetActorPoseOperation,
    SetNamedPointOperation,
    SetPathPointsOperation,
)


class PatchApplicationError(ValueError):
    """Raised when a valid PatchSpec cannot be applied to a ScenarioSpec."""


def apply_patch(spec: ScenarioSpec, patch: PatchSpec) -> ScenarioSpec:
    if not isinstance(spec, ScenarioSpec):
        raise PatchApplicationError("spec must be a ScenarioSpec.")
    if not isinstance(patch, PatchSpec):
        raise PatchApplicationError("patch must be a PatchSpec.")

    patched = spec
    for operation in patch.operations:
        if isinstance(operation, SetActorPoseOperation):
            patched = _set_actor_pose(patched, operation)
        elif isinstance(operation, RepositionActorToBandOperation):
            patched = _reposition_actor_to_band(patched, operation)
        elif isinstance(operation, SetPathPointsOperation):
            patched = _set_path_points(patched, operation)
        elif isinstance(operation, SetNamedPointOperation):
            patched = _set_named_point(patched, operation)
        else:
            raise PatchApplicationError(f"Unsupported patch operation: {type(operation).__name__}.")
    return patched


def _set_actor_pose(spec: ScenarioSpec, operation: SetActorPoseOperation) -> ScenarioSpec:
    layout = _require_layout(spec)
    _require_actor_pose(spec, layout, operation.actor_id)
    actor_poses = dict(layout.actor_poses)
    actor_poses[operation.actor_id] = Pose2D(
        x_m=operation.x_m,
        y_m=operation.y_m,
        heading_rad=operation.heading_rad,
    )
    return replace(spec, layout=replace(layout, actor_poses=actor_poses))


def _reposition_actor_to_band(
    spec: ScenarioSpec,
    operation: RepositionActorToBandOperation,
) -> ScenarioSpec:
    layout = _require_layout(spec)
    pose = _require_actor_pose(spec, layout, operation.actor_id)
    footprint = layout.actor_footprints.get(operation.actor_id)
    if footprint is None:
        raise PatchApplicationError(f"Actor footprint not found: {operation.actor_id}.")
    band = next((item for item in layout.road_bands if item.id == operation.target_band_id), None)
    if band is None:
        raise PatchApplicationError(f"Road band not found: {operation.target_band_id}.")
    band_width_m = band.y_max_m - band.y_min_m
    if footprint.width_m > band_width_m:
        raise PatchApplicationError(
            f"Actor footprint is wider than road band: {operation.actor_id} -> {operation.target_band_id}."
        )

    actor_poses = dict(layout.actor_poses)
    actor_poses[operation.actor_id] = Pose2D(
        x_m=pose.x_m,
        y_m=(band.y_min_m + band.y_max_m) / 2.0,
        heading_rad=pose.heading_rad,
    )
    return replace(spec, layout=replace(layout, actor_poses=actor_poses))


def _set_path_points(spec: ScenarioSpec, operation: SetPathPointsOperation) -> ScenarioSpec:
    layout = _require_layout(spec)
    path = layout.paths.get(operation.path_id)
    if path is None:
        raise PatchApplicationError(f"Path not found: {operation.path_id}.")
    paths = dict(layout.paths)
    paths[operation.path_id] = replace(path, points=operation.points)
    return replace(spec, layout=replace(layout, paths=paths))


def _set_named_point(spec: ScenarioSpec, operation: SetNamedPointOperation) -> ScenarioSpec:
    layout = _require_layout(spec)
    if operation.point_id not in layout.points:
        raise PatchApplicationError(f"Named point not found: {operation.point_id}.")
    points = dict(layout.points)
    points[operation.point_id] = Point2D(x_m=operation.x_m, y_m=operation.y_m)
    return replace(spec, layout=replace(layout, points=points))


def _require_layout(spec: ScenarioSpec) -> LayoutSpec:
    if spec.layout is None:
        raise PatchApplicationError("ScenarioSpec.layout is required for patch application.")
    return spec.layout


def _require_actor_pose(spec: ScenarioSpec, layout: LayoutSpec, actor_id: str) -> Pose2D:
    if spec.actor_by_id(actor_id) is None or actor_id not in layout.actor_poses:
        raise PatchApplicationError(f"Actor not found: {actor_id}.")
    return layout.actor_poses[actor_id]
