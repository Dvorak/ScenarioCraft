# ScenarioCraft [![Python versions](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue)](https://www.python.org/)

**A local-first harness for structured autonomous-driving scenario generation and validation.**

ScenarioCraft turns a natural-language scenario request into a typed `ScenarioSpec`, deterministic OpenSCENARIO/OpenDRIVE artifacts, semantic previews, validation probes, optional runtime evidence, and structured repair traces.

The current demo centers on a rainy pedestrian-occlusion scenario where an ego vehicle approaches a parked van and a pedestrian crosses from behind it.

```text
request
-> ScenarioSpec
-> XOSC/XODR
-> preview / probes / report
-> optional ASAM QC / esmini
-> PatchSpec repair when needed
```

ScenarioCraft is a research prototype, not a production validation suite.

---

## Quickstart

### 1. Prerequisites

- Python 3.11 or 3.12.
- [`uv`](https://docs.astral.sh/uv/) for package management.
- [`just`](https://github.com/casey/just) as the command runner.
- Optional: esmini for runtime checks and visual playback.
- Optional: ASAM OpenSCENARIO XML checker.

### 2. Setup

From the repo root:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip uv rust-just
.venv/bin/just setup
```

`just setup` uses the project-local uv binary and cache:

```bash
UV_CACHE_DIR=.uv-cache .venv/bin/uv sync --extra dev --extra web --extra openai --extra qc
```

If dependency resolution cannot reach PyPI but the environment already has the needed packages:

```bash
.venv/bin/python -m pip install -e . --no-build-isolation
```

### 3. Generate a Scenario

```bash
.venv/bin/just smoke
```

Equivalent direct command:

```bash
.venv/bin/python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo \
  --provider mock
```

Expected artifacts:

```text
outputs/demo/
  input.txt
  scenario_spec.json
  preview_2d.png
  scenario.xosc
  urban_two_way_parking.xodr
  validation_report.md
```

### 4. Open the Web UI

```bash
.venv/bin/just web
```

Equivalent direct command:

```bash
.venv/bin/python -m streamlit run scenariocraft/web/app.py
```

The Workspace page provides:

- scenario request input;
- controlled demo cases;
- generate and repair actions;
- Scenario / Probes / OSC Quality / Simulation status;
- Scenario Brief timing metrics;
- `Preview 2D Semantic`;
- `Playback Esmini`.

If real esmini visual media is unavailable, the playback panel says so and labels preview-derived media as `2D Preview Fallback`.

### 5. Run Tests

```bash
.venv/bin/just test
```

Useful focused checks:

```bash
.venv/bin/python -m pytest tests/test_core_boundary.py -q
.venv/bin/python -m pytest tests/test_web_workspace_layout.py -q
.venv/bin/python -m pytest tests/test_esmini_tool.py -q
```

The default tests do not require real esmini, ASAM QC, OpenAI, CARLA, Docker, or internet access.

---

## Project Layout

ScenarioCraft uses a no-`src` Python package layout:

```text
scenariocraft/
  core/             deterministic contracts, templates, probes, repair, build, metrics
  application/      CLI/Web shared workflows
  orchestration/    bounded workflow and repair coordination
  runtime/          esmini and ASAM QC adapters
  presentation/     preview and report rendering
  integrations/     optional provider adapters
  web/              Streamlit UI
  references/       external OpenSCENARIO reference helpers

examples/           input prompts
tests/              unit and workflow tests
outputs/            generated artifacts, gitignored
```

`scenariocraft/core` is deterministic and independent of Streamlit, provider APIs, and local simulator executables.

---

## CLI

Generate the default scenario:

```bash
.venv/bin/python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo \
  --provider mock
```

Require esmini:

```bash
.venv/bin/python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo_esmini \
  --provider mock \
  --require-esmini
```

Check an existing OpenSCENARIO file:

```bash
.venv/bin/python -m scenariocraft.main \
  --load-xosc path/to/scenario.xosc \
  --out outputs/reference_check \
  --run-esmini
```

When loading an existing `.xosc`, ScenarioCraft runs from the scenario file's parent directory by default so relative OpenDRIVE and catalog paths can resolve.

---

## Optional Tools

### esmini

Install the bundled esmini binary:

```bash
.venv/bin/python scripts/install_esmini.py --package bin
export ESMINI_BIN="$(cat third_party/esmini/ESMINI_BIN)"
```

Then run:

```bash
.venv/bin/python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo_esmini \
  --provider mock \
  --require-esmini
```

On macOS, visual capture uses windowed esmini capture. Headless capture is intentionally avoided for visual media because it produced invalid capture artifacts during local diagnosis.

### ASAM QC

```bash
.venv/bin/uv sync --extra qc
```

If the checker is available, ScenarioCraft records QC output in the artifact directory. If it is missing, runs still complete and the report records that QC was unavailable.

### OpenAI Repair Provider

```bash
.venv/bin/uv sync --extra openai
export OPENAI_API_KEY=...
```

The OpenAI repair provider is an integration adapter. It proposes structured `PatchSpec` JSON only; deterministic ScenarioCraft code validates, applies, rebuilds, and rechecks the result.

The default demo and tests use deterministic mock/fake providers and do not require an API key.

---

## Core Concepts

- `ScenarioSpec`: typed scenario contract.
- `ScenarioTemplate`: deterministic scenario family generator.
- `ProbeResult`: structured validation evidence.
- `PatchSpec`: structured scenario repair operation list.
- `scenariocraft.core.build`: ScenarioSpec to OpenSCENARIO/OpenDRIVE.
- `scenariocraft.runtime`: optional runtime adapters.
- `scenariocraft.presentation`: preview and report rendering.

Generated artifacts go under `outputs/`, which is gitignored.
