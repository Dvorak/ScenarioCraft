# ScenarioCraft [![Python versions](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue)](https://www.python.org/)

**A local-first harness for structured autonomous-driving scenario generation and validation.**

ScenarioCraft turns a natural-language scenario request into a typed `ScenarioSpec`, deterministic OpenSCENARIO/OpenDRIVE artifacts, semantic previews, validation probes, optional runtime evidence, and structured repair traces.

The current demo centers on a rainy pedestrian-occlusion scenario where an ego vehicle approaches a parked van and a pedestrian crosses from behind it.

ScenarioCraft is a research prototype, not a production validation suite.

---

## How It Works

![ScenarioCraft architecture](assets/readme/scenariocraft-architecture.png)

ScenarioCraft treats LLMs, RAG, quality checkers, simulators, and builder backends as replaceable adapters around a typed scenario contract. The stable path is: produce structured scenario data, build deterministic OpenSCENARIO/OpenDRIVE artifacts, collect validation evidence, and apply constrained `PatchSpec` repairs only when checks justify them.

---

## Quickstart

### 1. Clone

```bash
git clone https://github.com/Dvorak/ScenarioCraft-Agent.git
cd ScenarioCraft-Agent
```

### 2. Prerequisites

- Python 3.11 or 3.12.
- [`uv`](https://docs.astral.sh/uv/) for package management.
- [`just`](https://github.com/casey/just) is installed into `.venv` during setup and used as the command runner after that.

### 3. Recommended Setup

From the repo root:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip uv
UV_CACHE_DIR=.uv-cache .venv/bin/uv sync --extra dev --extra web --extra openai --extra qc
.venv/bin/python -m scenariocraft.setup
```

This installs the base package, Web UI dependencies, the OpenAI adapter dependency, `just`, esmini, and the ASAM OpenSCENARIO XML checker.

After setup, export the tool paths for the current shell:

```bash
export ESMINI_BIN="$(cat third_party/esmini/ESMINI_BIN)"
export ASAM_QC_OPENSCENARIOXML_BIN="$(cat third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN)"
```

Set `OPENAI_API_KEY` only when you want to try the OpenAI repair provider. The default demo works without an API key.

### 4. Open the Web UI

```bash
.venv/bin/just web
```

Then open:

```text
http://localhost:8501
```

The Workspace page is the fastest way to generate the demo scenario, inspect the semantic preview, run repair cases, and view verified runtime media when esmini is configured.

### 5. Run from the CLI

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

## Tool Setup Details

The recommended setup command runs the optional tool installers for you:

```bash
.venv/bin/python -m scenariocraft.setup
```

Use the individual commands below only when you want to refresh or troubleshoot one tool.

### esmini

Install or refresh the bundled esmini binary:

```bash
.venv/bin/python -m scenariocraft.tooling.install_esmini --package bin
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

Install and locate the ASAM OpenSCENARIO XML checker:

```bash
.venv/bin/python -m scenariocraft.tooling.install_asamqc
export ASAM_QC_OPENSCENARIOXML_BIN="$(cat third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN)"
"$ASAM_QC_OPENSCENARIOXML_BIN" --help
```

The script installs the `qc` extra, resolves `qc_openscenario`, and writes the resolved binary path to `third_party/asam_qc/ASAM_QC_OPENSCENARIOXML_BIN`.

If you prefer to install manually:

```bash
.venv/bin/just setup-qc
export ASAM_QC_OPENSCENARIOXML_BIN="$(command -v qc_openscenario)"
```

When the checker is available, ScenarioCraft records `qc_config.xml`, `qc_report.json`, and checker output in the artifact directory. If it is missing, runs still complete and the report records that QC was unavailable.

### OpenAI Repair Provider

```bash
.venv/bin/just setup-openai
export OPENAI_API_KEY=...
```

The OpenAI repair provider is an integration adapter. It proposes structured `PatchSpec` JSON only; deterministic ScenarioCraft code validates, applies, rebuilds, and rechecks the result.

The default demo and tests use deterministic mock/fake providers and do not require an API key.

Generated artifacts go under `outputs/`, which is gitignored.

## Platform Notes

ScenarioCraft is currently exercised primarily on macOS. The setup helper selects the esmini release asset for the current operating system when a matching release package exists. CLI generation and Python-based checks are intended to work on macOS, Linux, and Windows, but visual runtime capture is platform-sensitive.

On macOS, esmini visual capture uses a visible renderer window. Headless capture is intentionally avoided for visual media because it produced invalid capture artifacts during local diagnosis.

## Architecture Snapshot

Core objects:

- `ScenarioSpec`: typed scenario contract.
- `ScenarioTemplate`: deterministic scenario family generator.
- `ProbeResult`: structured validation evidence.
- `PatchSpec`: structured scenario repair operations.

Repository shape:

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

## Development Checks

For local development:

```bash
.venv/bin/just test
```

The test suite uses deterministic fakes by default and does not require real esmini, ASAM QC, OpenAI, CARLA, Docker, or internet access.

## References

- [esmini/esmini](https://github.com/esmini/esmini)
- [asam-ev/qc-framework](https://github.com/asam-ev/qc-framework)
- [pyoscx/scenariogeneration](https://github.com/pyoscx/scenariogeneration)
