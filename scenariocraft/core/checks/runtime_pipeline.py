from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from scenariocraft.core.checks.runtime_consistency import run_runtime_consistency_checks
from scenariocraft.core.schemas import CheckResult, ScenarioSpec


RUNTIME_CHECK_RESULTS_FILENAME = "runtime_check_results.json"


def run_and_write_runtime_consistency_checks(
    spec: ScenarioSpec,
    *,
    output_dir: Path,
    xosc_path: Path | None = None,
    xodr_path: Path | None = None,
) -> tuple[CheckResult, ...]:
    """Run runtime checks from generated artifacts and persist structured evidence."""
    output_dir = Path(output_dir)
    results = run_runtime_consistency_checks(
        spec,
        xosc_path=xosc_path,
        xodr_path=xodr_path,
        esmini_log_path=_first_existing(
            output_dir,
            (
                "esmini_capture_log.txt",
                "esmini_log.txt",
            ),
        ),
        playback_result_path=_first_existing(output_dir, ("esmini_playback_result.json",)),
    )
    write_runtime_check_results(output_dir / RUNTIME_CHECK_RESULTS_FILENAME, results)
    return results


def write_runtime_check_results(path: Path, results: Sequence[CheckResult]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([result.to_dict() for result in results], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _first_existing(output_dir: Path, filenames: tuple[str, ...]) -> Path | None:
    for filename in filenames:
        path = output_dir / filename
        if path.exists():
            return path
    return None
