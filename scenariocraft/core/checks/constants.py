"""Shared constants for ScenarioCraft check evidence."""

CHECK_CATEGORIES = {
    "structural_validity",
    "intent_alignment",
    "artifact_consistency",
    "external_quality",
    "runtime_behavior",
    "unknown",
}
CHECK_SEVERITIES = {"blocking", "repairable", "warning"}
LEGACY_SEVERITIES = {"failure", "note"}
INTENT_RELATIONS = {
    "matches_intent",
    "mismatches_intent",
    "valid_variant",
    "not_applicable",
    "unknown",
}
REPAIR_ACTIONS = {"repair", "regenerate", "allow_variant", "none"}


__all__ = [
    "CHECK_CATEGORIES",
    "CHECK_SEVERITIES",
    "INTENT_RELATIONS",
    "LEGACY_SEVERITIES",
    "REPAIR_ACTIONS",
]
