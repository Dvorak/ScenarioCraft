from xml.etree import ElementTree as ET

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.tools import FallbackXmlScenarioBuilder, build_openscenario


def test_scenario_builder_creates_xosc_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path)

    assert result.xosc_path.exists()
    assert result.builder == "scenariogeneration"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"
    assert root.find(".//ScenarioObject[@name='ego']") is not None
    assert root.find(".//ScenarioObject[@name='pedestrian']") is not None


def test_fallback_scenario_builder_creates_xosc_file(tmp_path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario")

    result = build_openscenario(spec, tmp_path, builder=FallbackXmlScenarioBuilder())

    assert result.xosc_path.exists()
    assert result.builder == "fallback_xml"
    root = ET.parse(result.xosc_path).getroot()
    assert root.tag == "OpenSCENARIO"
