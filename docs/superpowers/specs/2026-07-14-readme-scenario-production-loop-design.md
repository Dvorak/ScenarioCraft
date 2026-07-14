# README Scenario Production Loop Design

## Purpose

Replace the current README architecture image with a diagram whose first job is
to explain why ScenarioCraft can reliably produce high-quality scenarios and
variants.

The primary audience is:

- new users evaluating what ScenarioCraft does;
- research reviewers evaluating the method;
- product reviewers evaluating the system promise.

The initial version prioritizes a correct story over visual polish.

## Core Promise

ScenarioCraft does not guarantee that every input produces a scenario. It
guarantees that every scenario it accepts and delivers has passed the same
evidence gate. When the system cannot safely converge, it rejects the candidate,
asks for clarification, or reports the unsupported condition instead of silently
delivering a low-quality scenario.

## Narrative

The main diagram presents one evidence-gated Scenario Production Loop:

```text
Goal
-> Propose Candidate
-> ScenarioSpec
-> Deterministic Build
-> Evidence
-> Quality Gate
```

The quality gate has four explicit outcomes:

1. **Accepted**: the candidate passed the required evidence and can be delivered.
2. **Repairable failure**: failed evidence is converted into a constrained
   `PatchSpec`; the patched `ScenarioSpec` is rebuilt and evaluated again.
3. **Variant request**: an accepted scenario plus a revision goal produces a new
   candidate; the variant must pass the same build, evidence, and quality gate.
4. **Unresolved**: unsupported, unsafe, or exhausted work terminates as reject,
   clarify, or explicit failure.

Variant creation and repair share the quality loop but must remain semantically
distinct:

- a variant changes what scenario the user wants;
- a repair preserves the intended scenario while correcting a failed candidate;
- neither path bypasses deterministic rebuild and evaluation.

## Diagram Content

The README diagram includes only the concepts needed for the production-loop
story:

- user goal;
- candidate proposal through `ScenarioIntent`, family, and template capability;
- candidate `ScenarioSpec` as the semantic source of truth;
- deterministic artifact build;
- structured evidence;
- quality gate;
- accepted scenario and artifacts;
- variant re-entry;
- `PatchSpec` repair re-entry;
- explicit unresolved termination.

The diagram does not include package boundaries, delivery surfaces, RAG,
external-XOSC inspection, detailed tool names, or implementation modules. Those
belong in contributor and detailed architecture diagrams.

## Evidence Semantics

The diagram groups evidence for readability but the accompanying README text
must make clear that evidence can include:

- semantic validation;
- family and geometry checks;
- artifact consistency checks;
- optional ASAM quality checks;
- optional runtime consistency and esmini execution evidence.

Optional evidence providers must not be presented as universally available or
as prerequisites for every workflow. The acceptance policy determines which
evidence is required for a particular run.

## Editable Source and Generated Assets

Mermaid is the initial authoritative format because the first milestone is
logical clarity, it is easy to review as text, and it expresses branching and
feedback loops without a custom renderer.

Planned files:

```text
docs/diagrams/scenario-production-loop.mmd
docs/assets/scenario-production-loop.svg
docs/assets/scenario-production-loop.png
```

The Mermaid source is authoritative. SVG and PNG are generated artifacts. The
README references the SVG and links to the Mermaid source. PNG remains available
for contexts that cannot display SVG.

D2 remains a future rendering option if visual control becomes important. A
future D2 migration must preserve the approved concepts and edge semantics; it
must not create a second architecture source of truth.

## README Integration

The existing architecture image is replaced by the generated SVG. A nearby link
opens the editable Mermaid source so readers can inspect the model without
searching through the repository.

The short explanatory text next to the diagram states:

> Every accepted scenario passes the same evidence gate. Variants and repairs
> re-enter the loop and must be rebuilt and reevaluated.

## Failure and Safety Semantics

The diagram must not imply an unbounded autonomous retry loop. Repair is bounded,
and an unresolved candidate reaches an explicit terminal state. A failed or
unsupported candidate must never visually flow into `Accepted Scenario`.

The diagram must also avoid claiming that optional LLM providers, ASAM QC, or
esmini are always present. Model providers propose typed intent or patches;
ScenarioCraft owns deterministic build, evaluation, and acceptance.

## Verification

Implementation is complete when:

1. The Mermaid source renders without errors.
2. SVG and PNG are reproducibly generated from the committed Mermaid source.
3. The README uses the SVG and links to the `.mmd` file.
4. At README width, the flow and all outcome labels remain legible.
5. Variant and repair are visibly distinct and both re-enter evaluation.
6. The unresolved path cannot be mistaken for acceptance.
7. Existing README link and asset tests pass, with new checks added for the
   Mermaid source and generated assets.

Visual styling beyond basic legibility is intentionally out of scope for the
first implementation.
