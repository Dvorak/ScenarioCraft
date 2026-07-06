from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft.core.roads import (
    URBAN_FOUR_WAY_INTERSECTION_FILENAME,
    generate_urban_four_way_intersection_xodr,
    write_urban_four_way_intersection_xodr,
)


def test_urban_four_way_intersection_xodr_contains_crossing_roads() -> None:
    root = ET.fromstring(generate_urban_four_way_intersection_xodr())

    roads = root.findall("./road")

    assert root.tag == "OpenDRIVE"
    assert len(roads) == 2
    assert {road.attrib["name"] for road in roads} == {"east_west_main", "north_south_cross"}


def test_urban_four_way_intersection_can_center_cross_road_at_conflict_point() -> None:
    root = ET.fromstring(generate_urban_four_way_intersection_xodr(intersection_center_x=25.0))
    roads = {road.attrib["name"]: road for road in root.findall("./road")}
    cross_geometry = roads["north_south_cross"].find("./planView/geometry")

    assert cross_geometry is not None
    assert float(cross_geometry.attrib["x"]) == 25.0
    assert float(cross_geometry.attrib["y"]) == -50.0


def test_urban_four_way_intersection_xodr_contains_junction_connections_and_lane_links() -> None:
    root = ET.fromstring(generate_urban_four_way_intersection_xodr(intersection_center_x=25.0))

    junction = root.find("./junction")
    assert junction is not None
    assert junction.attrib["name"] == "urban_four_way_intersection_junction"
    assert junction.attrib["id"] == "1"
    connections = junction.findall("./connection")
    assert {connection.attrib["id"] for connection in connections} == {
        "west_to_east_straight",
        "south_to_north_straight",
        "east_to_west_oncoming",
        "oncoming_turn_across_path",
    }
    for connection in connections:
        lane_links = connection.findall("./laneLink")
        assert lane_links
        assert all(link.attrib["from"] and link.attrib["to"] for link in lane_links)


def test_urban_four_way_intersection_roads_participate_in_junction() -> None:
    root = ET.fromstring(generate_urban_four_way_intersection_xodr(intersection_center_x=25.0))
    roads = {road.attrib["name"]: road for road in root.findall("./road")}

    assert roads["east_west_main"].attrib["junction"] == "1"
    assert roads["north_south_cross"].attrib["junction"] == "1"


def test_write_urban_four_way_intersection_xodr_uses_canonical_filename(tmp_path: Path) -> None:
    path = write_urban_four_way_intersection_xodr(tmp_path / URBAN_FOUR_WAY_INTERSECTION_FILENAME)

    assert path == tmp_path / URBAN_FOUR_WAY_INTERSECTION_FILENAME
    assert path.exists()
    assert ET.parse(path).getroot().tag == "OpenDRIVE"


def test_checked_in_intersection_road_matches_deterministic_default_generator() -> None:
    fixture_path = Path("assets/roads/canonical") / URBAN_FOUR_WAY_INTERSECTION_FILENAME

    assert fixture_path.exists()
    assert _normalized_xml(fixture_path.read_text(encoding="utf-8")) == _normalized_xml(
        generate_urban_four_way_intersection_xodr()
    )


def _normalized_xml(raw: str) -> bytes:
    return ET.tostring(ET.fromstring(raw), encoding="utf-8")
