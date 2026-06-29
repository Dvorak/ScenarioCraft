from __future__ import annotations

from dataclasses import dataclass, replace
from math import hypot
from typing import Mapping

from scenariocraft.core.schemas import (
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
    ScenarioTimingSpec,
    SpatialRelationSpec,
    StoryboardActionSpec,
    StoryboardActSpec,
    StoryboardEventSpec,
    StoryboardManeuverGroupSpec,
    StoryboardSpec,
    StoryboardStorySpec,
    TriggerConditionSpec,
    TriggerSpec,
    WeatherSpec,
)


@dataclass(frozen=True)
class PedestrianOcclusionParameters:
    ego_speed_kph: float = 35.0
    pedestrian_speed_mps: float = 1.5
    trigger_offset_m: float = 18.0
    van_to_conflict_offset_m: float = 5.0
    ego_start_x_m: float = 0.0
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
    total_duration_s: float = 8.0
    preferred_trigger_earliest_s: float = 1.5
    preferred_trigger_latest_s: float = 3.0
    minimum_pre_trigger_context_s: float = 0.5
    minimum_post_trigger_buffer_s: float = 0.5
    canonical_nominal_trigger_time_s: float | None = None
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
        timing = _derive_timing(template_parameters)
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
                condition=_trigger_condition(template_parameters),
            ),
            intended_criticality=CriticalitySpec(type="near_miss", target_min_ttc_s=1.5),
            metadata=metadata,
            layout=layout,
            spatial_relations=_spatial_relations(template_parameters),
            timing=timing,
            storyboard=_storyboard_semantics(),
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


def _derive_timing(parameters: PedestrianOcclusionParameters) -> ScenarioTimingSpec:
    return ScenarioTimingSpec(
        total_duration_s=parameters.total_duration_s,
        preferred_trigger_earliest_s=parameters.preferred_trigger_earliest_s,
        preferred_trigger_latest_s=parameters.preferred_trigger_latest_s,
        minimum_pre_trigger_context_s=parameters.minimum_pre_trigger_context_s,
        minimum_post_trigger_buffer_s=parameters.minimum_post_trigger_buffer_s,
    )


def _trigger_condition(parameters: PedestrianOcclusionParameters) -> TriggerConditionSpec:
    return TriggerConditionSpec(
        id="pedestrian_start_relative_distance",
        metric="relative_distance",
        source="ego",
        target="parked_van",
        rule="lessThan",
        value=parameters.trigger_offset_m,
        unit="m",
        coordinate_system="entity",
        relative_distance_type="longitudinal",
        freespace=False,
        target_kind="entity",
    )


def _storyboard_semantics() -> StoryboardSpec:
    return StoryboardSpec(
        stories=(
            StoryboardStorySpec(
                id="rainy_pedestrian_occlusion_story",
                act_refs=("pedestrian_occlusion_act",),
            ),
        ),
        acts=(
            StoryboardActSpec(
                id="pedestrian_occlusion_act",
                maneuver_group_refs=("ego_driving", "pedestrian_crossing"),
                stop_trigger_ref="scenario_stop_time",
            ),
        ),
        maneuver_groups=(
            StoryboardManeuverGroupSpec(
                id="ego_driving",
                actor_refs=("ego",),
                event_refs=("ego_drives_forward",),
            ),
            StoryboardManeuverGroupSpec(
                id="pedestrian_crossing",
                actor_refs=("pedestrian",),
                event_refs=("pedestrian_starts_crossing",),
            ),
        ),
        events=(
            StoryboardEventSpec(
                id="ego_drives_forward",
                priority="overwrite",
                start_trigger_ref="ego_starts_driving",
                action_refs=("ego_follow_ego_path",),
            ),
            StoryboardEventSpec(
                id="pedestrian_starts_crossing",
                priority="overwrite",
                start_trigger_ref="pedestrian_start_relative_distance",
                action_refs=("pedestrian_follow_crossing_path",),
            ),
        ),
        actions=(
            StoryboardActionSpec(
                id="ego_follow_ego_path",
                type="follow_trajectory",
                actor_refs=("ego",),
                path_ref="ego_path",
            ),
            StoryboardActionSpec(
                id="pedestrian_follow_crossing_path",
                type="follow_trajectory",
                actor_refs=("pedestrian",),
                path_ref="pedestrian_crossing_path",
            ),
        ),
    )


def _derive_layout(parameters: PedestrianOcclusionParameters) -> LayoutSpec:
    """Derive ego-local layout from semantic template parameters.

    Convention: +x is ego forward, y=0 is ego lane center, positive y is curb/parked-van side,
    and actor poses reference the center of their footprint.
    """
    ego_speed_mps = parameters.ego_speed_kph / 3.6
    nominal_trigger_time_s = _nominal_trigger_time_s(parameters)
    van_center_x_m = parameters.ego_start_x_m + ego_speed_mps * nominal_trigger_time_s + parameters.trigger_offset_m
    conflict_point = Point2D(van_center_x_m + parameters.van_to_conflict_offset_m, 0.0)
    trigger_point = Point2D(van_center_x_m - parameters.trigger_offset_m, 0.0)
    pedestrian_start = Point2D(conflict_point.x_m, parameters.pedestrian_start_y_m)
    pedestrian_end = Point2D(conflict_point.x_m, parameters.pedestrian_end_y_m)
    ego_pose = Pose2D(x_m=parameters.ego_start_x_m, y_m=0.0, heading_rad=0.0)
    van_pose = Pose2D(x_m=van_center_x_m, y_m=parameters.van_center_y_m, heading_rad=0.0)
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
            "ego_path": PathSpec(name="ego_path", points=(Point2D(parameters.ego_start_x_m, 0.0), Point2D(conflict_point.x_m + 35.0, 0.0))),
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


@dataclass(frozen=True)
class TimingAssessment:
    predicted_trigger_time_s: float
    pedestrian_crossing_duration_s: float
    hard_latest_trigger_s: float
    classification: str

    def to_dict(self) -> dict[str, float | str]:
        return {
            "predicted_trigger_time_s": self.predicted_trigger_time_s,
            "pedestrian_crossing_duration_s": self.pedestrian_crossing_duration_s,
            "hard_latest_trigger_s": self.hard_latest_trigger_s,
            "classification": self.classification,
        }


def assess_pedestrian_occlusion_timing(spec: ScenarioSpec) -> TimingAssessment | None:
    if spec.timing is None or spec.layout is None:
        return None
    predicted_trigger_time_s = estimate_trigger_time_s(spec)
    pedestrian_duration_s = _pedestrian_crossing_duration_s(spec)
    if predicted_trigger_time_s is None or pedestrian_duration_s is None:
        return None
    hard_latest_trigger_s = (
        spec.timing.total_duration_s
        - pedestrian_duration_s
        - spec.timing.minimum_post_trigger_buffer_s
    )
    if predicted_trigger_time_s < spec.timing.minimum_pre_trigger_context_s:
        classification = "too_early"
    elif predicted_trigger_time_s > hard_latest_trigger_s:
        classification = "too_late"
    elif spec.timing.preferred_trigger_earliest_s <= predicted_trigger_time_s <= spec.timing.preferred_trigger_latest_s:
        classification = "preferred"
    else:
        classification = "acceptable"
    return TimingAssessment(
        predicted_trigger_time_s=predicted_trigger_time_s,
        pedestrian_crossing_duration_s=pedestrian_duration_s,
        hard_latest_trigger_s=hard_latest_trigger_s,
        classification=classification,
    )


def estimate_trigger_time_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    source_pose = spec.layout.actor_poses.get(spec.trigger.source)
    target_pose = spec.layout.actor_poses.get(spec.trigger.target)
    source_actor = spec.actor_by_id(spec.trigger.source)
    if source_pose is None or target_pose is None or source_actor is None or source_actor.initial_speed_kph is None:
        return None
    speed_mps = source_actor.initial_speed_kph / 3.6
    if speed_mps <= 0:
        return None
    return (target_pose.x_m - source_pose.x_m - spec.trigger.distance_m) / speed_mps


def _pedestrian_crossing_duration_s(spec: ScenarioSpec) -> float | None:
    if spec.layout is None:
        return None
    pedestrian = spec.actor_by_role("crossing_actor")
    path = spec.layout.paths.get("pedestrian_crossing_path")
    if pedestrian is None or pedestrian.speed_mps is None or pedestrian.speed_mps <= 0 or path is None:
        return None
    distance_m = 0.0
    for start, end in zip(path.points, path.points[1:]):
        distance_m += hypot(end.x_m - start.x_m, end.y_m - start.y_m)
    return distance_m / pedestrian.speed_mps


def _nominal_trigger_time_s(parameters: PedestrianOcclusionParameters) -> float:
    timing = _derive_timing(parameters)
    nominal = (
        parameters.canonical_nominal_trigger_time_s
        if parameters.canonical_nominal_trigger_time_s is not None
        else timing.preferred_trigger_latest_s
    )
    if not timing.preferred_trigger_earliest_s <= nominal <= timing.preferred_trigger_latest_s:
        raise ValueError("canonical_nominal_trigger_time_s must be inside the preferred trigger window.")
    return nominal


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
