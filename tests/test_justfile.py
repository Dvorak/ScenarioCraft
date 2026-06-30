from pathlib import Path


def test_web_recipe_prints_stable_local_url_and_binds_port() -> None:
    justfile = Path("justfile").read_text(encoding="utf-8")

    assert 'echo "ScenarioCraft Web UI: http://localhost:8501"' in justfile
    assert "--server.address localhost" in justfile
    assert "--server.port 8501" in justfile
