from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.tools import estimate_ttc_s, generate_2d_preview


def test_generate_2d_preview_writes_non_empty_png(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")
    preview_path = generate_2d_preview(spec, tmp_path / "preview_2d.png")

    assert preview_path.exists()
    assert preview_path.stat().st_size > 0
    assert preview_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_estimate_ttc_from_trigger_distance_and_ego_speed() -> None:
    spec = MockScenarioGenerator().generate_spec("rainy pedestrian occlusion")

    assert estimate_ttc_s(spec) == spec.trigger.distance_m / (35 / 3.6)
