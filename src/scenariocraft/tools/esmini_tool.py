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
    install_hint: str | None = None
    timeout_s: float | None = None
    timed_out: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def run_esmini(
    xosc_path: Path,
    output_dir: Path | None = None,
    required: bool = False,
    binary: str | None = None,
    timeout_s: float = 20.0,
) -> EsminiResult:
    resolved_binary = resolve_esmini_binary(binary)
    command_binary = str(resolved_binary or binary or os.environ.get("ESMINI_BIN", "esmini"))
    command = [command_binary, "--osc", str(xosc_path), "--headless", "--quit_at_end", "--disable_log"]
    if resolved_binary is None:
        result = EsminiResult(
            False,
            command,
            None,
            "",
            "esmini was not found.",
            None,
            None,
            required,
            _install_hint(),
            timeout_s,
            False,
        )
    else:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=timeout_s)
            result = EsminiResult(
                True,
                command,
                completed.returncode,
                completed.stdout,
                completed.stderr,
                completed.returncode == 0,
                None,
                required,
                None,
                timeout_s,
                False,
            )
        except subprocess.TimeoutExpired as exc:
            result = EsminiResult(
                True,
                command,
                None,
                _decode_timeout_output(exc.stdout),
                _decode_timeout_output(exc.stderr) or f"esmini timed out after {timeout_s:g} seconds.",
                False,
                None,
                required,
                None,
                timeout_s,
                True,
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
        f"timeout_s: {result.timeout_s}",
        f"timed_out: {result.timed_out}",
        f"return_code: {result.return_code}",
        "",
        "stdout:",
        result.stdout,
        "",
        "stderr:",
        result.stderr,
        "",
        "install_hint:",
        result.install_hint or "",
        "",
    ])


def resolve_esmini_binary(binary: str | None = None, search_root: Path | None = None) -> Path | None:
    configured = binary or os.environ.get("ESMINI_BIN")
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.exists():
            return configured_path.resolve()
        resolved = shutil.which(configured)
        if resolved is not None:
            return Path(resolved).resolve()
        return None

    resolved = shutil.which("esmini")
    if resolved is not None:
        return Path(resolved).resolve()

    root = search_root or _project_root()
    for candidate_root in [
        root / "third_party" / "esmini",
        root / "tools" / "esmini",
    ]:
        candidate = _find_esmini_executable(candidate_root)
        if candidate is not None:
            return candidate
    return None


def _find_esmini_executable(search_dir: Path) -> Path | None:
    if not search_dir.exists():
        return None
    names = {"esmini", "esmini.exe"}
    for path in sorted(search_dir.rglob("*")):
        if path.name in names and path.is_file() and os.access(path, os.X_OK):
            return path.resolve()
    return None


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _install_hint() -> str:
    return (
        "Install a prebuilt esmini release with "
        "`python scripts/install_esmini.py --package bin`, set ESMINI_BIN, "
        "or add esmini to PATH."
    )


def _decode_timeout_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value
