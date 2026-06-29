from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from scenariocraft.schemas import ProbeResult, ScenarioSpec


RUNTIME_PROBE_NAMES = (
    "runtime_esmini_execution_available",
    "runtime_xodr_loaded",
    "runtime_pedestrian_event_started",
    "runtime_pedestrian_event_reached_running_state",
    "runtime_pedestrian_event_completed",
    "runtime_trajectory_action_started",
    "runtime_visual_media_provenance_valid",
    "runtime_motion_verifiable",
)

GENUINE_ESMINI_MEDIA_KINDS = {"esmini_gif", "esmini_frame_sequence", "esmini_single_frame"}
ANIMATED_ESMINI_MEDIA_KINDS = {"esmini_gif", "esmini_frame_sequence"}
USABLE_MEDIA_QUALITY_STATUSES = {"valid", "suspicious"}


def run_runtime_consistency_probes(
    spec: ScenarioSpec,
    *,
    xosc_path: Path | None = None,
    xodr_path: Path | None = None,
    esmini_log_path: Path | None = None,
    playback_result_path: Path | None = None,
) -> tuple[ProbeResult, ...]:
    """Evaluate optional esmini runtime evidence without requiring esmini execution."""
    log_text, log_error = _read_text(esmini_log_path)
    playback_result, playback_error = _read_json(playback_result_path)
    evidence = _runtime_evidence(
        spec=spec,
        xosc_path=xosc_path,
        xodr_path=xodr_path,
        esmini_log_path=esmini_log_path,
        playback_result_path=playback_result_path,
        log_text=log_text,
        log_error=log_error,
        playback_result=playback_result,
        playback_error=playback_error,
    )
    return (
        _execution_available_probe(evidence),
        _xodr_loaded_probe(evidence),
        _event_started_probe(evidence),
        _event_running_probe(evidence),
        _event_completed_probe(evidence),
        _trajectory_action_started_probe(evidence),
        _visual_media_probe(evidence),
        _runtime_motion_verifiable_probe(evidence),
    )


def _execution_available_probe(evidence: dict[str, object]) -> ProbeResult:
    playback_result = evidence["playback_result"]
    log_available = bool(evidence["log_available"])
    esmini_available = _bool_or_none(playback_result.get("esmini_available")) if isinstance(playback_result, dict) else None
    executed = _bool_or_none(playback_result.get("executed")) if isinstance(playback_result, dict) else None
    return_code = playback_result.get("return_code") if isinstance(playback_result, dict) else None
    passed = log_available or executed is True or return_code == 0
    if passed:
        return _result(
            name="runtime_esmini_execution_available",
            passed=True,
            severity="note",
            message="esmini runtime evidence is available.",
            measured=evidence,
        )
    severity = "warning" if esmini_available is False or not log_available else "failure"
    return _result(
        name="runtime_esmini_execution_available",
        passed=False,
        severity=severity,
        message="esmini runtime evidence is unavailable or execution was skipped.",
        measured=evidence,
    )


def _xodr_loaded_probe(evidence: dict[str, object]) -> ProbeResult:
    if not evidence["xodr_expected"]:
        return _result(
            name="runtime_xodr_loaded",
            passed=True,
            severity="note",
            message="No XODR artifact was expected for this runtime probe input.",
            measured=evidence,
        )
    if not evidence["log_available"]:
        return _result(
            name="runtime_xodr_loaded",
            passed=False,
            severity="warning",
            message="XODR load evidence is unavailable because no esmini log was provided.",
            measured=evidence,
        )
    passed = bool(evidence["xodr_loaded"])
    return _result(
        name="runtime_xodr_loaded",
        passed=passed,
        severity="note" if passed else "failure",
        message=(
            "esmini log contains XODR/RoadManager load evidence."
            if passed
            else "esmini log does not contain expected XODR/RoadManager load evidence."
        ),
        measured=evidence,
    )


def _event_started_probe(evidence: dict[str, object]) -> ProbeResult:
    return _event_probe(
        evidence,
        name="runtime_pedestrian_event_started",
        evidence_key="pedestrian_event_started",
        pass_message="Pedestrian event entered startTransition.",
        missing_message="Pedestrian event start evidence is unavailable because no esmini log was provided.",
        failure_message="Pedestrian event was observed but did not enter startTransition.",
    )


def _event_running_probe(evidence: dict[str, object]) -> ProbeResult:
    return _event_probe(
        evidence,
        name="runtime_pedestrian_event_reached_running_state",
        evidence_key="pedestrian_event_running",
        pass_message="Pedestrian event reached runningState.",
        missing_message="Pedestrian running-state evidence is unavailable because no esmini log was provided.",
        failure_message="Pedestrian event was observed but did not reach runningState.",
    )


def _event_completed_probe(evidence: dict[str, object]) -> ProbeResult:
    return _event_probe(
        evidence,
        name="runtime_pedestrian_event_completed",
        evidence_key="pedestrian_event_completed",
        pass_message="Pedestrian event reached completeState.",
        missing_message="Pedestrian completion evidence is unavailable because no esmini log was provided.",
        failure_message="Pedestrian event was observed but did not reach completeState.",
    )


def _trajectory_action_started_probe(evidence: dict[str, object]) -> ProbeResult:
    if not evidence["log_available"]:
        return _result(
            name="runtime_trajectory_action_started",
            passed=False,
            severity="warning",
            message="Trajectory-action evidence is unavailable because no esmini log was provided.",
            measured=evidence,
        )
    passed = bool(evidence["trajectory_action_started"])
    observed = bool(evidence["pedestrian_event_observed"])
    return _result(
        name="runtime_trajectory_action_started",
        passed=passed,
        severity="note" if passed else ("failure" if observed else "warning"),
        message=(
            "Runtime log contains pedestrian trajectory-action evidence."
            if passed
            else "Runtime log does not contain pedestrian trajectory-action evidence."
        ),
        measured=evidence,
    )


def _visual_media_probe(evidence: dict[str, object]) -> ProbeResult:
    playback_result = evidence["playback_result"]
    if not isinstance(playback_result, dict):
        return _result(
            name="runtime_visual_media_provenance_valid",
            passed=False,
            severity="warning",
            message="Playback-result metadata is unavailable.",
            measured=evidence,
        )
    if evidence["visual_media_genuine_esmini"]:
        return _result(
            name="runtime_visual_media_provenance_valid",
            passed=True,
            severity="note",
            message="Playback metadata identifies genuine esmini visual media.",
            measured=evidence,
        )
    quality = evidence["media_quality_status"]
    kind = evidence["playback_kind"]
    severity = "failure" if quality == "corrupt" or str(kind).startswith("preview_") else "warning"
    return _result(
        name="runtime_visual_media_provenance_valid",
        passed=False,
        severity=severity,
        message="Playback metadata does not identify valid genuine esmini visual media.",
        measured=evidence,
    )


def _runtime_motion_verifiable_probe(evidence: dict[str, object]) -> ProbeResult:
    passed = bool(evidence["runtime_motion_verifiable"])
    if passed:
        return _result(
            name="runtime_motion_verifiable",
            passed=True,
            severity="note",
            message="Runtime motion is verifiable from event/action evidence and animated genuine esmini media.",
            measured=evidence,
        )
    has_runtime_evidence = bool(evidence["log_available"] or isinstance(evidence["playback_result"], dict))
    contradicts = bool(evidence["pedestrian_event_observed"]) or evidence["media_quality_status"] == "corrupt"
    return _result(
        name="runtime_motion_verifiable",
        passed=False,
        severity="failure" if has_runtime_evidence and contradicts else "warning",
        message="Runtime motion is not verifiable from the available evidence.",
        measured=evidence,
    )


def _event_probe(
    evidence: dict[str, object],
    *,
    name: str,
    evidence_key: str,
    pass_message: str,
    missing_message: str,
    failure_message: str,
) -> ProbeResult:
    if not evidence["log_available"]:
        return _result(name=name, passed=False, severity="warning", message=missing_message, measured=evidence)
    passed = bool(evidence[evidence_key])
    observed = bool(evidence["pedestrian_event_observed"])
    return _result(
        name=name,
        passed=passed,
        severity="note" if passed else ("failure" if observed else "warning"),
        message=pass_message if passed else failure_message,
        measured=evidence,
    )


def _runtime_evidence(
    *,
    spec: ScenarioSpec,
    xosc_path: Path | None,
    xodr_path: Path | None,
    esmini_log_path: Path | None,
    playback_result_path: Path | None,
    log_text: str | None,
    log_error: str | None,
    playback_result: dict[str, object] | None,
    playback_error: str | None,
) -> dict[str, object]:
    log_text = log_text or ""
    event_lines = _matching_lines(log_text, "pedestrian_starts_crossing")
    playback_kind = playback_result.get("playback_kind") if playback_result is not None else None
    media_quality_status = playback_result.get("media_quality_status") if playback_result is not None else None
    playback_frame_count = _int_or_zero(playback_result.get("playback_frame_count")) if playback_result else 0
    playback_is_animated = _bool_or_none(playback_result.get("playback_is_animated")) if playback_result else None
    visual_media_genuine = (
        playback_kind in GENUINE_ESMINI_MEDIA_KINDS
        and media_quality_status in USABLE_MEDIA_QUALITY_STATUSES
        and playback_frame_count > 0
    )
    visual_media_animated = (
        playback_kind in ANIMATED_ESMINI_MEDIA_KINDS
        and media_quality_status in USABLE_MEDIA_QUALITY_STATUSES
        and playback_frame_count > 1
        and (playback_is_animated is not False or playback_kind == "esmini_frame_sequence")
    )
    pedestrian_event_running = _line_matches(event_lines, r"runningState")
    trajectory_action_started = _trajectory_action_started(log_text)
    return {
        "scenario_name": spec.scenario_name,
        "scenario_type": spec.scenario_type,
        "xosc_path": str(xosc_path) if xosc_path is not None else None,
        "xosc_exists": bool(xosc_path and xosc_path.exists()),
        "xodr_path": str(xodr_path) if xodr_path is not None else None,
        "xodr_expected": xodr_path is not None,
        "xodr_exists": bool(xodr_path and xodr_path.exists()),
        "esmini_log_path": str(esmini_log_path) if esmini_log_path is not None else None,
        "log_available": log_text != "" and log_error is None,
        "log_error": log_error,
        "loaded_xosc": _loaded_xosc(log_text),
        "xodr_loaded": _xodr_loaded(log_text),
        "pedestrian_event_observed": bool(event_lines),
        "pedestrian_event_lines": event_lines,
        "pedestrian_event_started": _line_matches(event_lines, r"startTransition"),
        "pedestrian_event_running": pedestrian_event_running,
        "pedestrian_event_completed": _line_matches(event_lines, r"completeState"),
        "trajectory_action_started": trajectory_action_started,
        "playback_result_path": str(playback_result_path) if playback_result_path is not None else None,
        "playback_result": playback_result or {},
        "playback_error": playback_error,
        "playback_kind": playback_kind,
        "playback_frame_count": playback_frame_count,
        "playback_is_animated": playback_is_animated,
        "media_quality_status": media_quality_status,
        "playback_fallback_reason": playback_result.get("playback_fallback_reason") if playback_result else None,
        "playback_source_path": playback_result.get("playback_source_path") if playback_result else None,
        "visual_media_genuine_esmini": visual_media_genuine,
        "visual_media_animated_esmini": visual_media_animated,
        "runtime_loaded": _loaded_xosc(log_text) and (xodr_path is None or _xodr_loaded(log_text)),
        "event_started": _line_matches(event_lines, r"startTransition"),
        "event_completed": _line_matches(event_lines, r"completeState"),
        "visual_media_valid": visual_media_genuine,
        "runtime_motion_verifiable": pedestrian_event_running and trajectory_action_started and visual_media_animated,
    }


def _read_text(path: Path | None) -> tuple[str | None, str | None]:
    if path is None:
        return None, "not_provided"
    try:
        return Path(path).read_text(encoding="utf-8"), None
    except OSError as exc:
        return None, str(exc)


def _read_json(path: Path | None) -> tuple[dict[str, object] | None, str | None]:
    if path is None:
        return None, "not_provided"
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "playback result JSON must be an object"
    return data, None


def _loaded_xosc(log_text: str) -> bool:
    lowered = log_text.lower()
    return "loaded scenario.xosc" in lowered or bool(re.search(r"loaded .*\.xosc", lowered))


def _xodr_loaded(log_text: str) -> bool:
    lowered = log_text.lower()
    return "loading roadmanager" in lowered or "loaded roadmanager" in lowered or ".xodr" in lowered


def _trajectory_action_started(log_text: str) -> bool:
    lowered = log_text.lower()
    return (
        "followtrajectoryaction" in lowered
        or "pedestrian_follow_crossing_path" in lowered
        or "trajectory action" in lowered
    )


def _matching_lines(text: str, pattern: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if pattern in line]


def _line_matches(lines: list[str], pattern: str) -> bool:
    return any(re.search(pattern, line, re.IGNORECASE) for line in lines)


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _result(
    *,
    name: str,
    passed: bool,
    severity: str,
    message: str,
    measured: dict[str, object],
) -> ProbeResult:
    return ProbeResult(
        name=name,
        passed=passed,
        severity=severity,
        message=message,
        measured=measured,
    )
