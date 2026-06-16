from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class EsminiResult:
    esmini_available: bool
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str
    executed: bool | None
    playback_path: str | None
    required: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def run_esmini(xosc_path: Path, output_dir: Path | None = None, required: bool = False) -> EsminiResult:
    binary = os.environ.get("ESMINI_BIN", "esmini")
    command = [binary, "--osc", str(xosc_path), "--headless", "--quit_at_end"]
    if shutil.which(binary) is None:
        result = EsminiResult(False, command, None, "", "esmini was not found.", None, None, required)
    else:
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        result = EsminiResult(
            True,
            command,
            completed.returncode,
            completed.stdout,
            completed.stderr,
            completed.returncode == 0,
            None,
            required,
        )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "esmini_log.txt").write_text(_format_log(result), encoding="utf-8")
    return result


def _format_log(result: EsminiResult) -> str:
    return "\n".join([
        f"command: {' '.join(result.command)}",
        f"available: {result.esmini_available}",
        f"required: {result.required}",
        f"return_code: {result.return_code}",
        "",
        "stdout:",
        result.stdout,
        "",
        "stderr:",
        result.stderr,
        "",
    ])
