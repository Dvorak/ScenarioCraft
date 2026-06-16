from pathlib import Path

from scenariocraft.generators import MockScenarioGenerator
from scenariocraft.tools import build_openscenario, generate_validation_report, validate_semantics
from scenariocraft.tools.asam_qc_tool import AsamQcResult
from scenariocraft.tools.esmini_tool import EsminiResult


def test_report_includes_missing_tool_warnings(tmp_path: Path) -> None:
    spec = MockScenarioGenerator().generate_spec("scenario text")
    build_result = build_openscenario(spec, tmp_path)
    qc_result = AsamQcResult(False, ["asam-qc-openscenarioxml", "scenario.xosc"], None, "", "", None)
    esmini_result = EsminiResult(False, ["esmini", "--osc", "scenario.xosc"], None, "", "", None, None)

    report_path = generate_validation_report(
        "scenario text",
        spec,
        build_result,
        qc_result,
        esmini_result,
        validate_semantics(spec),
        tmp_path,
    )

    report = report_path.read_text(encoding="utf-8")
    assert "ASAM OpenSCENARIO XML checker was not found" in report
    assert "esmini was not found" in report
    assert "rainy_pedestrian_occlusion" in report
