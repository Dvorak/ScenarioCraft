from dataclasses import replace
from pathlib import Path

import pytest

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.rendering import estimate_ttc_s, generate_2d_preview
from scenariocraft.rendering.preview_2d import (
    CLEAN_PREVIEW_ASPECT_RATIO,
    _apply_display_orientation,
    _clean_legend_groups,
    _road_context_items,
    _layout_footprint,
    _layout_path,
    _layout_plot_limits,
    _layout_pose,
    _layout_point,
    _render_preview_figure,
)


def test_generate_2d_preview_writes_non_empty_png(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    preview_path = generate_2d_preview(spec, tmp_path / "preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_clean_split_preview_has_separate_unannotated_scene_and_grouped_legend() -> None:
    from matplotlib import pyplot as plt

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    fig, scene_ax, legend_ax = _render_preview_figure(
        spec,
        display_orientation="esmini_top_camera_raw",
        presentation_style="clean_split",
    )

    assert legend_ax is not None
    assert [text.get_text() for text in scene_ax.texts] == []
    group_axes = list(legend_ax.child_axes)
    legend_text = [text.get_text() for axis in group_axes for text in axis.texts]
    assert [axis.get_label() for axis in group_axes] == [
        "clean-legend:Road",
        "clean-legend:Actors",
        "clean-legend:Scenario Geometry",
    ]
    assert {"Road", "Actors", "Scenario Geometry"}.issubset(legend_text)
    assert "trigger point" in legend_text
    assert "conflict point" in legend_text
    assert "Trigger/conflict point" not in legend_text
    assert scene_ax.patches
    assert scene_ax.collections
    scene_height = scene_ax.get_position().height
    legend_height = legend_ax.get_position().height
    assert scene_height > legend_height * 2
    plt.close(fig)


def test_clean_split_legend_contract_has_three_groups_and_distinct_geometry_symbols() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    groups = _clean_legend_groups(spec, "esmini_top_camera_raw")

    assert [title for title, _items in groups] == ["Road", "Actors", "Scenario Geometry"]
    geometry = {label: symbol for label, _color, symbol in groups[2][1]}
    assert geometry == {
        "pedestrian crossing path": "dashed_line",
        "trigger point": "diamond",
        "conflict point": "ring",
    }


def test_clean_split_preview_does_not_repeat_summary_or_scene_labels(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    before = spec.to_json()

    preview_path = generate_2d_preview(
        spec,
        tmp_path / "clean_split.png",
        display_orientation="esmini_top_camera_raw",
        presentation_style="clean_split",
    )

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert spec.to_json() == before
    from matplotlib import pyplot as plt

    image = plt.imread(preview_path)
    assert image.shape[1] / image.shape[0] == pytest.approx(CLEAN_PREVIEW_ASPECT_RATIO, rel=0.002)


def test_clean_split_legend_groups_are_spatially_isolated() -> None:
    from matplotlib import pyplot as plt

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    fig, _scene_ax, legend_ax = _render_preview_figure(
        spec,
        display_orientation="esmini_top_camera_raw",
        presentation_style="clean_split",
    )
    fig.canvas.draw()
    assert legend_ax is not None
    group_axes = list(legend_ax.child_axes)
    group_bounds = [axis.get_window_extent() for axis in group_axes]

    for left, right in zip(group_bounds, group_bounds[1:]):
        assert left.x1 < right.x0
    for axis in group_axes:
        bounds = axis.get_window_extent()
        for text in axis.texts:
            text_bounds = text.get_window_extent(renderer=fig.canvas.get_renderer())
            assert text_bounds.x0 >= bounds.x0
            assert text_bounds.x1 <= bounds.x1
    plt.close(fig)


def test_clean_split_scene_uses_plain_vehicle_silhouettes_and_layered_geometry() -> None:
    from matplotlib import pyplot as plt
    from matplotlib.patches import FancyArrowPatch

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    fig, scene_ax, _legend_ax = _render_preview_figure(
        spec,
        display_orientation="esmini_top_camera_raw",
        presentation_style="clean_split",
    )

    translucent_detail_patches = [patch for patch in scene_ax.patches if patch.get_alpha() == pytest.approx(0.14)]
    assert translucent_detail_patches == []
    assert not any(isinstance(patch, FancyArrowPatch) for patch in scene_ax.patches)
    crossing_lines = [line for line in scene_ax.lines if line.get_color() == "#ef4444"]
    assert len(crossing_lines) == 1
    assert crossing_lines[0].get_zorder() < max(collection.get_zorder() for collection in scene_ax.collections)
    plt.close(fig)


def test_clean_split_preview_supports_layout_free_and_road_band_free_specs(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    variants = (
        replace(spec, layout=None, spatial_relations=()),
        replace(spec, layout=replace(spec.layout, road_bands=())),
    )

    for index, variant in enumerate(variants):
        path = generate_2d_preview(
            variant,
            tmp_path / f"clean_legacy_{index}.png",
            presentation_style="clean_split",
        )
        assert path.exists()
        assert path.stat().st_size > 0


def test_preview_rejects_unknown_presentation_style(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    with pytest.raises(ValueError, match="presentation style"):
        generate_2d_preview(spec, tmp_path / "invalid.png", presentation_style="unknown")


def test_annotated_preview_remains_the_default_presentation() -> None:
    from matplotlib import pyplot as plt

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    fig, scene_ax, legend_ax = _render_preview_figure(
        spec,
        display_orientation="semantic_canonical",
        presentation_style="annotated",
    )

    scene_text = {text.get_text() for text in scene_ax.texts}
    assert legend_ax is None
    assert any(spec.scenario_name in text for text in scene_text)
    assert {"EGO", "VAN", "pedestrian", "trigger", "conflict point"}.issubset(scene_text)
    plt.close(fig)


def test_generate_2d_preview_writes_non_empty_png_for_legacy_spec(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    legacy_spec = replace(spec, layout=None, spatial_relations=())

    preview_path = generate_2d_preview(legacy_spec, tmp_path / "legacy_preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_preview_supports_esmini_top_camera_raw_orientation_without_mutating_spec(tmp_path: Path) -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
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
    import scenariocraft.rendering.preview_2d as preview_2d

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    calls = []

    def record_road_bands(ax, layout, *, show_labels=True):
        calls.append(show_labels)

    monkeypatch.setattr(preview_2d, "_draw_layout_road_bands", record_road_bands)

    generate_2d_preview(spec, tmp_path / "semantic.png", display_orientation="semantic_canonical")
    generate_2d_preview(spec, tmp_path / "raw.png", display_orientation="esmini_top_camera_raw")

    assert calls == [True, False]


def test_road_context_legend_items_follow_raw_display_order() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
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
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    assert spec.layout is not None

    items = _road_context_items(spec.layout, "esmini_top_camera_raw")

    assert len(items) == 6
    assert all(color.startswith("#") for _label, color in items)


def test_actor_legend_is_still_drawn(monkeypatch, tmp_path: Path) -> None:
    import scenariocraft.rendering.preview_2d as preview_2d

    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
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
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
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
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")
    assert spec.layout is not None
    road_band_free_spec = replace(spec, layout=replace(spec.layout, road_bands=()))

    preview_path = generate_2d_preview(road_band_free_spec, tmp_path / "road_band_free_preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_estimate_ttc_from_trigger_distance_and_ego_speed() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    assert estimate_ttc_s(spec) == spec.trigger.distance_m / (35 / 3.6)
