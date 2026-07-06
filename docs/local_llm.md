# Local LLM Provider

ScenarioCraft supports OpenAI-compatible local model endpoints for
natural-language to `ScenarioIntent` routing.

Ollama is the simplest local setup:

```bash
ollama pull qwen2.5:7b
ollama serve
```

If `ollama serve` says the address is already in use, the server is already
running.

Configure ScenarioCraft:

```bash
export SCENARIOCRAFT_LOCAL_LLM_BASE_URL=http://localhost:11434/v1
export SCENARIOCRAFT_LOCAL_LLM_API_KEY=local
export SCENARIOCRAFT_LOCAL_LLM_MODEL=qwen2.5:7b
.venv/bin/just web
```

The local model proposes structured `ScenarioIntent` JSON only. It does not
write XOSC/XODR and does not decide whether the result is valid. Deterministic
templates, builders, and checks remain authoritative.

Useful checks:

```bash
ollama list
ollama ps
```
