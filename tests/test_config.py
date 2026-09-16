from __future__ import annotations

import json

from guitar_face.calibration import build_profile
from guitar_face.config import AppSettings, SettingsStore
from guitar_face.features import CANDIDATE_FEATURES


def test_settings_round_trip(tmp_path) -> None:
    base = {feature: 0.0 for feature in CANDIDATE_FEATURES}
    expression = dict(base, browDownLeft=0.7, eyeSquintLeft=0.8, jawOpen=0.9)
    profile = build_profile([base] * 20, [expression] * 20, "cam")
    settings = AppSettings(camera_id="cam", midi_channel=3, midi_cc=4)
    settings.profiles["cam"] = profile
    settings.mapping.sensitivity = 1.5
    store = SettingsStore(tmp_path / "settings.json")

    assert store.save(settings)
    loaded = store.load()
    assert loaded.camera_id == "cam"
    assert loaded.midi_channel == 3
    assert loaded.mapping.sensitivity == 1.5
    assert loaded.profiles["cam"] == profile


def test_v0_settings_migrate(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"channel": 2, "cc": 7}), encoding="utf-8")
    loaded = SettingsStore(path).load()
    assert loaded.schema_version == 1
    assert loaded.midi_channel == 2
    assert loaded.midi_cc == 7


def test_bad_settings_fall_back_to_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("not-json", encoding="utf-8")
    store = SettingsStore(path)
    loaded = store.load()
    assert loaded == AppSettings()
    assert store.last_error
