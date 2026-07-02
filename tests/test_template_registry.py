from dataclasses import replace

import pytest

from scenariocraft.core.templates import generate_default_pedestrian_occlusion_spec
from scenariocraft.core.roads import URBAN_TWO_WAY_PARKING_FILENAME
from scenariocraft.core.schemas import Point2D
from scenariocraft.core.schemas import ScenarioSpec
from scenariocraft.core.templates import PedestrianOcclusionTemplate, get_template, registered_templates
from scenariocraft.core.metrics import (
    compute_timing_metrics,
    ego_lead_time_to_conflict_s,
    pedestrian_time_to_conflict_s,
    trigger_threshold_time_s,
)
from scenariocraft.core.templates.pedestrian_occlusion import (
    PedestrianOcclusionParameters,
    _actor_rectangle,
    _segment_intersects_rect,
    _vertical_segment_intersects_rect,
    _vertical_segment_rect_clearance,
    assess_pedestrian_occlusion_timing,
    estimate_trigger_time_s,
)


DEFAULT_EGO_SPEED_MPS = 35.0 / 3.6
DEFAULT_TRIGGER_DISTANCE_M = 18.0
DEFAULT_NOMINAL_TRIGGER_TIME_S = 3.0
DEFAULT_VAN_X_M = DEFAULT_EGO_SPEED_MPS * DEFAULT_NOMINAL_TRIGGER_TIME_S + DEFAULT_TRIGGER_DISTANCE_M
DEFAULT_CONFLICT_X_M = DEFAULT_VAN_X_M + 5.0
DEFAULT_TRIGGER_X_M = DEFAULT_VAN_X_M - DEFAULT_TRIGGER_DISTANCE_M


def test_registry_contains_pedestrian_occlusion_template() -> None:
    templates = registered_templates()

    assert "pedestrian_occlusion" in templates
    assert isinstance(get_template("pedestrian_occlusion"), PedestrianOcclusionTemplate)


def test_registry_contains_lead_vehicle_braking_template() -> None:
    templates = registered_templates()

    assert "lead_vehicle_braking" in templates
    assert get_template("lead_vehicle_braking").template_id == "lead_vehicle_braking"


def test_pedestrian_occlusion_template_exposes_minimal_metadata() -> None:
    template = get_template("pedestrian_occlusion")

    assert template.template_id == "pedestrian_occlusion"
    assert template.description
    assert template.required_actors == ("ego", "occluder", "crossing_actor")
    assert "scenario_name" in template.default_parameters
    assert isinstance(template.supported_operations, tuple)


def test_pedestrian_occlusion_template_instantiates_schema_valid_spec() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assert isinstance(spec, ScenarioSpec)
    assert ScenarioSpec.from_json(spec.to_json()) == spec


def test_pedestrian_occlusion_template_emits_layout() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assert spec.layout is not None
    assert spec.layout.coordinate_frame == "ego_local"
    assert spec.layout.actor_poses["ego"].x_m == 0.0
    assert spec.layout.actor_poses["ego"].y_m == 0.0
    assert spec.layout.actor_poses["parked_van"].x_m == pytest.approx(DEFAULT_VAN_X_M)
    assert spec.layout.actor_poses["parked_van"].y_m == 3.25
    assert spec.layout.actor_poses["pedestrian"].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert spec.layout.actor_poses["pedestrian"].y_m == 4.60
    assert spec.layout.actor_footprints["ego"].length_m == 4.6
    assert spec.layout.actor_footprints["parked_van"].length_m == 5.3
    assert spec.layout.actor_footprints["pedestrian"].width_m == 0.6
    crossing_path = spec.layout.paths["pedestrian_crossing_path"]
    assert crossing_path.points[0].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert crossing_path.points[0].y_m == 4.60
    assert crossing_path.points[-1].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert crossing_path.points[-1].y_m == -1.00
    assert spec.layout.points["conflict_point"].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert spec.layout.points["conflict_point"].y_m == 0.0
    assert spec.layout.points["trigger_point"].x_m == pytest.approx(DEFAULT_TRIGGER_X_M)
    assert spec.layout.points["trigger_point"].y_m == 0.0
    assert spec.spatial_relations


def test_pedestrian_occlusion_template_emits_default_timing_policy() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assert spec.timing is not None
    assert spec.timing.total_duration_s == 8.0
    assert spec.timing.preferred_trigger_earliest_s == 1.5
    assert spec.timing.preferred_trigger_latest_s == 3.0
    assert spec.timing.minimum_pre_trigger_context_s == 0.5
    assert spec.timing.minimum_post_trigger_buffer_s == 0.5


def test_pedestrian_occlusion_template_emits_trigger_and_storyboard_semantics() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assert spec.trigger.condition is not None
    assert spec.trigger.condition.id == "pedestrian_start_relative_distance"
    assert spec.trigger.condition.metric == "relative_distance"
    assert spec.trigger.condition.source == "ego"
    assert spec.trigger.condition.target == "parked_van"
    assert spec.trigger.condition.rule == "lessThan"
    assert spec.trigger.condition.value == DEFAULT_TRIGGER_DISTANCE_M
    assert spec.trigger.condition.unit == "m"
    assert spec.trigger.condition.coordinate_system == "entity"
    assert spec.trigger.condition.relative_distance_type == "longitudinal"
    assert spec.storyboard is not None
    events = {event.id: event for event in spec.storyboard.events}
    actions = {action.id: action for action in spec.storyboard.actions}
    assert events["pedestrian_starts_crossing"].start_trigger_ref == "pedestrian_start_relative_distance"
    assert events["pedestrian_starts_crossing"].action_refs == ("pedestrian_follow_crossing_path",)
    assert actions["pedestrian_follow_crossing_path"].type == "follow_trajectory"
    assert actions["pedestrian_follow_crossing_path"].actor_refs == ("pedestrian",)
    assert actions["pedestrian_follow_crossing_path"].path_ref == "pedestrian_crossing_path"


def test_canonical_timing_metrics_distinguish_target_ttc_threshold_and_lead_time() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    metrics = compute_timing_metrics(spec)

    assert metrics.target_ttc_s == 1.5
    assert metrics.trigger_threshold_time_s == pytest.approx(DEFAULT_TRIGGER_DISTANCE_M / DEFAULT_EGO_SPEED_MPS)
    assert metrics.ego_lead_time_to_conflict_s == pytest.approx(
        (DEFAULT_CONFLICT_X_M - DEFAULT_TRIGGER_X_M) / DEFAULT_EGO_SPEED_MPS
    )
    assert metrics.pedestrian_time_to_conflict_s == pytest.approx(4.6 / 1.5)
    assert metrics.runtime_min_ttc_s is None
    assert metrics.time_headway_s is None
    assert trigger_threshold_time_s(spec) == metrics.trigger_threshold_time_s
    assert ego_lead_time_to_conflict_s(spec) == metrics.ego_lead_time_to_conflict_s
    assert pedestrian_time_to_conflict_s(spec) == metrics.pedestrian_time_to_conflict_s


def test_trigger_point_repair_changes_lead_time_not_relative_distance_threshold_time() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    assert spec.layout is not None
    conflict = spec.layout.points["conflict_point"]
    original_threshold_time = trigger_threshold_time_s(spec)

    after_conflict_layout = replace(
        spec.layout,
        points={
            **spec.layout.points,
            "trigger_point": Point2D(conflict.x_m + 1.0, spec.layout.points["trigger_point"].y_m),
        },
    )
    after_conflict = replace(spec, layout=after_conflict_layout)
    repaired_layout = replace(
        spec.layout,
        points={
            **spec.layout.points,
            "trigger_point": Point2D(conflict.x_m - 1.0, spec.layout.points["trigger_point"].y_m),
        },
    )
    repaired = replace(spec, layout=repaired_layout)

    assert trigger_threshold_time_s(after_conflict) == original_threshold_time
    assert trigger_threshold_time_s(repaired) == original_threshold_time
    assert ego_lead_time_to_conflict_s(after_conflict) == pytest.approx(-1.0 / DEFAULT_EGO_SPEED_MPS)
    assert ego_lead_time_to_conflict_s(repaired) == pytest.approx(1.0 / DEFAULT_EGO_SPEED_MPS)


def test_pedestrian_occlusion_template_window_changes_nominal_longitudinal_geometry_only() -> None:
    default_spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    changed_spec = get_template("pedestrian_occlusion").instantiate(
        source_text="rainy pedestrian occlusion",
        total_duration_s=10.0,
        preferred_trigger_earliest_s=2.0,
        preferred_trigger_latest_s=4.0,
    )
    assert default_spec.layout is not None
    assert changed_spec.layout is not None

    expected_van_x = DEFAULT_EGO_SPEED_MPS * 4.0 + DEFAULT_TRIGGER_DISTANCE_M
    expected_conflict_x = expected_van_x + 5.0
    assert changed_spec.layout.actor_poses["parked_van"].x_m == pytest.approx(expected_van_x)
    assert changed_spec.layout.actor_poses["pedestrian"].x_m == pytest.approx(expected_conflict_x)
    assert changed_spec.layout.points["conflict_point"].x_m == pytest.approx(expected_conflict_x)
    assert changed_spec.layout.actor_poses["parked_van"].y_m == default_spec.layout.actor_poses["parked_van"].y_m
    assert changed_spec.layout.actor_poses["pedestrian"].y_m == default_spec.layout.actor_poses["pedestrian"].y_m
    assert changed_spec.layout.road_bands == default_spec.layout.road_bands


def test_pedestrian_occlusion_timing_assessment_classifies_default_as_preferred() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assessment = assess_pedestrian_occlusion_timing(spec)

    assert assessment is not None
    assert estimate_trigger_time_s(spec) == pytest.approx(DEFAULT_NOMINAL_TRIGGER_TIME_S)
    assert assessment.predicted_trigger_time_s == pytest.approx(DEFAULT_NOMINAL_TRIGGER_TIME_S)
    assert assessment.pedestrian_crossing_duration_s == pytest.approx(5.6 / 1.5)
    assert assessment.hard_latest_trigger_s == pytest.approx(8.0 - (5.6 / 1.5) - 0.5)
    assert assessment.classification == "preferred"


def test_pedestrian_occlusion_timing_assessment_classifies_mutations() -> None:
    preferred_spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    assert preferred_spec.layout is not None

    too_early_layout = replace(
        preferred_spec.layout,
        actor_poses={
            **preferred_spec.layout.actor_poses,
            "parked_van": replace(preferred_spec.layout.actor_poses["parked_van"], x_m=20.0),
        },
    )
    too_early = assess_pedestrian_occlusion_timing(replace(preferred_spec, layout=too_early_layout))
    assert too_early is not None
    assert too_early.classification == "too_early"

    acceptable_base = get_template("pedestrian_occlusion").instantiate(
        source_text="rainy pedestrian occlusion",
        preferred_trigger_earliest_s=1.5,
        preferred_trigger_latest_s=2.0,
    )
    assert acceptable_base.layout is not None
    acceptable_layout = replace(
        acceptable_base.layout,
        actor_poses={
            **acceptable_base.layout.actor_poses,
            "parked_van": replace(
                acceptable_base.layout.actor_poses["parked_van"],
                x_m=DEFAULT_EGO_SPEED_MPS * 2.5 + DEFAULT_TRIGGER_DISTANCE_M,
            ),
        },
    )
    acceptable = assess_pedestrian_occlusion_timing(replace(acceptable_base, layout=acceptable_layout))
    assert acceptable is not None
    assert acceptable.predicted_trigger_time_s == pytest.approx(2.5)
    assert acceptable.classification == "acceptable"

    too_late_layout = replace(
        preferred_spec.layout,
        actor_poses={
            **preferred_spec.layout.actor_poses,
            "parked_van": replace(preferred_spec.layout.actor_poses["parked_van"], x_m=70.0),
        },
    )
    too_late = assess_pedestrian_occlusion_timing(replace(preferred_spec, layout=too_late_layout))
    assert too_late is not None
    assert too_late.classification == "too_late"


def test_pedestrian_occlusion_template_emits_canonical_road_bands() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    assert spec.layout is not None

    bands = {band.id: band for band in spec.layout.road_bands}

    assert bands["ego_side_sidewalk"].kind == "sidewalk"
    assert (bands["ego_side_sidewalk"].y_min_m, bands["ego_side_sidewalk"].y_max_m) == (4.25, 6.50)
    assert bands["ego_side_parking_strip"].kind == "parking_strip"
    assert (bands["ego_side_parking_strip"].y_min_m, bands["ego_side_parking_strip"].y_max_m) == (1.75, 4.25)
    assert bands["ego_driving_lane"].kind == "driving_lane"
    assert (bands["ego_driving_lane"].y_min_m, bands["ego_driving_lane"].y_max_m, bands["ego_driving_lane"].travel_direction) == (-1.75, 1.75, "+x")
    assert bands["center_divider"].kind == "center_divider"
    assert (bands["center_divider"].y_min_m, bands["center_divider"].y_max_m) == (-2.00, -1.75)
    assert bands["opposing_driving_lane"].kind == "driving_lane"
    assert (bands["opposing_driving_lane"].y_min_m, bands["opposing_driving_lane"].y_max_m, bands["opposing_driving_lane"].travel_direction) == (-5.50, -2.00, "-x")
    assert bands["opposing_side_sidewalk"].kind == "sidewalk"
    assert (bands["opposing_side_sidewalk"].y_min_m, bands["opposing_side_sidewalk"].y_max_m) == (-7.50, -5.50)


def test_pedestrian_occlusion_template_uses_canonical_opendrive_candidate_road_metadata() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")

    assert spec.road.type == "urban_straight"
    assert spec.road.lanes_per_direction == 1
    assert spec.layout is not None
    assert spec.layout.coordinate_frame == "ego_local"
    assert spec.layout.road_bands
    assert URBAN_TWO_WAY_PARKING_FILENAME == "urban_two_way_parking.xodr"


def test_pedestrian_occlusion_template_emits_spatial_semantics() -> None:
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    assert spec.layout is not None
    relations = {(relation.relation_type, relation.subject, relation.object) for relation in spec.spatial_relations}

    assert ("occludes", "parked_van", "pedestrian") in relations
    assert ("emerges_from_behind", "pedestrian", "parked_van") in relations
    assert ("path_intersects", "pedestrian_crossing_path", "ego_path") in relations
    assert ("ahead_of", "conflict_point", "ego") in relations
    assert ("trigger_before_conflict", "trigger_point", "conflict_point") in relations
    crossing_path = spec.layout.paths["pedestrian_crossing_path"]
    assert crossing_path.points[0].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert crossing_path.points[0].y_m == 4.60
    assert crossing_path.points[-1].x_m == pytest.approx(DEFAULT_CONFLICT_X_M)
    assert crossing_path.points[-1].y_m == -1.00
    assert spec.layout.actor_poses["pedestrian"].x_m == crossing_path.points[0].x_m
    assert spec.layout.actor_poses["pedestrian"].y_m == crossing_path.points[0].y_m
    assert spec.layout.points["trigger_point"].x_m < spec.layout.points["conflict_point"].x_m
    assert spec.layout.points["conflict_point"].x_m > spec.layout.actor_poses["ego"].x_m


def test_pedestrian_occlusion_geometry_satisfies_non_overlap_and_occlusion() -> None:
    parameters = PedestrianOcclusionParameters()
    spec = get_template("pedestrian_occlusion").instantiate(source_text="rainy pedestrian occlusion")
    assert spec.layout is not None
    van_rect = _actor_rectangle(spec.layout, "parked_van")
    crossing_path = spec.layout.paths["pedestrian_crossing_path"]
    ego_pose = spec.layout.actor_poses["ego"]
    pedestrian_start = crossing_path.points[0]
    conflict_point = spec.layout.points["conflict_point"]
    trigger_point = spec.layout.points["trigger_point"]
    ego_lane = _band(spec, "ego_driving_lane")
    parking_strip = _band(spec, "ego_side_parking_strip")
    sidewalk = _band(spec, "ego_side_sidewalk")

    assert _rect_inside_band(_actor_rectangle(spec.layout, "ego"), ego_lane)
    assert _rect_inside_band(van_rect, parking_strip)
    assert _rect_inside_band(_actor_rectangle(spec.layout, "pedestrian"), sidewalk)
    assert _point_inside_band(conflict_point, ego_lane)
    assert _point_inside_band(trigger_point, ego_lane)
    assert _point_inside_band(pedestrian_start, sidewalk)
    assert _vertical_segment_intersects_band(crossing_path.points[0], crossing_path.points[-1], ego_lane)
    assert not _vertical_segment_intersects_rect(crossing_path.points[0], crossing_path.points[-1], van_rect)
    assert _vertical_segment_rect_clearance(crossing_path.points[0], crossing_path.points[-1], van_rect) >= parameters.minimum_path_clearance_m
    assert _segment_intersects_rect(Point2D(ego_pose.x_m, ego_pose.y_m), pedestrian_start, van_rect)


def _band(spec: ScenarioSpec, band_id: str):
    assert spec.layout is not None
    return next(band for band in spec.layout.road_bands if band.id == band_id)


def _rect_inside_band(rect: tuple[float, float, float, float], band: object) -> bool:
    _, _, min_y, max_y = rect
    return band.y_min_m <= min_y <= max_y <= band.y_max_m


def _point_inside_band(point: Point2D, band: object) -> bool:
    return band.y_min_m <= point.y_m <= band.y_max_m


def _vertical_segment_intersects_band(start: Point2D, end: Point2D, band: object) -> bool:
    y0, y1 = sorted((start.y_m, end.y_m))
    return max(y0, band.y_min_m) <= min(y1, band.y_max_m)


def test_mock_generation_preserves_normal_pedestrian_occlusion_spec() -> None:
    spec = generate_default_pedestrian_occlusion_spec("rainy pedestrian occlusion")

    assert spec.scenario_name == "rainy_pedestrian_occlusion"
    assert spec.scenario_type == "pedestrian_occlusion"
    assert [(actor.id, actor.type, actor.role) for actor in spec.actors] == [
        ("ego", "car", "ego"),
        ("parked_van", "van", "occluder"),
        ("pedestrian", "pedestrian", "crossing_actor"),
    ]
    assert spec.actor_by_role("ego").initial_speed_kph == 35
    assert spec.actor_by_role("crossing_actor").speed_mps == 1.5
    assert spec.trigger.type == "relative_distance"
    assert spec.trigger.source == "ego"
    assert spec.trigger.target == "parked_van"
    assert spec.trigger.distance_m == 18
    assert spec.intended_criticality.type == "near_miss"
    assert spec.intended_criticality.target_min_ttc_s == 1.5
