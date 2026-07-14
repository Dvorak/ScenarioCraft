from pathlib import Path


def test_web_recipe_prints_stable_local_url_and_binds_port() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert 'echo "ScenarioCraft Web UI: http://localhost:3000"' in justfile
    assert "scenariocraft.api.app:app" in justfile
    assert "--port 8000" in justfile
    assert "npm --prefix web run dev" in justfile
    assert "--port 3000" in justfile


def test_legacy_web_recipe_remains_an_explicit_debug_fallback() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert "web-legacy:" in justfile
    assert "scenariocraft/_legacy_streamlit/app.py" in justfile
    assert "--server.port 8501" in justfile


def test_api_recipe_runs_only_the_http_delivery_adapter() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert "api:" in justfile
    assert "uvicorn scenariocraft.api.app:app" in justfile


def test_setup_web_recipe_uses_the_public_frontend_checkout() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert "setup-web:" in justfile
    assert "git submodule update --init --recursive web" in justfile
    assert "npm --prefix web ci" in justfile


def test_readme_explains_optional_react_and_legacy_streamlit_paths() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")

    assert ".venv/bin/just setup-web" in readme
    assert ".venv/bin/just web-legacy" in readme
    assert "web/                pinned React frontend Git submodule" in readme
