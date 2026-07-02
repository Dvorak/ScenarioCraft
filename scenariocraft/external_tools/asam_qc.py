"""Runtime adapter for invoking an already-configured ASAM QC checker."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from xml.dom import minidom
from xml.etree import ElementTree as ET


CHECKER_IDS = [
    "check_asam_xosc_xml_valid_xml_document",
    "check_asam_xosc_xml_root_tag_is_openscenario",
    "check_asam_xosc_xml_fileheader_is_present",
    "check_asam_xosc_xml_version_is_defined",
    "check_asam_xosc_xml_valid_schema",
    "check_asam_xosc_reference_control_uniquely_resolvable_entity_references",
    "check_asam_xosc_reference_control_resolvable_signal_id_in_traffic_signal_state_action",
    "check_asam_xosc_reference_control_resolvable_traffic_signal_controller_by_traffic_signal_controller_ref",
    "check_asam_xosc_reference_control_valid_actor_reference_in_private_actions",
    "check_asam_xosc_reference_control_resolvable_entity_references",
    "check_asam_xosc_reference_control_resolvable_variable_reference",
    "check_asam_xosc_reference_control_resolvable_storyboard_element_reference",
    "check_asam_xosc_reference_control_unique_element_names_on_same_level",
    "check_asam_xosc_parameters_valid_parameter_declaration_in_catalogs",
    "check_asam_xosc_data_type_allowed_operators",
    "check_asam_xosc_data_type_non_negative_transition_time_in_light_state_action",
    "check_asam_xosc_positive_duration_in_phase",
]


@dataclass(frozen=True)
class AsamQcResult:
    checker_available: bool
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str
    passed: bool | None
    config_path: str | None = None
    result_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def run_asam_qc(xosc_path: Path, output_dir: Path | None = None) -> AsamQcResult:
    work_dir = output_dir or xosc_path.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    config_path = work_dir / "qc_config.xml"
    result_path = work_dir / "qc_result.xqar"
    write_qc_config(xosc_path=xosc_path, result_path=result_path, config_path=config_path)

    binary = os.environ.get("ASAM_QC_OPENSCENARIOXML_BIN", "qc_openscenario")
    resolved_binary = _resolve_binary(binary)
    command = [binary, "-c", str(config_path)]
    if resolved_binary is None:
        result = AsamQcResult(
            False,
            command,
            None,
            "",
            "ASAM OpenSCENARIO XML checker was not found.",
            None,
            str(config_path),
            str(result_path),
        )
    else:
        completed = subprocess.run([str(resolved_binary), "-c", str(config_path)], capture_output=True, text=True, check=False)
        result = AsamQcResult(
            True,
            command,
            completed.returncode,
            completed.stdout,
            completed.stderr,
            _qc_passed(completed.returncode, completed.stdout, result_path),
            str(config_path),
            str(result_path),
        )
    if output_dir is not None:
        (output_dir / "qc_report.json").write_text(result.to_json(), encoding="utf-8")
    return result


def write_qc_config(xosc_path: Path, result_path: Path, config_path: Path) -> Path:
    root = ET.Element("Config")
    ET.SubElement(root, "Param", {"name": "InputFile", "value": str(xosc_path)})
    bundle = ET.SubElement(root, "CheckerBundle", {"application": "xoscBundle"})
    ET.SubElement(bundle, "Param", {"name": "resultFile", "value": str(result_path)})
    for checker_id in CHECKER_IDS:
        ET.SubElement(bundle, "Checker", {"checkerId": checker_id, "maxLevel": "1", "minLevel": "3"})
    report = ET.SubElement(root, "ReportModule", {"application": "TextReport"})
    ET.SubElement(report, "Param", {"name": "strInputFile", "value": str(result_path)})
    ET.SubElement(report, "Param", {"name": "strReportFile", "value": str(config_path.with_name("qc_report.txt"))})
    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    config_path.write_text(pretty, encoding="utf-8")
    return config_path


def _qc_passed(return_code: int, stdout: str, result_path: Path) -> bool:
    if return_code != 0:
        return False
    if "Issues found - 0" in stdout:
        return True
    if "Issues found -" in stdout:
        return False
    if result_path.exists():
        result_text = result_path.read_text(encoding="utf-8", errors="replace")
        if "Issue" in result_text or "ERROR" in result_text:
            return False
    return True


def _resolve_binary(binary: str) -> Path | None:
    resolved = shutil.which(binary)
    if resolved is not None:
        return Path(resolved)
    sibling = Path(sys.executable).with_name(binary)
    if sibling.exists():
        return sibling
    return None
