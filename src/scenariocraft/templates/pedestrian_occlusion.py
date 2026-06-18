from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from scenariocraft.schemas import (
    ActorSpec,
    CriticalitySpec,
    FootprintSpec,
    LayoutSpec,
    PathSpec,
    Point2D,
    Pose2D,
    RoadBandSpec,
    RoadSpec,
    ScenarioSpec,
    SpatialRelationSpec,
    TriggerSpec,
    WeatherSpec,
)


@dataclass(frozen=True)
class PedestrianOcclusionParameters:
    ego_speed_kph: float = 35.0
    pedestrian_speed_mps: float = 1.5
    target_conflict_distance_m: float = 25.0
    trigger_offset_m: float = 18.0
    van_center_x_m: float = 20.0
    van_center_y_m: float = 3.25
    pedestrian_start_y_m: float = 4.60
    pedestrian_end_y_m: float = -1.00
    van_length_m: float = 5.3
    van_width_m: float = 2.0
    ego_length_m: float = 4.6
    ego_width_m: float = 1.9
    pedestrian_length_m: float = 0.6
    pedestrian_width_m: float = 0.6
    minimum_path_clearance_m: float = 0.5
    weather: str = "rainy_wet"


class PedestrianOcclusionTemplate:
    template_id = "pedestrian_occlusion"
    description = "Rainy urban pedestrian occlusion with ego approaching a parked van."
    required_actors = ("ego", "occluder", "crossing_actor")
    default_parameters: Mapping[str, object] = {
        "scenario_name": "rainy_pedestrian_occlusion",
        "source_text": "",
        "parameters": PedestrianOcclusionParameters(),
    }
    supported_operations = ()

    def instantiate(self, **parameters: object) -> ScenarioSpec:
        scenario_name = str(parameters.get("scenario_name", self.default_parameters["scenario_name"]))
        source_text = str(parameters.get("source_text", self.default_parameters["source_text"]))
        template_parameters = _parameters_from_mapping(parameters)
        layout = _derive_layout(template_parameters)
        metadata = {"generator": "mock", "source_text": source_text}
        return ScenarioSpec(
            scenario_name=scenario_name,
            scenario_type=self.template_id,
            road=RoadSpec(type="urban_straight", lanes_per_direction=1, speed_limit_kph=50),
            weather=WeatherSpec(rain=True, road_condition="wet"),
            actors=[
                ActorSpec(id="ego", type="car", role="ego", initial_speed_kph=template_parameters.ego_speed_kph),
                ActorSpec(id="parked_van", type="van", role="occluder", state="parked"),
                ActorSpec(id="pedestrian", type="pedestrian", role="crossing_actor", speed_mps=template_parameters.pedestrian_speed_mps),
            ],
            trigger=TriggerSpec(
                type="relative_distance",
                source="ego",
                target="parked_van",
                distance_m=template_parameters.trigger_offset_m,
            ),
            intended_criticality=CriticalitySpec(type="near_miss", target_min_ttc_s=1.5),
            metadata=metadata,
            layout=layout,
            spatial_relations=_spatial_relations(template_parameters),
        )


def _parameters_from_mapping(values: Mapping[str, object]) -> PedestrianOcclusionParameters:
    template_parameters = values.get("parameters", PedestrianOcclusionParameters())
    if isinstance(template_parameters, PedestrianOcclusionParameters):
        base = template_parameters
    elif isinstance(template_parameters, Mapping):
        base = PedestrianOcclusionParameters(**template_parameters)
    else:
        raise TypeError("parameters must be a PedestrianOcclusionParameters or mapping.")
    overrides = {
        field_name: values[field_name]
        for field_name in PedestrianOcclusionParameters.__dataclass_fields__
        if field_name in values
    }
    return replace(base, **overrides) if overrides else base


def _derive_layout(parameters: PedestrianOcclusionParameters) -> LayoutSpec:
    """Derive ego-local layout from semantic template parameters.

    Convention: +x is ego forward, y=0 is ego lane center, positive y is curb/parked-van side,
    and actor poses reference the center of their footprint.
    """
    conflict_point = Point2D(parameters.target_conflict_distance_m, 0.0)
    trigger_point = Point2D(conflict_point.x_m - parameters.trigger_offset_m, 0.0)
    pedestrian_start = Point2D(conflict_point.x_m, parameters.pedestrian_start_y_m)
    pedestrian_end = Point2D(conflict_point.x_m, parameters.pedestrian_end_y_m)
    ego_pose = Pose2D(x_m=0.0, y_m=0.0, heading_rad=0.0)
    van_pose = Pose2D(x_m=parameters.van_center_x_m, y_m=parameters.van_center_y_m, heading_rad=0.0)
    pedestrian_pose = Pose2D(x_m=pedestrian_start.x_m, y_m=pedestrian_start.y_m, heading_rad=0.0)
    layout = LayoutSpec(
        coordinate_frame="ego_local",
        actor_poses={
            "ego": ego_pose,
            "parked_van": van_pose,
            "pedestrian": pedestrian_pose,
        },
        actor_footprints={
            "ego": FootprintSpec(length_m=parameters.ego_length_m, width_m=parameters.ego_width_m),
            "parked_van": FootprintSpec(length_m=parameters.van_length_m, width_m=parameters.van_width_m),
            "pedestrian": FootprintSpec(length_m=parameters.pedestrian_length_m, width_m=parameters.pedestrian_width_m),
        },
        paths={
            "ego_path": PathSpec(name="ego_path", points=(Point2D(0.0, 0.0), Point2D(60.0, 0.0))),
            "pedestrian_crossing_path": PathSpec(
                name="pedestrian_crossing_path",
                points=(pedestrian_start, pedestrian_end),
            ),
        },
        points={
            "conflict_point": conflict_point,
            "trigger_point": trigger_point,
        },
        road_bands=_road_bands(),
    )
    _validate_derived_geometry(layout, parameters)
    return layout


def _road_bands() -> tuple[RoadBandSpec, ...]:
    return (
        RoadBandSpec(id="ego_side_sidewalk", kind="sidewalk", y_min_m=4.25, y_max_m=6.50),
        RoadBandSpec(id="ego_side_parking_strip", kind="parking_strip", y_min_m=1.75, y_max_m=4.25),
        RoadBandSpec(id="ego_driving_lane", kind="driving_lane", y_min_m=-1.75, y_max_m=1.75, travel_direction="+x"),
        RoadBandSpec(id="center_divider", kind="center_divider", y_min_m=-2.00, y_max_m=-1.75),
        RoadBandSpec(id="opposing_driving_lane", kind="driving_lane", y_min_m=-5.50, y_max_m=-2.00, travel_direction="-x"),
        RoadBandSpec(id="opposing_side_sidewalk", kind="sidewalk", y_min_m=-7.50, y_max_m=-5.50),
    )


def _spatial_relations(parameters: PedestrianOcclusionParameters) -> tuple[SpatialRelationSpec, ...]:
    return (
        SpatialRelationSpec(
            relation_type="occludes",
            subject="parked_van",
            object="pedestrian",
            metadata={
                "coordinate_frame": "ego_local",
                "occlusion_line_of_sight": "ego_to_pedestrian_start",
            },
        ),
        SpatialRelationSpec(
            relation_type="emerges_from_behind",
            subject="pedestrian",
            object="parked_van",
        ),
        SpatialRelationSpec(
            relation_type="path_intersects",
            subject="pedestrian_crossing_path",
            object="ego_path",
            metadata={"at": "conflict_point", "minimum_clearance_m": parameters.minimum_path_clearance_m},
        ),
        SpatialRelationSpec(
            relation_type="ahead_of",
            subject="conflict_point",
            object="ego",
            metadata={"axis": "+x"},
        ),
        SpatialRelationSpec(
            relation_type="trigger_before_conflict",
            subject="trigger_point",
            object="conflict_point",
            metadata={"axis": "+x"},
        ),
    )


def _validate_derived_geometry(layout: LayoutSpec, parameters: PedestrianOcclusionParameters) -> None:
    ego_lane = _road_band(layout, "ego_driving_lane")
    parking_strip = _road_band(layout, "ego_side_parking_strip")
    sidewalk = _road_band(layout, "ego_side_sidewalk")
    van_rect = _actor_rectangle(layout, "parked_van")
    ego_rect = _actor_rectangle(layout, "ego")
    pedestrian_rect = _actor_rectangle(layout, "pedestrian")
    pedestrian_path = layout.paths["pedestrian_crossing_path"]
    pedestrian_start = pedestrian_path.points[0]
    conflict_point = layout.points["conflict_point"]
    trigger_point = layout.points["trigger_point"]
    ego_pose = layout.actor_poses["ego"]
    if not _rect_inside_band(ego_rect, ego_lane):
        raise ValueError("Derived ego footprint is not fully inside ego driving lane.")
    if not _rect_inside_band(van_rect, parking_strip):
        raise ValueError("Derived parked van footprint is not fully inside parking strip.")
    if not _rect_inside_band(pedestrian_rect, sidewalk):
        raise ValueError("Derived pedestrian footprint is not fully inside ego-side sidewalk.")
    if not _point_inside_band(conflict_point, ego_lane):
        raise ValueError("Derived conflict point is not inside ego driving lane.")
    if not _point_inside_band(trigger_point, ego_lane):
        raise ValueError("Derived trigger point is not inside ego driving lane.")
    if not _point_inside_band(pedestrian_start, sidewalk):
        raise ValueError("Derived pedestrian path does not start on the sidewalk.")
    if not _vertical_segment_intersects_band(pedestrian_path.points[0], pedestrian_path.points[-1], ego_lane):
        raise ValueError("Derived pedestrian path does not cross ego driving lane.")
    if _vertical_segment_intersects_rect(pedestrian_path.points[0], pedestrian_path.points[-1], van_rect):
        raise ValueError("Derived pedestrian path intersects parked van footprint.")
    clearance = _vertical_segment_rect_clearance(pedestrian_path.points[0], pedestrian_path.points[-1], van_rect)
    if clearance + 1e-9 < parameters.minimum_path_clearance_m:
        raise ValueError("Derived pedestrian path does not satisfy minimum parked-van clearance.")
    if not _point_on_vertical_segment(conflict_point, pedestrian_path.points[0], pedestrian_path.points[-1]):
        raise ValueError("Derived conflict point does not lie on pedestrian crossing path.")
    if conflict_point.x_m <= ego_pose.x_m:
        raise ValueError("Derived conflict point must be ahead of ego.")
    if trigger_point.x_m >= conflict_point.x_m:
        raise ValueError("Derived trigger point must be before conflict point.")
    if not _segment_intersects_rect(Point2D(ego_pose.x_m, ego_pose.y_m), pedestrian_start, van_rect):
        raise ValueError("Derived parked van does not occlude ego-to-pedestrian-start line of sight.")


def _road_band(layout: LayoutSpec, band_id: str) -> RoadBandSpec:
    for band in layout.road_bands:
        if band.id == band_id:
            return band
    raise ValueError(f"Derived layout is missing road band {band_id}.")


def _actor_rectangle(layout: LayoutSpec, actor_id: str) -> tuple[float, float, float, float]:
    pose = layout.actor_poses[actor_id]
    footprint = layout.actor_footprints[actor_id]
    half_length = footprint.length_m / 2.0
    half_width = footprint.width_m / 2.0
    return (
        pose.x_m - half_length,
        pose.x_m + half_length,
        pose.y_m - half_width,
        pose.y_m + half_width,
    )


def _rect_inside_band(rect: tuple[float, float, float, float], band: RoadBandSpec) -> bool:
    _, _, min_y, max_y = rect
    return band.y_min_m <= min_y <= max_y <= band.y_max_m


def _point_inside_band(point: Point2D, band: RoadBandSpec) -> bool:
    return band.y_min_m <= point.y_m <= band.y_max_m


def _vertical_segment_intersects_band(start: Point2D, end: Point2D, band: RoadBandSpec) -> bool:
    y0, y1 = sorted((start.y_m, end.y_m))
    return max(y0, band.y_min_m) <= min(y1, band.y_max_m)


def _vertical_segment_intersects_rect(start: Point2D, end: Point2D, rect: tuple[float, float, float, float]) -> bool:
    min_x, max_x, min_y, max_y = rect
    y0, y1 = sorted((start.y_m, end.y_m))
    return min_x <= start.x_m <= max_x and max(y0, min_y) <= min(y1, max_y)


def _vertical_segment_rect_clearance(start: Point2D, end: Point2D, rect: tuple[float, float, float, float]) -> float:
    min_x, max_x, min_y, max_y = rect
    y0, y1 = sorted((start.y_m, end.y_m))
    dx = 0.0 if min_x <= start.x_m <= max_x else min(abs(start.x_m - min_x), abs(start.x_m - max_x))
    dy = 0.0 if max(y0, min_y) <= min(y1, max_y) else min(abs(y0 - max_y), abs(y1 - min_y))
    return (dx ** 2 + dy ** 2) ** 0.5


def _point_on_vertical_segment(point: Point2D, start: Point2D, end: Point2D) -> bool:
    y0, y1 = sorted((start.y_m, end.y_m))
    return point.x_m == start.x_m and y0 <= point.y_m <= y1


def _segment_intersects_rect(start: Point2D, end: Point2D, rect: tuple[float, float, float, float]) -> bool:
    min_x, max_x, min_y, max_y = rect
    if _point_in_rect(start, rect) or _point_in_rect(end, rect):
        return True
    corners = (
        Point2D(min_x, min_y),
        Point2D(max_x, min_y),
        Point2D(max_x, max_y),
        Point2D(min_x, max_y),
    )
    edges = ((corners[0], corners[1]), (corners[1], corners[2]), (corners[2], corners[3]), (corners[3], corners[0]))
    return any(_segments_intersect(start, end, edge_start, edge_end) for edge_start, edge_end in edges)


def _point_in_rect(point: Point2D, rect: tuple[float, float, float, float]) -> bool:
    min_x, max_x, min_y, max_y = rect
    return min_x <= point.x_m <= max_x and min_y <= point.y_m <= max_y


def _segments_intersect(a: Point2D, b: Point2D, c: Point2D, d: Point2D) -> bool:
    def orientation(p: Point2D, q: Point2D, r: Point2D) -> float:
        return (q.y_m - p.y_m) * (r.x_m - q.x_m) - (q.x_m - p.x_m) * (r.y_m - q.y_m)

    def on_segment(p: Point2D, q: Point2D, r: Point2D) -> bool:
        return (
            min(p.x_m, r.x_m) <= q.x_m <= max(p.x_m, r.x_m)
            and min(p.y_m, r.y_m) <= q.y_m <= max(p.y_m, r.y_m)
        )

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    if o1 == 0 and on_segment(a, c, b):
        return True
    if o2 == 0 and on_segment(a, d, b):
        return True
    if o3 == 0 and on_segment(c, a, d):
        return True
    if o4 == 0 and on_segment(c, b, d):
        return True
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)
