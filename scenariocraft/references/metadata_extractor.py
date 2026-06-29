from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class XoscMetadata:
    xosc_path: str
    file_exists: bool
    parse_success: bool
    parse_error: str | None = None
    open_scenario_version: str | None = None
    file_header: dict[str, str] = field(default_factory=dict)
    logic_file_paths: list[str] = field(default_factory=list)
    scene_graph_file_paths: list[str] = field(default_factory=list)
    catalog_locations: list[str] = field(default_factory=list)
    parameter_names: list[str] = field(default_factory=list)
    scenario_object_names: list[str] = field(default_factory=list)
    has_storyboard: bool = False
    parameter_count: int = 0
    scenario_object_count: int = 0
    maneuver_count: int = 0
    event_count: int = 0
    condition_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def extract_xosc_metadata(xosc_path: Path) -> XoscMetadata:
    path = Path(xosc_path)
    display_path = str(path)
    if not path.exists():
        return XoscMetadata(
            xosc_path=display_path,
            file_exists=False,
            parse_success=False,
            parse_error="OpenSCENARIO file does not exist.",
        )

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return XoscMetadata(
            xosc_path=display_path,
            file_exists=True,
            parse_success=False,
            parse_error=str(exc),
        )
    except OSError as exc:
        return XoscMetadata(
            xosc_path=display_path,
            file_exists=True,
            parse_success=False,
            parse_error=str(exc),
        )

    file_header = _first(root, "FileHeader")
    file_header_fields = dict(file_header.attrib) if file_header is not None else {}
    parameter_elements = _all(root, "ParameterDeclaration")
    scenario_objects = _all(root, "ScenarioObject")

    return XoscMetadata(
        xosc_path=display_path,
        file_exists=True,
        parse_success=True,
        parse_error=None,
        open_scenario_version=_detect_version(root, file_header_fields),
        file_header=file_header_fields,
        logic_file_paths=_attribute_values(_all(root, "LogicFile"), "filepath"),
        scene_graph_file_paths=_attribute_values(_all(root, "SceneGraphFile"), "filepath"),
        catalog_locations=_catalog_locations(root),
        parameter_names=_attribute_values(parameter_elements, "name"),
        scenario_object_names=_attribute_values(scenario_objects, "name"),
        has_storyboard=_first(root, "Storyboard") is not None,
        parameter_count=len(parameter_elements),
        scenario_object_count=len(scenario_objects),
        maneuver_count=len(_all(root, "Maneuver")),
        event_count=len(_all(root, "Event")),
        condition_count=len(_all(root, "Condition")),
    )


def _detect_version(root: ET.Element, file_header: dict[str, str]) -> str | None:
    major = file_header.get("revMajor") or root.attrib.get("revMajor")
    minor = file_header.get("revMinor") or root.attrib.get("revMinor")
    if major is not None and minor is not None:
        return f"{major}.{minor}"
    return root.attrib.get("version")


def _catalog_locations(root: ET.Element) -> list[str]:
    catalog_root = _first(root, "CatalogLocations")
    if catalog_root is None:
        return []
    locations: list[str] = []
    for element in catalog_root.iter():
        if _local_name(element.tag) == "Directory":
            path = element.attrib.get("path")
            if path:
                locations.append(path)
    return locations


def _attribute_values(elements: list[ET.Element], attribute_name: str) -> list[str]:
    return [value for element in elements if (value := element.attrib.get(attribute_name))]


def _first(root: ET.Element, name: str) -> ET.Element | None:
    return next((element for element in root.iter() if _local_name(element.tag) == name), None)


def _all(root: ET.Element, name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == name]


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
