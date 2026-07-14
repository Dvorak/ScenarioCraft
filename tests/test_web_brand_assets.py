from pathlib import Path
from xml.etree import ElementTree

from PIL import Image


WEB_ROOT = Path("web")


def test_web_uses_one_scenariocraft_brand_mark_and_current_product_copy() -> None:
    mark_path = WEB_ROOT / "public" / "scenariocraft-mark.svg"
    header = (WEB_ROOT / "src/components/scenariocraft/AppHeader.tsx").read_text(
        encoding="utf-8"
    )
    root_route = (WEB_ROOT / "src/routes/__root.tsx").read_text(encoding="utf-8")

    assert mark_path.is_file()
    root = ElementTree.parse(mark_path).getroot()
    assert root.attrib["viewBox"] == "0 0 64 64"

    svg = mark_path.read_text(encoding="utf-8")
    assert "#171717" in svg
    assert "#FF5A5F" in svg
    assert "<linearGradient" not in svg
    assert "<radialGradient" not in svg

    assert 'src="/scenariocraft-mark.svg"' in header
    assert "GENERATE · VALIDATE · ITERATE" in header
    assert "Scenario authoring" not in header

    assert 'href: "/scenariocraft-mark.svg"' in root_route
    assert 'type: "image/svg+xml"' in root_route
    assert 'href: "/favicon.ico"' in root_route
    assert "ScenarioCraft — Generate, validate & iterate" in root_route
    assert "Scenario authoring & validation" not in root_route


def test_favicon_contains_small_and_retina_sizes() -> None:
    with Image.open(WEB_ROOT / "public" / "favicon.ico") as favicon:
        assert favicon.format == "ICO"
        assert {(16, 16), (32, 32), (64, 64), (256, 256)} <= favicon.ico.sizes()
