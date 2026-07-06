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

## Deferred Road Scope

- generic OpenDRIVE parsing;
- complex imported map matching;
- roundabouts;
- multi-road route planning;
- CARLA-specific map adaptation;
- LanePosition/RoadPosition migration.
