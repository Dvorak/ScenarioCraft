from __future__ import annotations

import argparse
from pathlib import Path

from scenariocraft.tooling import install_asamqc, install_esmini


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    project_root = Path(args.project_root).resolve()

    if not args.skip_esmini:
        exit_code = install_esmini.main([
            "--install-dir",
            str(project_root / "third_party/esmini"),
            "--package",
            args.esmini_package,
        ])
        if exit_code != 0:
            return exit_code

    if not args.skip_asam_qc:
        exit_code = install_asamqc.main(["--project-root", str(project_root)])
        if exit_code != 0:
            return exit_code

    _print_next_steps(project_root)
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Configure optional ScenarioCraft local tools.")
    parser.add_argument("--project-root", default=".", help="ScenarioCraft repository root.")
    parser.add_argument("--skip-esmini", action="store_true", help="Do not install or locate esmini.")
    parser.add_argument("--skip-asam-qc", action="store_true", help="Do not install or locate ASAM QC.")
    parser.add_argument("--esmini-package", choices=["bin", "demo"], default="bin", help="esmini release package family.")
    return parser.parse_args(argv)


def _print_next_steps(project_root: Path) -> None:
    esmini_marker = project_root / "third_party/esmini/ESMINI_BIN"
    asam_marker = project_root / "third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN"
    print("")
    print("ScenarioCraft setup is ready.")
    print("")
    print("For this shell, run:")
    print(f'  export ESMINI_BIN="$(cat {esmini_marker})"')
    print(f'  export ASAM_QC_OPENSCENARIOXML_BIN="$(cat {asam_marker})"')
    print("")
    print("Then start the Web UI:")
    print("  .venv/bin/just web")
    print("  open http://localhost:3000")


if __name__ == "__main__":
    raise SystemExit(main())
