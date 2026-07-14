from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from scenariocraft.external_tools.opendrive_mcp import (
    OpenDriveMcpConfig,
    run_opendrive_mcp_sidecar,
)


def _write_mcp_stub(path: Path, mode: str = "success") -> Path:
    path.write_text(
        f"""from __future__ import annotations

import json
import sys
import time

MODE = {mode!r}


def payload_for(name, arguments):
    backend = {{"name": "libOpenDRIVE", "mode": "cli", "source": "stub", "commit": "test"}}
    if MODE == "wrong-backend" and name == "summarize_map":
        backend["name"] = "mock"
    base = {{"ok": True, "warnings": [], "error": None, "backend": backend}}
    if name == "validate_basic":
        base.update(valid=MODE != "invalid-map", checks=[])
    elif name == "summarize_map":
        base.update(file_path=arguments["file_path"], road_count=2, junction_count=0, total_length_m=20.0)
    elif name == "list_roads":
        base.update(roads=[
            {{"road_id": "0", "name": "first", "length_m": 10.0, "junction_id": "-1"}},
            {{"road_id": "1", "name": "second", "length_m": 10.0, "junction_id": "-1"}},
        ])
    elif name == "list_lanes":
        base.update(road_id=arguments["road_id"], lanes=[
            {{"lane_id": -1, "type": "driving", "side": "right"}}
        ])
    if MODE == "tool-failure" and name == "summarize_map":
        base.update(ok=False, error={{"code": "PARSE_FAILED", "message": "bad map"}})
    return base


if MODE == "timeout":
    time.sleep(2)

requests = [json.loads(line) for line in sys.stdin if line.strip()]
if MODE == "invalid-json":
    print("not-json")
    raise SystemExit(0)

responses = []
for request in requests:
    request_id = request.get("id")
    method = request.get("method")
    if method == "initialize":
        response = {{
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {{"serverInfo": {{"name": "stub", "version": "0"}}}},
        }}
    else:
        params = request.get("params", {{}})
        name = params.get("name")
        arguments = params.get("arguments", {{}})
        if MODE == "rpc-error" and name == "summarize_map":
            response = {{
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {{"code": -32000, "message": "tool exploded"}},
            }}
        elif MODE == "missing-content" and name == "summarize_map":
            response = {{"jsonrpc": "2.0", "id": request_id, "result": {{"content": []}}}}
        else:
            response = {{
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {{
                    "content": [{{"type": "text", "text": json.dumps(payload_for(name, arguments))}}]
                }},
            }}
    responses.append(response)

if MODE == "missing-id" and responses:
    responses.pop()
if MODE == "duplicate-id" and responses:
    responses.append(responses[-1])

for response in responses:
    print(json.dumps(response))
""",
        encoding="utf-8",
    )
    return path


def _config(stub_path: Path, *, timeout_s: float = 1.0) -> OpenDriveMcpConfig:
    return OpenDriveMcpConfig(
        command=(sys.executable, str(stub_path)),
        cwd=None,
        timeout_s=timeout_s,
    )


def test_sidecar_collects_map_and_per_road_lane_evidence(tmp_path: Path) -> None:
    xodr_path = tmp_path / "map.xodr"
    xodr_path.write_text("<OpenDRIVE />", encoding="utf-8")
    output_path = tmp_path / "opendrive_mcp_result.json"

    evidence = run_opendrive_mcp_sidecar(
        xodr_path,
        config=_config(_write_mcp_stub(tmp_path / "stub.py")),
        output_path=output_path,
    )

    assert evidence.available is True
    assert evidence.passed is True
    assert evidence.backend_name == "libOpenDRIVE"
    assert evidence.file_path == str(xodr_path.resolve())
    assert [item.tool_name for item in evidence.tools[:3]] == [
        "validate_basic",
        "summarize_map",
        "list_roads",
    ]
    assert [item.arguments["road_id"] for item in evidence.tools[3:]] == ["0", "1"]
    assert all(item.ok for item in evidence.tools)
    assert json.loads(output_path.read_text(encoding="utf-8")) == evidence.to_dict()


def test_sidecar_uses_environment_configuration(monkeypatch, tmp_path: Path) -> None:
    xodr_path = tmp_path / "map.xodr"
    xodr_path.write_text("<OpenDRIVE />", encoding="utf-8")
    package_dir = tmp_path / "opendrive_mcp"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    _write_mcp_stub(package_dir / "server.py")
    monkeypatch.setenv("SCENARIOCRAFT_OPENDRIVE_MCP_PYTHON", sys.executable)
    monkeypatch.setenv("SCENARIOCRAFT_OPENDRIVE_MCP_CWD", str(tmp_path))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))

    evidence = run_opendrive_mcp_sidecar(xodr_path)

    assert evidence.available is True
    assert evidence.command == (
        sys.executable,
        "-m",
        "opendrive_mcp.server",
        "--mcp",
    )


@pytest.mark.parametrize(
    ("mode", "expected_available", "message_fragment"),
    [
        ("timeout", False, "timed out"),
        ("invalid-json", True, "invalid JSON"),
        ("rpc-error", True, "JSON-RPC error"),
        ("missing-content", True, "content[0].text"),
        ("tool-failure", True, "PARSE_FAILED"),
        ("wrong-backend", True, "libOpenDRIVE"),
        ("invalid-map", True, "validate_basic"),
        ("missing-id", True, "missing response"),
        ("duplicate-id", True, "duplicate response"),
    ],
)
def test_sidecar_returns_structured_failure_evidence(
    mode: str,
    expected_available: bool,
    message_fragment: str,
    tmp_path: Path,
) -> None:
    xodr_path = tmp_path / "map.xodr"
    xodr_path.write_text("<OpenDRIVE />", encoding="utf-8")
    timeout_s = 0.01 if mode == "timeout" else 1.0

    evidence = run_opendrive_mcp_sidecar(
        xodr_path,
        config=_config(_write_mcp_stub(tmp_path / "stub.py", mode), timeout_s=timeout_s),
    )

    assert evidence.available is expected_available
    assert evidence.passed is False
    assert evidence.error_message is not None
    assert message_fragment in evidence.error_message


def test_sidecar_returns_unavailable_for_missing_executable(tmp_path: Path) -> None:
    xodr_path = tmp_path / "map.xodr"
    xodr_path.write_text("<OpenDRIVE />", encoding="utf-8")

    evidence = run_opendrive_mcp_sidecar(
        xodr_path,
        config=OpenDriveMcpConfig(
            command=(str(tmp_path / "missing-python"),),
            cwd=None,
            timeout_s=1.0,
        ),
    )

    assert evidence.available is False
    assert evidence.passed is False
    assert evidence.error_message is not None
    assert "not found" in evidence.error_message


def test_sidecar_rejects_missing_xodr_without_starting_process(tmp_path: Path) -> None:
    evidence = run_opendrive_mcp_sidecar(
        tmp_path / "missing.xodr",
        config=OpenDriveMcpConfig(
            command=(str(tmp_path / "also-missing"),),
            cwd=None,
            timeout_s=1.0,
        ),
    )

    assert evidence.available is False
    assert evidence.passed is False
    assert evidence.error_message == "OpenDRIVE file was not found."
