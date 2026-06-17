from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

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
            xosc_path=xosc_path,
            scenario_out=scenario_out,
            run_qc=run_qc,
            run_esmini_check=run_esmini_check,
            esmini_timeout_s=esmini_timeout_s,
        )
        cards.append(card)
        (scenario_out / "result.json").write_text(json.dumps(card, indent=2, sort_keys=True), encoding="utf-8")

    _write_jsonl(out_dir / "reference_cards.jsonl", cards)
    _write_csv(out_dir / "compatibility_summary.csv", cards)
    summary = _summary(root, all_xosc_files, cards)
    (out_dir / "compatibility_summary.md").write_text(_render_summary(summary), encoding="utf-8")
    return summary


def _scan_one(
    index: int,
    xosc_path: Path,
    scenario_out: Path,
    run_qc: bool,
    run_esmini_check: bool,
    esmini_timeout_s: float,
) -> dict[str, Any]:
    metadata = extract_xosc_metadata(xosc_path)
    qc_result = run_asam_qc(xosc_path, scenario_out) if run_qc else None
    esmini_result = (
        run_esmini(xosc_path, scenario_out, working_dir=xosc_path.parent, timeout_s=esmini_timeout_s)
        if run_esmini_check
        else None
    )
    return {
        "index": index,
        "xosc_path": str(xosc_path),
        "metadata": metadata.to_dict(),
        "qc_requested": run_qc,
        "qc_status": _qc_status(qc_result, run_qc),
        "qc_result": qc_result.to_dict() if qc_result is not None else None,
        "esmini_requested": run_esmini_check,
        "esmini_status": _esmini_status(esmini_result, run_esmini_check),
        "esmini_result": esmini_result.to_dict() if esmini_result is not None else None,
    }


def _write_jsonl(path: Path, cards: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(card, sort_keys=True) + "\n" for card in cards), encoding="utf-8")


def _write_csv(path: Path, cards: list[dict[str, Any]]) -> None:
    fieldnames = [
        "index",
        "xosc_path",
        "parse_success",
        "open_scenario_version",
        "logic_file_count",
        "scenario_object_count",
        "has_storyboard",
        "qc_status",
        "esmini_status",
    ]
    with path.open("w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        for card in cards:
            metadata = card["metadata"]
            writer.writerow({
                "index": card["index"],
                "xosc_path": card["xosc_path"],
                "parse_success": metadata["parse_success"],
                "open_scenario_version": metadata["open_scenario_version"] or "",
                "logic_file_count": len(metadata["logic_file_paths"]),
                "scenario_object_count": metadata["scenario_object_count"],
                "has_storyboard": metadata["has_storyboard"],
                "qc_status": card["qc_status"],
                "esmini_status": card["esmini_status"],
            })


def _summary(root: Path, all_xosc_files: list[Path], cards: list[dict[str, Any]]) -> dict[str, Any]:
    parsed_successfully = sum(1 for card in cards if card["metadata"]["parse_success"])
    with_logic_files = sum(1 for card in cards if card["metadata"]["logic_file_paths"])
    qc_counts = Counter(card["qc_status"] for card in cards)
    esmini_counts = Counter(card["esmini_status"] for card in cards)
    return {
        "root": str(root),
        "total_found": len(all_xosc_files),
        "total_scanned": len(cards),
        "parsed_successfully": parsed_successfully,
        "with_logic_file_references": with_logic_files,
        "qc_counts": _status_counts(qc_counts),
        "esmini_counts": _status_counts(esmini_counts),
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


def _top_failure_messages(cards: list[dict[str, Any]], limit: int = 5) -> list[str]:
    messages: Counter[str] = Counter()
    for card in cards:
        metadata = card["metadata"]
        if not metadata["parse_success"] and metadata["parse_error"]:
            messages[metadata["parse_error"]] += 1
        qc_result = card.get("qc_result")
        if qc_result and card["qc_status"] == "failed":
            message = _first_non_empty(qc_result.get("stderr"), qc_result.get("stdout"), "ASAM QC failed.")
            messages[_short_message(message)] += 1
        esmini_result = card.get("esmini_result")
        if esmini_result and card["esmini_status"] == "failed":
            message = _first_non_empty(
                esmini_result.get("error_message"),
                esmini_result.get("stderr"),
                "esmini failed.",
            )
            messages[_short_message(message)] += 1
    return [f"{message} ({count})" for message, count in messages.most_common(limit)]


def _first_non_empty(*values: str | None) -> str:
    for value in values:
        if value:
            return value.strip()
    return ""


def _short_message(message: str, max_length: int = 180) -> str:
    compact = " ".join(message.split())
    return compact if len(compact) <= max_length else compact[: max_length - 3] + "..."


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return slug or "scenario"
