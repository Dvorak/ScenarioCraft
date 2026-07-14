from pathlib import Path

from PIL import Image


def test_readme_uses_product_illustration_and_links_d2_technical_flow() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    source_path = Path("docs/diagrams/scenariocraft-architecture.d2")
    png_path = Path("docs/diagrams/scenariocraft-architecture.png")

    assert "![ScenarioCraft architecture](docs/diagrams/scenariocraft-architecture.png)" in readme
    assert "docs/diagrams/scenariocraft-architecture.d2" in readme
    assert "![ScenarioCraft architecture](docs/assets/" not in readme
    assert "scenario-production-loop.mmd" not in readme
    assert "conceptual overview" in readme

    source = source_path.read_text(encoding="utf-8")
    for label in (
        "LLM Intent Provider",
        "Evidence Gate",
        "Variant Request",
        "PatchSpec",
        "Reject / Clarify",
    ):
        assert label in source
    assert "→ PatchSpec → ScenarioSpec" in source
    assert "→ new candidate → Intent" in source

    with Image.open(png_path) as image:
        assert image.format == "PNG"
        assert image.width >= 1200
        assert 2.0 <= image.width / image.height <= 2.8


def test_readme_embeds_an_optimized_animated_web_walkthrough() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    gif_path = Path("docs/assets/scenariocraft-web-demo.gif")

    assert (
        "![ScenarioCraft Web walkthrough showing Demo and Local LLM workflows]"
        "(docs/assets/scenariocraft-web-demo.gif)"
    ) in readme
    assert gif_path.stat().st_size < 2_000_000

    with Image.open(gif_path) as image:
        assert image.format == "GIF"
        assert image.is_animated
        assert image.n_frames >= 5
        assert image.size == (1152, 720)
        total_duration_ms = 0
        for frame_index in range(image.n_frames):
            image.seek(frame_index)
            total_duration_ms += image.info["duration"]
        assert 10_000 <= total_duration_ms <= 20_000
