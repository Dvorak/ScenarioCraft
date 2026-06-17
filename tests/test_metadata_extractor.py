from pathlib import Path

from scenariocraft.references import extract_xosc_metadata


def test_extract_xosc_metadata_from_namespaced_fixture(tmp_path: Path) -> None:
    xosc_path = tmp_path / "reference.xosc"
    xosc_path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<OpenSCENARIO xmlns="http://example.test/xosc">
  <FileHeader revMajor="1" revMinor="2" date="2024-01-01" description="demo" author="tester"/>
  <ParameterDeclarations>
    <ParameterDeclaration name="EgoSpeed" parameterType="double" value="13.9"/>
    <ParameterDeclaration name="TriggerDistance" parameterType="double" value="18"/>
  </ParameterDeclarations>
  <CatalogLocations>
    <VehicleCatalog><Directory path="../Catalogs/Vehicles"/></VehicleCatalog>
    <PedestrianCatalog><Directory path="../Catalogs/Pedestrians"/></PedestrianCatalog>
  </CatalogLocations>
  <RoadNetwork>
    <LogicFile filepath="../Maps/town.xodr"/>
    <SceneGraphFile filepath="../Scenes/town.osgb"/>
  </RoadNetwork>
  <Entities>
    <ScenarioObject name="ego"/>
    <ScenarioObject name="pedestrian"/>
  </Entities>
  <Storyboard>
    <Story name="story">
      <Act name="act">
        <ManeuverGroup name="group">
          <Maneuver name="maneuver">
            <Event name="event">
              <StartTrigger>
                <ConditionGroup>
                  <Condition name="condition"/>
                </ConditionGroup>
              </StartTrigger>
            </Event>
          </Maneuver>
        </ManeuverGroup>
      </Act>
    </Story>
  </Storyboard>
</OpenSCENARIO>
""",
        encoding="utf-8",
    )

    metadata = extract_xosc_metadata(xosc_path)

    assert metadata.file_exists is True
    assert metadata.parse_success is True
    assert metadata.open_scenario_version == "1.2"
    assert metadata.file_header["description"] == "demo"
    assert metadata.logic_file_paths == ["../Maps/town.xodr"]
    assert metadata.scene_graph_file_paths == ["../Scenes/town.osgb"]
    assert metadata.catalog_locations == ["../Catalogs/Vehicles", "../Catalogs/Pedestrians"]
    assert metadata.parameter_names == ["EgoSpeed", "TriggerDistance"]
    assert metadata.scenario_object_names == ["ego", "pedestrian"]
    assert metadata.has_storyboard is True
    assert metadata.parameter_count == 2
    assert metadata.scenario_object_count == 2
    assert metadata.maneuver_count == 1
    assert metadata.event_count == 1
    assert metadata.condition_count == 1


def test_extract_xosc_metadata_reports_parse_failure(tmp_path: Path) -> None:
    xosc_path = tmp_path / "broken.xosc"
    xosc_path.write_text("<OpenSCENARIO><FileHeader></OpenSCENARIO>", encoding="utf-8")

    metadata = extract_xosc_metadata(xosc_path)

    assert metadata.file_exists is True
    assert metadata.parse_success is False
    assert metadata.parse_error
