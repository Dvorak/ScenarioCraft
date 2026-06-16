from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "scenariocraft-matplotlib"))

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt
from matplotlib.patches import FancyArrow, FancyArrowPatch, Rectangle

from scenariocraft.schemas import ScenarioSpec


def generate_2d_preview(spec: ScenarioSpec, out_path: Path) -> Path:
    """Generate a deterministic top-down preview image for the scenario."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.8, 5.4), dpi=140)
    ax.set_xlim(-8, 62)
    ax.set_ylim(-13, 13)
    ax.axis("off")

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
    ax.add_patch(Rectangle((-8, -13), 70, 26, facecolor="#e8f1e6", edgecolor="none"))
    ax.add_patch(Rectangle((-8, 6.2), 23, 6.8, facecolor="#7aa36f", edgecolor="none", alpha=0.55))
    ax.add_patch(Rectangle((43, 6.2), 19, 6.8, facecolor="#7aa36f", edgecolor="none", alpha=0.55))
    ax.add_patch(Rectangle((15, 6.2), 28, 6.8, facecolor="#c6b59d", edgecolor="none", alpha=0.8))


def _draw_road(ax: object) -> None:
    ax.add_patch(Rectangle((-8, -6.5), 70, 13, facecolor="#b8bec3", edgecolor="none"))
    ax.plot([-8, 62], [0, 0], color="white", linewidth=2.4, linestyle=(0, (9, 7)), alpha=0.95)
    ax.plot([-8, 62], [-6.4, -6.4], color="#eef2f7", linewidth=1.4)
    ax.plot([-8, 62], [6.4, 6.4], color="#eef2f7", linewidth=1.4)
    ax.add_patch(FancyArrow(2, 3.6, 10, 0, width=0.22, head_width=1.3, head_length=2.4, color="white", alpha=0.95))


def _draw_actors(ax: object, spec: ScenarioSpec) -> None:
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


def _draw_legend(ax: object) -> None:
    legend_y = -11.3
    items = [
        ("#151515", "Ego vehicle"),
        ("#2563eb", "Parked van"),
        ("#f97316", "Pedestrian"),
        ("#7c3aed", "Trigger/conflict point"),
    ]
    x = -5.4
    for color, label in items:
        ax.add_patch(Rectangle((x, legend_y - 0.45), 1.1, 0.9, facecolor=color, edgecolor="#0f172a", linewidth=0.4))
        ax.text(x + 1.55, legend_y, label, fontsize=8.8, color="#0f172a", va="center")
        x += 15.2 if label != "Trigger/conflict point" else 18


def _draw_title(ax: object, spec: ScenarioSpec) -> None:
    ttc = estimate_ttc_s(spec)
    ttc_label = "n/a" if ttc is None else f"{ttc:.1f} s"
    ax.text(
        -5.5,
        11.6,
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
