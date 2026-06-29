from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path


NCAP_SOURCE = "OSC-NCAP-scenarios"
ALKS_SOURCE = "ALKS scenarios"
OTHER_SOURCE = "Other external scenarios"


@dataclass(frozen=True)
class ReferenceScenarioOption:
    source: str
    label: str
    xosc_path: Path
    relative_path: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["xosc_path"] = str(self.xosc_path)
        return data


def discover_external_scenarios(external_root: Path) -> list[ReferenceScenarioOption]:
    root = Path(external_root)
    if not root.exists():
        return []

    options = [
        _to_option(root, xosc_path)
        for xosc_path in sorted(path for path in root.rglob("*.xosc") if path.is_file())
    ]
    return sorted(options, key=lambda option: (option.source, option.relative_path.lower()))


def _to_option(external_root: Path, xosc_path: Path) -> ReferenceScenarioOption:
    relative_path = _relative_label(external_root, xosc_path)
    return ReferenceScenarioOption(
        source=classify_reference_source(xosc_path),
        label=relative_path,
        xosc_path=xosc_path,
        relative_path=relative_path,
    )


def classify_reference_source(path: Path) -> str:
    parts = set(path.parts)
    if NCAP_SOURCE in parts:
        return NCAP_SOURCE
    if "sl-3-1-osc-alks-scenarios" in parts:
        return ALKS_SOURCE
    return OTHER_SOURCE


def _relative_label(external_root: Path, xosc_path: Path) -> str:
    try:
        return xosc_path.relative_to(external_root).as_posix()
    except ValueError:
        return xosc_path.name
