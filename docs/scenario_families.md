# Scenario Families

ScenarioCraft uses interaction-first scenario families. A family is not one
fixed scenario file; it is a bounded, parameterized generator for many concrete
`ScenarioSpec` instances.

## Current Golden Families

| Family | Core interaction | Typical road scope |
| --- | --- | --- |
| `pedestrian_occlusion` | Pedestrian emerges from behind an occluder. | Two-way urban road with parking/sidewalk. |
| `lead_vehicle_braking` | Lead vehicle brakes while ego follows. | Same-direction lane. |
| `cut_in` | Adjacent vehicle cuts into ego lane. | Multi-lane same-direction road. |
| `crossing_vehicle` | Vehicle crosses ego path at an intersection. | Four-way intersection. |
| `oncoming_turn_across_path` | Oncoming vehicle turns across ego path. | Four-way intersection. |

## Design Rules

- Prefer a small number of mature scenario families over many fixed examples.
- Treat ODD, road topology, weather, speed, timing, and actors as parameters.
- Use deterministic defaults and seeded variation for concrete instances.
- Return `unsupported` or `clarification_required` when a request does not fit a
  registered family.

## Adding a Family

A new family should define:

- interaction type;
- supported road/topology assumptions;
- required actors and roles;
- parameter domains;
- generated layout paths and points;
- build/storyboard support;
- family checks and artifact consistency checks;
- at least one deterministic controlled case.
