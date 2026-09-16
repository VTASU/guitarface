"""Versioned settings and per-camera calibration persistence."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from platformdirs import user_config_dir

from .calibration import CalibrationError, CalibrationProfile
from .mapping import MappingSettings

SETTINGS_SCHEMA_VERSION = 1


@dataclass(slots=True)
class AppSettings:
    schema_version: int = SETTINGS_SCHEMA_VERSION
    camera_id: str | None = None
    midi_channel: int = 1
    midi_cc: int = 11
    mapping: MappingSettings = field(default_factory=MappingSettings)
    profiles: dict[str, CalibrationProfile] = field(default_factory=dict)

    def validate(self) -> None:
        if not 1 <= self.midi_channel <= 16:
            raise ValueError("MIDI channel must be between 1 and 16.")
        if not 0 <= self.midi_cc <= 127:
            raise ValueError("MIDI CC must be between 0 and 127.")
        self.mapping.validate()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["profiles"] = {key: profile.to_dict() for key, profile in self.profiles.items()}
        return data

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> AppSettings:
        schema = int(raw.get("schema_version", 0))
        if schema == 0:
            raw = _migrate_v0(raw)
            schema = SETTINGS_SCHEMA_VERSION
        if schema != SETTINGS_SCHEMA_VERSION:
            return cls()

        mapping_raw = dict(raw.get("mapping", {}))
        defaults = MappingSettings()
        mapping = MappingSettings(
            sensitivity=float(mapping_raw.get("sensitivity", defaults.sensitivity)),
            smoothing_ms=int(mapping_raw.get("smoothing_ms", defaults.smoothing_ms)),
            deadzone=float(mapping_raw.get("deadzone", defaults.deadzone)),
            curve_gamma=float(mapping_raw.get("curve_gamma", defaults.curve_gamma)),
            inverted=bool(mapping_raw.get("inverted", defaults.inverted)),
            output_min=int(mapping_raw.get("output_min", defaults.output_min)),
            output_max=int(mapping_raw.get("output_max", defaults.output_max)),
        )
        profiles: dict[str, CalibrationProfile] = {}
        for key, value in dict(raw.get("profiles", {})).items():
            try:
                profiles[str(key)] = CalibrationProfile.from_dict(dict(value))
            except (CalibrationError, KeyError, TypeError, ValueError):
                continue
        settings = cls(
            schema_version=schema,
            camera_id=str(raw["camera_id"]) if raw.get("camera_id") else None,
            midi_channel=int(raw.get("midi_channel", 1)),
            midi_cc=int(raw.get("midi_cc", 11)),
            mapping=mapping,
            profiles=profiles,
        )
        settings.validate()
        return settings


def _migrate_v0(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SETTINGS_SCHEMA_VERSION,
        "camera_id": raw.get("camera_id"),
        "midi_channel": raw.get("midi_channel", raw.get("channel", 1)),
        "midi_cc": raw.get("midi_cc", raw.get("cc", 11)),
        "mapping": raw.get("mapping", {}),
        "profiles": raw.get("profiles", {}),
    }


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(user_config_dir("Guitar Face", "Guitar Face")) / "settings.json"
        self.last_error: str | None = None

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            settings = AppSettings.from_dict(data)
            self.last_error = None
            return settings
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            self.last_error = f"Could not load settings: {exc}"
            return AppSettings()

    def save(self, settings: AppSettings) -> bool:
        try:
            settings.validate()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix="settings-", suffix=".json", dir=self.path.parent
            )
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    json.dump(settings.to_dict(), handle, indent=2, sort_keys=True)
                    handle.write("\n")
                os.replace(temporary, self.path)
            except Exception:
                Path(temporary).unlink(missing_ok=True)
                raise
            self.last_error = None
            return True
        except (OSError, TypeError, ValueError) as exc:
            self.last_error = f"Could not save settings: {exc}"
            return False
