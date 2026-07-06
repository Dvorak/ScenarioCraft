"""Compile lightweight StoryboardSpec semantics into builder plans."""

from dataclasses import dataclass

from scenariocraft.core.schemas import ScenarioSpec


@dataclass(frozen=True)
class StoryboardBuildPlan:
    story_name: str
    act_name: str
    stop_trigger_name: str | None
    ego_group_name: str
    ego_maneuver_name: str
    ego_event_name: str
    ego_event_priority: str
    ego_action_name: str
    ego_path_ref: str | None
    ego_start_trigger_name: str
    pedestrian_group_name: str
    pedestrian_maneuver_name: str
    pedestrian_event_name: str
    pedestrian_event_priority: str
    pedestrian_action_name: str
    pedestrian_path_ref: str | None
    pedestrian_start_trigger_name: str


@dataclass(frozen=True)
class ActorEventBuildPlan:
    group_name: str
    maneuver_name: str
    event_name: str
    event_priority: str
    action_name: str
    start_trigger_name: str
    path_ref: str | None = None
    action_type: str = "follow_trajectory"
    action_metadata: dict[str, object] | None = None


def storyboard_build_plan(spec: ScenarioSpec) -> StoryboardBuildPlan:
    default = StoryboardBuildPlan(
        story_name=spec.scenario_name,
        act_name="pedestrian_occlusion_act",
        stop_trigger_name=None,
        ego_group_name="ego_driving",
        ego_maneuver_name="ego_drive_maneuver",
        ego_event_name="ego_drives_forward",
        ego_event_priority="override",
        ego_action_name="ego_follow_ego_path",
        ego_path_ref="ego_path",
        ego_start_trigger_name="ego_starts_driving",
        pedestrian_group_name="pedestrian_crossing",
        pedestrian_maneuver_name="crossing_maneuver",
        pedestrian_event_name="pedestrian_starts_crossing",
        pedestrian_event_priority="override",
        pedestrian_action_name="pedestrian_follow_crossing_path",
        pedestrian_path_ref="pedestrian_crossing_path",
        pedestrian_start_trigger_name=spec.trigger.type,
    )
    storyboard = spec.storyboard
    if storyboard is None:
        return default

    stories = {story.id: story for story in storyboard.stories}
    acts = {act.id: act for act in storyboard.acts}
    groups = {group.id: group for group in storyboard.maneuver_groups}
    events = {event.id: event for event in storyboard.events}
    actions = {action.id: action for action in storyboard.actions}

    story = next(iter(stories.values()), None)
    act = acts.get(story.act_refs[0]) if story is not None and story.act_refs else next(iter(acts.values()), None)
    ego_group = storyboard_group_for_actor(groups.values(), "ego")
    pedestrian_group = storyboard_group_for_actor(groups.values(), "pedestrian")
    ego_event = storyboard_first_event(ego_group, events)
    pedestrian_event = storyboard_first_event(pedestrian_group, events)
    ego_action = storyboard_first_action(ego_event, actions)
    pedestrian_action = storyboard_first_action(pedestrian_event, actions)

    return StoryboardBuildPlan(
        story_name=story.id if story is not None else default.story_name,
        act_name=act.id if act is not None else default.act_name,
        stop_trigger_name=act.stop_trigger_ref if act is not None else default.stop_trigger_name,
        ego_group_name=ego_group.id if ego_group is not None else default.ego_group_name,
        ego_maneuver_name=f"{ego_group.id}_maneuver" if ego_group is not None else default.ego_maneuver_name,
        ego_event_name=ego_event.id if ego_event is not None else default.ego_event_name,
        ego_event_priority=ego_event.priority if ego_event is not None else default.ego_event_priority,
        ego_action_name=ego_action.id if ego_action is not None else default.ego_action_name,
        ego_path_ref=ego_action.path_ref if ego_action is not None else default.ego_path_ref,
        ego_start_trigger_name=ego_event.start_trigger_ref if ego_event is not None else default.ego_start_trigger_name,
        pedestrian_group_name=(
            pedestrian_group.id if pedestrian_group is not None else default.pedestrian_group_name
        ),
        pedestrian_maneuver_name=(
            f"{pedestrian_group.id}_maneuver"
            if pedestrian_group is not None
            else default.pedestrian_maneuver_name
        ),
        pedestrian_event_name=(
            pedestrian_event.id if pedestrian_event is not None else default.pedestrian_event_name
        ),
        pedestrian_event_priority=(
            pedestrian_event.priority if pedestrian_event is not None else default.pedestrian_event_priority
        ),
        pedestrian_action_name=(
            pedestrian_action.id if pedestrian_action is not None else default.pedestrian_action_name
        ),
        pedestrian_path_ref=(
            pedestrian_action.path_ref if pedestrian_action is not None else default.pedestrian_path_ref
        ),
        pedestrian_start_trigger_name=(
            pedestrian_event.start_trigger_ref
            if pedestrian_event is not None
            else default.pedestrian_start_trigger_name
        ),
    )


def storyboard_group_for_actor(groups: object, actor_id: str) -> object | None:
    return next((group for group in groups if actor_id in group.actor_refs), None)


def storyboard_first_event(group: object | None, events: dict[str, object]) -> object | None:
    if group is None:
        return None
    return events.get(group.event_refs[0]) if group.event_refs else None


def storyboard_first_action(event: object | None, actions: dict[str, object]) -> object | None:
    if event is None:
        return None
    return actions.get(event.action_refs[0]) if event.action_refs else None


def actor_event_build_plan(spec: ScenarioSpec, actor_id: str, default: ActorEventBuildPlan) -> ActorEventBuildPlan:
    storyboard = spec.storyboard
    if storyboard is None:
        return default
    groups = {group.id: group for group in storyboard.maneuver_groups}
    events = {event.id: event for event in storyboard.events}
    actions = {action.id: action for action in storyboard.actions}
    group = storyboard_group_for_actor(groups.values(), actor_id)
    event = storyboard_first_event(group, events)
    action = storyboard_first_action(event, actions)
    return ActorEventBuildPlan(
        group_name=group.id if group is not None else default.group_name,
        maneuver_name=f"{group.id}_maneuver" if group is not None else default.maneuver_name,
        event_name=event.id if event is not None else default.event_name,
        event_priority=event.priority if event is not None else default.event_priority,
        action_name=action.id if action is not None else default.action_name,
        start_trigger_name=event.start_trigger_ref if event is not None else default.start_trigger_name,
        path_ref=action.path_ref if action is not None else default.path_ref,
        action_type=action.type if action is not None else default.action_type,
        action_metadata=dict(action.metadata) if action is not None else default.action_metadata,
    )
