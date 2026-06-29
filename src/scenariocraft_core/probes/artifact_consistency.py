from __future__ import annotations

import math
from pathlib import Path
from xml.etree import ElementTree as ET

from scenariocraft_core.roads import URBAN_TWO_WAY_PARKING_FILENAME
from scenariocraft_core.schemas import ProbeResult, ScenarioSpec

POSITION_TOLERANCE_M = 1e-6
HEADING_TOLERANCE_RAD = 1e-6
PATH_TOLERANCE_M = 1e-6
CANONICAL_ACTOR_IDS = ("ego", "parked_van", "pedestrian")


def run_artifact_consistency_probes(
    spec: ScenarioSpec,
    *,
    xosc_path: Path,
    xodr_path: Path | None,
) -> tuple[ProbeResult, ...]:
    if spec.scenario_type != "pedestrian_occlusion" or spec.layout is None:
        return ()

    root, parse_error = _parse_xosc(xosc_path)
    logic_file_path = _logic_file_path(root)
    return (
        _actor_poses_probe(spec, root, parse_error),
        _pedestrian_trajectory_probe(spec, root, parse_error),
        _logic_file_relative_probe(logic_file_path, parse_error),
        _logic_file_target_exists_probe(xosc_path, xodr_path, logic_file_path, parse_error),
        _logic_file_canonical_probe(logic_file_path, parse_error),
    )


def _parse_xosc(xosc_path: Path) -> tuple[ET.Element | None, str | None]:
    try:
        return ET.parse(xosc_path).getroot(), None
    except (OSError, ET.ParseError) as exc:
        return None, str(exc)


def _actor_poses_probe(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> ProbeResult:
    observed = _initial_world_positions(root)
    actor_ids = list(CANONICAL_ACTOR_IDS)
    expected_x: dict[str, float] = {}
    expected_y: dict[str, float] = {}
    expected_heading: dict[str, float] = {}
    observed_x: dict[str, float | None] = {}
    observed_y: dict[str, float | None] = {}
    observed_heading: dict[str, float | None] = {}
    position_error: dict[str, float | None] = {}
    heading_error: dict[str, float | None] = {}

    for actor_id in actor_ids:
        pose = spec.layout.actor_poses[actor_id]
        expected_x[actor_id] = pose.x_m
        expected_y[actor_id] = pose.y_m
        expected_heading[actor_id] = pose.heading_rad
        world_position = observed.get(actor_id)
        if world_position is None:
            observed_x[actor_id] = None
            observed_y[actor_id] = None
            observed_heading[actor_id] = None
            position_error[actor_id] = None
            heading_error[actor_id] = None
            continue
        x_m, y_m, heading_rad = world_position
        observed_x[actor_id] = x_m
        observed_y[actor_id] = y_m
        observed_heading[actor_id] = heading_rad
        position_error[actor_id] = math.hypot(x_m - pose.x_m, y_m - pose.y_m)
        heading_error[actor_id] = abs(heading_rad - pose.heading_rad)

    passed = parse_error is None and all(
        position_error[actor_id] is not None
        and position_error[actor_id] <= POSITION_TOLERANCE_M
        and heading_error[actor_id] is not None
        and heading_error[actor_id] <= HEADING_TOLERANCE_RAD
        for actor_id in actor_ids
    )
    measured: dict[str, object] = {
        "actor_id": actor_ids,
        "expected_x_m": expected_x,
        "expected_y_m": expected_y,
        "expected_heading_rad": expected_heading,
        "observed_x_m": observed_x,
        "observed_y_m": observed_y,
        "observed_heading_rad": observed_heading,
        "position_error_m": position_error,
        "heading_error_rad": heading_error,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_actor_poses_match_layout",
        passed=passed,
        pass_message="XOSC initial actor WorldPosition values match ScenarioSpec layout poses.",
        failure_message="XOSC initial actor WorldPosition values diverge from ScenarioSpec layout poses.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC actor initial pose diverges from ScenarioSpec layout.",
        },),
    )


def _pedestrian_trajectory_probe(
    spec: ScenarioSpec,
    root: ET.Element | None,
    parse_error: str | None,
) -> ProbeResult:
    path_id = "pedestrian_crossing_path"
    expected_points = spec.layout.paths[path_id].points
    expected_vertices = [{"x_m": point.x_m, "y_m": point.y_m} for point in expected_points]
    observed_vertices, times_parseable = _pedestrian_trajectory_vertices(root)
    comparable_count = min(len(expected_vertices), len(observed_vertices))
    errors = [
        math.hypot(
            float(observed_vertices[index]["x_m"]) - expected_vertices[index]["x_m"],
            float(observed_vertices[index]["y_m"]) - expected_vertices[index]["y_m"],
        )
        for index in range(comparable_count)
        if observed_vertices[index]["x_m"] is not None and observed_vertices[index]["y_m"] is not None
    ]
    maximum_error = max(errors) if len(errors) == comparable_count and errors else None
    passed = (
        parse_error is None
        and len(expected_vertices) == len(observed_vertices)
        and maximum_error is not None
        and maximum_error <= PATH_TOLERANCE_M
        and times_parseable
    )
    measured: dict[str, object] = {
        "path_id": path_id,
        "expected_vertex_count": len(expected_vertices),
        "observed_vertex_count": len(observed_vertices),
        "expected_vertices": expected_vertices,
        "observed_vertices": observed_vertices,
        "maximum_position_error_m": maximum_error,
        "time_attributes_parseable": times_parseable,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_pedestrian_trajectory_matches_layout_path",
        passed=passed,
        pass_message="XOSC pedestrian FollowTrajectoryAction vertices match ScenarioSpec layout path.",
        failure_message="XOSC pedestrian FollowTrajectoryAction vertices diverge from ScenarioSpec layout path.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC pedestrian trajectory diverges from ScenarioSpec layout path.",
        },),
    )


def _logic_file_relative_probe(logic_file_path: str | None, parse_error: str | None) -> ProbeResult:
    user_home = str(Path.home())
    is_relative = bool(
        logic_file_path
        and not Path(logic_file_path).is_absolute()
        and user_home not in logic_file_path
    )
    measured: dict[str, object] = {
        "logic_file_path": logic_file_path,
        "is_relative": is_relative,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_logic_file_is_relative",
        passed=parse_error is None and is_relative,
        pass_message="XOSC RoadNetwork LogicFile uses a portable relative path.",
        failure_message="XOSC RoadNetwork LogicFile is missing or is not portable and relative.",
        measured=measured,
        suggested_operations=({
            "op": "rebuild_artifacts",
            "reason": "XOSC LogicFile must use a portable relative path.",
        },),
    )


def _logic_file_target_exists_probe(
    xosc_path: Path,
    xodr_path: Path | None,
    logic_file_path: str | None,
    parse_error: str | None,
) -> ProbeResult:
    xosc_directory = xosc_path.parent.resolve()
    relative = bool(logic_file_path and not Path(logic_file_path).is_absolute())
    resolved = (xosc_directory / logic_file_path).resolve() if relative and logic_file_path else None
    supplied_xodr = xodr_path.resolve() if xodr_path is not None else None
    matches_build_result = bool(resolved is not None and supplied_xodr is not None and resolved == supplied_xodr)
    target_exists = bool(resolved is not None and resolved.is_file() and matches_build_result)
    measured: dict[str, object] = {
        "xosc_directory": str(xosc_directory),
        "logic_file_path": logic_file_path,
        "resolved_xodr_path": str(resolved) if resolved is not None else None,
        "target_exists": target_exists,
        "build_result_xodr_path": str(supplied_xodr) if supplied_xodr is not None else None,
        "matches_build_result_xodr_path": matches_build_result,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xodr_logic_file_target_exists",
        passed=parse_error is None and target_exists,
        pass_message="XOSC LogicFile resolves to the generated OpenDRIVE file beside the XOSC artifact.",
        failure_message="XOSC LogicFile does not resolve to the generated OpenDRIVE file.",
        measured=measured,
        suggested_operations=({
            "op": "materialize_canonical_road_asset",
            "road_asset": URBAN_TWO_WAY_PARKING_FILENAME,
        },),
    )


def _logic_file_canonical_probe(logic_file_path: str | None, parse_error: str | None) -> ProbeResult:
    observed_basename = Path(logic_file_path).name if logic_file_path else None
    passed = parse_error is None and observed_basename == URBAN_TWO_WAY_PARKING_FILENAME
    measured: dict[str, object] = {
        "expected_basename": URBAN_TWO_WAY_PARKING_FILENAME,
        "observed_basename": observed_basename,
    }
    if parse_error is not None:
        measured["xosc_parse_error"] = parse_error
    return _result(
        name="xosc_logic_file_matches_canonical_road",
        passed=passed,
        pass_message="XOSC LogicFile references the canonical urban two-way parking road.",
        failure_message="XOSC LogicFile does not reference the canonical urban two-way parking road.",
        measured=measured,
        suggested_operations=({
            "op": "materialize_canonical_road_asset",
            "road_asset": URBAN_TWO_WAY_PARKING_FILENAME,
        },),
    )


def _initial_world_positions(root: ET.Element | None) -> dict[str, tuple[float, float, float]]:
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


def _pedestrian_trajectory_vertices(
    root: ET.Element | None,
) -> tuple[list[dict[str, float | None]], bool]:
    if root is None:
        return [], False
    action = root.find(".//Action[@name='pedestrian_follow_crossing_path']")
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


def _logic_file_path(root: ET.Element | None) -> str | None:
    if root is None:
        return None
    logic_file = root.find("./RoadNetwork/LogicFile")
    if logic_file is None:
        return None
    return logic_file.attrib.get("filepath")


def _result(
    *,
    name: str,
    passed: bool,
    pass_message: str,
    failure_message: str,
    measured: dict[str, object],
    suggested_operations: tuple[dict[str, object], ...],
) -> ProbeResult:
    return ProbeResult(
        name=name,
        passed=passed,
        severity="note" if passed else "failure",
        message=pass_message if passed else failure_message,
        measured=measured,
        suggested_operations=() if passed else suggested_operations,
    )
