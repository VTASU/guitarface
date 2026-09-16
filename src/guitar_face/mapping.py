"""Map calibrated expression intensity to a stable MIDI controller value."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(slots=True)
class MappingSettings:
    sensitivity: float = 1.0
    smoothing_ms: int = 60
    deadzone: float = 0.05
    curve_gamma: float = 1.0
    inverted: bool = False
    output_min: int = 0
    output_max: int = 127

    def validate(self) -> None:
        if not 0.25 <= self.sensitivity <= 3.0:
            raise ValueError("Sensitivity must be between 0.25 and 3.0.")
        if not 0 <= self.smoothing_ms <= 250:
            raise ValueError("Smoothing must be between 0 and 250 ms.")
        if not 0.0 <= self.deadzone < 0.5:
            raise ValueError("Deadzone must be between 0 and 0.5.")
        if not 0.5 <= self.curve_gamma <= 2.0:
            raise ValueError("Curve gamma must be between 0.5 and 2.0.")
        if not 0 <= self.output_min <= 127 or not 0 <= self.output_max <= 127:
            raise ValueError("MIDI output endpoints must be between 0 and 127.")
        if self.output_min >= self.output_max:
            raise ValueError("MIDI output minimum must be below maximum.")


class OutputMapper:
    def __init__(self, settings: MappingSettings) -> None:
        self.settings = settings
        self._smoothed: float | None = None
        self._last_timestamp_ms: int | None = None

    def reset(self, value: float | None = None) -> None:
        self._smoothed = value
        self._last_timestamp_ms = None

    def neutral_value(self) -> int:
        return self.settings.output_max if self.settings.inverted else self.settings.output_min

    def process(self, raw_intensity: float, timestamp_ms: int) -> tuple[float, int]:
        self.settings.validate()
        raw = min(max(float(raw_intensity), 0.0), 1.0)
        if raw <= self.settings.deadzone:
            shaped = 0.0
        else:
            shaped = (raw - self.settings.deadzone) / (1.0 - self.settings.deadzone)
        shaped = min(max(shaped * self.settings.sensitivity, 0.0), 1.0)
        shaped = shaped**self.settings.curve_gamma

        if self._smoothed is None or self.settings.smoothing_ms == 0:
            self._smoothed = shaped
        else:
            previous = self._last_timestamp_ms
            elapsed = max(timestamp_ms - (previous if previous is not None else timestamp_ms), 0)
            alpha = 1.0 - math.exp(-elapsed / max(self.settings.smoothing_ms, 1))
            self._smoothed += alpha * (shaped - self._smoothed)
        self._last_timestamp_ms = timestamp_ms

        output_fraction = 1.0 - self._smoothed if self.settings.inverted else self._smoothed
        span = self.settings.output_max - self.settings.output_min
        midi_value = round(self.settings.output_min + output_fraction * span)
        return self._smoothed, min(max(midi_value, 0), 127)
