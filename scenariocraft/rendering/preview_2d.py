from __future__ import annotations

import os
import tempfile
import math
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "scenariocraft-matplotlib"))

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrow, FancyArrowPatch, Rectangle

from scenariocraft.core.roads import road_preview_surface_kind
from scenariocraft.core.schemas import FootprintSpec, LayoutSpec, PathSpec, Point2D, Pose2D, RoadBandSpec, ScenarioSpec

PREVIEW_DISPLAY_ORIENTATIONS = {"semantic_canonical", "esmini_top_camera_raw"}
PREVIEW_PRESENTATION_STYLES = {"annotated", "clean_split"}
CLEAN_PREVIEW_ASPECT_RATIO = 16 / 9


def generate_2d_preview(
    spec: ScenarioSpec,
    out_path: Path,
    *,
    display_orientation: str = "semantic_canonical",
    presentation_style: str = "annotated",
) -> Path:
    """Generate a deterministic top-down preview image for the scenario."""
    if display_orientation not in PREVIEW_DISPLAY_ORIENTATIONS:
        raise ValueError(f"Unsupported preview display orientation: {display_orientation}")
    if presentation_style not in PREVIEW_PRESENTATION_STYLES:
        raise ValueError(f"Unsupported preview presentation style: {presentation_style}")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, _ax, _legend_ax = _render_preview_figure(
        spec,
        display_orientation=display_orientation,
        presentation_style=presentation_style,
    )
    if presentation_style == "clean_split":
        fig.savefig(out_path, bbox_inches=None, pad_inches=0)
    else:
        fig.savefig(out_path, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    return out_path


def _render_preview_figure(
    spec: ScenarioSpec,
    *,
    display_orientation: str,
    presentation_style: str,
) -> tuple[object, object, object | None]:
    fig, ax, legend_ax = _build_preview_figure(presentation_style)
    if spec.layout is not None:
        xlim, ylim = _layout_plot_limits(spec.layout)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
    else:
        ax.set_xlim(-8, 62)
        ax.set_ylim(-13, 13)
    ax.axis("off")

    road_surface_style = _road_surface_style(spec)
    if spec.layout is not None and road_surface_style == "intersection":
        _draw_layout_background(ax)
        _draw_intersection_road_surface(ax, spec)
    elif spec.layout is not None and spec.layout.road_bands:
        _draw_layout_background(ax)
        show_band_labels = presentation_style == "annotated" and display_orientation == "semantic_canonical"
        _draw_layout_road_bands(ax, spec.layout, show_labels=show_band_labels)
    else:
        _draw_background(ax)
        _draw_road(ax)
    show_scene_labels = presentation_style == "annotated"
    _draw_actors(ax, spec, show_labels=show_scene_labels)
    _draw_scenario_marks(ax, spec, show_labels=show_scene_labels)
    if presentation_style == "clean_split":
        assert legend_ax is not None
        _draw_clean_split_legend(legend_ax, spec, display_orientation)
    else:
        if spec.layout is not None and spec.layout.road_bands and display_orientation == "esmini_top_camera_raw":
            _draw_road_context_legend(ax, spec.layout, display_orientation)
        _draw_legend(ax)
        _draw_title(ax, spec)
    _apply_display_orientation(ax, display_orientation)
    return fig, ax, legend_ax


def _build_preview_figure(
    presentation_style: str,
) -> tuple[object, object, object | None]:
    if presentation_style == "clean_split":
        fig = plt.figure(figsize=(9.6, 5.4), dpi=140)
        grid = fig.add_gridspec(
            2,
            1,
            height_ratios=(0.72, 0.28),
            hspace=0.02,
            left=0,
            right=1,
            top=1,
            bottom=0,
        )
        scene_ax = fig.add_subplot(grid[0])
        legend_ax = fig.add_subplot(grid[1])
        legend_ax.set_facecolor("#f6f8f5")
        legend_ax.set_xlim(0, 1)
        legend_ax.set_ylim(0, 1)
        legend_ax.axis("off")
        return fig, scene_ax, legend_ax
    fig, scene_ax = plt.subplots(figsize=(8.8, 5.4), dpi=140)
    return fig, scene_ax, None


def _apply_display_orientation(ax: object, display_orientation: str) -> None:
    if display_orientation == "esmini_top_camera_raw":
        ax.invert_xaxis()
        ax.invert_yaxis()


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


def _road_surface_style(spec: ScenarioSpec) -> str:
    preview_surface_kind = road_preview_surface_kind(_road_asset_id(spec))
    if preview_surface_kind == "intersection_cross":
        return "intersection"
    if preview_surface_kind == "road_bands" and spec.layout is not None and spec.layout.road_bands:
        return "road_bands"
    if spec.layout is not None and spec.layout.road_bands:
        return "road_bands"
    return "legacy"


def _road_asset_id(spec: ScenarioSpec) -> str | None:
    value = spec.metadata.get("road_asset_id")
    if isinstance(value, str) and value:
        return value
    return None


def _draw_intersection_road_surface(ax: object, spec: ScenarioSpec) -> None:
    assert spec.layout is not None
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    road_y_min, road_y_max = _main_road_y_bounds(spec.layout)
    cross_x = _intersection_cross_x(spec)
    cross_width = max(road_y_max - road_y_min, 5.6)
    road_color = "#b8bec3"
    edge_color = "#eef2f7"

    ax.add_patch(
        Rectangle(
            (x0, road_y_min),
            x1 - x0,
            road_y_max - road_y_min,
            facecolor=road_color,
            edgecolor="none",
            zorder=1,
        )
    )
    ax.add_patch(
        Rectangle(
            (cross_x - cross_width / 2, y0),
            cross_width,
            y1 - y0,
            facecolor=road_color,
            edgecolor="none",
            zorder=1.1,
        )
    )
    ax.plot([x0, x1], [0, 0], color=edge_color, linewidth=1.2, alpha=0.8, zorder=2)
    ax.plot([cross_x, cross_x], [y0, y1], color=edge_color, linewidth=1.2, alpha=0.8, zorder=2)
    ax.plot([x0, x1], [road_y_min, road_y_min], color=edge_color, linewidth=1.0, alpha=0.9, zorder=2)
    ax.plot([x0, x1], [road_y_max, road_y_max], color=edge_color, linewidth=1.0, alpha=0.9, zorder=2)
    ax.plot(
        [cross_x - cross_width / 2, cross_x - cross_width / 2],
        [y0, y1],
        color=edge_color,
        linewidth=1.0,
        alpha=0.9,
        zorder=2,
    )
    ax.plot(
        [cross_x + cross_width / 2, cross_x + cross_width / 2],
        [y0, y1],
        color=edge_color,
        linewidth=1.0,
        alpha=0.9,
        zorder=2,
    )


def _main_road_y_bounds(layout: LayoutSpec) -> tuple[float, float]:
    driving_bands = [band for band in layout.road_bands if band.kind == "driving_lane"]
    if driving_bands:
        return min(band.y_min_m for band in driving_bands), max(band.y_max_m for band in driving_bands)
    return -3.5, 3.5


def _intersection_cross_x(spec: ScenarioSpec) -> float:
    layout = spec.layout
    if layout is None:
        return 0.0
    conflict = layout.points.get("conflict_point")
    if conflict is not None:
        return conflict.x_m
    for name, path in layout.paths.items():
        if name != "ego_path" and path.points:
            return path.points[0].x_m
    return 0.0


def _draw_layout_road_bands(ax: object, layout: LayoutSpec, *, show_labels: bool = True) -> None:
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
        if show_labels:
            ax.text(
                x0 + 1.3,
                (band.y_min_m + band.y_max_m) / 2,
                band.id.replace("_", " "),
                fontsize=7.4,
                color="#334155",
                va="center",
                zorder=3,
            )
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


def _road_context_items(layout: LayoutSpec, display_orientation: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (band.id.replace("_", " "), _road_band_color(band))
        for band in _displayed_road_band_order(layout, display_orientation)
    )


def _displayed_road_band_order(layout: LayoutSpec, display_orientation: str) -> tuple[RoadBandSpec, ...]:
    bands = tuple(sorted(layout.road_bands, key=lambda band: band.y_min_m))
    if display_orientation == "semantic_canonical":
        return tuple(reversed(bands))
    return bands


def _draw_road_context_legend(ax: object, layout: LayoutSpec, display_orientation: str) -> None:
    items = _road_context_items(layout, display_orientation)
    if not items:
        return
    ax.text(0.04, 0.145, "Road context", fontsize=7.8, color="#334155", weight="bold", va="center", transform=ax.transAxes)
    for index, (label, color) in enumerate(items):
        row = index // 3
        col = index % 3
        x = 0.18 + col * 0.26
        y = 0.145 - row * 0.045
        ax.add_patch(
            Rectangle(
                (x, y - 0.015),
                0.014,
                0.03,
                facecolor=color,
                edgecolor="#334155",
                linewidth=0.35,
                transform=ax.transAxes,
                clip_on=False,
                zorder=20,
            )
        )
        ax.text(x + 0.019, y, label, fontsize=7.2, color="#334155", va="center", transform=ax.transAxes, zorder=20)


def _draw_actors(ax: object, spec: ScenarioSpec, *, show_labels: bool = True) -> None:
    if spec.layout is not None:
        _draw_layout_actors(ax, spec, show_labels=show_labels)
        return
    ego = spec.actor_by_role("ego")
    occluder = spec.actor_by_role("occluder")
    pedestrian = spec.actor_by_role("crossing_actor")
    if ego is not None:
        _vehicle(
            ax,
            x=6,
            y=-3.25,
            width=9.5,
            height=3.4,
            color="#151515",
            label="EGO" if show_labels else None,
            show_detail=show_labels,
        )
        ax.add_patch(FancyArrow(16.2, -3.25, 7.2, 0, width=0.12, head_width=0.95, head_length=1.4, color="#f8fafc"))
    if occluder is not None:
        _vehicle(
            ax,
            x=33,
            y=3.25,
            width=12,
            height=3.6,
            color="#2563eb",
            label="VAN" if show_labels else None,
            show_detail=show_labels,
        )
    if pedestrian is not None:
        ax.scatter([35], [-8.2], s=70, color="#f97316", edgecolor="#dc2626", linewidth=1.2, zorder=7)
        if show_labels:
            ax.text(36.1, -8.3, "pedestrian", fontsize=8.5, color="#7f1d1d", va="center")


def _draw_scenario_marks(ax: object, spec: ScenarioSpec, *, show_labels: bool = True) -> None:
    if spec.layout is not None:
        _draw_layout_scenario_marks(ax, spec, show_labels=show_labels)
        return
    pedestrian = spec.actor_by_role("crossing_actor")
    trigger_x = min(31, max(17, 6 + spec.trigger.distance_m * 0.55))
    conflict_x = 35 if pedestrian is not None else trigger_x
    if pedestrian is not None:
        if show_labels:
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
            ax.plot([35, conflict_x], [-8.0, 0.8], color="#ef4444", linewidth=2.0, linestyle=(0, (4, 4)), zorder=4)
    else:
        ax.plot([conflict_x, conflict_x], [-8, 2], color="#ef4444", linewidth=2, linestyle=(0, (4, 4)), alpha=0.35)

    ax.scatter([trigger_x], [-3.25], s=82, color="#7c3aed", edgecolor="white", linewidth=1.3, zorder=8)
    if show_labels:
        ax.text(trigger_x + 0.9, -4.35, "trigger", fontsize=8.5, color="#3b0764", va="top")
    ax.scatter([conflict_x], [0.8], s=92, color="#f59e0b", edgecolor="white", linewidth=1.3, zorder=8)
    if show_labels:
        ax.text(conflict_x + 1.0, 0.15, "conflict point", fontsize=8.5, color="#78350f", va="top")


def _draw_layout_actors(ax: object, spec: ScenarioSpec, *, show_labels: bool = True) -> None:
    assert spec.layout is not None
    for actor in spec.actors:
        pose = _layout_pose(spec.layout, actor.id)
        if pose is None:
            continue
        footprint = _layout_footprint(spec.layout, actor.id)
        color = _actor_color(actor.id, actor.role, actor.type)
        label = _actor_scene_label(actor.id) if show_labels else None
        if actor.type == "pedestrian":
            ax.add_patch(
                Rectangle(
                    (pose.x_m - footprint.length_m / 2, pose.y_m - footprint.width_m / 2),
                    footprint.length_m,
                    footprint.width_m,
                    facecolor=color,
                    edgecolor="#dc2626",
                    linewidth=1.2,
                    zorder=7,
                )
            )
            ax.scatter([pose.x_m], [pose.y_m], s=24, color="#fed7aa", edgecolor="#dc2626", linewidth=0.8, zorder=8)
            if show_labels:
                ax.text(pose.x_m + 0.9, pose.y_m + 0.45, label or actor.id, fontsize=8.5, color="#7f1d1d", va="center")
            continue
        _vehicle(
            ax,
            x=pose.x_m,
            y=pose.y_m,
            width=footprint.length_m,
            height=footprint.width_m,
            color=color,
            label=label,
            show_detail=show_labels,
        )
        if actor.initial_speed_kph is not None and actor.initial_speed_kph > 0:
            _direction_arrow(ax, pose, color="#f8fafc")


def _draw_layout_scenario_marks(ax: object, spec: ScenarioSpec, *, show_labels: bool = True) -> None:
    assert spec.layout is not None
    for path_name, path in spec.layout.paths.items():
        if len(path.points) < 2:
            continue
        color = _path_color(path_name)
        linestyle = "-" if path_name == "ego_path" else (0, (4, 4))
        if show_labels and path_name != "ego_path":
            start = path.points[0]
            end = path.points[-1]
            ax.add_patch(
                FancyArrowPatch(
                    (start.x_m, start.y_m),
                    (end.x_m, end.y_m),
                    connectionstyle="arc3,rad=-0.04",
                    arrowstyle="-|>",
                    mutation_scale=12,
                    linewidth=2.0,
                    linestyle=linestyle,
                    color=color,
                    zorder=6,
                )
            )
        else:
            ax.plot(
                [point.x_m for point in path.points],
                [point.y_m for point in path.points],
                color=color,
                linewidth=2.0 if path_name != "ego_path" else 1.2,
                linestyle=linestyle,
                alpha=0.95 if path_name != "ego_path" else 0.7,
                zorder=4,
            )
    for point_name, point in spec.layout.points.items():
        marker = "D" if point_name == "trigger_point" else "o"
        color = "#7c3aed" if point_name == "trigger_point" else "#f59e0b"
        facecolor = color if point_name == "trigger_point" else ("none" if show_labels else _layout_point_background(spec.layout, point))
        ax.scatter(
            [point.x_m],
            [point.y_m],
            s=82 if point_name == "trigger_point" else 92,
            marker=marker,
            facecolor=facecolor,
            edgecolor="white" if point_name == "trigger_point" else "#f59e0b",
            linewidth=1.3 if point_name == "trigger_point" else 2.0,
            zorder=9,
        )
        if show_labels:
            label = "trigger" if point_name == "trigger_point" else point_name.replace("_", " ")
            text_color = "#3b0764" if point_name == "trigger_point" else "#78350f"
            ax.text(point.x_m + 0.9, point.y_m - 0.85, label, fontsize=8.5, color=text_color, va="top")


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


def _layout_point_background(layout: LayoutSpec, point: Point2D) -> str:
    for band in layout.road_bands:
        if band.y_min_m <= point.y_m <= band.y_max_m:
            return _road_band_color(band)
    return "#e8f1e6"


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


def _actor_color(actor_id: str, role: str, actor_type: str) -> str:
    if role == "ego" or actor_id == "ego":
        return "#151515"
    if actor_id == "parked_van" or actor_type == "van":
        return "#2563eb"
    if actor_type == "pedestrian":
        return "#f97316"
    if role == "lead_vehicle":
        return "#d9d6c8"
    if role == "cut_in_actor" or actor_id == "cut_in_vehicle":
        return "#ef4444"
    if role == "crossing_vehicle":
        return "#0ea5e9"
    if role == "oncoming_vehicle":
        return "#f97316"
    return "#64748b"


def _actor_scene_label(actor_id: str) -> str:
    if actor_id == "ego":
        return "EGO"
    if actor_id == "parked_van":
        return "VAN"
    return actor_id.replace("_", " ")


def _path_color(path_name: str) -> str:
    if path_name == "ego_path":
        return "#f8fafc"
    if path_name == "pedestrian_crossing_path":
        return "#ef4444"
    if "cut_in" in path_name:
        return "#ef4444"
    if "crossing" in path_name:
        return "#0ea5e9"
    if "turn" in path_name:
        return "#f97316"
    if "lead" in path_name:
        return "#d9d6c8"
    return "#64748b"


def _actor_legend_items(spec: ScenarioSpec) -> tuple[tuple[str, str, str], ...]:
    if spec.layout is None:
        return (
            ("ego vehicle", "#151515", "swatch"),
            ("parked van", "#2563eb", "swatch"),
            ("pedestrian", "#f97316", "circle"),
        )
    return tuple(
        (
            actor.id.replace("_", " "),
            _actor_color(actor.id, actor.role, actor.type),
            "circle" if actor.type == "pedestrian" else "swatch",
        )
        for actor in spec.actors
        if actor.id in spec.layout.actor_poses
    )


def _scenario_geometry_items(spec: ScenarioSpec) -> tuple[tuple[str, str, str], ...]:
    if spec.layout is None:
        return (
            ("pedestrian crossing path", "#ef4444", "dashed_line"),
            ("trigger point", "#7c3aed", "diamond"),
            ("conflict point", "#f59e0b", "ring"),
        )
    items: list[tuple[str, str, str]] = []
    for path_name in spec.layout.paths:
        items.append(
            (
                path_name.replace("_", " "),
                _path_color(path_name),
                "line" if path_name == "ego_path" else "dashed_line",
            )
        )
    for point_name in spec.layout.points:
        items.append(
            (
                point_name.replace("_", " "),
                "#7c3aed" if point_name == "trigger_point" else "#f59e0b",
                "diamond" if point_name == "trigger_point" else "ring",
            )
        )
    return tuple(items)


def _draw_legend(ax: object) -> None:
    items = [
        ("#151515", "Ego vehicle"),
        ("#2563eb", "Parked van"),
        ("#f97316", "Pedestrian"),
        ("#7c3aed", "Trigger/conflict point"),
    ]
    x = 0.04
    y = 0.06
    for color, label in items:
        ax.add_patch(
            Rectangle(
                (x, y - 0.018),
                0.016,
                0.04,
                facecolor=color,
                edgecolor="#0f172a",
                linewidth=0.4,
                transform=ax.transAxes,
                clip_on=False,
            )
        )
        ax.text(x + 0.022, y, label, fontsize=8.8, color="#0f172a", va="center", transform=ax.transAxes)
        x += 0.19 if label != "Trigger/conflict point" else 0.23


def _clean_legend_groups(
    spec: ScenarioSpec,
    display_orientation: str,
) -> tuple[tuple[str, tuple[tuple[str, str, str], ...]], ...]:
    if spec.layout is not None and spec.layout.road_bands:
        road_items = tuple(
            (label, color, "swatch")
            for label, color in _road_context_items(spec.layout, display_orientation)
        )
    else:
        road_items = (
            ("road surface", "#b8bec3", "swatch"),
            ("lane boundary", "#eef2f7", "line"),
        )
    return (
        ("Road", road_items),
        ("Actors", _actor_legend_items(spec)),
        ("Scenario Geometry", _scenario_geometry_items(spec)),
    )


def _draw_clean_split_legend(ax: object, spec: ScenarioSpec, display_orientation: str) -> None:
    groups = _clean_legend_groups(spec, display_orientation)
    positions = {
        "Road": (0.018, 0.0, 0.49, 1.0),
        "Actors": (0.525, 0.0, 0.19, 1.0),
        "Scenario Geometry": (0.73, 0.0, 0.252, 1.0),
    }
    for title, items in groups:
        group_ax = ax.inset_axes(positions[title], transform=ax.transAxes)
        group_ax.set_label(f"clean-legend:{title}")
        group_ax.set_xlim(0, 1)
        group_ax.set_ylim(0, 1)
        group_ax.axis("off")
        group_ax.text(0, 0.88, title, fontsize=8.2, weight="bold", color="#334155", va="top", transform=group_ax.transAxes)
        columns = 2 if title == "Road" and len(items) > 3 else 1
        rows = math.ceil(len(items) / columns)
        col_width = 1 / columns
        row_step = min(0.24, 0.56 / max(rows - 1, 1))
        for index, (label, color, symbol) in enumerate(items):
            column = index // rows
            row = index % rows
            x = column * col_width
            y = 0.65 - row * row_step
            _draw_clean_legend_symbol(group_ax, x, y, color, symbol)
            group_ax.text(
                x + 0.075,
                y,
                label,
                fontsize=7.1,
                color="#334155",
                va="center",
                transform=group_ax.transAxes,
                clip_on=True,
            )


def _draw_clean_legend_symbol(ax: object, x: float, y: float, color: str, symbol: str) -> None:
    if symbol in {"swatch", "circle"}:
        ax.add_patch(
            Rectangle(
                (x, y - 0.045),
                0.055,
                0.09,
                facecolor=color,
                edgecolor="#334155",
                linewidth=0.45,
                transform=ax.transAxes,
                clip_on=False,
            )
        )
        return
    if symbol in {"line", "dashed_line"}:
        ax.add_line(
            Line2D(
                [x, x + 0.065],
                [y, y],
                color=color,
                linewidth=2.0,
                linestyle="--" if symbol == "dashed_line" else "-",
                transform=ax.transAxes,
            )
        )
        return
    marker = "D" if symbol == "diamond" else "o"
    ax.scatter(
        [x + 0.0275],
        [y],
        s=30,
        marker=marker,
        facecolor=color if symbol == "diamond" else "none",
        edgecolor="#f59e0b" if symbol == "ring" else "white",
        linewidth=1.2,
        transform=ax.transAxes,
        clip_on=False,
        zorder=5,
    )


def _draw_title(ax: object, spec: ScenarioSpec) -> None:
    ttc = estimate_ttc_s(spec)
    ttc_label = "n/a" if ttc is None else f"{ttc:.1f} s"
    ax.text(
        0.04,
        0.96,
        f"{spec.scenario_name} | rain: {spec.weather.rain} | est. TTC: {ttc_label}",
        fontsize=10.5,
        color="#0f172a",
        weight="bold",
        va="center",
        transform=ax.transAxes,
    )


def _vehicle(
    ax: object,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str,
    label: str | None,
    *,
    show_detail: bool = True,
) -> None:
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
    if show_detail:
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
    if label:
        ax.text(x, y, label, ha="center", va="center", fontsize=9, color="white", weight="bold", zorder=7)
