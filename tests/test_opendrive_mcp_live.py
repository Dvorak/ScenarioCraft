from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

import pytest

from scenariocraft.external_tools import run_opendrive_mcp_sidecar


pytestmark = pytest.mark.skipif(
    os.environ.get("SCENARIOCRAFT_OPENDRIVE_MCP_LIVE") != "1",
    reason="set SCENARIOCRAFT_OPENDRIVE_MCP_LIVE=1 to run the real MCP acceptance",
)


def test_all_canonical_roads_pass_real_opendrive_mcp_acceptance() -> None:
    road_paths = sorted(Path("assets/roads/canonical").glob("*.xodr"))
    assert road_paths, "canonical OpenDRIVE corpus must not be empty"

    results: list[dict[str, object]] = []
    for road_path in road_paths:
        evidence = run_opendrive_mcp_sidecar(road_path)

        assert evidence.available is True, evidence.error_message
        assert evidence.passed is True, evidence.error_message
        assert evidence.backend_name == "libOpenDRIVE"
        assert evidence.file_path == str(road_path.resolve())
        assert [tool.tool_name for tool in evidence.tools[:3]] == [
            "validate_basic",
            "summarize_map",
            "list_roads",
        ]
        assert all(tool.ok for tool in evidence.tools)

        validation_payload = evidence.tools[0].payload
        roads_payload = evidence.tools[2].payload
        assert validation_payload is not None
        assert validation_payload.get("valid") is True
        assert roads_payload is not None
        roads = roads_payload.get("roads")
        assert isinstance(roads, tuple)
        road_ids = [
            road.get("road_id")
            for road in roads
            if isinstance(road, Mapping)
        ]
        lane_calls = evidence.tools[3:]
        assert [tool.arguments.get("road_id") for tool in lane_calls] == road_ids

        results.append(evidence.to_dict())

    output_value = os.environ.get("SCENARIOCRAFT_OPENDRIVE_MCP_EVIDENCE_PATH")
    if output_value:
        output_path = Path(output_value).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "canonical_road_count": len(results),
                    "results": results,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
