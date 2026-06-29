from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET


URBAN_TWO_WAY_PARKING_FILENAME = "urban_two_way_parking.xodr"
ROAD_LENGTH_M = 120.0
REFERENCE_LINE_Y_M = 1.75


@dataclass(frozen=True)
class OpenDriveLaneSpec:
    lane_id: int
    lane_type: str
    width_m: float
    road_mark: str
    layout_band: str
    y_min_m: float
    y_max_m: float


# OpenDRIVE lane sign convention for this road:
# - the reference line runs along +x at world y=1.75, the ego-lane/parking boundary;
# - positive lane IDs are left of the reference line, i.e. positive world y;
# - negative lane IDs are right of the reference line, i.e. lower world y;
# - Phase A keeps XOSC actors on WorldPosition and does not reference these lane IDs.
URBAN_TWO_WAY_PARKING_LANES: tuple[OpenDriveLaneSpec, ...] = (
    OpenDriveLaneSpec(2, "sidewalk", 2.25, "none", "ego_side_sidewalk", 4.25, 6.50),
    OpenDriveLaneSpec(1, "parking", 2.50, "solid", "ego_side_parking_strip", 1.75, 4.25),
    OpenDriveLaneSpec(-1, "driving", 3.50, "broken", "ego_driving_lane", -1.75, 1.75),
    OpenDriveLaneSpec(-2, "median", 0.25, "solid", "center_divider", -2.00, -1.75),
    OpenDriveLaneSpec(-3, "driving", 3.50, "broken", "opposing_driving_lane", -5.50, -2.00),
    OpenDriveLaneSpec(-4, "sidewalk", 2.00, "none", "opposing_side_sidewalk", -7.50, -5.50),
)


def canonical_urban_two_way_parking_asset_path() -> Path:
    return Path(__file__).resolve().parents[3] / "assets" / "roads" / URBAN_TWO_WAY_PARKING_FILENAME


def write_urban_two_way_parking_xodr(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_urban_two_way_parking_xodr(), encoding="utf-8")
    return path


def generate_urban_two_way_parking_xodr() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(root, "header", {
        "revMajor": "1",
        "revMinor": "6",
        "name": "urban_two_way_parking",
        "version": "1.00",
        "date": "2026-06-18T00:00:00",
        "north": "0",
        "south": "0",
        "east": "0",
        "west": "0",
        "vendor": "ScenarioCraft",
    })
    road = ET.SubElement(root, "road", {
        "name": "urban_two_way_parking_main",
        "length": _fmt(ROAD_LENGTH_M),
        "id": "1",
        "junction": "-1",
    })
    ET.SubElement(road, "type", {"s": "0", "type": "town"})
    plan_view = ET.SubElement(road, "planView")
    geometry = ET.SubElement(plan_view, "geometry", {
        "s": "0",
        "x": "0",
        "y": _fmt(REFERENCE_LINE_Y_M),
        "hdg": "0",
        "length": _fmt(ROAD_LENGTH_M),
    })
    ET.SubElement(geometry, "line")
    lanes = ET.SubElement(road, "lanes")
    lane_section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    left = ET.SubElement(lane_section, "left")
    for lane in [item for item in URBAN_TWO_WAY_PARKING_LANES if item.lane_id > 0]:
        _append_lane(left, lane)
    center = ET.SubElement(lane_section, "center")
    center_lane = ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    ET.SubElement(center_lane, "roadMark", {"sOffset": "0", "type": "solid", "weight": "standard", "color": "white", "width": "0.12"})
    right = ET.SubElement(lane_section, "right")
    for lane in [item for item in URBAN_TWO_WAY_PARKING_LANES if item.lane_id < 0]:
        _append_lane(right, lane)
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip()) + "\n"


def _append_lane(parent: ET.Element, lane: OpenDriveLaneSpec) -> None:
    lane_element = ET.SubElement(parent, "lane", {
        "id": str(lane.lane_id),
        "type": lane.lane_type,
        "level": "false",
    })
    ET.SubElement(lane_element, "width", {
        "sOffset": "0",
        "a": _fmt(lane.width_m),
        "b": "0",
        "c": "0",
        "d": "0",
    })
    if lane.road_mark != "none":
        ET.SubElement(lane_element, "roadMark", {
            "sOffset": "0",
            "type": lane.road_mark,
            "weight": "standard",
            "color": "white",
            "width": "0.12",
        })
    ET.SubElement(lane_element, "userData", {
        "code": "scenariocraft_layout_band",
        "value": lane.layout_band,
    })


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
