from dataclasses import replace
from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.tools import estimate_ttc_s, generate_2d_preview
from scenariocraft.tools.preview_2d import (
    _apply_display_orientation,
    _road_context_items,
    _layout_footprint,
    _layout_path,
    _layout_plot_limits,
    _layout_pose,
    _layout_point,
)


def test_generate_2d_preview_writes_non_empty_png(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    preview_path = generate_2d_preview(spec, tmp_path / "preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_generate_2d_preview_writes_non_empty_png_for_legacy_spec(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    legacy_spec = replace(spec, layout=None, spatial_relations=())

    preview_path = generate_2d_preview(legacy_spec, tmp_path / "legacy_preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_preview_supports_esmini_top_camera_raw_orientation_without_mutating_spec(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    before_pose = spec.layout.actor_poses["parked_van"]
    semantic_path = generate_2d_preview(
        spec,
        tmp_path / "semantic_preview_2d.png",
        display_orientation="semantic_canonical",
    )
    raw_path = generate_2d_preview(
        spec,
        tmp_path / "raw_oriented_preview_2d.png",
        display_orientation="esmini_top_camera_raw",
    )

    assert semantic_path.exists()
    assert raw_path.exists()
    assert semantic_path.read_bytes() != raw_path.read_bytes()
    assert spec.layout.actor_poses["parked_van"] == before_pose


def test_renderer_aligned_preview_suppresses_in_road_band_labels(monkeypatch, tmp_path: Path) -> None:
    import scenariocraft.tools.preview_2d as preview_2d

    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    calls = []

    def record_road_bands(ax, layout, *, show_labels=True):
        calls.append(show_labels)

    monkeypatch.setattr(preview_2d, "_draw_layout_road_bands", record_road_bands)

    generate_2d_preview(spec, tmp_path / "semantic.png", display_orientation="semantic_canonical")
    generate_2d_preview(spec, tmp_path / "raw.png", display_orientation="esmini_top_camera_raw")

    assert calls == [True, False]


def test_road_context_legend_items_follow_raw_display_order() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None

    labels = [label for label, _color in _road_context_items(spec.layout, "esmini_top_camera_raw")]

    assert labels == [
        "opposing side sidewalk",
        "opposing driving lane",
        "center divider",
        "ego driving lane",
        "ego side parking strip",
        "ego side sidewalk",
    ]


def test_road_context_legend_uses_band_colors() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None

    items = _road_context_items(spec.layout, "esmini_top_camera_raw")

    assert len(items) == 6
    assert all(color.startswith("#") for _label, color in items)


def test_actor_legend_is_still_drawn(monkeypatch, tmp_path: Path) -> None:
    import scenariocraft.tools.preview_2d as preview_2d

    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    called = {"actor_legend": False}

    def record_actor_legend(ax):
        called["actor_legend"] = True

    monkeypatch.setattr(preview_2d, "_draw_legend", record_actor_legend)

    generate_2d_preview(spec, tmp_path / "raw.png", display_orientation="esmini_top_camera_raw")

    assert called["actor_legend"] is True


def test_preview_orientation_helper_reverses_axes_for_raw_esmini_mode() -> None:
    from matplotlib import pyplot as plt

    fig, ax = plt.subplots()
    ax.set_xlim(-1, 30)
    ax.set_ylim(-10, 6)

    _apply_display_orientation(ax, "semantic_canonical")

    assert ax.get_xlim() == (-1.0, 30.0)
    assert ax.get_ylim() == (-10.0, 6.0)

    _apply_display_orientation(ax, "esmini_top_camera_raw")

    assert ax.get_xlim() == (30.0, -1.0)
    assert ax.get_ylim() == (6.0, -10.0)
    plt.close(fig)


def test_preview_uses_layout_backed_geometry_helpers() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None

    assert _layout_pose(spec.layout, "parked_van").x_m == spec.layout.actor_poses["parked_van"].x_m
    assert _layout_pose(spec.layout, "parked_van").y_m == 3.25
    assert _layout_footprint(spec.layout, "parked_van").length_m == 5.3
    assert _layout_path(spec.layout, "pedestrian_crossing_path").points[0].y_m == 4.60
    assert _layout_point(spec.layout, "trigger_point").x_m < _layout_point(spec.layout, "conflict_point").x_m
    xlim, ylim = _layout_plot_limits(spec.layout)
    assert xlim[0] < 0.0 < xlim[1]
    assert ylim[0] < -7.50 < 6.50 < ylim[1]


def test_road_band_free_preview_fallback_writes_non_empty_png(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    road_band_free_spec = replace(spec, layout=replace(spec.layout, road_bands=()))

    preview_path = generate_2d_preview(road_band_free_spec, tmp_path / "road_band_free_preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_estimate_ttc_from_trigger_distance_and_ego_speed() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    assert estimate_ttc_s(spec) == spec.trigger.distance_m / (35 / 3.6)
