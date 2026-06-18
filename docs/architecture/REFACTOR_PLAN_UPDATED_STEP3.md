# Refactor Plan

This plan stages the migration toward the template/probe/repair architecture without rewriting the project in one step. Each step should preserve the current CLI, generated Web demo, esmini wrappers, and reference scanner unless that step explicitly says otherwise.

Baseline commands for every step:

```bash
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

Use the active virtual environment's Python executable when appropriate.

> **Revision note — Step 3 expansion:** Steps 1 and 2 are completed. Step 3 has been expanded into Step 3A, Step 3B, and Step 3C after discovering that actor poses and footprints alone do not encode the road topology needed for a realistic parked-van pedestrian-occlusion scenario. This update preserves the earlier migration plan while making road bands, parking-strip semantics, sidewalk origin, and builder alignment explicit.


## Step 1: ScenarioTemplate Registry

Goal:

Introduce a deterministic template abstraction and registry while keeping `MockScenarioGenerator` behavior stable.

Files likely to change:

- `src/scenariocraft/templates/__init__.py`
- `src/scenariocraft/templates/base.py`
- `src/scenariocraft/templates/registry.py`
- `src/scenariocraft/templates/pedestrian_occlusion.py`
- `src/scenariocraft/generators/mock_generator.py`
- `tests/test_template_registry.py`
- `tests/test_mock_generator.py`

Files that should not change:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/tools/asam_qc_tool.py`
- `src/scenariocraft/references/*`
- `external/*`
- OpenSCENARIO builder behavior unless a test reveals an accidental mismatch.

Tests to add/update:

- Registry contains `pedestrian_occlusion`.
- Template exposes `template_id`, `description`, `required_actors`, `default_parameters`, and `supported_operations`.
- Template instantiation returns a valid `ScenarioSpec`.
- `MockScenarioGenerator` still returns the same scenario name, type, actors, trigger, and criticality as before.

Acceptance criteria:

- `MockScenarioGenerator().generate_spec(...)` delegates to the registered template.
- Existing CLI output still builds and validates.
- No LLM, RAG, CARLA, Docker, or CAMEL is introduced.

Risks:

- Over-generalizing template APIs too early.
- Accidentally changing generated XML due to changed actor IDs or trigger values.

Commands to run:

```bash
python -m pytest tests/test_template_registry.py tests/test_mock_generator.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 2: layout/spatial_relations in ScenarioSpec

Goal:

Add explicit typed layout and spatial relations to `ScenarioSpec` while preserving backward-compatible JSON loading.

Files likely to change:

- `src/scenariocraft/schemas/scenario_spec.py`
- `src/scenariocraft/schemas/__init__.py`
- `tests/test_scenario_spec.py`
- Template files added in Step 1.

Possible new file if the schema grows:

- `src/scenariocraft/schemas/layout_spec.py`

Files that should not change:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/references/*`
- `src/scenariocraft/web/app.py`, except later display changes.
- `external/*`

Tests to add/update:

- `ScenarioSpec` serializes and deserializes with `layout`.
- `ScenarioSpec` serializes and deserializes with `spatial_relations`.
- Existing JSON without layout still loads.
- Invalid duplicate actor IDs still fail as before.

Acceptance criteria:

- `layout` and `spatial_relations` are optional.
- Coordinate convention is represented or documented in the layout object.
- Existing CLI and tests pass with old and new specs.

Risks:

- Breaking saved `scenario_spec.json` compatibility.
- Encoding too much OpenSCENARIO-specific data into the template-level layout.

Commands to run:

```bash
python -m pytest tests/test_scenario_spec.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 3: Explicit Spatial Semantics for `pedestrian_occlusion`

### Why Step 3 is split

Step 1 established the template registry and Step 2 established optional typed layout and spatial-relation schemas. Step 3 turns those schemas into a usable, trustworthy spatial source of truth.

This cannot be treated as only a preview improvement. A realistic pedestrian-occlusion scenario requires:

```text
template parameters
-> derived road cross-section and actor geometry
-> ScenarioSpec.layout / spatial_relations
-> preview / future probes / future repair
```

The step is split to preserve compatibility and isolate risks:

```text
Step 3A: Actor geometry, footprints, pedestrian path, and layout-first preview
Step 3B: Road cross-section, lane topology, parking strip, sidewalk, and road-band-aware preview
Step 3C: Conditional builder alignment with the new layout
```

### Step 3A: Parameterized actor geometry and layout-first preview

**Status:** completed baseline; preserve it while implementing Step 3B.

Goal:

Make `pedestrian_occlusion` emit explicit layout, actor footprints, pedestrian path, named points, and spatial relations. The preview uses layout when present and retains a legacy fallback when layout is absent.

Expected template outputs:

```text
layout.coordinate_frame = ego_local
layout.actor_poses:
  ego
  parked_van
  pedestrian

layout.actor_footprints:
  ego
  parked_van
  pedestrian

layout.paths:
  pedestrian_crossing_path

layout.points:
  conflict_point
  trigger_point

spatial_relations:
  occludes
  emerges_from_behind
  path_intersects
  ahead_of
  trigger_before_conflict
```

Step 3A compatibility rules:

- `layout` remains optional.
- `actor_footprints` remains optional.
- Existing layout-free JSON remains valid.
- Existing preview fallback remains valid.
- No probe, PatchSpec, LLM, RAG, esmini, ASAM QC, or reference-scanner changes are introduced.

### Step 3B: Road Cross-Section and Lane Topology

**Status:** next implementation step.

Goal:

Add a minimal road-cross-section representation to `ScenarioSpec.layout`, make the canonical `pedestrian_occlusion` template emit it, and make the preview render it from the layout.

This step resolves a critical domain-model gap: actor poses and footprints alone do not state whether the ego is in a travel lane, whether the van is parked legally in a curbside strip, or whether the pedestrian starts on a sidewalk.

The canonical scenario must no longer be interpreted merely as "two lanes." Its first ODD is explicitly:

```text
urban two-way road
one travel lane in each direction
ego-side curbside parking strip
ego-side sidewalk

ego drives in +x direction
ego lane centerline is y = 0
positive y is the ego-side curb / parking / sidewalk side
```

The intended transverse road order is:

```text
positive y
  ego-side sidewalk
  ego-side parking strip
  ego travel lane (+x)
  center divider / centerline
  opposing travel lane (-x)
  opposing-side sidewalk
negative y
```

Important terminology:

```text
two travel lanes total
= one driving lane in each direction

two same-direction lanes
= a different topology, typically for cut-in / highway merge templates

one travel lane + parking strip
= an urban parked-vehicle occlusion layout; the parking strip is not a driving lane
```

#### Step 3B schema addition

Files likely to change:

- `src/scenariocraft/schemas/scenario_spec.py`
- `src/scenariocraft/schemas/__init__.py`
- `tests/test_scenario_spec.py`

Add a minimal typed road-band schema consistent with the current dataclass and serialization style:

```python
@dataclass(frozen=True)
class RoadBandSpec:
    id: str
    kind: str
    y_min_m: float
    y_max_m: float
    travel_direction: str | None = None
```

Supported first MVP `kind` values:

```text
sidewalk
parking_strip
driving_lane
center_divider
shoulder
```

Additively extend `LayoutSpec`:

```python
road_bands: tuple[RoadBandSpec, ...] = ()
```

Backward compatibility:

- Existing `ScenarioSpec` without `layout` remains valid.
- Existing `LayoutSpec` without `road_bands` remains valid.
- Existing JSON without `road_bands` deserializes to an empty tuple.
- Legacy preview fallback remains valid.

Minimal validation:

- non-empty road-band id;
- supported kind;
- finite y boundaries;
- `y_min_m < y_max_m`;
- `travel_direction` is `+x`, `-x`, or `None` when it is validated.

Do not add an OpenDRIVE lane graph, map matcher, junction topology, or generic road-geometry engine.

#### Step 3B canonical road bands

The first canonical pedestrian-occlusion layout should use the following ego-local y-ranges unless a documented existing builder convention requires a compatible adjustment:

```text
ego-side sidewalk:
  y = [4.25, 6.50]

ego-side parking strip:
  y = [1.75, 4.25]

ego travel lane:
  y = [-1.75, 1.75]
  travel direction = +x

center divider:
  y = [-2.00, -1.75]

opposing travel lane:
  y = [-5.50, -2.00]
  travel direction = -x

opposing-side sidewalk:
  y = [-7.50, -5.50]
```

#### Step 3B canonical actor and path placement

The template must derive positions from named semantic parameters rather than scatter magic coordinates through the generator, preview, builder, or Web UI.

Recommended default parameters:

```text
ego:
  pose = (0.0, 0.0, 0.0)
  footprint = 4.6 m x 1.9 m

parked van:
  footprint = 5.3 m x 2.0 m
  pose = (20.0, 3.25, 0.0)

pedestrian:
  footprint = 0.6 m x 0.6 m
  initial pose = (25.0, 4.60, 0.0)

pedestrian crossing path:
  start = (25.0, 4.60)
  end = (25.0, -1.00)

conflict point:
  (25.0, 0.0)

trigger point:
  (7.0, 0.0)
```

The canonical geometry must satisfy all of these invariants:

```text
ego footprint is fully inside ego travel lane

parked van footprint is fully inside ego-side parking strip

pedestrian initial footprint is fully inside ego-side sidewalk

pedestrian crossing path:
  starts on ego-side sidewalk
  crosses the parking strip
  crosses the ego lane
  does not intersect the parked van footprint

minimum path-to-van-footprint clearance >= configured minimum clearance

conflict point lies on the pedestrian crossing path and inside ego travel lane

trigger point lies inside ego travel lane and is longitudinally before conflict point

ego-to-pedestrian-start line of sight intersects the parked van footprint
```

The final values may vary only where the template documents and tests an equivalent geometry. A preview-only visual offset is not an acceptable fix.

#### Step 3B template and preview changes

Files likely to change:

- `src/scenariocraft/templates/pedestrian_occlusion.py`
- `src/scenariocraft/tools/preview_2d.py`
- `tests/test_template_registry.py`
- `tests/test_preview_2d.py`

Template responsibilities:

```text
derive road_bands
derive actor poses
derive actor footprints
derive pedestrian path
derive conflict and trigger points
emit spatial relations
```

Preview responsibilities:

```text
if layout and road_bands are present:
  render road bands from layout.road_bands
  render lane boundaries from band boundaries
  render direction cues for +x and -x driving lanes
  render actors, footprints, paths, points, labels from layout only
  derive plot limits from road bands, geometry, and margins

otherwise:
  retain legacy preview fallback
```

The preview must not maintain a second hidden set of lane, parking-strip, sidewalk, van, or pedestrian placement constants for layout-backed specs.

#### Step 3B tests

Tests to add or update:

```text
RoadBandSpec round-trips through ScenarioSpec JSON.

Legacy layout without road_bands remains valid.
Legacy ScenarioSpec without layout remains valid.

The pedestrian-occlusion layout contains:
- ego-side sidewalk
- ego-side parking strip
- ego driving lane
- center divider
- opposing driving lane

Ego pose / footprint belongs to ego lane.
Parked-van footprint belongs fully to parking strip.
Pedestrian initial footprint belongs to ego-side sidewalk.
Conflict point and trigger point belong to ego lane.
Pedestrian crossing path starts in sidewalk and crosses ego lane.
Pedestrian crossing path does not intersect parked-van footprint.
Line of sight from ego to pedestrian start intersects parked-van footprint.

Layout-backed preview writes a non-empty PNG.
Legacy layout-free preview fallback writes a non-empty PNG.
```

Acceptance criteria:

- Road topology is represented in `ScenarioSpec.layout`, not only drawn in preview.
- The normal mock scenario emits road bands, layout, actor footprints, paths, points, and relations.
- The van is visibly and geometrically in the parking strip, not in the ego lane.
- The pedestrian begins on the sidewalk and crosses into the ego lane.
- The path does not overlap the van footprint.
- Existing CLI pipeline remains successful.

Risks:

- Introducing road-band constants in preview instead of template/layout.
- Confusing a parking strip with an additional travel lane.
- Overfitting the first road cross-section so it cannot later serve one-way roads or cut-in templates.
- Accidentally changing builder pose behavior while only improving layout and preview.

Commands to run:

```bash
python -m pytest   tests/test_scenario_spec.py   tests/test_template_registry.py   tests/test_preview_2d.py   tests/test_mock_generator.py

python -m pytest

python -m scenariocraft.main   --input examples/pedestrian_occlusion.txt   --out outputs/demo_road_topology   --provider mock
```

Inspect:

```text
outputs/demo_road_topology/scenario_spec.json
outputs/demo_road_topology/preview_2d.png
outputs/demo_road_topology/scenario.xosc
outputs/demo_road_topology/validation_report.md
```

### Step 3C: Builder Alignment with Layout (Conditional)

**Status:** perform only after Step 3B implementation and review.

Goal:

Determine whether the OpenSCENARIO builder's initial actor poses and road assumptions match the template's canonical layout and road bands.

Files to inspect first:

- `src/scenariocraft/tools/scenario_builder.py`
- builder-specific tests
- generated `scenario.xosc`
- `outputs/demo_road_topology/scenario_spec.json`

Decision rule:

```text
If builder initial poses are already aligned with the template layout:
  document alignment and proceed to Step 4.

If builder initial poses are partially aligned:
  document exact mismatches and implement a narrow Step 3C change.

If builder initial poses diverge:
  add a dedicated builder-layout adapter or shared layout helper before Step 4.
```

Possible files if implementation is required:

- `src/scenariocraft/tools/scenario_builder.py`
- narrowly scoped shared layout helper only if necessary
- `tests/test_scenario_builder.py`
- template tests affected by verified alignment behavior

Files that should not change unless required by a narrow compatibility fix:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/tools/asam_qc_tool.py`
- `src/scenariocraft/references/*`
- `src/scenariocraft/web/app.py`
- `external/*`

Acceptance criteria:

- Builder placement does not contradict the canonical layout.
- Alignment status is documented honestly: aligned, partially aligned, or divergent.
- No broader map, OpenDRIVE, or road-network refactor is introduced.
- Existing generated scenario continues to build and run through the normal CLI pipeline.

Implemented Step 3D only.
Movement Primitive
Selected OpenSCENARIO FollowTrajectoryAction with an inline Trajectory containing a Polyline of WorldPosition vertices. It fits the current builder because both the scenariogeneration path and fallback XML path already operate in WorldPosition coordinates, and scenariogeneration.xosc supports FollowTrajectoryAction, Trajectory, and Polyline.
Files Changed
[layout_adapter.py (line 1)](/Users/zhang/ScenarioCraft-Agent/src/scenariocraft/tools/layout_adapter.py:1)
[scenario_builder.py (line 1)](/Users/zhang/ScenarioCraft-Agent/src/scenariocraft/tools/scenario_builder.py:1)
[test_scenario_builder.py (line 1)](/Users/zhang/ScenarioCraft-Agent/tests/test_scenario_builder.py:1)
Mapping Added
Added layout_path_to_builder_trajectory(...), which maps PathSpec points from ego_local / urban_straight directly to timed WorldPosition trajectory vertices. Timing is deterministic: cumulative segment distance divided by traversal speed.
Alignment
For the canonical scenario, XOSC now has:
pedestrian initial pose: (25.0, 4.6, 0.0)
trajectory vertices:time 0.0: (25.0, 4.6, 0.0)
time 3.733333333333333: (25.0, -1.0, 0.0)

That matches layout.paths["pedestrian_crossing_path"].
Speed Source
Traversal speed comes from pedestrian.speed_mps; if absent, it falls back narrowly to 1.5 m/s.
Legacy Fallback
Layout-free or path-free specs still use the previous speed-action-only pedestrian behavior. They do not fail just because no layout path exists.
Validation
Required focused suite: 36 passed
Full suite: 72 passed
CLI smoke passed:
.venv/bin/python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo_path_aligned --provider mock
outputs/demo_path_aligned/scenario.xosc contains the aligned FollowTrajectoryAction, and the validation report passed with ASAM QC/esmini return code 0.
The full crossing path is now aligned for the current layout-backed pedestrian occlusion template. Deferred to Step 4: ProbeResult framework and template-aware geometric probes.

### Step 3F: Canonical OpenDRIVE Binding for `urban_two_way_parking`

Goal:

Bind one project-owned, deterministic, straight OpenDRIVE road to the canonical layout-backed `pedestrian_occlusion` scenario while preserving the current `WorldPosition` actor poses and trajectories.

Design plan:

- See `docs/architecture/STEP_3F_OPENDRIVE_BINDING_PLAN.md`.
- OpenDRIVE is useful for road rendering, lane semantics, and future lane/map probes, but it is not a prerequisite for the current no-road `WorldPosition` runtime.
- Recommended asset strategy is both generated and checked in: `assets/roads/urban_two_way_parking.xodr` should be reproducible from a deterministic project-owned generator and committed as the canonical fixture.
- The builder should copy/materialize the road asset into the scenario output directory and reference it with `RoadNetwork/LogicFile filepath="urban_two_way_parking.xodr"`.
- Phase A must keep `layout x/y -> WorldPosition x/y`; do not migrate initial poses or trajectories to `LanePosition` / `RoadPosition`.
- The OpenDRIVE cross-section should align with the existing `LayoutSpec.road_bands`: ego-side sidewalk, ego-side parking strip, ego driving lane, center divider, opposing driving lane, and opposing-side sidewalk.
- Missing esmini actor model warnings and macOS capture reliability remain separate issues.

Files likely to change during implementation:

- `assets/roads/urban_two_way_parking.xodr`
- `src/scenariocraft/roads/__init__.py`
- `src/scenariocraft/roads/urban_two_way_parking.py`
- `src/scenariocraft/tools/scenario_builder.py`
- `tests/test_opendrive_asset.py`
- `tests/test_scenario_builder.py`
- `tests/test_template_registry.py`

Files that should not change:

- `external/*`
- generic reference scanner behavior
- probe / repair / LLM / RAG modules
- CARLA, Docker, ASAM QC integrations

Acceptance criteria:

- Generated canonical XOSC includes a relative `RoadNetwork/LogicFile` reference.
- Generated artifacts include the canonical `.xodr`.
- `BuildResult.xodr_path` points to the generated/bound road asset.
- Current layout-backed `WorldPosition` poses and `FollowTrajectoryAction` vertices remain unchanged.
- Legacy layout-free specs continue to build.
- Default tests pass without requiring esmini.
- A local esmini no-capture run still executes the canonical scenario when esmini is available.

Deferred:

- `LanePosition` / `RoadPosition`
- map matching
- curved roads
- junctions
- multi-road routes
- external map adaptation
- full OpenDRIVE-based lane probes

## Step 4: ProbeResult Framework

Goal:

Introduce deterministic probe results without removing the current semantic validator.

Files likely to change:

- `src/scenariocraft/schemas/probe_result.py` or `src/scenariocraft/probes/base.py`
- `src/scenariocraft/probes/__init__.py`
- `src/scenariocraft/tools/semantic_validator.py`
- `src/scenariocraft/tools/report_tool.py`
- `tests/test_probe_result.py`
- `tests/test_semantic_validator.py`
- `tests/test_report_tool.py`

Files that should not change:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/references/*`
- XML builder internals.
- `external/*`

Tests to add/update:

- `ProbeResult` serializes with `name`, `passed`, `severity`, `message`, `measured`, and `suggested_operations`.
- Semantic validation can be adapted into probe-like output or reports can accept both.
- Reports include probe output when provided.

Acceptance criteria:

- Probes are deterministic and independent of esmini, ASAM QC, LLMs, and external repos.
- Existing `validate_semantics()` callers keep working.
- Reports remain readable.

Risks:

- Duplicating semantic checks and probes without a clear migration path.
- Adding too broad a probe framework before the first template probes exist.

Commands to run:

```bash
python -m pytest tests/test_probe_result.py tests/test_semantic_validator.py tests/test_report_tool.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 5: pedestrian_occlusion Probes

Goal:

Add template-aware probes for the first scenario pattern.

Files likely to change:

- `src/scenariocraft/probes/pedestrian_occlusion.py`
- `src/scenariocraft/probes/__init__.py`
- `src/scenariocraft/tools/semantic_validator.py`
- `src/scenariocraft/tools/report_tool.py`
- `src/scenariocraft/web/view_models.py`
- `src/scenariocraft/web/app.py` only to display probe summaries.
- `tests/test_pedestrian_occlusion_probes.py`
- `tests/test_report_tool.py`

Files that should not change:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/references/*`
- ASAM QC wrapper.
- `external/*`

Tests to add/update:

- Passing mock scenario passes all first probes.
- Missing pedestrian fails `pedestrian_exists`.
- Missing occluder fails `occluder_exists`.
- Wrong pedestrian side fails `pedestrian_starts_on_occluded_side`.
- Non-intersecting path fails `pedestrian_path_intersects_ego_path`.
- Low criticality creates a warning with measured arrival-time gap.

Acceptance criteria:

- Probe results contain measured values.
- Probe failures include suggested operations compatible with future PatchSpec.
- Reports and Web UI can show probe state without becoming noisy.

Risks:

- Probe thresholds may be too brittle.
- Layout math may overfit the first coordinate convention.

Commands to run:

```bash
python -m pytest tests/test_pedestrian_occlusion_probes.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 6: PatchSpec Repair for Probe Failures

Goal:

Move deterministic repair out of Streamlit helpers and into typed PatchSpec operations driven by probe failures.

Files likely to change:

- `src/scenariocraft/schemas/patch_spec.py`
- `src/scenariocraft/repair/__init__.py`
- `src/scenariocraft/repair/patcher.py`
- `src/scenariocraft/repair/suggestions.py`
- `src/scenariocraft/web/app.py`
- `src/scenariocraft/web/view_models.py`
- `tests/test_patch_spec.py`
- `tests/test_repair_patcher.py`
- `tests/test_pedestrian_occlusion_repair.py`

Files that should not change:

- `src/scenariocraft/tools/esmini_tool.py`
- `src/scenariocraft/references/*`
- ASAM QC wrapper.
- External `.xosc` files.

Tests to add/update:

- Valid PatchSpec operations apply to `ScenarioSpec`.
- Unknown operations are rejected.
- Missing pedestrian repair adds a crossing actor.
- Missing occluder repair adds a parked vehicle.
- Low criticality repair adjusts trigger/layout/criticality deterministically.
- Repair history is written by CLI/Web callers, not by patch application itself.

Acceptance criteria:

- Repair modifies `ScenarioSpec`, not raw XML.
- Repair loop remains bounded.
- Web `Repair Scenario` button calls the reusable repair layer.
- Generated scenario is rebuilt after repair.

Risks:

- Patching frozen dataclasses can become verbose.
- Repair suggestions may need to update related layout and trigger fields together.

Commands to run:

```bash
python -m pytest tests/test_patch_spec.py tests/test_repair_patcher.py tests/test_pedestrian_occlusion_repair.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 7: More Templates

Goal:

Add additional deterministic scenario templates only after pedestrian occlusion is stable.

Candidate templates:

- `cut_in`
- `lead_vehicle_sudden_braking`
- `stationary_vehicle_aeb`

Files likely to change:

- `src/scenariocraft/templates/cut_in.py`
- `src/scenariocraft/templates/lead_vehicle_sudden_braking.py`
- `src/scenariocraft/templates/stationary_vehicle_aeb.py`
- `src/scenariocraft/templates/registry.py`
- `tests/test_templates_cut_in.py`
- `tests/test_templates_lead_vehicle_sudden_braking.py`
- `tests/test_templates_stationary_vehicle_aeb.py`

Files that should not change:

- Existing pedestrian occlusion tests unless shared interfaces evolve.
- esmini wrapper.
- reference scanner.
- external files.

Tests to add/update:

- Each template instantiates a schema-valid `ScenarioSpec`.
- Each template emits layout and spatial relations.
- Each template can build OpenSCENARIO through the existing builder or a scoped builder enhancement.

Acceptance criteria:

- One template per implementation task.
- No new template breaks the generated pedestrian occlusion demo.
- Mock provider remains deterministic.

Risks:

- Builder may need more scenario-type awareness.
- Preview may need generic layout rendering rather than pedestrian-specific drawing.

Commands to run:

```bash
python -m pytest tests/test_template_registry.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 8: LLM Template Selection Only

Goal:

Add optional LLM-assisted `ScenarioIntent` generation/template selection without allowing raw XML generation.

Files likely to change:

- `src/scenariocraft/schemas/scenario_intent.py`
- `src/scenariocraft/generators/intent_generator.py`
- `src/scenariocraft/generators/openai_generator.py` only if explicitly requested later.
- `src/scenariocraft/generators/local_generator.py` only if explicitly requested later.
- `src/scenariocraft/main.py` provider selection only if a provider is explicitly added.
- `tests/test_scenario_intent.py`
- provider tests using fake clients only.

Files that should not change:

- Template instantiation internals.
- XML builder.
- esmini wrapper.
- reference scanner.
- Web demo default provider.
- external files.

Tests to add/update:

- LLM/provider output must parse as schema-valid JSON.
- Invalid template IDs are rejected.
- Mock provider remains default.
- Tests use fake providers and require no network/API keys.

Acceptance criteria:

- LLM output is `ScenarioIntent` or PatchSpec JSON only.
- No raw XML generation path is introduced.
- `--provider mock` still works without configuration.

Risks:

- Provider code can leak prompt policy into root modules.
- Tests could accidentally depend on external APIs if not isolated.

Commands to run:

```bash
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Step 9: ReferenceScenarioCards/RAG Hints

Goal:

Convert scanner outputs into compatibility-aware reference cards that can later provide template hints.

Files likely to change:

- `src/scenariocraft/references/cards.py`
- `src/scenariocraft/references/scanner.py`
- `src/scenariocraft/references/scan.py`
- `tests/test_reference_cards.py`
- `tests/test_reference_scanner.py`

Files that should not change:

- `external/*`
- esmini wrapper unless scanner result fields require a narrow addition.
- Web main generated-scenario flow.
- Template/probe core behavior.

Tests to add/update:

- Synthetic scanner fixtures produce typed `ReferenceScenarioCard` objects.
- Cards include source, relative path, actors, logic files, compatibility category, esmini status, and template hints.
- Retrieval is keyword/metadata-based only at first.

Acceptance criteria:

- No vector database.
- No automatic repo downloads.
- RAG cards are hints only and do not replace probes/QC/esmini.
- Existing scanner outputs continue to be generated.

Risks:

- Treating external reference metadata as complete semantics.
- Bringing external-scenario complexity back into the main Web demo too early.

Commands to run:

```bash
python -m pytest tests/test_reference_cards.py tests/test_reference_scanner.py
python -m pytest
python -m scenariocraft.references.scan --root tests/fixtures/reference_scenarios --out outputs/reference_scan/test_fixture --limit 2
```

## Step 10: Agentic Generate-Build-Probe-Repair Loop

Goal:

Add a bounded orchestrator for the full deterministic loop.

Target loop:

```text
prompt
-> ScenarioIntent
-> ScenarioTemplate
-> ScenarioSpec
-> build XML
-> preview
-> probes
-> ASAM QC/esmini if available
-> PatchSpec if needed
-> rerun until pass or max rounds
```

Files likely to change:

- `src/scenariocraft/loop/__init__.py`
- `src/scenariocraft/loop/orchestrator.py`
- `src/scenariocraft/main.py`
- `src/scenariocraft/tools/report_tool.py`
- `src/scenariocraft/web/app.py`
- `src/scenariocraft/web/view_models.py`
- `tests/test_agentic_loop.py`
- `tests/test_cli.py`

Files that should not change:

- esmini low-level wrapper except for result-field additions.
- ASAM QC low-level wrapper.
- reference scanner behavior.
- external files.

Tests to add/update:

- Loop succeeds in one round for the normal pedestrian occlusion template.
- Loop repairs missing pedestrian within a bounded number of rounds.
- Loop stops and reports failure when a repair is unsupported.
- Loop writes artifacts and repair history under `outputs/`.
- Tests use mocked ASAM QC/esmini results.

Acceptance criteria:

- Deterministic tools remain authoritative.
- LLMs, if present, only produce `ScenarioIntent` or PatchSpec.
- Repair loop is bounded and inspectable.
- CLI and Web generated demo remain simple entry points into the loop.

Risks:

- Orchestrator can become a large god function.
- Reports can become too verbose if all artifacts are always visible.
- Tool failures can be mistaken for semantic failures unless result categories remain explicit.

Commands to run:

```bash
python -m pytest tests/test_agentic_loop.py tests/test_cli.py
python -m pytest
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
```

## Implementation Order Recommendation

Do not start with the full agentic loop. Start with the narrowest structural slice:

```text
Step 1 -> Step 2 -> Step 3A -> Step 3B -> Step 3C (only if needed) -> Step 4
```

This sequence first establishes a stable template seam, then typed spatial data, then actor geometry, then explicit road topology, and finally verifies that OpenSCENARIO construction agrees with the same source of truth. Only after the scene knows where the road, parking strip, sidewalk, actors, paths, and conflict points are should probe and repair work begin.
