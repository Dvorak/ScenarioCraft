"""Shared style decisions for deterministic ScenarioCraft preview rendering."""

from __future__ import annotations

from scenariocraft.core.schemas import RoadBandSpec

PREVIEW_DISPLAY_ORIENTATIONS = {"semantic_canonical", "esmini_top_camera_raw"}
PREVIEW_PRESENTATION_STYLES = {"annotated", "clean_split"}
CLEAN_PREVIEW_ASPECT_RATIO = 16 / 9

ROAD_BAND_COLORS = {
    "sidewalk": "#d8d2c4",
    "parking_strip": "#9aa3ad",
    "driving_lane": "#b8bec3",
    "center_divider": "#f8fafc",
    "shoulder": "#aeb6bf",
}


def road_band_color(band: RoadBandSpec) -> str:
    return ROAD_BAND_COLORS[band.kind]


def actor_color(actor_id: str, role: str, actor_type: str) -> str:
    if role == "ego" or actor_id == "ego":
        return "#151515"
    if actor_id == "parked_van" or actor_type == "van":
        return "#2563eb"
    if actor_type == "pedestrian":
        return "#f97316"
    if role == "lead_vehicle":
        return "#d9d6c8"
    if role == "cut_in_actor" or actor_id == "cut_in_vehicle":
        return "#ef4444"
    if role == "crossing_vehicle":
        return "#0ea5e9"
    if role == "oncoming_vehicle":
        return "#f97316"
    return "#64748b"


def path_color(path_name: str) -> str:
    if path_name == "ego_path":
        return "#f8fafc"
    if path_name == "pedestrian_crossing_path":
        return "#ef4444"
    if "cut_in" in path_name:
        return "#ef4444"
    if "crossing" in path_name:
        return "#0ea5e9"
    if "turn" in path_name:
        return "#f97316"
    if "lead" in path_name:
        return "#d9d6c8"
    return "#64748b"


__all__ = [
    "CLEAN_PREVIEW_ASPECT_RATIO",
    "PREVIEW_DISPLAY_ORIENTATIONS",
    "PREVIEW_PRESENTATION_STYLES",
    "actor_color",
    "path_color",
    "road_band_color",
]
