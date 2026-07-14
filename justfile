set shell := ["bash", "-cu"]

python := ".venv/bin/python"
uv := ".venv/bin/uv"

setup:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra api --extra dev --extra web

setup-full:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra api --extra dev --extra web --extra openai --extra qc
    {{python}} -m scenariocraft.tooling.setup_tools

setup-web:
    mkdir -p web-ref
    if [ ! -d web-ref/scenariocraft-web/.git ]; then git clone https://github.com/Dvorak/scenariocraft-web.git web-ref/scenariocraft-web; fi
    npm --prefix web-ref/scenariocraft-web ci

setup-openai:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra dev --extra web --extra openai

setup-qc:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra dev --extra web --extra qc

test:
    {{python}} -m pytest

smoke:
    {{python}} -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock

web:
    test -f web-ref/scenariocraft-web/package.json || (echo "React frontend is missing; run: .venv/bin/just setup-web" && exit 1)
    echo "ScenarioCraft Web UI: http://localhost:3000"
    echo "ScenarioCraft API: http://localhost:8000"
    {{python}} -m uvicorn scenariocraft.http_api:app --host 127.0.0.1 --port 8000 & api_pid=$!; trap 'kill "$api_pid" 2>/dev/null || true' EXIT INT TERM; npm --prefix web-ref/scenariocraft-web run dev -- --host 127.0.0.1 --port 3000

streamlit:
    echo "ScenarioCraft Web UI: http://localhost:8501"
    {{python}} -m streamlit run scenariocraft/web/app.py --server.address localhost --server.port 8501

clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
