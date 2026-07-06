from __future__ import annotations

"""Canonical minimal four-way urban intersection OpenDRIVE road."""

from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET


URBAN_FOUR_WAY_INTERSECTION_FILENAME = "urban_four_way_intersection.xodr"
ROAD_LENGTH_M = 100.0
ROAD_HALF_LENGTH_M = ROAD_LENGTH_M / 2.0
LANE_WIDTH_M = 3.5


def write_urban_four_way_intersection_xodr(
    path: Path,
    *,
    intersection_center_x: float = 0.0,
    intersection_center_y: float = 0.0,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        generate_urban_four_way_intersection_xodr(
            intersection_center_x=intersection_center_x,
            intersection_center_y=intersection_center_y,
        ),
        encoding="utf-8",
    )
    return path


def generate_urban_four_way_intersection_xodr(
    *,
    intersection_center_x: float = 0.0,
    intersection_center_y: float = 0.0,
) -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(
        root,
        "header",
        {
            "revMajor": "1",
            "revMinor": "6",
            "name": "urban_four_way_intersection",
            "version": "1.00",
            "date": "2026-07-06T00:00:00",
            "north": _fmt(intersection_center_y + ROAD_HALF_LENGTH_M),
            "south": _fmt(intersection_center_y - ROAD_HALF_LENGTH_M),
            "east": _fmt(intersection_center_x + ROAD_HALF_LENGTH_M),
            "west": _fmt(intersection_center_x - ROAD_HALF_LENGTH_M),
            "vendor": "ScenarioCraft",
        },
    )
    _append_two_lane_road(
        root,
        road_id="1",
        name="east_west_main",
        x=intersection_center_x - ROAD_HALF_LENGTH_M,
        y=intersection_center_y + LANE_WIDTH_M / 2,
        hdg=0.0,
    )
    _append_two_lane_road(
        root,
        road_id="2",
        name="north_south_cross",
        x=intersection_center_x,
        y=intersection_center_y - ROAD_HALF_LENGTH_M,
        hdg=1.57079632679,
    )
    _append_junction(root)
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip()) + "\n"


def _append_two_lane_road(root: ET.Element, *, road_id: str, name: str, x: float, y: float, hdg: float) -> None:
    road = ET.SubElement(
        root,
        "road",
        {
            "name": name,
            "length": _fmt(ROAD_LENGTH_M),
            "id": road_id,
            "junction": "1",
        },
    )
    ET.SubElement(road, "type", {"s": "0", "type": "town"})
    plan_view = ET.SubElement(road, "planView")
    geometry = ET.SubElement(
        plan_view,
        "geometry",
        {
            "s": "0",
            "x": _fmt(x),
            "y": _fmt(y),
            "hdg": _fmt(hdg),
            "length": _fmt(ROAD_LENGTH_M),
        },
    )
    ET.SubElement(geometry, "line")
    lanes = ET.SubElement(road, "lanes")
    lane_section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    center = ET.SubElement(lane_section, "center")
    center_lane = ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    ET.SubElement(
        center_lane,
        "roadMark",
        {"sOffset": "0", "type": "broken", "weight": "standard", "color": "yellow", "width": "0.12"},
    )
    left = ET.SubElement(lane_section, "left")
    _append_driving_lane(left, lane_id=1, road_mark="broken")
    right = ET.SubElement(lane_section, "right")
    _append_driving_lane(right, lane_id=-1, road_mark="solid")


def _append_driving_lane(parent: ET.Element, *, lane_id: int, road_mark: str) -> None:
    lane = ET.SubElement(parent, "lane", {"id": str(lane_id), "type": "driving", "level": "false"})
    ET.SubElement(lane, "width", {"sOffset": "0", "a": _fmt(LANE_WIDTH_M), "b": "0", "c": "0", "d": "0"})
    ET.SubElement(
        lane,
        "roadMark",
        {"sOffset": "0", "type": road_mark, "weight": "standard", "color": "white", "width": "0.12"},
    )


def _append_junction(root: ET.Element) -> None:
    junction = ET.SubElement(root, "junction", {"name": "urban_four_way_intersection_junction", "id": "1"})
    for connection_id, incoming_road, connecting_road, lane_pairs in (
        ("west_to_east_straight", "1", "1", ((-1, -1),)),
        ("south_to_north_straight", "2", "2", ((-1, -1),)),
        ("east_to_west_oncoming", "1", "1", ((1, 1),)),
        ("oncoming_turn_across_path", "1", "2", ((1, -1),)),
    ):
        connection = ET.SubElement(
            junction,
            "connection",
            {
                "id": connection_id,
                "incomingRoad": incoming_road,
                "connectingRoad": connecting_road,
                "contactPoint": "start",
            },
        )
        for from_lane, to_lane in lane_pairs:
            ET.SubElement(connection, "laneLink", {"from": str(from_lane), "to": str(to_lane)})


def _fmt(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")
