from pathlib import Path

from PIL import Image


def test_readme_uses_product_illustration_and_links_d2_technical_flow() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    source_path = Path("docs/diagrams/scenariocraft-architecture.d2")
    png_path = Path("docs/diagrams/scenariocraft-architecture.png")

    assert "![ScenarioCraft architecture](docs/diagrams/scenariocraft-architecture.png)" in readme
    assert "docs/diagrams/scenariocraft-architecture.d2" in readme
    assert "docs/assets/" not in readme
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
