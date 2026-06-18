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
    stdout: str = ""
    command: list[str] | None = None
    working_dir: str | None = None
    timeout_s: float | None = None
    process_timeout_s: float | None = None
    mode: str = "smoke"
    sim_duration_s: float | None = None
    timeout_classification: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "esmini_available": self.esmini_available,
            "executed": self.executed,
            "error_message": self.error_message,
            "stderr": self.stderr,
            "stdout": self.stdout,
            "command": self.command or ["esmini"],
            "working_dir": self.working_dir,
            "timeout_s": self.timeout_s,
            "process_timeout_s": self.process_timeout_s,
            "mode": self.mode,
            "sim_duration_s": self.sim_duration_s,
            "timeout_classification": self.timeout_classification,
        }

    def __post_init__(self) -> None:
        if self.command is None:
            object.__setattr__(self, "command", ["esmini", "--osc", "scenario.xosc"])


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
    assert summary["compatibility_category_counts"] == {"metadata_fail": 1, "tool_skipped": 1}

    cards = [json.loads(line) for line in (out_dir / "reference_cards.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(cards) == 2
    assert (out_dir / "compatibility_summary.md").exists()
    assert "Total scenarios scanned" in (out_dir / "compatibility_summary.md").read_text(encoding="utf-8")
    assert (out_dir / "recommended_examples.json").exists()

    with (out_dir / "compatibility_summary.csv").open(encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    assert len(rows) == 2
    assert rows[1]["logic_file_count"] == "1"
    assert rows[1]["relative_path"] == "valid/reference_valid.xosc"
    assert rows[1]["compatibility_category"] == "tool_skipped"


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
        mode: str = "smoke",
        sim_duration_s: float = 3.0,
    ) -> FakeEsminiResult:
        captured_working_dirs.append(working_dir if working_dir is not None else Path(""))
        return FakeEsminiResult(
            executed=xosc_path.name != "broken.xosc",
            error_message="load failed" if xosc_path.name == "broken.xosc" else None,
            timeout_s=timeout_s,
            mode=mode,
            sim_duration_s=sim_duration_s,
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
        "--esmini-mode",
        "smoke",
        "--timeout-s",
        "7",
        "--sim-duration-s",
        "2",
    ])

    assert exit_code == 0
    assert captured_working_dirs == [path.parent for path in scan_xosc_files(FIXTURE_ROOT)]
    summary = (out_dir / "compatibility_summary.md").read_text(encoding="utf-8")
    assert "Passed: `1`" in summary
    assert "Failed: `1`" in summary
    assert "metadata_fail" in summary
    assert "mismatched tag" in summary

    result_files = sorted((out_dir / "results").glob("*/result.json"))
    assert len(result_files) == 2


def test_reference_scan_classifies_compatibility_examples(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / "external"
    full_pass = root / "OSC-NCAP-scenarios" / "full_pass.xosc"
    qc_fail = root / "sl-3-1-osc-alks-scenarios" / "qc_fail.xosc"
    esmini_fail = root / "other" / "esmini_fail.xosc"
    for path in (full_pass, qc_fail, esmini_fail):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            """<OpenSCENARIO>
  <FileHeader revMajor="1" revMinor="3"/>
  <RoadNetwork><LogicFile filepath="../maps/test.xodr"/></RoadNetwork>
  <CatalogLocations><VehicleCatalog><Directory path="../Catalogs/Vehicles"/></VehicleCatalog></CatalogLocations>
  <Entities><ScenarioObject name="ego"/></Entities>
  <Storyboard/>
</OpenSCENARIO>
""",
            encoding="utf-8",
        )

    def fake_qc(xosc_path: Path, output_dir: Path | None = None) -> FakeQcResult:
        if xosc_path.name == "qc_fail.xosc":
            return FakeQcResult(passed=False, stderr="ASAM rule failed")
        return FakeQcResult(passed=True)

    def fake_esmini(
        xosc_path: Path,
        output_dir: Path | None = None,
        working_dir: Path | None = None,
        timeout_s: float = 20.0,
        mode: str = "smoke",
        sim_duration_s: float = 3.0,
    ) -> FakeEsminiResult:
        if xosc_path.name == "esmini_fail.xosc":
            return FakeEsminiResult(
                executed=False,
                error_message="Failed to open OpenDRIVE file ../maps/test.xodr",
                timeout_s=timeout_s,
                mode=mode,
                sim_duration_s=sim_duration_s,
            )
        return FakeEsminiResult(executed=True, timeout_s=timeout_s, mode=mode, sim_duration_s=sim_duration_s)

    monkeypatch.setattr("scenariocraft.references.scanner.run_asam_qc", fake_qc)
    monkeypatch.setattr("scenariocraft.references.scanner.run_esmini", fake_esmini)

    out_dir = tmp_path / "scan"
    summary = run_reference_scan(root, out_dir, run_qc=True, run_esmini_check=True)

    assert summary["compatibility_category_counts"] == {
        "esmini_fail": 1,
        "full_pass": 1,
        "qc_fail": 1,
    }
    assert summary["esmini_failure_class_counts"] == {"missing_opendrive_or_file": 1}

    cards = [json.loads(line) for line in (out_dir / "reference_cards.jsonl").read_text(encoding="utf-8").splitlines()]
    by_name = {Path(card["xosc_path"]).name: card for card in cards}
    assert by_name["full_pass.xosc"]["source"] == "OSC-NCAP-scenarios"
    assert by_name["full_pass.xosc"]["compatibility_category"] == "full_pass"
    assert by_name["qc_fail.xosc"]["source"] == "ALKS scenarios"
    assert by_name["qc_fail.xosc"]["compatibility_category"] == "qc_fail"
    assert by_name["esmini_fail.xosc"]["compatibility_category"] == "esmini_fail"
    assert by_name["esmini_fail.xosc"]["esmini_failure_class"] == "missing_opendrive_or_file"
    assert by_name["esmini_fail.xosc"]["failure_message"] == "Failed to open OpenDRIVE file ../maps/test.xodr"
    assert by_name["full_pass.xosc"]["esmini_mode"] == "smoke"
    assert by_name["full_pass.xosc"]["esmini_timeout_s"] == 20.0
    assert by_name["full_pass.xosc"]["esmini_sim_duration_s"] == 3.0
    assert by_name["full_pass.xosc"]["logic_file_references"] == ["../maps/test.xodr"]
    assert by_name["full_pass.xosc"]["catalog_locations"] == ["../Catalogs/Vehicles"]

    recommended = json.loads((out_dir / "recommended_examples.json").read_text(encoding="utf-8"))
    assert [item["relative_path"] for item in recommended["full_pass"]] == ["OSC-NCAP-scenarios/full_pass.xosc"]
    assert [item["relative_path"] for item in recommended["qc_fail"]] == ["sl-3-1-osc-alks-scenarios/qc_fail.xosc"]
    assert [item["relative_path"] for item in recommended["esmini_fail"]] == ["other/esmini_fail.xosc"]

    with (out_dir / "compatibility_summary.csv").open(encoding="utf-8", newline="") as file_obj:
        rows = list(csv.DictReader(file_obj))
    assert rows[0]["esmini_mode"] == "smoke"
    assert "esmini" in rows[0]["esmini_command"]
