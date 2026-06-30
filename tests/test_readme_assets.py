from pathlib import Path

from PIL import Image


def test_readme_architecture_asset_is_png() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    png_path = Path("assets/readme/scenariocraft-architecture.png")

    assert "assets/readme/scenariocraft-architecture.png" in readme
    assert png_path.exists()

    with Image.open(png_path) as image:
        assert image.format == "PNG"
        assert image.mode == "RGBA"
        assert image.width >= 1200
        assert image.height >= 600
