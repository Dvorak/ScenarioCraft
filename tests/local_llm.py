from __future__ import annotations

import json
import shutil
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest


OLLAMA_BASE_URL = "http://localhost:11434"


def ensure_ollama_server(*, timeout_s: float = 12.0) -> None:
    """Ensure the local Ollama server is reachable for live local-LLM tests."""

    if _ollama_models(timeout_s=0.75):
        return
    if shutil.which("ollama") is None:
        pytest.fail(
            "Local LLM tests require Ollama. Install Ollama, run `ollama pull qwen2.5:7b`, "
            "then rerun the tests."
        )
    subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _ollama_models(timeout_s=0.75):
            return
        time.sleep(0.25)
    pytest.fail(
        "Started `ollama serve`, but no local model is available. Run `ollama pull qwen2.5:7b`, "
        "then rerun the tests."
    )


def _ollama_models(*, timeout_s: float) -> tuple[str, ...]:
    try:
        with urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=timeout_s) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return ()
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return ()
    names = [model.get("name") for model in models if isinstance(model, dict)]
    return tuple(name for name in names if isinstance(name, str) and name)
