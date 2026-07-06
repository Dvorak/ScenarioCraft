from __future__ import annotations

"""Canonical straight multi-lane same-direction OpenDRIVE road."""

from dataclasses import dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET


MULTI_LANE_SAME_DIRECTION_FILENAME = "multi_lane_same_direction.xodr"
ROAD_LENGTH_M = 140.0
REFERENCE_LINE_Y_M = 1.75


@dataclass(frozen=True)
class MultiLaneSameDirectionLaneSpec:
    lane_id: int
    lane_type: str
    width_m: float
    road_mark: str
    layout_band: str
    y_min_m: float
    y_max_m: float


MULTI_LANE_SAME_DIRECTION_LANES: tuple[MultiLaneSameDirectionLaneSpec, ...] = (
    MultiLaneSameDirectionLaneSpec(1, "driving", 3.50, "broken", "adjacent_same_direction_lane", 1.75, 5.25),
    MultiLaneSameDirectionLaneSpec(-1, "driving", 3.50, "broken", "ego_driving_lane", -1.75, 1.75),
    MultiLaneSameDirectionLaneSpec(-2, "shoulder", 2.00, "solid", "ego_side_shoulder", -3.75, -1.75),
)


def write_multi_lane_same_direction_xodr(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate_multi_lane_same_direction_xodr(), encoding="utf-8")
    return path


def generate_multi_lane_same_direction_xodr() -> str:
    root = ET.Element("OpenDRIVE")
    ET.SubElement(
        root,
        "header",
        {
            "revMajor": "1",
            "revMinor": "6",
            "name": "multi_lane_same_direction",
            "version": "1.00",
            "date": "2026-07-06T00:00:00",
            "north": "0",
            "south": "0",
            "east": "0",
            "west": "0",
            "vendor": "ScenarioCraft",
        },
    )
    road = ET.SubElement(
        root,
        "road",
        {
            "name": "multi_lane_same_direction_main",
            "length": _fmt(ROAD_LENGTH_M),
            "id": "1",
            "junction": "-1",
        },
    )
    ET.SubElement(road, "type", {"s": "0", "type": "town"})
    plan_view = ET.SubElement(road, "planView")
    geometry = ET.SubElement(
        plan_view,
        "geometry",
        {
            "s": "0",
            "x": "0",
            "y": _fmt(REFERENCE_LINE_Y_M),
            "hdg": "0",
            "length": _fmt(ROAD_LENGTH_M),
        },
    )
    ET.SubElement(geometry, "line")
    lanes = ET.SubElement(road, "lanes")
    lane_section = ET.SubElement(lanes, "laneSection", {"s": "0"})
    left = ET.SubElement(lane_section, "left")
    for lane in [item for item in MULTI_LANE_SAME_DIRECTION_LANES if item.lane_id > 0]:
        _append_lane(left, lane)
    center = ET.SubElement(lane_section, "center")
    center_lane = ET.SubElement(center, "lane", {"id": "0", "type": "none", "level": "false"})
    ET.SubElement(
        center_lane,
        "roadMark",
        {"sOffset": "0", "type": "broken", "weight": "standard", "color": "white", "width": "0.12"},
    )
    right = ET.SubElement(lane_section, "right")
    for lane in [item for item in MULTI_LANE_SAME_DIRECTION_LANES if item.lane_id < 0]:
        _append_lane(right, lane)
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    return "\n".join(line for line in pretty.splitlines() if line.strip()) + "\n"


def _append_lane(parent: ET.Element, lane: MultiLaneSameDirectionLaneSpec) -> None:
    lane_element = ET.SubElement(
        parent,
        "lane",
        {
            "id": str(lane.lane_id),
            "type": lane.lane_type,
            "level": "false",
        },
    )
    ET.SubElement(lane_element, "width", {"sOffset": "0", "a": _fmt(lane.width_m), "b": "0", "c": "0", "d": "0"})
    ET.SubElement(
        lane_element,
        "roadMark",
        {"sOffset": "0", "type": lane.road_mark, "weight": "standard", "color": "white", "width": "0.12"},
    )
    ET.SubElement(lane_element, "userData", {"code": "scenariocraft_layout_band", "value": lane.layout_band})


def _fmt(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
