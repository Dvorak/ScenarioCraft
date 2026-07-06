from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.roads import (
    MULTI_LANE_SAME_DIRECTION_FILENAME,
    MULTI_LANE_SAME_DIRECTION_LANES,
    generate_multi_lane_same_direction_xodr,
)


def test_multilane_road_generator_emits_valid_xodr() -> None:
    xodr = generate_multi_lane_same_direction_xodr()

    assert xodr.strip()
    root = ET.fromstring(xodr)
    assert root.tag == "OpenDRIVE"
    assert root.find("./road/planView/geometry/line") is not None
    assert float(root.find("./road").attrib["length"]) >= 100.0


def test_checked_in_multilane_road_matches_deterministic_generator() -> None:
    fixture_path = Path("assets/roads/canonical") / MULTI_LANE_SAME_DIRECTION_FILENAME

    assert fixture_path.exists()
    assert _normalized_xml(fixture_path.read_text(encoding="utf-8")) == _normalized_xml(
        generate_multi_lane_same_direction_xodr()
    )


def test_multilane_road_documents_cut_in_lane_semantics() -> None:
    lanes = {lane.layout_band: lane for lane in MULTI_LANE_SAME_DIRECTION_LANES}

    assert lanes["ego_driving_lane"].lane_type == "driving"
    assert lanes["ego_driving_lane"].y_min_m == -1.75
    assert lanes["ego_driving_lane"].y_max_m == 1.75
    assert lanes["adjacent_same_direction_lane"].lane_type == "driving"
    assert lanes["adjacent_same_direction_lane"].y_min_m == 1.75
    assert lanes["adjacent_same_direction_lane"].y_max_m == 5.25


def _normalized_xml(raw: str) -> bytes:
    return ET.tostring(ET.fromstring(raw), encoding="utf-8")
