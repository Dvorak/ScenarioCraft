set shell := ["bash", "-cu"]

python := ".venv/bin/python"
uv := ".venv/bin/uv"

setup:
    UV_CACHE_DIR=.uv-cache {{uv}} sync --extra dev --extra web --extra openai --extra qc

test:
    {{python}} -m pytest

smoke:
    {{python}} -m scenariocraft.main --input examples/pedestrian_occlusion.txt --out outputs/demo --provider mock

web:
    {{python}} -m streamlit run scenariocraft/web/app.py

clean:
    find . -type d -name __pycache__ -prune -exec rm -rf {} +
    rm -rf .pytest_cache .mypy_cache .ruff_cache build dist *.egg-info
