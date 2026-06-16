from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


GITHUB_LATEST_RELEASE_API = "https://api.github.com/repos/esmini/esmini/releases/latest"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    install_dir = Path(args.install_dir)
    release = _load_release(args.version)
    asset = _select_asset(release, args.package, args.asset)
    target_dir = install_dir / release["tag_name"]
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / asset["name"]

    if not archive_path.exists() or args.force:
        print(f"Downloading {asset['name']} from {release['html_url']}")
        _download(asset["browser_download_url"], archive_path)
    else:
        print(f"Using cached archive {archive_path}")

    extract_dir = target_dir / "extracted"
    if extract_dir.exists() and args.force:
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    _extract_zip(archive_path, extract_dir)
    esmini_bin = _find_esmini_binary(extract_dir)
    if esmini_bin is None:
        print(f"Could not find an esmini executable in {extract_dir}", file=sys.stderr)
        return 1

    _make_executable(esmini_bin)
    marker = install_dir / "ESMINI_BIN"
    marker.write_text(str(esmini_bin) + "\n", encoding="utf-8")
    print(f"Installed esmini: {esmini_bin}")
    print(f"Marker file: {marker}")
    print("")
    print("Use one of:")
    print(f"  export ESMINI_BIN={esmini_bin}")
    print("  python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock")
    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download a prebuilt esmini release package.")
    parser.add_argument("--install-dir", default="third_party/esmini", help="Directory for downloaded esmini packages.")
    parser.add_argument("--version", default="latest", help="Release tag, or 'latest'. Example: v3.3.0")
    parser.add_argument("--package", choices=["bin", "demo"], default="bin", help="esmini release package family.")
    parser.add_argument("--asset", default=None, help="Exact release asset name to download.")
    parser.add_argument("--force", action="store_true", help="Re-download and re-extract the selected asset.")
    return parser.parse_args(argv)


def _load_release(version: str) -> dict[str, Any]:
    url = GITHUB_LATEST_RELEASE_API if version == "latest" else f"https://api.github.com/repos/esmini/esmini/releases/tags/{version}"
    with urllib.request.urlopen(url, timeout=30) as response:
        return json.load(response)


def _select_asset(release: dict[str, Any], package: str, requested_asset: str | None) -> dict[str, Any]:
    assets = release.get("assets", [])
    if requested_asset is not None:
        for asset in assets:
            if asset.get("name") == requested_asset:
                return asset
        raise SystemExit(f"Asset {requested_asset!r} was not found in release {release.get('tag_name')}.")

    os_key = _asset_os_key()
    prefix = f"esmini-{package}_"
    for asset in assets:
        name = asset.get("name", "")
        if name.startswith(prefix) and os_key in name.lower() and name.endswith(".zip"):
            return asset

    available = ", ".join(asset.get("name", "") for asset in assets)
    raise SystemExit(f"No {package!r} asset for {os_key!r}. Available assets: {available}")


def _asset_os_key() -> str:
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    raise SystemExit(f"Unsupported platform for automatic esmini asset selection: {platform.system()}")


def _download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, dir=destination.parent) as tmp:
        tmp_path = Path(tmp.name)
        with urllib.request.urlopen(url, timeout=120) as response:
            shutil.copyfileobj(response, tmp)
    tmp_path.replace(destination)


def _extract_zip(archive_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target = destination / member.filename
            if not target.resolve().is_relative_to(destination.resolve()):
                raise RuntimeError(f"Unsafe archive path: {member.filename}")
        archive.extractall(destination)


def _find_esmini_binary(search_dir: Path) -> Path | None:
    names = {"esmini", "esmini.exe"}
    for path in sorted(search_dir.rglob("*")):
        if path.name in names and path.is_file():
            return path.resolve()
    return None


def _make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    raise SystemExit(main())
