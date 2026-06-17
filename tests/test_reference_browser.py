from pathlib import Path

from scenariocraft.references.browser import discover_external_scenarios


def test_discover_external_scenarios_classifies_sources(tmp_path: Path) -> None:
    external_root = tmp_path / "external"
    ncap = external_root / "OSC-NCAP-scenarios" / "a" / "test.xosc"
    alks = external_root / "sl-3-1-osc-alks-scenarios" / "b" / "test.xosc"
    other = external_root / "other" / "test.xosc"
    for path in (ncap, alks, other):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<OpenSCENARIO />", encoding="utf-8")

    options = discover_external_scenarios(external_root)

    by_relative_path = {option.relative_path: option for option in options}
    assert by_relative_path["OSC-NCAP-scenarios/a/test.xosc"].source == "OSC-NCAP-scenarios"
    assert by_relative_path["sl-3-1-osc-alks-scenarios/b/test.xosc"].source == "ALKS scenarios"
    assert by_relative_path["other/test.xosc"].source == "Other external scenarios"
    assert by_relative_path["OSC-NCAP-scenarios/a/test.xosc"].label == "OSC-NCAP-scenarios/a/test.xosc"
    assert by_relative_path["OSC-NCAP-scenarios/a/test.xosc"].xosc_path == ncap


def test_discover_external_scenarios_returns_empty_for_empty_or_missing_root(tmp_path: Path) -> None:
    empty_root = tmp_path / "external"
    empty_root.mkdir()

    assert discover_external_scenarios(empty_root) == []
    assert discover_external_scenarios(tmp_path / "missing") == []
