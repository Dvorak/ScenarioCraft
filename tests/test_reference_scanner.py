from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from scenariocraft.references.scan import main as scan_main
from scenariocraft.references.scanner import run_reference_scan, scan_xosc_files


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "reference_scenarios"


@dataclass(frozen=True)
class FakeQcResult:
    checker_available: bool = True
    passed: bool = True
    stderr: str = ""
    stdout: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "checker_available": self.checker_available,
            "passed": self.passed,
            "stderr": self.stderr,
            "stdout": self.stdout,
        }


@dataclass(frozen=True)
class FakeEsminiResult:
    esmini_available: bool = True
    executed: bool = True
    error_message: str | None = None
    stderr: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "esmini_available": self.esmini_available,
            "executed": self.executed,
            "error_message": self.error_message,
            "stderr": self.stderr,
        }


def test_scan_xosc_files_recurses_and_sorts() -> None:
    paths = scan_xosc_files(FIXTURE_ROOT)

    assert [path.name for path in paths] == ["broken.xosc", "reference_valid.xosc"]


def test_reference_scan_writes_cards_and_summaries(tmp_path: Path) -> None:
    out_dir = tmp_path / "scan"

    summary = run_reference_scan(FIXTURE_ROOT, out_dir)

    assert summary["total_found"] == 2
    assert summary["total_scanned"] == 2
    assert summary["parsed_successfully"] == 1
    assert summary["with_logic_file_references"] == 1
    assert summary["qc_counts"] == {"passed": 0, "failed": 0, "skipped": 2}
    assert summary["esmini_counts"] == {"passed": 0, "failed": 0, "skipped": 2}

    cards = [json.loads(line) for line in (out_dir / "reference_cards.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(cards) == 2
    assert (out_dir / "compatibility_summary.md").exists()
    assert "Total scenarios scanned" in (out_dir / "compatibility_summary.md").read_text(encoding="utf-8")

    with (out_dir / "compatibility_summary.csv").open(encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    assert len(rows) == 2
    assert rows[1]["logic_file_count"] == "1"


def test_reference_scan_can_run_fake_qc_and_esmini(monkeypatch, tmp_path: Path) -> None:
    out_dir = tmp_path / "scan"
    captured_working_dirs: list[Path] = []

    def fake_qc(xosc_path: Path, output_dir: Path | None = None) -> FakeQcResult:
        return FakeQcResult(passed=xosc_path.name != "broken.xosc", stderr="qc failed" if xosc_path.name == "broken.xosc" else "")

    def fake_esmini(
        xosc_path: Path,
        output_dir: Path | None = None,
        working_dir: Path | None = None,
        timeout_s: float = 20.0,
    ) -> FakeEsminiResult:
        captured_working_dirs.append(working_dir if working_dir is not None else Path(""))
        return FakeEsminiResult(
            executed=xosc_path.name != "broken.xosc",
            error_message="load failed" if xosc_path.name == "broken.xosc" else None,
        )

    monkeypatch.setattr("scenariocraft.references.scanner.run_asam_qc", fake_qc)
    monkeypatch.setattr("scenariocraft.references.scanner.run_esmini", fake_esmini)

    exit_code = scan_main([
        "--root",
        str(FIXTURE_ROOT),
        "--out",
        str(out_dir),
        "--run-qc",
        "--run-esmini",
    ])

    assert exit_code == 0
    assert captured_working_dirs == [path.parent for path in scan_xosc_files(FIXTURE_ROOT)]
    summary = (out_dir / "compatibility_summary.md").read_text(encoding="utf-8")
    assert "Passed: `1`" in summary
    assert "Failed: `1`" in summary
    assert "qc failed" in summary
    assert "load failed" in summary

    result_files = sorted((out_dir / "results").glob("*/result.json"))
    assert len(result_files) == 2
