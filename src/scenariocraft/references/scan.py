from __future__ import annotations

import argparse
from pathlib import Path

from scenariocraft.references.scanner import run_reference_scan


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    summary = run_reference_scan(
        root=Path(args.root),
        out_dir=Path(args.out),
        limit=args.limit,
        run_qc=args.run_qc,
        run_esmini_check=args.run_esmini,
        esmini_timeout_s=args.esmini_timeout,
        esmini_mode=args.esmini_mode,
        esmini_sim_duration_s=args.sim_duration_s,
    )
    print(f"Found .xosc files: {summary['total_found']}")
    print(f"Scanned scenarios: {summary['total_scanned']}")
    print(f"Wrote reference cards: {Path(args.out) / 'reference_cards.jsonl'}")
    print(f"Wrote compatibility summary: {Path(args.out) / 'compatibility_summary.md'}")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan reference OpenSCENARIO files for compatibility metadata.")
    parser.add_argument("--root", required=True, help="Root directory to scan recursively for .xosc files.")
    parser.add_argument("--out", required=True, help="Output directory for scan cards and summaries.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of .xosc files to scan.")
    parser.add_argument("--run-qc", action="store_true", help="Run ASAM QC when available.")
    parser.add_argument("--run-esmini", action="store_true", help="Run esmini checks when available.")
    parser.add_argument("--esmini-mode", choices=["smoke", "full"], default="smoke", help="esmini check mode for reference scans.")
    parser.add_argument(
        "--esmini-timeout",
        "--timeout-s",
        dest="esmini_timeout",
        type=float,
        default=20.0,
        help="Maximum seconds per esmini check.",
    )
    parser.add_argument("--sim-duration-s", type=float, default=3.0, help="Smoke-mode subprocess duration before classifying startup behavior.")
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(main())
