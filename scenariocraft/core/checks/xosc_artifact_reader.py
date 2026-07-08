"""Small XML readers used by artifact-consistency checks."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET


def parse_xosc(xosc_path: Path) -> tuple[ET.Element | None, str | None]:
    try:
        return ET.parse(xosc_path).getroot(), None
    except (OSError, ET.ParseError) as exc:
        return None, str(exc)


def initial_world_positions(root: ET.Element | None) -> dict[str, tuple[float, float, float]]:
    if root is None:
        return {}
    positions: dict[str, tuple[float, float, float]] = {}
    for private in root.findall(".//Init/Actions/Private"):
        actor_id = private.attrib.get("entityRef")
        world_position = private.find("./PrivateAction/TeleportAction/Position/WorldPosition")
        if actor_id is None or world_position is None:
            continue
        try:
            positions[actor_id] = (
                float(world_position.attrib["x"]),
                float(world_position.attrib["y"]),
                float(world_position.attrib.get("h", "0")),
            )
        except (KeyError, ValueError):
            continue
    return positions


def trajectory_vertices(
    root: ET.Element | None,
    *,
    action_name: str,
) -> tuple[list[dict[str, float | None]], bool]:
    if root is None:
        return [], False
    action = root.find(f".//Action[@name='{action_name}']")
    if action is None:
        return [], False
    vertices: list[dict[str, float | None]] = []
    times_parseable = True
    for vertex in action.findall(".//FollowTrajectoryAction//Polyline/Vertex"):
        world_position = vertex.find("./Position/WorldPosition")
        try:
            time_s = float(vertex.attrib["time"])
        except (KeyError, ValueError):
            time_s = None
            times_parseable = False
        try:
            x_m = float(world_position.attrib["x"]) if world_position is not None else None
            y_m = float(world_position.attrib["y"]) if world_position is not None else None
        except (KeyError, ValueError):
            x_m = None
            y_m = None
        vertices.append({"x_m": x_m, "y_m": y_m, "time_s": time_s})
    return vertices, times_parseable and bool(vertices)


def logic_file_path(root: ET.Element | None) -> str | None:
    if root is None:
        return None
    logic_file = root.find("./RoadNetwork/LogicFile")
    if logic_file is None:
        return None
    return logic_file.attrib.get("filepath")


def float_attr(element: ET.Element | None, name: str) -> float | None:
    if element is None:
        return None
    try:
        return float(element.attrib[name])
    except (KeyError, ValueError):
        return None


__all__ = [
    "float_attr",
    "initial_world_positions",
    "logic_file_path",
    "parse_xosc",
    "trajectory_vertices",
]
