"""Fail-safe behavior for temporarily lost face tracking."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrackingState(str, Enum):
    TRACKING = "Tracking"
    HOLDING = "Holding last value"
    RETURNING = "Returning to neutral"
    LOST = "Face not found"


@dataclass(slots=True)
class TrackingOutput:
    value: int
    state: TrackingState


class TrackingLossController:
    def __init__(self, neutral_value: int, hold_ms: int = 500, return_ms: int = 500) -> None:
        self.neutral_value = neutral_value
        self.hold_ms = hold_ms
        self.return_ms = return_ms
        self._last_seen_ms: int | None = None
        self._last_value = neutral_value

    def reset(self, neutral_value: int | None = None) -> None:
        if neutral_value is not None:
            self.neutral_value = neutral_value
        self._last_seen_ms = None
        self._last_value = self.neutral_value

    def detected(self, value: int, timestamp_ms: int) -> TrackingOutput:
        self._last_seen_ms = timestamp_ms
        self._last_value = int(value)
        return TrackingOutput(self._last_value, TrackingState.TRACKING)

    def missing(self, timestamp_ms: int) -> TrackingOutput:
        if self._last_seen_ms is None:
            return TrackingOutput(self.neutral_value, TrackingState.LOST)
        elapsed = max(timestamp_ms - self._last_seen_ms, 0)
        if elapsed <= self.hold_ms:
            return TrackingOutput(self._last_value, TrackingState.HOLDING)
        if self.return_ms > 0 and elapsed < self.hold_ms + self.return_ms:
            progress = (elapsed - self.hold_ms) / self.return_ms
            value = round(self._last_value + (self.neutral_value - self._last_value) * progress)
            return TrackingOutput(value, TrackingState.RETURNING)
        return TrackingOutput(self.neutral_value, TrackingState.LOST)
