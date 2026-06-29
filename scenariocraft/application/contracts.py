from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Literal, TypeAlias

from scenariocraft.core.build import BuildResult
from scenariocraft.runtime import AsamQcResult, EsminiPlaybackResult, EsminiResult
from scenariocraft.core.schemas import ProbeResult, ScenarioSpec
from scenariocraft.core.validation import SemanticValidationResult


WorkflowTerminalStatus: TypeAlias = Literal[
    "loaded",
    "generated",
    "built",
    "validation_failed",
    "repair_required",
    "artifact_mismatch",
    "passed",
    "failed",
]

ExternalWorkflowTerminalStatus: TypeAlias = Literal[
    "loaded",
    "checked",
    "failed",
]


@dataclass(frozen=True)
class ScenarioWorkflowOptions:
    run_preview: bool = True
    run_semantics: bool = True
    run_geometry_probes: bool = True
    run_artifact_probes: bool = False
    run_runtime_probes: bool = True
    run_report: bool = True
    run_asam_qc: bool = False
    run_esmini: bool = False
    run_playback: bool = False
    require_esmini: bool = False
    esmini_bin: str | None = None
    esmini_timeout_s: float = 20.0
    playback_timeout_s: float = 30.0
    esmini_sim_duration_s: float = 3.0
    try_playback_video: bool = True
    playback_mode: Literal["playback", "smoke"] = "playback"
    preview_display_orientation: str = "semantic_canonical"
    preview_presentation_style: str = "annotated"
    stop_optional_integrations_when_demo_repair_required: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ScenarioWorkflowRequest:
    scenario_text: str
    output_dir: Path
    provider_name: str = "mock"
    demo_case_id: str | None = None
    template_parameters: dict[str, object] = field(default_factory=dict)
    options: ScenarioWorkflowOptions = field(default_factory=ScenarioWorkflowOptions)

    def to_dict(self) -> dict[str, object]:
        return {
            "scenario_text": self.scenario_text,
            "output_dir": str(self.output_dir),
            "provider_name": self.provider_name,
            "demo_case_id": self.demo_case_id,
            "template_parameters": _json_value(self.template_parameters),
            "options": self.options.to_dict(),
        }


@dataclass(frozen=True)
class ScenarioArtifactPaths:
    output_dir: Path
    input_path: Path | None = None
    scenario_spec_path: Path | None = None
    xosc_path: Path | None = None
    xodr_path: Path | None = None
    preview_path: Path | None = None
    report_path: Path | None = None
    qc_report_path: Path | None = None
    esmini_result_path: Path | None = None
    playback_result_path: Path | None = None
    playback_path: Path | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            field_name: _path_to_str(getattr(self, field_name))
            for field_name in (
                "output_dir",
                "input_path",
                "scenario_spec_path",
                "xosc_path",
                "xodr_path",
                "preview_path",
                "report_path",
                "qc_report_path",
                "esmini_result_path",
                "playback_result_path",
                "playback_path",
            )
        }


@dataclass(frozen=True)
class ScenarioWorkflowStatus:
    terminal_status: WorkflowTerminalStatus
    terminal_reason: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "terminal_status": self.terminal_status,
            "terminal_reason": self.terminal_reason,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ScenarioWorkflowResult:
    request: ScenarioWorkflowRequest
    status: ScenarioWorkflowStatus
    artifacts: ScenarioArtifactPaths
    spec: ScenarioSpec
    original_spec: ScenarioSpec | None = None
    prepared_case: object | None = None
    build_result: BuildResult | None = None
    semantic_result: SemanticValidationResult | None = None
    geometry_probe_results: tuple[ProbeResult, ...] = ()
    artifact_probe_results: tuple[ProbeResult, ...] = ()
    runtime_probe_results: tuple[ProbeResult, ...] = ()
    qc_result: AsamQcResult | None = None
    esmini_result: EsminiResult | None = None
    playback_result: EsminiPlaybackResult | None = None
    xosc_text: str = ""
    report_text: str = ""

    @property
    def terminal_status(self) -> WorkflowTerminalStatus:
        return self.status.terminal_status

    @property
    def terminal_reason(self) -> str:
        return self.status.terminal_reason

    def to_dict(self) -> dict[str, object]:
        return {
            "request": self.request.to_dict(),
            "status": self.status.to_dict(),
            "artifacts": self.artifacts.to_dict(),
            "spec": self.spec.to_dict(),
            "original_spec": self.original_spec.to_dict() if self.original_spec is not None else None,
            "prepared_case": _prepared_case_to_dict(self.prepared_case),
            "build_result": _build_result_to_dict(self.build_result),
            "semantic_result": _json_value(self.semantic_result),
            "geometry_probe_results": [_json_value(result) for result in self.geometry_probe_results],
            "artifact_probe_results": [_json_value(result) for result in self.artifact_probe_results],
            "runtime_probe_results": [_json_value(result) for result in self.runtime_probe_results],
            "qc_result": _json_value(self.qc_result),
            "esmini_result": _json_value(self.esmini_result),
            "playback_result": _json_value(self.playback_result),
            "xosc_text_available": bool(self.xosc_text),
            "report_text_available": bool(self.report_text),
        }


def _path_to_str(path: Path | None) -> str | None:
    return str(path) if path is not None else None


def _build_result_to_dict(result: BuildResult | None) -> dict[str, object] | None:
    if result is None:
        return None
    return {
        "xosc_path": str(result.xosc_path),
        "xodr_path": str(result.xodr_path) if result.xodr_path is not None else None,
        "builder": result.builder,
        "fallback_reason": result.fallback_reason,
        "artifact_paths": [str(path) for path in result.artifact_paths()],
    }


def _prepared_case_to_dict(prepared_case: object | None) -> dict[str, object] | None:
    if prepared_case is None:
        return None
    case = getattr(prepared_case, "case", None)
    return {
        "case_id": getattr(case, "case_id", None),
        "display_name": getattr(case, "display_name", None),
        "fault_domain": getattr(case, "fault_domain", None),
        "repair_expectation": getattr(case, "repair_expectation", None),
        "terminal_status": getattr(prepared_case, "terminal_status", None),
        "terminal_reason": getattr(prepared_case, "terminal_reason", None),
        "repair_required": bool(getattr(prepared_case, "repair_required", False)),
        "detection_only": bool(getattr(prepared_case, "detection_only", False)),
    }


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "to_dict"):
        return _json_value(value.to_dict())
    if is_dataclass(value):
        return _json_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


@dataclass(frozen=True)
class ExternalScenarioWorkflowOptions:
    run_asam_qc: bool = True
    run_esmini: bool = True
    run_report: bool = True
    require_esmini: bool = False
    esmini_bin: str | None = None
    esmini_timeout_s: float = 20.0
    esmini_mode: Literal["smoke", "full"] = "smoke"
    esmini_sim_duration_s: float = 3.0

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ExternalScenarioWorkflowRequest:
    xosc_path: Path
    output_dir: Path
    source: str = ""
    relative_path: str = ""
    options: ExternalScenarioWorkflowOptions = field(default_factory=ExternalScenarioWorkflowOptions)

    def to_dict(self) -> dict[str, object]:
        return {
            "xosc_path": str(self.xosc_path),
            "output_dir": str(self.output_dir),
            "source": self.source,
            "relative_path": self.relative_path,
            "options": self.options.to_dict(),
        }


@dataclass(frozen=True)
class ExternalScenarioWorkflowStatus:
    terminal_status: ExternalWorkflowTerminalStatus
    terminal_reason: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "terminal_status": self.terminal_status,
            "terminal_reason": self.terminal_reason,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ExternalScenarioWorkflowResult:
    request: ExternalScenarioWorkflowRequest
    status: ExternalScenarioWorkflowStatus
    xosc_path: Path
    working_dir: Path
    metadata: object
    build_result: BuildResult
    xosc_text: str = ""
    qc_result: AsamQcResult | None = None
    esmini_result: EsminiResult | None = None
    report_path: Path | None = None
    report_text: str = ""

    @property
    def terminal_status(self) -> ExternalWorkflowTerminalStatus:
        return self.status.terminal_status

    @property
    def terminal_reason(self) -> str:
        return self.status.terminal_reason

    def to_dict(self) -> dict[str, object]:
        return {
            "request": self.request.to_dict(),
            "status": self.status.to_dict(),
            "xosc_path": str(self.xosc_path),
            "working_dir": str(self.working_dir),
            "metadata": _json_value(self.metadata),
            "build_result": _build_result_to_dict(self.build_result),
            "xosc_text_available": bool(self.xosc_text),
            "qc_result": _json_value(self.qc_result),
            "esmini_result": _json_value(self.esmini_result),
            "report_path": str(self.report_path) if self.report_path else None,
            "report_text_available": bool(self.report_text),
        }
