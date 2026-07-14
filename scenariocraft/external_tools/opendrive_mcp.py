"""Optional sidecar adapter for deterministic OpenDRIVE MCP evidence."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class OpenDriveMcpConfig:
    command: tuple[str, ...]
    cwd: str | None = None
    timeout_s: float = 30.0

    @classmethod
    def from_environment(cls) -> OpenDriveMcpConfig:
        python = os.environ.get("SCENARIOCRAFT_OPENDRIVE_MCP_PYTHON", sys.executable)
        cwd = os.environ.get("SCENARIOCRAFT_OPENDRIVE_MCP_CWD")
        return cls(
            command=(python, "-m", "opendrive_mcp.server", "--mcp"),
            cwd=cwd,
        )

    def __post_init__(self) -> None:
        if not self.command or not all(isinstance(item, str) and item for item in self.command):
            raise ValueError("OpenDRIVE MCP command must contain non-empty strings.")
        if self.timeout_s <= 0:
            raise ValueError("OpenDRIVE MCP timeout must be greater than zero.")


@dataclass(frozen=True)
class OpenDriveMcpToolEvidence:
    tool_name: str
    arguments: Mapping[str, object]
    ok: bool
    payload: Mapping[str, object] | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "arguments", _freeze_mapping(self.arguments))
        if self.payload is not None:
            object.__setattr__(self, "payload", _freeze_mapping(self.payload))

    def to_dict(self) -> dict[str, object]:
        return {
            "tool_name": self.tool_name,
            "arguments": _thaw_json(self.arguments),
            "ok": self.ok,
            "payload": _thaw_json(self.payload),
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class OpenDriveMcpEvidence:
    available: bool
    passed: bool
    backend_name: str | None
    file_path: str
    command: tuple[str, ...]
    tools: tuple[OpenDriveMcpToolEvidence, ...] = ()
    error_message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "available": self.available,
            "passed": self.passed,
            "backend_name": self.backend_name,
            "file_path": self.file_path,
            "command": list(self.command),
            "tools": [tool.to_dict() for tool in self.tools],
            "error_message": self.error_message,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


class _McpUnavailableError(RuntimeError):
    pass


class _McpProtocolError(RuntimeError):
    pass


def run_opendrive_mcp_sidecar(
    file_path: Path,
    *,
    config: OpenDriveMcpConfig | None = None,
    output_path: Path | None = None,
) -> OpenDriveMcpEvidence:
    resolved_path = Path(file_path).expanduser().resolve()
    resolved_config = config or OpenDriveMcpConfig.from_environment()
    if not resolved_path.is_file():
        return _write_evidence(
            OpenDriveMcpEvidence(
                available=False,
                passed=False,
                backend_name=None,
                file_path=str(resolved_path),
                command=resolved_config.command,
                error_message="OpenDRIVE file was not found.",
            ),
            output_path,
        )

    calls = (
        (2, "validate_basic", {"file_path": str(resolved_path)}),
        (3, "summarize_map", {"file_path": str(resolved_path)}),
        (4, "list_roads", {"file_path": str(resolved_path)}),
    )
    tools: list[OpenDriveMcpToolEvidence] = []
    try:
        first_responses = _run_session(resolved_config, calls)
        first_tools = [
            _tool_evidence(tool_name, arguments, first_responses[call_id])
            for call_id, tool_name, arguments in calls
        ]
        tools.extend(first_tools)
        first_failure = next((tool for tool in first_tools if not tool.ok), None)
        if first_failure is not None:
            return _write_evidence(
                _failure_evidence(
                    resolved_path,
                    resolved_config,
                    tools,
                    first_failure.error_message,
                ),
                output_path,
            )

        road_ids = _road_ids(tools[-1].payload)
        lane_calls = tuple(
            (
                101 + index,
                "list_lanes",
                {"file_path": str(resolved_path), "road_id": road_id},
            )
            for index, road_id in enumerate(road_ids)
        )
        if lane_calls:
            lane_responses = _run_session(resolved_config, lane_calls, initialize_id=100)
            lane_tools = [
                _tool_evidence(tool_name, arguments, lane_responses[call_id])
                for call_id, tool_name, arguments in lane_calls
            ]
            tools.extend(lane_tools)
            lane_failure = next((tool for tool in lane_tools if not tool.ok), None)
            if lane_failure is not None:
                return _write_evidence(
                    _failure_evidence(
                        resolved_path,
                        resolved_config,
                        tools,
                        lane_failure.error_message,
                    ),
                    output_path,
                )
    except _McpUnavailableError as exc:
        evidence = OpenDriveMcpEvidence(
            available=False,
            passed=False,
            backend_name=_backend_name(tools),
            file_path=str(resolved_path),
            command=resolved_config.command,
            tools=tuple(tools),
            error_message=str(exc),
        )
        return _write_evidence(evidence, output_path)
    except _McpProtocolError as exc:
        evidence = OpenDriveMcpEvidence(
            available=True,
            passed=False,
            backend_name=_backend_name(tools),
            file_path=str(resolved_path),
            command=resolved_config.command,
            tools=tuple(tools),
            error_message=str(exc),
        )
        return _write_evidence(evidence, output_path)

    return _write_evidence(
        OpenDriveMcpEvidence(
            available=True,
            passed=True,
            backend_name="libOpenDRIVE",
            file_path=str(resolved_path),
            command=resolved_config.command,
            tools=tuple(tools),
        ),
        output_path,
    )


def _run_session(
    config: OpenDriveMcpConfig,
    calls: Sequence[tuple[int, str, dict[str, object]]],
    *,
    initialize_id: int = 1,
) -> dict[int, dict[str, object]]:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": initialize_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "scenariocraft", "version": "0.1.0"},
            },
        },
        *(
            {
                "jsonrpc": "2.0",
                "id": call_id,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            }
            for call_id, tool_name, arguments in calls
        ),
    ]
    input_text = "".join(json.dumps(request, sort_keys=True) + "\n" for request in requests)
    try:
        completed = subprocess.run(
            list(config.command),
            input=input_text,
            capture_output=True,
            text=True,
            timeout=config.timeout_s,
            cwd=config.cwd,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise _McpUnavailableError(
            f"OpenDRIVE MCP process timed out after {config.timeout_s:g} seconds."
        ) from exc
    except OSError as exc:
        raise _McpUnavailableError(
            f"OpenDRIVE MCP executable was not found or could not start: {exc}"
        ) from exc

    if completed.returncode != 0:
        detail = completed.stderr.strip() or f"process exited with code {completed.returncode}"
        raise _McpUnavailableError(f"OpenDRIVE MCP process failed: {detail}")

    responses: dict[int, dict[str, object]] = {}
    for raw_line in completed.stdout.splitlines():
        if not raw_line.strip():
            continue
        try:
            decoded = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise _McpProtocolError(f"OpenDRIVE MCP returned invalid JSON: {exc}") from exc
        if not isinstance(decoded, dict):
            raise _McpProtocolError("OpenDRIVE MCP returned a non-object JSON-RPC response.")
        if decoded.get("jsonrpc") != "2.0":
            raise _McpProtocolError(
                'OpenDRIVE MCP response must declare jsonrpc version "2.0".'
            )
        response_id = decoded.get("id")
        if isinstance(response_id, bool) or not isinstance(response_id, int):
            raise _McpProtocolError("OpenDRIVE MCP response is missing an integer id.")
        if response_id in responses:
            raise _McpProtocolError(f"OpenDRIVE MCP returned duplicate response id {response_id}.")
        responses[response_id] = decoded

    expected_ids = {initialize_id, *(call_id for call_id, _, _ in calls)}
    missing = sorted(expected_ids - responses.keys())
    if missing:
        raise _McpProtocolError(
            "OpenDRIVE MCP session is missing response IDs: " + ", ".join(map(str, missing))
        )
    unexpected = sorted(responses.keys() - expected_ids)
    if unexpected:
        raise _McpProtocolError(
            "OpenDRIVE MCP session returned unexpected response IDs: "
            + ", ".join(map(str, unexpected))
        )
    initialize = responses[initialize_id]
    if "error" in initialize or not isinstance(initialize.get("result"), dict):
        raise _McpProtocolError("OpenDRIVE MCP initialize response is invalid.")
    return responses


def _tool_evidence(
    tool_name: str,
    arguments: dict[str, object],
    response: Mapping[str, object],
) -> OpenDriveMcpToolEvidence:
    protocol_error = response.get("error")
    if isinstance(protocol_error, Mapping):
        message = (
            f"MCP JSON-RPC error calling {tool_name}: "
            f"{protocol_error.get('code')} {protocol_error.get('message')}"
        )
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, error_message=message)

    result = response.get("result")
    content = result.get("content") if isinstance(result, Mapping) else None
    if not isinstance(content, list) or not content or not isinstance(content[0], Mapping):
        message = f"MCP result for {tool_name} is missing content[0].text."
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, error_message=message)
    result_text = content[0].get("text")
    if not isinstance(result_text, str):
        message = f"MCP result for {tool_name} is missing content[0].text."
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, error_message=message)
    try:
        payload = json.loads(result_text)
    except json.JSONDecodeError as exc:
        message = f"MCP tool {tool_name} returned invalid JSON payload: {exc}"
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, error_message=message)
    if not isinstance(payload, dict):
        message = f"MCP tool {tool_name} returned a non-object payload."
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, error_message=message)

    backend = payload.get("backend")
    backend_name = backend.get("name") if isinstance(backend, Mapping) else None
    if backend_name != "libOpenDRIVE":
        message = f"MCP tool {tool_name} did not report backend libOpenDRIVE."
        return OpenDriveMcpToolEvidence(tool_name, arguments, False, payload, message)
    if payload.get("ok") is not True:
        error = payload.get("error")
        if isinstance(error, Mapping):
            detail = f"{error.get('code')} {error.get('message')}"
        else:
            detail = "tool returned ok=false"
        return OpenDriveMcpToolEvidence(
            tool_name,
            arguments,
            False,
            payload,
            f"MCP tool {tool_name} failed: {detail}",
        )
    if tool_name == "validate_basic" and payload.get("valid") is not True:
        return OpenDriveMcpToolEvidence(
            tool_name,
            arguments,
            False,
            payload,
            "MCP tool validate_basic did not validate the OpenDRIVE file.",
        )
    return OpenDriveMcpToolEvidence(tool_name, arguments, True, payload)


def _road_ids(payload: Mapping[str, object] | None) -> tuple[str, ...]:
    roads = payload.get("roads") if isinstance(payload, Mapping) else None
    if not isinstance(roads, tuple):
        raise _McpProtocolError("MCP tool list_roads returned an invalid roads list.")
    road_ids: list[str] = []
    for road in roads:
        road_id = road.get("road_id") if isinstance(road, Mapping) else None
        if not isinstance(road_id, str) or not road_id:
            raise _McpProtocolError("MCP tool list_roads returned an invalid road_id.")
        if road_id in road_ids:
            raise _McpProtocolError(f"MCP tool list_roads returned duplicate road_id {road_id}.")
        road_ids.append(road_id)
    return tuple(road_ids)


def _failure_evidence(
    file_path: Path,
    config: OpenDriveMcpConfig,
    tools: Sequence[OpenDriveMcpToolEvidence],
    error_message: str | None,
) -> OpenDriveMcpEvidence:
    return OpenDriveMcpEvidence(
        available=True,
        passed=False,
        backend_name=_backend_name(tools),
        file_path=str(file_path),
        command=config.command,
        tools=tuple(tools),
        error_message=error_message,
    )


def _backend_name(tools: Sequence[OpenDriveMcpToolEvidence]) -> str | None:
    names = {
        backend.get("name")
        for tool in tools
        if isinstance(tool.payload, Mapping)
        for backend in [tool.payload.get("backend")]
        if isinstance(backend, Mapping) and isinstance(backend.get("name"), str)
    }
    if names == {"libOpenDRIVE"}:
        return "libOpenDRIVE"
    if len(names) == 1:
        return next(iter(names))
    return None


def _freeze_mapping(value: Mapping[str, object]) -> Mapping[str, object]:
    return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})


def _freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return _freeze_mapping(value)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item) for item in value)
    return value


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value


def _write_evidence(
    evidence: OpenDriveMcpEvidence,
    output_path: Path | None,
) -> OpenDriveMcpEvidence:
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(evidence.to_json() + "\n", encoding="utf-8")
    return evidence
