from __future__ import annotations

from guitar_face.config import SettingsStore
from guitar_face.midi import MidiOutput
from guitar_face.ui import MainWindow


class FakeBackend:
    def open_virtual_port(self, _name):
        pass

    def send_message(self, _message):
        pass

    def close_port(self):
        pass


def test_window_constructs_without_camera_or_model(qtbot, tmp_path) -> None:
    midi = MidiOutput(backend_factory=FakeBackend)
    window = MainWindow(SettingsStore(tmp_path / "settings.json"), None, midi)
    qtbot.addWidget(window)
    assert window.windowTitle() == "Guitar Face"
    assert "missing" in window.model_status.text()


def test_camera_error_stays_visible_and_stop_ignores_late_results(qtbot, tmp_path):
    from guitar_face.vision import VisionResult

    window = MainWindow(
        SettingsStore(tmp_path / "settings.json"), None, MidiOutput(backend_factory=FakeBackend)
    )
    qtbot.addWidget(window)
    window.camera._fail("Camera access denied")
    window._refresh_cameras()
    window._on_vision_result(VisionResult(100, 110, {"jawOpen": 1.0}, []))
    assert window.start_button.text() == "Start"
    assert "Camera access denied" in window.camera_status.text()
    assert window.tracking_status.text() == "Stopped"
    assert not window.neutral_button.isEnabled()
