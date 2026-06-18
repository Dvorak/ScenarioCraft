from __future__ import annotations

import os
import tempfile
import math
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "scenariocraft-matplotlib"))

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrow, FancyArrowPatch, Rectangle

from scenariocraft.schemas import FootprintSpec, LayoutSpec, PathSpec, Point2D, Pose2D, RoadBandSpec, ScenarioSpec


def generate_2d_preview(spec: ScenarioSpec, out_path: Path) -> Path:
    """Generate a deterministic top-down preview image for the scenario."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.8, 5.4), dpi=140)
    if spec.layout is not None:
        xlim, ylim = _layout_plot_limits(spec.layout)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
    else:
        ax.set_xlim(-8, 62)
        ax.set_ylim(-13, 13)
    ax.axis("off")

    if spec.layout is not None and spec.layout.road_bands:
        _draw_layout_background(ax)
        _draw_layout_road_bands(ax, spec.layout)
    else:
        _draw_background(ax)
        _draw_road(ax)
    _draw_actors(ax, spec)
    _draw_scenario_marks(ax, spec)
    _draw_legend(ax)
    _draw_title(ax, spec)

    fig.savefig(out_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


def estimate_ttc_s(spec: ScenarioSpec) -> float | None:
    ego = spec.actor_by_role("ego")
    if ego is None or ego.initial_speed_kph is None or ego.initial_speed_kph <= 0:
        return None
    return spec.trigger.distance_m / (ego.initial_speed_kph / 3.6)


def _draw_background(ax: object) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    width = x1 - x0
    ax.add_patch(Rectangle((x0, y0), width, y1 - y0, facecolor="#e8f1e6", edgecolor="none"))
    ax.add_patch(Rectangle((x0, 6.2), width * 0.32, max(0, y1 - 6.2), facecolor="#7aa36f", edgecolor="none", alpha=0.55))
    ax.add_patch(Rectangle((x0 + width * 0.72, 6.2), width * 0.28, max(0, y1 - 6.2), facecolor="#7aa36f", edgecolor="none", alpha=0.55))
    ax.add_patch(Rectangle((x0 + width * 0.32, 6.2), width * 0.4, max(0, y1 - 6.2), facecolor="#c6b59d", edgecolor="none", alpha=0.8))


def _draw_road(ax: object) -> None:
    x0, x1 = ax.get_xlim()
    ax.add_patch(Rectangle((x0, -6.5), x1 - x0, 13, facecolor="#b8bec3", edgecolor="none"))
    ax.plot([x0, x1], [0, 0], color="white", linewidth=2.4, linestyle=(0, (9, 7)), alpha=0.95)
    ax.plot([x0, x1], [-6.4, -6.4], color="#eef2f7", linewidth=1.4)
    ax.plot([x0, x1], [6.4, 6.4], color="#eef2f7", linewidth=1.4)
    ax.add_patch(FancyArrow(x0 + 10, 3.6, 10, 0, width=0.22, head_width=1.3, head_length=2.4, color="white", alpha=0.95))


def _draw_layout_background(ax: object) -> None:
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor="#e8f1e6", edgecolor="none"))


def _draw_layout_road_bands(ax: object, layout: LayoutSpec) -> None:
    x0, x1 = ax.get_xlim()
    sorted_bands = sorted(layout.road_bands, key=lambda band: band.y_min_m)
    for band in sorted_bands:
        ax.add_patch(
            Rectangle(
                (x0, band.y_min_m),
                x1 - x0,
                band.y_max_m - band.y_min_m,
                facecolor=_road_band_color(band),
                edgecolor="none",
                zorder=1,
            )
        )
        ax.plot([x0, x1], [band.y_min_m, band.y_min_m], color="#eef2f7", linewidth=1.1, alpha=0.88, zorder=2)
        ax.text(x0 + 1.3, (band.y_min_m + band.y_max_m) / 2, band.id.replace("_", " "), fontsize=7.4, color="#334155", va="center", zorder=3)
        if band.kind == "driving_lane" and band.travel_direction is not None:
            _road_band_direction_arrow(ax, band)
    ax.plot([x0, x1], [sorted_bands[-1].y_max_m, sorted_bands[-1].y_max_m], color="#eef2f7", linewidth=1.1, alpha=0.88, zorder=2)


def _road_band_color(band: RoadBandSpec) -> str:
    colors = {
        "sidewalk": "#d8d2c4",
        "parking_strip": "#9aa3ad",
        "driving_lane": "#b8bec3",
        "center_divider": "#f8fafc",
        "shoulder": "#aeb6bf",
    }
    return colors[band.kind]


def _road_band_direction_arrow(ax: object, band: RoadBandSpec) -> None:
    x0, x1 = ax.get_xlim()
    y = (band.y_min_m + band.y_max_m) / 2
    if band.travel_direction == "+x":
        start_x = x0 + max(6.0, (x1 - x0) * 0.18)
        dx = min(10.0, (x1 - x0) * 0.18)
    else:
        start_x = x1 - max(6.0, (x1 - x0) * 0.18)
        dx = -min(10.0, (x1 - x0) * 0.18)
    ax.add_patch(
        FancyArrow(
            start_x,
            y,
            dx,
            0,
            width=0.10,
            head_width=0.62,
            head_length=1.25,
            color="white",
            alpha=0.95,
            zorder=3,
        )
    )


def _draw_actors(ax: object, spec: ScenarioSpec) -> None:
    if spec.layout is not None:
        _draw_layout_actors(ax, spec)
        return
    ego = spec.actor_by_role("ego")
    occluder = spec.actor_by_role("occluder")
    pedestrian = spec.actor_by_role("crossing_actor")
    if ego is not None:
        _vehicle(ax, x=6, y=-3.25, width=9.5, height=3.4, color="#151515", label="EGO")
        ax.add_patch(FancyArrow(16.2, -3.25, 7.2, 0, width=0.12, head_width=0.95, head_length=1.4, color="#f8fafc"))
    if occluder is not None:
        _vehicle(ax, x=33, y=3.25, width=12, height=3.6, color="#2563eb", label="VAN")
    if pedestrian is not None:
        ax.scatter([35], [-8.2], s=70, color="#f97316", edgecolor="#dc2626", linewidth=1.2, zorder=7)
        ax.text(36.1, -8.3, "pedestrian", fontsize=8.5, color="#7f1d1d", va="center")


def _draw_scenario_marks(ax: object, spec: ScenarioSpec) -> None:
    if spec.layout is not None:
        _draw_layout_scenario_marks(ax, spec)
        return
    pedestrian = spec.actor_by_role("crossing_actor")
    trigger_x = min(31, max(17, 6 + spec.trigger.distance_m * 0.55))
    conflict_x = 35 if pedestrian is not None else trigger_x
    if pedestrian is not None:
        path = FancyArrowPatch(
            (35, -8.0),
            (conflict_x, 0.8),
            connectionstyle="arc3,rad=-0.16",
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=2.0,
            linestyle=(0, (4, 4)),
            color="#ef4444",
            zorder=6,
        )
        ax.add_patch(path)
    else:
        ax.plot([conflict_x, conflict_x], [-8, 2], color="#ef4444", linewidth=2, linestyle=(0, (4, 4)), alpha=0.35)

    ax.scatter([trigger_x], [-3.25], s=82, color="#7c3aed", edgecolor="white", linewidth=1.3, zorder=8)
    ax.text(trigger_x + 0.9, -4.35, "trigger", fontsize=8.5, color="#3b0764", va="top")
    ax.scatter([conflict_x], [0.8], s=92, color="#f59e0b", edgecolor="white", linewidth=1.3, zorder=8)
    ax.text(conflict_x + 1.0, 0.15, "conflict point", fontsize=8.5, color="#78350f", va="top")


def _draw_layout_actors(ax: object, spec: ScenarioSpec) -> None:
    assert spec.layout is not None
    ego = spec.actor_by_role("ego")
    occluder = spec.actor_by_role("occluder")
    pedestrian = spec.actor_by_role("crossing_actor")
    ego_pose = _layout_pose(spec.layout, ego.id if ego else "ego")
    van_pose = _layout_pose(spec.layout, occluder.id if occluder else "parked_van")
    pedestrian_pose = _layout_pose(spec.layout, pedestrian.id if pedestrian else "pedestrian")

    if ego is not None and ego_pose is not None:
        footprint = _layout_footprint(spec.layout, ego.id)
        _vehicle(ax, x=ego_pose.x_m, y=ego_pose.y_m, width=footprint.length_m, height=footprint.width_m, color="#151515", label="EGO")
        _direction_arrow(ax, ego_pose, color="#f8fafc")
    if occluder is not None and van_pose is not None:
        footprint = _layout_footprint(spec.layout, occluder.id)
        _vehicle(ax, x=van_pose.x_m, y=van_pose.y_m, width=footprint.length_m, height=footprint.width_m, color="#2563eb", label="VAN")
    if pedestrian is not None and pedestrian_pose is not None:
        footprint = _layout_footprint(spec.layout, pedestrian.id)
        ax.add_patch(Rectangle(
            (pedestrian_pose.x_m - footprint.length_m / 2, pedestrian_pose.y_m - footprint.width_m / 2),
            footprint.length_m,
            footprint.width_m,
            facecolor="#f97316",
            edgecolor="#dc2626",
            linewidth=1.2,
            zorder=7,
        ))
        ax.scatter([pedestrian_pose.x_m], [pedestrian_pose.y_m], s=24, color="#fed7aa", edgecolor="#dc2626", linewidth=0.8, zorder=8)
        ax.text(pedestrian_pose.x_m + 0.9, pedestrian_pose.y_m + 0.45, "pedestrian", fontsize=8.5, color="#7f1d1d", va="center")


def _draw_layout_scenario_marks(ax: object, spec: ScenarioSpec) -> None:
    assert spec.layout is not None
    crossing_path = _layout_path(spec.layout, "pedestrian_crossing_path")
    trigger_point = _layout_point(spec.layout, "trigger_point")
    conflict_point = _layout_point(spec.layout, "conflict_point")
    if crossing_path is not None and len(crossing_path.points) >= 2:
        start = crossing_path.points[0]
        end = crossing_path.points[-1]
        path = FancyArrowPatch(
            (start.x_m, start.y_m),
            (end.x_m, end.y_m),
            connectionstyle="arc3,rad=-0.04",
            arrowstyle="-|>",
            mutation_scale=12,
            linewidth=2.0,
            linestyle=(0, (4, 4)),
            color="#ef4444",
            zorder=6,
        )
        ax.add_patch(path)
    if trigger_point is not None:
        ax.scatter([trigger_point.x_m], [trigger_point.y_m], s=82, color="#7c3aed", edgecolor="white", linewidth=1.3, zorder=8)
        ax.text(trigger_point.x_m + 0.9, trigger_point.y_m - 1.1, "trigger", fontsize=8.5, color="#3b0764", va="top")
    if conflict_point is not None:
        ax.scatter([conflict_point.x_m], [conflict_point.y_m], s=92, color="#f59e0b", edgecolor="white", linewidth=1.3, zorder=8)
        ax.text(conflict_point.x_m + 1.0, conflict_point.y_m - 0.65, "conflict point", fontsize=8.5, color="#78350f", va="top")


def _direction_arrow(ax: object, pose: Pose2D, color: str) -> None:
    length = 7.2
    dx = length * math.cos(pose.heading_rad)
    dy = length * math.sin(pose.heading_rad)
    ax.add_patch(FancyArrow(pose.x_m + 2.4, pose.y_m, dx, dy, width=0.12, head_width=0.95, head_length=1.4, color=color))


def _layout_pose(layout: LayoutSpec, actor_id: str) -> Pose2D | None:
    return layout.actor_poses.get(actor_id)


def _layout_path(layout: LayoutSpec, path_name: str) -> PathSpec | None:
    return layout.paths.get(path_name)


def _layout_point(layout: LayoutSpec, point_name: str) -> Point2D | None:
    return layout.points.get(point_name)


def _layout_footprint(layout: LayoutSpec, actor_id: str) -> FootprintSpec:
    return layout.actor_footprints.get(actor_id, FootprintSpec(length_m=4.5, width_m=1.8))


def _layout_plot_limits(layout: LayoutSpec) -> tuple[tuple[float, float], tuple[float, float]]:
    xs: list[float] = []
    ys: list[float] = []
    for actor_id, pose in layout.actor_poses.items():
        footprint = _layout_footprint(layout, actor_id)
        xs.extend([pose.x_m - footprint.length_m / 2, pose.x_m + footprint.length_m / 2])
        ys.extend([pose.y_m - footprint.width_m / 2, pose.y_m + footprint.width_m / 2])
    for path in layout.paths.values():
        for point in path.points:
            xs.append(point.x_m)
            ys.append(point.y_m)
    for point in layout.points.values():
        xs.append(point.x_m)
        ys.append(point.y_m)
    for band in layout.road_bands:
        ys.extend([band.y_min_m, band.y_max_m])
    if not xs or not ys:
        return (-8, 62), (-13, 13)
    x0 = min(xs) - 6
    x1 = max(xs) + 8
    y0 = min(min(ys) - 4, -10)
    y1 = max(max(ys) + 4, 10)
    return (x0, x1), (y0, y1)


def _draw_legend(ax: object) -> None:
    x0, _ = ax.get_xlim()
    y0, _ = ax.get_ylim()
    legend_y = y0 + 1.3
    items = [
        ("#151515", "Ego vehicle"),
        ("#2563eb", "Parked van"),
        ("#f97316", "Pedestrian"),
        ("#7c3aed", "Trigger/conflict point"),
    ]
    x = x0 + 3.0
    for color, label in items:
        ax.add_patch(Rectangle((x, legend_y - 0.45), 1.1, 0.9, facecolor=color, edgecolor="#0f172a", linewidth=0.4))
        ax.text(x + 1.55, legend_y, label, fontsize=8.8, color="#0f172a", va="center")
        x += 15.2 if label != "Trigger/conflict point" else 18


def _draw_title(ax: object, spec: ScenarioSpec) -> None:
    ttc = estimate_ttc_s(spec)
    ttc_label = "n/a" if ttc is None else f"{ttc:.1f} s"
    x0, _ = ax.get_xlim()
    _, y1 = ax.get_ylim()
    ax.text(
        x0 + 3.0,
        y1 - 1.0,
        f"{spec.scenario_name} | rain: {spec.weather.rain} | est. TTC: {ttc_label}",
        fontsize=10.5,
        color="#0f172a",
        weight="bold",
        va="center",
    )


def _vehicle(ax: object, x: float, y: float, width: float, height: float, color: str, label: str) -> None:
    ax.add_patch(
        Rectangle(
            (x - width / 2, y - height / 2),
            width,
            height,
            facecolor=color,
            edgecolor="#0f172a",
            linewidth=1.2,
            zorder=5,
        )
    )
    ax.add_patch(
        Rectangle(
            (x - width * 0.18, y - height * 0.36),
            width * 0.28,
            height * 0.72,
            facecolor="white",
            alpha=0.14,
            edgecolor="none",
            zorder=6,
        )
    )
    ax.text(x, y, label, ha="center", va="center", fontsize=9, color="white", weight="bold", zorder=7)
