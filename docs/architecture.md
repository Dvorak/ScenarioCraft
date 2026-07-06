# Architecture

ScenarioCraft keeps scenario generation structured and inspectable.

```text
natural language
-> ScenarioIntent
-> scenario family template
-> ScenarioSpec
-> deterministic build
-> checks / preview / optional QC and runtime evidence
-> PatchSpec repair when needed
```

LLMs and local models are adapters around typed contracts. They may propose
`ScenarioIntent` or `PatchSpec` JSON, but they do not generate or repair raw
OpenSCENARIO XML directly.

## Core Contracts

- `ScenarioIntent`: compact intent extracted from a user request.
- `ScenarioTemplate`: parameterized scenario-family generator.
- `ScenarioSpec`: semantic source of truth for actors, road context, layout,
  paths, triggers, timing, and storyboard semantics.
- `CheckResult`: structured evidence from deterministic checks.
- `PatchSpec`: constrained repair operations applied to `ScenarioSpec`.

## Three Loops

```text
Candidate Generation Loop
  candidate parameters/spec -> deterministic checks -> accepted ScenarioSpec

Scenario Revision Loop
  existing ScenarioSpec + user edit request -> Candidate Generation Loop

PatchSpec Repair Loop
  failed accepted evidence -> PatchSpec -> patcher -> rebuild/recheck
```

These loops stay separate so scenario variation, user edits, and artifact repair
do not collapse into one opaque "fix it" step.

## Package Boundaries

```text
scenariocraft/core
  deterministic contracts, templates, checks, repair, build, roads, metrics

scenariocraft/application
  reusable CLI/Web workflows

scenariocraft/external_tools
  optional executable adapters such as esmini and ASAM QC

scenariocraft/providers
  optional model/provider adapters

scenariocraft/rendering
  deterministic previews and reports

scenariocraft/web
  Streamlit delivery surface
```

`scenariocraft/core` should remain independent of Streamlit, provider SDKs,
subprocess execution, local simulator binaries, and Web session state.

## Build Boundary

`scenariocraft/core/build/` compiles `ScenarioSpec` to scenario artifacts. It
contains separate modules for:

- public builder facade;
- canonical road binding;
- StoryboardSpec-to-builder plans;
- layout trajectory compilation;
- trigger compilation;
- fallback XML writing.

`scenariogeneration` is used as an OpenSCENARIO writer/adapter. ScenarioCraft
still owns family action plans, road binding, trigger semantics, and checks.
