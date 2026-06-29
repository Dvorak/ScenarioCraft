from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from scenariocraft_core.probes.runtime_consistency import run_runtime_consistency_probes
from scenariocraft_core.schemas import ProbeResult, ScenarioSpec


RUNTIME_PROBE_RESULTS_FILENAME = "runtime_probe_results.json"


def run_and_write_runtime_consistency_probes(
    spec: ScenarioSpec,
    *,
    output_dir: Path,
    xosc_path: Path | None = None,
    xodr_path: Path | None = None,
) -> tuple[ProbeResult, ...]:
    """Run runtime probes from generated artifacts and persist structured evidence."""
    output_dir = Path(output_dir)
    results = run_runtime_consistency_probes(
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
    write_runtime_probe_results(output_dir / RUNTIME_PROBE_RESULTS_FILENAME, results)
    return results


def write_runtime_probe_results(path: Path, results: Sequence[ProbeResult]) -> Path:
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
