from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MARKER = Path("third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = Path(args.project_root).resolve()
    marker_arg = Path(args.marker)
    marker_path = (project_root / marker_arg).resolve() if not marker_arg.is_absolute() else marker_arg.resolve()

    if not args.skip_install:
        command = _install_command(project_root, args)
        print("Installing ASAM QC dependencies:")
        print("  " + " ".join(command))
        completed = subprocess.run(command, cwd=project_root, check=False)
        if completed.returncode != 0:
            print("ASAM QC dependency installation failed.", file=sys.stderr)
            return completed.returncode

    binary_path = _resolve_qc_binary(args.binary)
    if binary_path is None:
        print("Could not find `qc_openscenario` after installation.", file=sys.stderr)
        print("Try rerunning without --skip-install, or set ASAM_QC_OPENSCENARIOXML_BIN manually.", file=sys.stderr)
        return 1

    marker_path.parent.mkdir(parents=True, exist_ok=True)
    marker_path.write_text(str(binary_path) + "\n", encoding="utf-8")
    print(f"Resolved ASAM QC OpenSCENARIO checker: {binary_path}")
    print(f"Marker file: {marker_path}")
    print("")
    print("Use one of:")
    print(f"  export ASAM_QC_OPENSCENARIOXML_BIN={binary_path}")
    print(f'  export ASAM_QC_OPENSCENARIOXML_BIN="$(cat {marker_path})"')
    print("")
    print("Verify with:")
    print('  "$ASAM_QC_OPENSCENARIOXML_BIN" --help')
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install and locate the ASAM OpenSCENARIO XML QC checker.")
    parser.add_argument("--project-root", default=".", help="ScenarioCraft repository root.")
    parser.add_argument("--marker", default=str(DEFAULT_MARKER), help="Marker file that stores the resolved checker path.")
    parser.add_argument("--binary", default=None, help="Explicit qc_openscenario executable path.")
    parser.add_argument("--skip-install", action="store_true", help="Only locate and record an already-installed checker.")
    parser.add_argument(
        "--installer",
        choices=["uv", "pip"],
        default="uv",
        help="Installer to use for the project qc extra.",
    )
    return parser.parse_args(argv)


def _install_command(project_root: Path, args: argparse.Namespace) -> list[str]:
    if args.installer == "uv":
        uv = Path(sys.executable).with_name("uv")
        uv_binary = str(uv if uv.exists() else "uv")
        command = [uv_binary, "sync", "--extra", "qc"]
        return command
    return [sys.executable, "-m", "pip", "install", "-e", f"{project_root}[qc]", "--no-build-isolation"]


def _resolve_qc_binary(binary: str | None) -> Path | None:
    candidates: list[str] = []
    if binary:
        candidates.append(binary)
    env_binary = os.environ.get("ASAM_QC_OPENSCENARIOXML_BIN")
    if env_binary:
        candidates.append(env_binary)
    candidates.append("qc_openscenario")

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return Path(resolved).resolve()
        path = Path(candidate).expanduser()
        if path.exists() and path.is_file():
            return path.resolve()

    sibling = Path(sys.executable).with_name("qc_openscenario")
    if sibling.exists():
        return sibling.resolve()
    return None


if __name__ == "__main__":
    raise SystemExit(main())
