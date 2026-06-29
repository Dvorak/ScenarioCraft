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

from scenariocraft_core.schemas import FootprintSpec, LayoutSpec, PathSpec, Point2D, Pose2D, RoadBandSpec, ScenarioSpec

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

    if spec.layout is not None and spec.layout.road_bands:
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
    ego = spec.actor_by_role("ego")
    occluder = spec.actor_by_role("occluder")
    pedestrian = spec.actor_by_role("crossing_actor")
    ego_pose = _layout_pose(spec.layout, ego.id if ego else "ego")
    van_pose = _layout_pose(spec.layout, occluder.id if occluder else "parked_van")
    pedestrian_pose = _layout_pose(spec.layout, pedestrian.id if pedestrian else "pedestrian")

    if ego is not None and ego_pose is not None:
        footprint = _layout_footprint(spec.layout, ego.id)
        _vehicle(
            ax,
            x=ego_pose.x_m,
            y=ego_pose.y_m,
            width=footprint.length_m,
            height=footprint.width_m,
            color="#151515",
            label="EGO" if show_labels else None,
            show_detail=show_labels,
        )
        _direction_arrow(ax, ego_pose, color="#f8fafc")
    if occluder is not None and van_pose is not None:
        footprint = _layout_footprint(spec.layout, occluder.id)
        _vehicle(
            ax,
            x=van_pose.x_m,
            y=van_pose.y_m,
            width=footprint.length_m,
            height=footprint.width_m,
            color="#2563eb",
            label="VAN" if show_labels else None,
            show_detail=show_labels,
        )
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
        if show_labels:
            ax.text(pedestrian_pose.x_m + 0.9, pedestrian_pose.y_m + 0.45, "pedestrian", fontsize=8.5, color="#7f1d1d", va="center")


def _draw_layout_scenario_marks(ax: object, spec: ScenarioSpec, *, show_labels: bool = True) -> None:
    assert spec.layout is not None
    crossing_path = _layout_path(spec.layout, "pedestrian_crossing_path")
    trigger_point = _layout_point(spec.layout, "trigger_point")
    conflict_point = _layout_point(spec.layout, "conflict_point")
    if crossing_path is not None and len(crossing_path.points) >= 2:
        start = crossing_path.points[0]
        end = crossing_path.points[-1]
        if show_labels:
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
        else:
            ax.plot(
                [point.x_m for point in crossing_path.points],
                [point.y_m for point in crossing_path.points],
                color="#ef4444",
                linewidth=2.0,
                linestyle=(0, (4, 4)),
                zorder=4,
            )
    if trigger_point is not None:
        ax.scatter([trigger_point.x_m], [trigger_point.y_m], s=82, color="#7c3aed", edgecolor="white", linewidth=1.3, marker="D", zorder=8)
        if show_labels:
            ax.text(trigger_point.x_m + 0.9, trigger_point.y_m - 1.1, "trigger", fontsize=8.5, color="#3b0764", va="top")
    if conflict_point is not None:
        facecolor = "none" if show_labels else _layout_point_background(spec.layout, conflict_point)
        ax.scatter(
            [conflict_point.x_m],
            [conflict_point.y_m],
            s=92,
            facecolor=facecolor,
            edgecolor="#f59e0b",
            linewidth=2.0,
            zorder=9,
        )
        if show_labels:
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
        (
            "Actors",
            (
                ("ego vehicle", "#151515", "swatch"),
                ("parked van", "#2563eb", "swatch"),
                ("pedestrian", "#f97316", "circle"),
            ),
        ),
        (
            "Scenario Geometry",
            (
                ("pedestrian crossing path", "#ef4444", "dashed_line"),
                ("trigger point", "#7c3aed", "diamond"),
                ("conflict point", "#f59e0b", "ring"),
            ),
        ),
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
        for index, (label, color, symbol) in enumerate(items):
            column = index // rows
            row = index % rows
            x = column * col_width
            y = 0.65 - row * 0.24
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
