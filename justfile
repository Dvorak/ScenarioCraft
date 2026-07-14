set shell := ["bash", "-cu"]

python := ".venv/bin/python"
uv := ".venv/bin/uv"

setup:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra api --extra dev --extra web

setup-full:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra api --extra dev --extra web --extra openai --extra qc
    {{python}} -m scenariocraft.tooling.setup_tools

setup-web:
    git submodule update --init --recursive web
    npm --prefix web ci

setup-openai:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra dev --extra web --extra openai

setup-qc:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra dev --extra web --extra qc

test:
    {{python}} -m pytest

smoke:
    {{python}} -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock

api:
    echo "ScenarioCraft API: http://localhost:8000"
    {{python}} -m uvicorn scenariocraft.api.app:app --host 127.0.0.1 --port 8000

web:
    test -f web/package.json || (echo "React frontend is not initialized; run: .venv/bin/just setup-web" && exit 1)
    echo "ScenarioCraft Web UI: http://localhost:3000"
    echo "ScenarioCraft API: http://localhost:8000"
    {{python}} -m uvicorn scenariocraft.api.app:app --host 127.0.0.1 --port 8000 & api_pid=$!; trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM; npm --prefix web run dev -- --host 127.0.0.1 --port 3000

web-legacy:
    echo "ScenarioCraft legacy Streamlit UI: http://localhost:8501"
    {{python}} -m streamlit run scenariocraft/_legacy_streamlit/app.py --server.address localhost --server.port 8501

clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
