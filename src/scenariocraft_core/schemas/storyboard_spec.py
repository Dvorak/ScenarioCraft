from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scenariocraft_core.schemas.common import ScenarioSpecError, require_non_empty, require_unique_ids


@dataclass(frozen=True)
class StoryboardActionSpec:
    id: str
    type: str
    actor_refs: tuple[str, ...] = ()
    path_ref: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty(self.id, "storyboard.action.id")
        require_non_empty(self.type, f"storyboard.action[{self.id}].type")
        for actor_ref in self.actor_refs:
            require_non_empty(actor_ref, f"storyboard.action[{self.id}].actor_refs")
        if self.path_ref is not None:
            require_non_empty(self.path_ref, f"storyboard.action[{self.id}].path_ref")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "actor_refs": list(self.actor_refs),
        }
        if self.path_ref is not None:
            data["path_ref"] = self.path_ref
        if self.metadata:
            data["metadata"] = self.metadata
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardActionSpec":
        return cls(
            id=str(data["id"]),
            type=str(data["type"]),
            actor_refs=tuple(str(actor) for actor in data.get("actor_refs", ())),
            path_ref=str(data["path_ref"]) if data.get("path_ref") is not None else None,
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class StoryboardEventSpec:
    id: str
    priority: str
    start_trigger_ref: str
    action_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.id, "storyboard.event.id")
        require_non_empty(self.priority, f"storyboard.event[{self.id}].priority")
        require_non_empty(self.start_trigger_ref, f"storyboard.event[{self.id}].start_trigger_ref")
        if not self.action_refs:
            raise ScenarioSpecError(f"storyboard.event[{self.id}].action_refs must not be empty.")
        for action_ref in self.action_refs:
            require_non_empty(action_ref, f"storyboard.event[{self.id}].action_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "priority": self.priority,
            "start_trigger_ref": self.start_trigger_ref,
            "action_refs": list(self.action_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardEventSpec":
        return cls(
            id=str(data["id"]),
            priority=str(data["priority"]),
            start_trigger_ref=str(data["start_trigger_ref"]),
            action_refs=tuple(str(action) for action in data["action_refs"]),
        )


@dataclass(frozen=True)
class StoryboardManeuverGroupSpec:
    id: str
    actor_refs: tuple[str, ...]
    event_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.id, "storyboard.maneuver_group.id")
        if not self.actor_refs:
            raise ScenarioSpecError(f"storyboard.maneuver_group[{self.id}].actor_refs must not be empty.")
        if not self.event_refs:
            raise ScenarioSpecError(f"storyboard.maneuver_group[{self.id}].event_refs must not be empty.")
        for actor_ref in self.actor_refs:
            require_non_empty(actor_ref, f"storyboard.maneuver_group[{self.id}].actor_refs")
        for event_ref in self.event_refs:
            require_non_empty(event_ref, f"storyboard.maneuver_group[{self.id}].event_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "actor_refs": list(self.actor_refs),
            "event_refs": list(self.event_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardManeuverGroupSpec":
        return cls(
            id=str(data["id"]),
            actor_refs=tuple(str(actor) for actor in data["actor_refs"]),
            event_refs=tuple(str(event) for event in data["event_refs"]),
        )


@dataclass(frozen=True)
class StoryboardActSpec:
    id: str
    maneuver_group_refs: tuple[str, ...]
    stop_trigger_ref: str | None = None

    def __post_init__(self) -> None:
        require_non_empty(self.id, "storyboard.act.id")
        if not self.maneuver_group_refs:
            raise ScenarioSpecError(f"storyboard.act[{self.id}].maneuver_group_refs must not be empty.")
        for maneuver_group_ref in self.maneuver_group_refs:
            require_non_empty(maneuver_group_ref, f"storyboard.act[{self.id}].maneuver_group_refs")
        if self.stop_trigger_ref is not None:
            require_non_empty(self.stop_trigger_ref, f"storyboard.act[{self.id}].stop_trigger_ref")

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "maneuver_group_refs": list(self.maneuver_group_refs),
        }
        if self.stop_trigger_ref is not None:
            data["stop_trigger_ref"] = self.stop_trigger_ref
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardActSpec":
        return cls(
            id=str(data["id"]),
            maneuver_group_refs=tuple(str(group) for group in data["maneuver_group_refs"]),
            stop_trigger_ref=str(data["stop_trigger_ref"]) if data.get("stop_trigger_ref") is not None else None,
        )


@dataclass(frozen=True)
class StoryboardStorySpec:
    id: str
    act_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        require_non_empty(self.id, "storyboard.story.id")
        if not self.act_refs:
            raise ScenarioSpecError(f"storyboard.story[{self.id}].act_refs must not be empty.")
        for act_ref in self.act_refs:
            require_non_empty(act_ref, f"storyboard.story[{self.id}].act_refs")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "act_refs": list(self.act_refs),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardStorySpec":
        return cls(
            id=str(data["id"]),
            act_refs=tuple(str(act) for act in data["act_refs"]),
        )


@dataclass(frozen=True)
class StoryboardSpec:
    stories: tuple[StoryboardStorySpec, ...]
    acts: tuple[StoryboardActSpec, ...]
    maneuver_groups: tuple[StoryboardManeuverGroupSpec, ...]
    events: tuple[StoryboardEventSpec, ...]
    actions: tuple[StoryboardActionSpec, ...]

    def __post_init__(self) -> None:
        require_unique_ids("storyboard.stories", self.stories)
        require_unique_ids("storyboard.acts", self.acts)
        require_unique_ids("storyboard.maneuver_groups", self.maneuver_groups)
        require_unique_ids("storyboard.events", self.events)
        require_unique_ids("storyboard.actions", self.actions)
        action_ids = {action.id for action in self.actions}
        event_ids = {event.id for event in self.events}
        maneuver_group_ids = {group.id for group in self.maneuver_groups}
        act_ids = {act.id for act in self.acts}
        for event in self.events:
            for action_ref in event.action_refs:
                if action_ref not in action_ids:
                    raise ScenarioSpecError(f"storyboard.event[{event.id}] references unknown action {action_ref}.")
        for group in self.maneuver_groups:
            for event_ref in group.event_refs:
                if event_ref not in event_ids:
                    raise ScenarioSpecError(f"storyboard.maneuver_group[{group.id}] references unknown event {event_ref}.")
        for act in self.acts:
            for group_ref in act.maneuver_group_refs:
                if group_ref not in maneuver_group_ids:
                    raise ScenarioSpecError(f"storyboard.act[{act.id}] references unknown maneuver group {group_ref}.")
        for story in self.stories:
            for act_ref in story.act_refs:
                if act_ref not in act_ids:
                    raise ScenarioSpecError(f"storyboard.story[{story.id}] references unknown act {act_ref}.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "stories": [story.to_dict() for story in self.stories],
            "acts": [act.to_dict() for act in self.acts],
            "maneuver_groups": [group.to_dict() for group in self.maneuver_groups],
            "events": [event.to_dict() for event in self.events],
            "actions": [action.to_dict() for action in self.actions],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryboardSpec":
        return cls(
            stories=tuple(StoryboardStorySpec.from_dict(story) for story in data.get("stories", ())),
            acts=tuple(StoryboardActSpec.from_dict(act) for act in data.get("acts", ())),
            maneuver_groups=tuple(
                StoryboardManeuverGroupSpec.from_dict(group)
                for group in data.get("maneuver_groups", ())
            ),
            events=tuple(StoryboardEventSpec.from_dict(event) for event in data.get("events", ())),
            actions=tuple(StoryboardActionSpec.from_dict(action) for action in data.get("actions", ())),
        )
