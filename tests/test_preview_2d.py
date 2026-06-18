from dataclasses import replace
from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.tools import estimate_ttc_s, generate_2d_preview
from scenariocraft.tools.preview_2d import _layout_footprint, _layout_path, _layout_plot_limits, _layout_pose, _layout_point


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


def test_preview_uses_layout_backed_geometry_helpers() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    assert spec.layout is not None

    assert _layout_pose(spec.layout, "parked_van").x_m == 20.0
    assert _layout_pose(spec.layout, "parked_van").y_m == 3.25
    assert _layout_footprint(spec.layout, "parked_van").length_m == 5.3
    assert _layout_path(spec.layout, "pedestrian_crossing_path").points[0].y_m == 4.60
    assert _layout_point(spec.layout, "trigger_point").x_m == 7.0
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
