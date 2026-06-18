# Step 3F OpenDRIVE Binding Plan

## Goal

Bind one project-owned, deterministic, straight OpenDRIVE road to the canonical layout-backed `pedestrian_occlusion` scenario.

This step is specifically for the current `urban_straight` / `urban_two_way_parking` case. It is not a generic map engine, OpenDRIVE editor, junction graph, route planner, or external ALKS/NCAP map adapter.

## Why OpenDRIVE Is Useful but Not a Prerequisite

The current canonical scenario is executable in esmini without OpenDRIVE because all initial actor poses and trajectories are serialized as OpenSCENARIO `WorldPosition` values. The current deterministic runtime chain is:

```text
ScenarioSpec.layout
-> ego-local x/y actor poses and paths
-> OpenSCENARIO WorldPosition
-> esmini execution
```

OpenDRIVE is still useful because it provides road surface rendering, lane semantics, road marks, sidewalk/parking context, and a future target for lane-based probes and reference-scenario compatibility. It should be added as map context first, not as a replacement for the working WorldPosition coordinate convention.

## Recommended Asset Strategy

Use both a checked-in fixture and deterministic generation:

```text
assets/roads/urban_two_way_parking.xodr
```

The checked-in `.xodr` keeps CLI, Web, tests, and artifact review simple and reproducible. A deterministic generator should also exist in the implementation so the fixture is not a hand-edited mystery asset. Tests should compare the generated canonical road with the checked-in fixture, either byte-for-byte if stable or via normalized XML if formatting is tool-dependent.

This gives ScenarioCraft a project-owned canonical road while avoiding a generic OpenDRIVE authoring subsystem.

## Canonical Road Design

The road asset must align with the current canonical coordinate convention:

```text
coordinate_frame = ego_local
road.type = urban_straight
road longitudinal direction = +x
ego lane centerline = y = 0
positive y = ego-side parking strip / curb / sidewalk
```

The OpenDRIVE road reference line should run straight along +x. Its lateral placement must be chosen so the rendered road areas line up with the existing layout y bands. The implementation should document the chosen reference-line convention and test the resulting visual/logical alignment.

Current logical bands:

```text
ego_side_sidewalk:      y [ 4.25,  6.50]  sidewalk
ego_side_parking_strip: y [ 1.75,  4.25]  parking
ego_driving_lane:       y [-1.75,  1.75]  driving, +x
center_divider:         y [-2.00, -1.75]  divider / centerline
opposing_driving_lane:  y [-5.50, -2.00]  driving, -x
opposing_side_sidewalk: y [-7.50, -5.50]  sidewalk
```

Expected OpenDRIVE mapping:

```text
ego driving lane:
  driving lane covering y near 0, width 3.5 m, travel direction +x

ego-side parking strip:
  parking or shoulder-style lane/area covering y [1.75, 4.25]

ego-side sidewalk:
  sidewalk lane/area covering y [4.25, 6.50]

center divider:
  narrow median, lane marking, or non-driving separation around y [-2.00, -1.75]

opposing driving lane:
  driving lane covering y [-5.50, -2.00], travel direction -x

opposing-side sidewalk:
  sidewalk lane/area covering y [-7.50, -5.50]
```

Perfect automatic alignment between `LayoutSpec.road_bands` and OpenDRIVE lane IDs is deferred. Phase A only needs a deterministic road whose geometry and rendered semantics match the canonical y bands closely enough to support inspection and future probes.

## XOSC Binding Strategy

The builder should bind the map through OpenSCENARIO `RoadNetwork` / `LogicFile`.

Recommended artifact behavior:

```text
assets/roads/urban_two_way_parking.xodr
-> copied into the scenario output directory
-> scenario.xosc references it with a relative LogicFile filepath
```

Example:

```xml
<RoadNetwork>
  <LogicFile filepath="urban_two_way_parking.xodr"/>
</RoadNetwork>
```

Using a relative path keeps generated artifacts portable and matches the current esmini wrapper behavior of running from the `.xosc` parent directory to preserve relative map/catalog paths. `BuildResult.xodr_path` should be populated with the copied output asset path.

The scenariogeneration builder may need a narrow library-specific API check for `RoadNetwork` / `LogicFile`. The fallback XML builder can write the element directly.

## WorldPosition Compatibility Strategy

Phase A should preserve the existing working placement:

```text
layout x/y
-> WorldPosition x/y
```

Initial actor poses and `FollowTrajectoryAction` vertices should remain `WorldPosition` for the canonical scenario. Binding OpenDRIVE must not change:

```text
ego:          (0.0,  0.0, 0.0)
parked_van:   (20.0, 3.25, 0.0)
pedestrian:   (25.0, 4.60, 0.0)
ego path:      (0.0, 0.0) -> (60.0, 0.0)
pedestrian path: (25.0, 4.60) -> (25.0, -1.00)
conflict point: (25.0, 0.0)
trigger point:  (7.0, 0.0)
```

Current WorldPosition actors remain valid after binding a map as long as the OpenDRIVE road is constructed in the same coordinate space. The first implementation should verify this with XML tests and, where local esmini is available, a no-capture runtime smoke check.

## Proposed Files for Later Implementation

Likely new files:

```text
assets/roads/urban_two_way_parking.xodr
src/scenariocraft/roads/__init__.py
src/scenariocraft/roads/urban_two_way_parking.py
tests/test_opendrive_asset.py
```

Likely modified files:

```text
src/scenariocraft/tools/scenario_builder.py
tests/test_scenario_builder.py
tests/test_template_registry.py
```

Avoid modifying:

```text
external/*
src/scenariocraft/tools/esmini_tool.py, unless a narrow xodr-path artifact field is proven necessary
src/scenariocraft/tools/layout_adapter.py, unless a narrow documentation or helper addition is necessary
src/scenariocraft/tools/preview_2d.py
```

## Proposed Tests

Focused deterministic tests:

- canonical OpenDRIVE fixture exists at `assets/roads/urban_two_way_parking.xodr`;
- deterministic generator output matches the checked-in fixture;
- canonical `pedestrian_occlusion` road metadata maps to the canonical road asset;
- `build_openscenario(...)` copies or materializes the road asset into the output directory;
- generated `scenario.xosc` contains `RoadNetwork/LogicFile` with a relative `urban_two_way_parking.xodr` filepath;
- `BuildResult.xodr_path` points to the output `.xodr`;
- layout-backed `WorldPosition` actor poses and trajectory vertices are unchanged;
- layout-free legacy specs still build with the previous fallback behavior;
- road-band sample y values are documented against the expected OpenDRIVE lane/area design;
- local esmini no-capture smoke/run is conditional and does not make the test suite require esmini.

The tests should not require OpenDRIVE map matching, `LanePosition`, or esmini availability in the default suite.

## Migration Risks

- OpenDRIVE lane side/sign conventions may invert the apparent positive-y side if the reference line is placed or oriented incorrectly.
- esmini may render the map but still report independent model-resource warnings for missing actor models.
- A map binding can give false confidence if WorldPosition actors lie visually off the intended lanes; tests must preserve exact actor coordinates and inspect alignment.
- Copying assets into outputs can introduce path drift if the XOSC uses absolute paths.
- Scenariogeneration and fallback XML builders can diverge unless both are covered by tests.
- OpenDRIVE binding might be mistaken for a trigger, motion, or capture fix; those are separate concerns.

## Model and Capture Issues

The following esmini warnings are model-resource lookup issues and should be handled separately:

```text
missing car_white.osgb
missing car_red.osgb
missing adult
```

OpenDRIVE binding does not solve those warnings. It also does not solve the independent macOS capture crash tracked after Step 3E-2. Step 3F should validate map binding and runtime behavior with no-capture execution first.

## Deferred Work

Explicitly deferred:

- `LanePosition` / `RoadPosition`;
- map matching from `LayoutSpec.road_bands` to OpenDRIVE lanes;
- curved roads;
- junctions;
- multi-road routes;
- external map adaptation;
- full OpenDRIVE-based lane probes;
- model resource packaging;
- macOS capture reliability.

## Acceptance Criteria

Step 3F implementation is complete when:

- the canonical road asset is project-owned, deterministic, and reproducible;
- generated canonical XOSC references the road via `RoadNetwork/LogicFile`;
- the `.xodr` is present with generated artifacts using a portable relative path;
- `BuildResult.xodr_path` records the bound road asset;
- existing WorldPosition actor placement and trajectories are unchanged;
- the canonical scenario still runs in esmini no-capture mode when esmini is available;
- default tests pass without requiring esmini;
- legacy layout-free specs still build;
- no generic map engine, external map dependency, lane-position migration, probes, repair, LLM, RAG, CARLA, Docker, or ASAM QC changes are introduced.
