from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from scenariocraft.references.browser import classify_reference_source
from scenariocraft.references.metadata_extractor import XoscMetadata, extract_xosc_metadata
from scenariocraft.tools import run_asam_qc, run_esmini


def scan_xosc_files(root: Path) -> list[Path]:
    scan_root = Path(root)
    if not scan_root.exists():
        return []
    return sorted(path for path in scan_root.rglob("*.xosc") if path.is_file())


def run_reference_scan(
    root: Path,
    out_dir: Path,
    limit: int | None = None,
    run_qc: bool = False,
    run_esmini_check: bool = False,
    esmini_timeout_s: float = 20.0,
    esmini_mode: str = "smoke",
    esmini_sim_duration_s: float = 3.0,
) -> dict[str, Any]:
    all_xosc_files = scan_xosc_files(root)
    selected_files = all_xosc_files[:limit] if limit is not None else all_xosc_files
    out_dir.mkdir(parents=True, exist_ok=True)
    result_dir = out_dir / "results"
    result_dir.mkdir(parents=True, exist_ok=True)

    cards: list[dict[str, Any]] = []
    for index, xosc_path in enumerate(selected_files, start=1):
        scenario_out = result_dir / f"{index:04d}_{_slug(xosc_path.stem)}"
        scenario_out.mkdir(parents=True, exist_ok=True)
        card = _scan_one(
            index=index,
            root=root,
            xosc_path=xosc_path,
            scenario_out=scenario_out,
            run_qc=run_qc,
            run_esmini_check=run_esmini_check,
            esmini_timeout_s=esmini_timeout_s,
            esmini_mode=esmini_mode,
            esmini_sim_duration_s=esmini_sim_duration_s,
        )
        cards.append(card)
        (scenario_out / "result.json").write_text(json.dumps(card, indent=2, sort_keys=True), encoding="utf-8")

    _write_jsonl(out_dir / "reference_cards.jsonl", cards)
    _write_csv(out_dir / "compatibility_summary.csv", cards)
    _write_recommended_examples(out_dir / "recommended_examples.json", cards)
    summary = _summary(root, all_xosc_files, cards)
    (out_dir / "compatibility_summary.md").write_text(_render_summary(summary), encoding="utf-8")
    return summary


def _scan_one(
    index: int,
    root: Path,
    xosc_path: Path,
    scenario_out: Path,
    run_qc: bool,
    run_esmini_check: bool,
    esmini_timeout_s: float,
    esmini_mode: str,
    esmini_sim_duration_s: float,
) -> dict[str, Any]:
    metadata = extract_xosc_metadata(xosc_path)
    qc_result = run_asam_qc(xosc_path, scenario_out) if run_qc else None
    esmini_result = (
        run_esmini(
            xosc_path,
            scenario_out,
            working_dir=xosc_path.parent,
            timeout_s=esmini_timeout_s,
            mode=esmini_mode,
            sim_duration_s=esmini_sim_duration_s,
        )
        if run_esmini_check
        else None
    )
    qc_status = _qc_status(qc_result, run_qc)
    esmini_status = _esmini_status(esmini_result, run_esmini_check)
    esmini_failure_class = _classify_esmini_failure(esmini_result)
    failure_message = _failure_message(metadata, qc_result, qc_status, esmini_result, esmini_status)
    compatibility_category = _compatibility_category(metadata, qc_status, esmini_status)
    return {
        "index": index,
        "source": classify_reference_source(xosc_path),
        "relative_path": _relative_path(root, xosc_path),
        "xosc_path": str(xosc_path),
        "metadata_parse_status": "passed" if metadata.parse_success else "failed",
        "logic_file_references": list(metadata.logic_file_paths),
        "catalog_locations": list(metadata.catalog_locations),
        "metadata": metadata.to_dict(),
        "qc_requested": run_qc,
        "qc_status": qc_status,
        "qc_result": qc_result.to_dict() if qc_result is not None else None,
        "esmini_requested": run_esmini_check,
        "esmini_status": esmini_status,
        "esmini_failure_class": esmini_failure_class,
        "esmini_mode": _esmini_result_field(esmini_result, "mode", esmini_mode if run_esmini_check else ""),
        "esmini_command": _esmini_result_field(esmini_result, "command", []),
        "esmini_working_dir": _esmini_result_field(esmini_result, "working_dir", ""),
        "esmini_timeout_s": _esmini_result_field(esmini_result, "timeout_s", esmini_timeout_s if run_esmini_check else None),
        "esmini_process_timeout_s": _esmini_result_field(esmini_result, "process_timeout_s", None),
        "esmini_sim_duration_s": _esmini_result_field(esmini_result, "sim_duration_s", None),
        "esmini_timeout_classification": _esmini_result_field(esmini_result, "timeout_classification", None),
        "esmini_result": esmini_result.to_dict() if esmini_result is not None else None,
        "failure_message": failure_message,
        "compatibility_category": compatibility_category,
    }


def _write_jsonl(path: Path, cards: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(card, sort_keys=True) + "\n" for card in cards), encoding="utf-8")


def _write_csv(path: Path, cards: list[dict[str, Any]]) -> None:
    fieldnames = [
        "index",
        "source",
        "relative_path",
        "xosc_path",
        "metadata_parse_status",
        "parse_success",
        "open_scenario_version",
        "logic_file_references",
        "logic_file_count",
        "catalog_locations",
        "scenario_object_count",
        "has_storyboard",
        "qc_status",
        "esmini_status",
        "esmini_failure_class",
        "esmini_mode",
        "esmini_command",
        "esmini_working_dir",
        "esmini_timeout_s",
        "esmini_process_timeout_s",
        "esmini_sim_duration_s",
        "esmini_timeout_classification",
        "compatibility_category",
        "failure_message",
    ]
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for card in cards:
            metadata = card["metadata"]
            writer.writerow({
                "index": card["index"],
                "source": card["source"],
                "relative_path": card["relative_path"],
                "xosc_path": card["xosc_path"],
                "metadata_parse_status": card["metadata_parse_status"],
                "parse_success": metadata["parse_success"],
                "open_scenario_version": metadata["open_scenario_version"] or "",
                "logic_file_references": ";".join(metadata["logic_file_paths"]),
                "logic_file_count": len(metadata["logic_file_paths"]),
                "catalog_locations": ";".join(metadata["catalog_locations"]),
                "scenario_object_count": metadata["scenario_object_count"],
                "has_storyboard": metadata["has_storyboard"],
                "qc_status": card["qc_status"],
                "esmini_status": card["esmini_status"],
                "esmini_failure_class": card["esmini_failure_class"] or "",
                "esmini_mode": card["esmini_mode"] or "",
                "esmini_command": " ".join(card["esmini_command"]) if isinstance(card["esmini_command"], list) else str(card["esmini_command"] or ""),
                "esmini_working_dir": card["esmini_working_dir"] or "",
                "esmini_timeout_s": card["esmini_timeout_s"] or "",
                "esmini_process_timeout_s": card["esmini_process_timeout_s"] or "",
                "esmini_sim_duration_s": card["esmini_sim_duration_s"] or "",
                "esmini_timeout_classification": card["esmini_timeout_classification"] or "",
                "compatibility_category": card["compatibility_category"],
                "failure_message": card["failure_message"] or "",
            })


def _write_recommended_examples(path: Path, cards: list[dict[str, Any]]) -> None:
    recommended = {
        "full_pass": _examples_for_category(cards, "full_pass"),
        "qc_fail": _examples_for_category(cards, "qc_fail"),
        "esmini_fail": _examples_for_category(cards, "esmini_fail"),
    }
    path.write_text(json.dumps(recommended, indent=2, sort_keys=True), encoding="utf-8")


def _summary(root: Path, all_xosc_files: list[Path], cards: list[dict[str, Any]]) -> dict[str, Any]:
    parsed_successfully = sum(1 for card in cards if card["metadata"]["parse_success"])
    with_logic_files = sum(1 for card in cards if card["metadata"]["logic_file_paths"])
    qc_counts = Counter(card["qc_status"] for card in cards)
    esmini_counts = Counter(card["esmini_status"] for card in cards)
    category_counts = Counter(card["compatibility_category"] for card in cards)
    esmini_failure_counts = Counter(
        card["esmini_failure_class"]
        for card in cards
        if card.get("esmini_failure_class")
    )
    return {
        "root": str(root),
        "total_found": len(all_xosc_files),
        "total_scanned": len(cards),
        "parsed_successfully": parsed_successfully,
        "with_logic_file_references": with_logic_files,
        "qc_counts": _status_counts(qc_counts),
        "esmini_counts": _status_counts(esmini_counts),
        "compatibility_category_counts": dict(sorted(category_counts.items())),
        "esmini_failure_class_counts": dict(sorted(esmini_failure_counts.items())),
        "top_failure_messages": _top_failure_messages(cards),
    }


def _render_summary(summary: dict[str, Any]) -> str:
    failures = summary["top_failure_messages"] or ["None"]
    failure_lines = "\n".join(f"- {message}" for message in failures)
    return f"""# Reference Scenario Compatibility Summary

## Scan

- Root: `{summary['root']}`
- Total .xosc files found: `{summary['total_found']}`
- Total scenarios scanned: `{summary['total_scanned']}`
- Parsed successfully: `{summary['parsed_successfully']}`
- With OpenDRIVE LogicFile references: `{summary['with_logic_file_references']}`

## ASAM QC

- Passed: `{summary['qc_counts']['passed']}`
- Failed: `{summary['qc_counts']['failed']}`
- Skipped: `{summary['qc_counts']['skipped']}`

## esmini

- Passed: `{summary['esmini_counts']['passed']}`
- Failed: `{summary['esmini_counts']['failed']}`
- Skipped: `{summary['esmini_counts']['skipped']}`

## Compatibility Categories

{_render_count_lines(summary['compatibility_category_counts'])}

## esmini Failure Classes

{_render_count_lines(summary['esmini_failure_class_counts'])}

## Top Failure Messages

{failure_lines}
"""


def _status_counts(counter: Counter[str]) -> dict[str, int]:
    return {
        "passed": counter.get("passed", 0),
        "failed": counter.get("failed", 0),
        "skipped": counter.get("skipped", 0),
    }


def _qc_status(result: object | None, requested: bool) -> str:
    if not requested or result is None or not getattr(result, "checker_available", False):
        return "skipped"
    return "passed" if getattr(result, "passed", False) else "failed"


def _esmini_status(result: object | None, requested: bool) -> str:
    if not requested or result is None or not getattr(result, "esmini_available", False):
        return "skipped"
    return "passed" if getattr(result, "executed", False) else "failed"


def _esmini_result_field(result: object | None, field_name: str, default: Any) -> Any:
    if result is None:
        return default
    value = getattr(result, field_name, default)
    return default if value is None else value


def _compatibility_category(metadata: XoscMetadata, qc_status: str, esmini_status: str) -> str:
    if not metadata.parse_success:
        return "metadata_fail"
    if qc_status == "failed":
        return "qc_fail"
    if esmini_status == "failed":
        return "esmini_fail"
    if esmini_status == "passed" and qc_status in {"passed", "skipped"}:
        return "full_pass"
    if qc_status == "skipped" or esmini_status == "skipped":
        return "tool_skipped"
    return "unknown"


def _classify_esmini_failure(result: object | None) -> str | None:
    if result is None or not getattr(result, "esmini_available", False) or getattr(result, "executed", False):
        return None
    timeout_classification = getattr(result, "timeout_classification", None)
    if timeout_classification:
        return str(timeout_classification)
    message = _first_non_empty(
        getattr(result, "stderr", None),
        getattr(result, "stdout", None),
        getattr(result, "error_message", None),
    ).lower()
    if not message:
        return "unknown_runtime_error"
    if "timeout" in message or "timed out" in message:
        return "timeout_no_output"
    if "catalog" in message and any(token in message for token in ("missing", "not found", "can't find", "cannot find", "failed to open")):
        return "missing_catalog"
    if any(token in message for token in ("opendrive", ".xodr", "logicfile", "roadnetwork")) and any(
        token in message for token in ("missing", "not found", "can't find", "cannot find", "failed to open", "no such file")
    ):
        return "missing_opendrive_or_file"
    if any(token in message for token in ("no such file", "not found", "failed to open", "cannot open", "can't find")):
        return "missing_opendrive_or_file"
    if any(token in message for token in ("unsupported", "not supported", "unknown element", "version")):
        return "unsupported_feature_or_version"
    if any(token in message for token in ("xml", "parse", "parser", "malformed")):
        return "xml_parse_runtime_error"
    return "unknown_runtime_error"


def _failure_message(
    metadata: XoscMetadata,
    qc_result: object | None,
    qc_status: str,
    esmini_result: object | None,
    esmini_status: str,
) -> str:
    if not metadata.parse_success and metadata.parse_error:
        return _short_message(metadata.parse_error)
    if qc_status == "failed" and qc_result is not None:
        return _short_message(
            _first_non_empty(
                _qc_result_issue_summary(qc_result),
                getattr(qc_result, "stderr", None),
                getattr(qc_result, "stdout", None),
                "ASAM QC failed.",
            )
        )
    if esmini_status == "failed" and esmini_result is not None:
        return _short_message(
            _first_non_empty(
                getattr(esmini_result, "stderr", None),
                getattr(esmini_result, "stdout", None),
                getattr(esmini_result, "error_message", None),
                "esmini failed.",
            )
        )
    return ""


def _top_failure_messages(cards: list[dict[str, Any]], limit: int = 5) -> list[str]:
    messages: Counter[str] = Counter()
    for card in cards:
        if card.get("failure_message"):
            messages[card["failure_message"]] += 1
    return [f"{message} ({count})" for message, count in messages.most_common(limit)]


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value:
            return value.strip()
    return ""


def _short_message(message: str, max_length: int = 180) -> str:
    compact = " ".join(message.split())
    return compact if len(compact) <= max_length else compact[: max_length - 3] + "..."


def _qc_result_issue_summary(result: object) -> str:
    result_path = getattr(result, "result_path", None)
    if not result_path:
        return ""
    path = Path(str(result_path))
    if not path.exists():
        return ""
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return ""
    issue = root.find(".//Issue")
    if issue is None:
        return ""
    checker = next((element for element in root.iter("Checker") if issue in list(element)), None)
    checker_id = checker.attrib.get("checkerId", "ASAM QC") if checker is not None else "ASAM QC"
    description = issue.attrib.get("description", "ASAM QC issue")
    location = issue.find("Locations")
    location_description = location.attrib.get("description", "") if location is not None else ""
    return " ".join(part for part in [checker_id, description, location_description] if part)


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return slug or "scenario"


def _relative_path(root: Path, path: Path) -> str:
    resolved = Path(path)
    try:
        return resolved.relative_to(root).as_posix()
    except ValueError:
        pass
    for marker in ("OSC-NCAP-scenarios", "sl-3-1-osc-alks-scenarios"):
        if marker in resolved.parts:
            index = resolved.parts.index(marker)
            return Path(*resolved.parts[index:]).as_posix()
    return resolved.name


def _examples_for_category(cards: list[dict[str, Any]], category: str, limit: int = 3) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for card in cards:
        if card["compatibility_category"] != category:
            continue
        examples.append({
            "source": card["source"],
            "relative_path": card["relative_path"],
            "xosc_path": card["xosc_path"],
            "qc_status": card["qc_status"],
            "esmini_status": card["esmini_status"],
            "esmini_failure_class": card["esmini_failure_class"],
            "failure_message": card["failure_message"],
        })
        if len(examples) >= limit:
            break
    return examples


def _render_count_lines(counts: dict[str, int]) -> str:
    if not counts:
        return "- None"
    return "\n".join(f"- {name}: `{count}`" for name, count in counts.items())
