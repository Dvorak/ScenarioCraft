# Contributing

ScenarioCraft is a local-first research prototype. Contributions should keep the
deterministic scenario pipeline inspectable.

## Development Setup

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -U pip uv
UV_CACHE_DIR=.uv-cache .venv/bin/uv sync --extra dev --extra web --extra openai --extra qc
```

Optional tools:

```bash
.venv/bin/python -m scenariocraft.tooling.setup_tools
```

## Checks

```bash
.venv/bin/just test
.venv/bin/just smoke
```

The full local test path may use a local Ollama model for live
OpenAI-compatible intent-provider checks.

## Development Rules

- Keep `scenariocraft/core` deterministic.
- Do not let LLMs generate or repair raw OpenSCENARIO XML directly.
- Add scenario behavior through typed contracts, templates, checks, and
  deterministic builders.
- Keep generated artifacts under `outputs/`.
- Do not commit local agent notes, milestone logs, caches, virtualenvs, or
  third-party binary downloads.

## Adding a Scenario Family

A mature family should include:

- a registered template capability;
- parameter domains and deterministic defaults;
- ScenarioSpec generation;
- build/storyboard support;
- Preview 2D support;
- family and artifact consistency checks;
- at least one controlled case;
- tests.

See [Scenario families](docs/scenario_families.md).
