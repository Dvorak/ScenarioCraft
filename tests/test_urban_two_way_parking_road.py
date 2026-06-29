from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft_core.roads import (
    URBAN_TWO_WAY_PARKING_FILENAME,
    URBAN_TWO_WAY_PARKING_LANES,
    canonical_urban_two_way_parking_asset_path,
    generate_urban_two_way_parking_xodr,
)


def test_canonical_road_generator_emits_non_empty_valid_xodr() -> None:
    xodr = generate_urban_two_way_parking_xodr()

    assert xodr.strip()
    root = ET.fromstring(xodr)
    assert root.tag == "OpenDRIVE"
    assert root.find("./road/planView/geometry/line") is not None
    assert float(root.find("./road").attrib["length"]) >= 100.0


def test_checked_in_canonical_road_matches_deterministic_generator() -> None:
    fixture_path = canonical_urban_two_way_parking_asset_path()

    assert fixture_path.name == URBAN_TWO_WAY_PARKING_FILENAME
    assert fixture_path.exists()
    assert _normalized_xml(fixture_path.read_text(encoding="utf-8")) == _normalized_xml(generate_urban_two_way_parking_xodr())


def test_canonical_road_documents_lane_sign_and_widths() -> None:
    lanes = {lane.lane_id: lane for lane in URBAN_TWO_WAY_PARKING_LANES}

    assert lanes[2].lane_type == "sidewalk"
    assert lanes[2].width_m == 2.25
    assert lanes[2].y_min_m == 4.25
    assert lanes[2].y_max_m == 6.50
    assert lanes[1].lane_type == "parking"
    assert lanes[1].width_m == 2.50
    assert lanes[-1].lane_type == "driving"
    assert lanes[-1].width_m == 3.50
    assert lanes[-1].y_min_m == -1.75
    assert lanes[-1].y_max_m == 1.75
    assert lanes[-2].lane_type == "median"
    assert lanes[-2].width_m == 0.25
    assert lanes[-3].lane_type == "driving"
    assert lanes[-3].width_m == 3.50
    assert lanes[-4].lane_type == "sidewalk"
    assert lanes[-4].width_m == 2.00


def _normalized_xml(raw: str) -> bytes:
    return ET.tostring(ET.fromstring(raw), encoding="utf-8")
