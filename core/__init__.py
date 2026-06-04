"""
Event bus for decoupled communication between game systems.
"""
from collections import defaultdict
from typing import Callable, Any


class EventBus:
    """Simple publish/subscribe event system."""

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable):
        self._listeners[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable):
        if callback in self._listeners[event_type]:
            self._listeners[event_type].remove(callback)

    def emit(self, event_type: str, **kwargs):
        for callback in self._listeners.get(event_type, []):
            callback(**kwargs)

    def clear(self):
        self._listeners.clear()


# Global event bus instance
event_bus = EventBus()
