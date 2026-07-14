# Road Assets

ScenarioCraft currently uses project-owned canonical OpenDRIVE assets for the
supported golden families.

## Canonical Roads

| Road asset | Purpose |
| --- | --- |
| `urban_two_way_parking` | Two-way urban road with ego lane, opposing lane, parking strip, and sidewalk. |
| `multi_lane_same_direction` | Same-direction multi-lane road for cut-in behavior. |
| `urban_four_way_intersection` | Minimal four-way intersection with junction, connections, and lane links. |

These roads are intentionally representative rather than exhaustive. They are
used to keep the scenario pipeline runnable and inspectable before adding
complex imported maps.

## Current Strategy

```text
ScenarioSpec layout/world positions
-> canonical road asset binding
-> XOSC + XODR artifacts
-> preview/check/runtime evidence
```

WorldPosition remains the baseline placement mechanism. OpenDRIVE binding adds
road geometry and rendering context; it does not yet imply full LanePosition,
RoadPosition, map matching, route planning, or imported-map adaptation.

## Optional OpenDRIVE MCP Evidence

Generated-scenario workflows can ask a local `opendrive-mcp` installation to
inspect the emitted XODR artifact. This integration is disabled by default. Set
the following environment variables before starting ScenarioCraft:

```bash
export SCENARIOCRAFT_OPENDRIVE_MCP_PYTHON=/path/to/opendrive-mcp/.venv/bin/python
export SCENARIOCRAFT_OPENDRIVE_MCP_CWD=/path/to/opendrive-mcp
```

Then set `run_opendrive_mcp` to `true` in the workflow options. ScenarioCraft
calls `validate_basic`, `summarize_map`, and `list_roads`, followed by
`list_lanes` for every returned road. Detailed responses are written to
`opendrive_mcp_result.json` and a concise status is included in
`validation_report.md`.

This Phase 1 sidecar output is report-only road evidence. MCP availability or
failure does not change scenario acceptance, and MCP does not select scenario
families, modify actor placement, or replace the project-owned canonical road
assets.

## Deferred Road Scope

- generic OpenDRIVE parsing;
- complex imported map matching;
- roundabouts;
- multi-road route planning;
- CARLA-specific map adaptation;
- LanePosition/RoadPosition migration.
