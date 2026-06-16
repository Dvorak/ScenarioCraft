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
    working_dir: str | None
    return_code: int | None
    stdout: str
    stderr: str
    executed: bool | None
    error_message: str | None
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
    working_dir: Path | None = None,
    required: bool = False,
    binary: str | None = None,
    timeout_s: float = 20.0,
) -> EsminiResult:
    resolved_xosc_path = Path(xosc_path).expanduser().resolve()
    resolved_working_dir = Path(working_dir).expanduser().resolve() if working_dir else resolved_xosc_path.parent
    result_working_dir = _display_path(resolved_working_dir)
    command_xosc_path = os.path.relpath(resolved_xosc_path, resolved_working_dir)
    resolved_binary = resolve_esmini_binary(binary)
    command_binary = str(resolved_binary or binary or os.environ.get("ESMINI_BIN", "esmini"))
    command = [command_binary, "--osc", command_xosc_path, "--headless", "--quit_at_end", "--disable_log"]
    if resolved_binary is None:
        result = EsminiResult(
            esmini_available=False,
            command=command,
            working_dir=result_working_dir,
            return_code=None,
            stdout="",
            stderr="esmini was not found.",
            executed=None,
            error_message="esmini was not found.",
            playback_path=None,
            required=required,
            install_hint=_install_hint(),
            timeout_s=timeout_s,
            timed_out=False,
        )
    else:
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_s,
                cwd=resolved_working_dir,
            )
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                executed=completed.returncode == 0,
                error_message=None if completed.returncode == 0 else f"esmini exited with code {completed.returncode}.",
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            stderr = _decode_timeout_output(exc.stderr) or f"esmini timed out after {timeout_s:g} seconds."
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=None,
                stdout=_decode_timeout_output(exc.stdout),
                stderr=stderr,
                executed=False,
                error_message=stderr,
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                timed_out=True,
            )
        except OSError as exc:
            result = EsminiResult(
                esmini_available=True,
                command=command,
                working_dir=result_working_dir,
                return_code=None,
                stdout="",
                stderr=str(exc),
                executed=False,
                error_message=str(exc),
                playback_path=None,
                required=required,
                install_hint=None,
                timeout_s=timeout_s,
                timed_out=False,
            )
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "esmini_log.txt").write_text(_format_log(result), encoding="utf-8")
        (output_dir / "esmini_stdout.txt").write_text(result.stdout, encoding="utf-8")
        (output_dir / "esmini_stderr.txt").write_text(result.stderr, encoding="utf-8")
    return result


def _format_log(result: EsminiResult) -> str:
    return "\n".join([
        f"command: {' '.join(result.command)}",
        f"working_dir: {result.working_dir}",
        f"available: {result.esmini_available}",
        f"required: {result.required}",
        f"timeout_s: {result.timeout_s}",
        f"timed_out: {result.timed_out}",
        f"return_code: {result.return_code}",
        f"executed: {result.executed}",
        f"error_message: {result.error_message or ''}",
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


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path)


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
