# scenarioCraft

scenarioCraft is a lightweight research prototype for structured autonomous-driving scenario generation and validation. The current implementation uses a deterministic mock provider to convert a natural-language scenario request into `ScenarioSpec` JSON, build OpenSCENARIO artifacts with `scenariogeneration`, run optional external checks, and produce a human-readable validation report.

This is a research demo, not a production-grade validation tool.

## Pipeline

```text
Natural-language request
  -> ScenarioSpec JSON
  -> deterministic OpenSCENARIO XML via scenariogeneration
  -> optional ASAM QC check
  -> optional esmini load/run check
  -> semantic validation
  -> Markdown validation report
```

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip setuptools wheel
python -m pip install --no-build-isolation -e ".[dev,qc]"
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock
pytest
```

The default `mock` provider requires no API key, simulator, GPU, CARLA, or esmini installation. When esmini is available, the CLI includes it in the validation flow as a load/run check.

## CLI

```bash
python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo \
  --provider mock
```

Generated artifacts:

- `input.txt`
- `scenario_spec.json`
- `scenario.xosc`
- `qc_config.xml`
- `qc_report.json`
- `qc_result.xqar`, when ASAM QC runs
- `esmini_log.txt`
- `validation_report.md`

## OpenSCENARIO Builder

The default builder is `ScenariogenerationBuilder`, backed by the `pyoscx/scenariogeneration` package. A small deterministic XML fallback remains in the codebase so the artifact path stays inspectable if the default builder fails in an unusual environment.

## Providers

- `mock`: deterministic rainy urban pedestrian occlusion scenario. Implemented in this version.
- `openai`: planned optional provider. Not implemented in this version.
- `local`: planned OpenAI-compatible local provider. Not implemented in this version.

## Optional External Tools

ASAM OpenSCENARIO XML checker:

```bash
python -m pip install -e ".[qc]"
qc_openscenario --help
```

scenarioCraft writes `qc_config.xml` automatically and runs:

```bash
qc_openscenario -c outputs/demo/qc_config.xml
```

Override the checker binary when needed:

```bash
ASAM_QC_OPENSCENARIOXML_BIN=/path/to/qc_openscenario
```

esmini:

```bash
python scripts/install_esmini.py --package bin
export ESMINI_BIN="$(cat third_party/esmini/ESMINI_BIN)"
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock --require-esmini
```

The installer downloads the matching prebuilt esmini release asset for the current OS from `https://github.com/esmini/esmini/releases/latest`, extracts it under `third_party/esmini/`, and writes the resolved executable path to `third_party/esmini/ESMINI_BIN`.

The esmini wrapper resolves the executable in this order:

- `--esmini-bin /path/to/esmini`
- `ESMINI_BIN=/path/to/esmini`
- `esmini` on `PATH`
- a downloaded executable under `third_party/esmini/` or `tools/esmini/`

If you already downloaded esmini manually, point the CLI at the compiled binary:

```bash
python -m scenariocraft.main \
  --input examples/pedestrian_occlusion.txt \
  --out outputs/demo \
  --provider mock \
  --esmini-bin /path/to/esmini \
  --require-esmini
```

If either ASAM QC or esmini is not installed, the CLI still completes and writes a clear warning into `validation_report.md`. To make missing esmini a hard failure:

```bash
python -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock --require-esmini
```

## Limitations

- Only the deterministic rainy pedestrian occlusion scenario is implemented.
- The generated scenario is intentionally small and suitable for a research artifact trail, not a complete simulation environment.
- No CARLA, CAMEL, Streamlit, Docker, repair loop, OpenAI provider, or local LLM provider is included in this version.
