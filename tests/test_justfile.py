from pathlib import Path


def test_web_recipe_prints_stable_local_url_and_binds_port() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert 'echo "ScenarioCraft Web UI: http://localhost:3000"' in justfile
    assert "scenariocraft.http_api:app" in justfile
    assert "--port 8000" in justfile
    assert "npm --prefix web-ref/scenariocraft-web run dev" in justfile
    assert "--port 3000" in justfile


def test_streamlit_recipe_remains_an_explicit_debug_fallback() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert "streamlit:" in justfile
    assert "scenariocraft/_legacy_streamlit/app.py" in justfile
    assert "--server.port 8501" in justfile


def test_setup_web_recipe_uses_the_public_frontend_checkout() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert "setup-web:" in justfile
    assert "https://github.com/Dvorak/scenariocraft-web.git" in justfile
    assert "npm --prefix web-ref/scenariocraft-web ci" in justfile
