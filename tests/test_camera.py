"""Camera lifecycle regressions without prompting for real camera permission."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QCamera, QVideoFrame

import guitar_face.camera as camera_module
from guitar_face.camera import CameraController, CameraInfo


class FakeApplication:
    def __init__(self):
        self.permission = Qt.PermissionStatus.Undetermined
        self.callbacks = []

    def checkPermission(self, _permission):
        return self.permission

    def requestPermission(self, _permission, _context, callback):
        self.callbacks.append(callback)

    def reply(self, status):
        self.permission = status
        self.callbacks.pop(0)(SimpleNamespace(status=lambda: status))


class FakeCamera(QObject):
    Error = QCamera.Error
    errorOccurred = Signal(object, str)
    activeChanged = Signal(bool)
    instances = []
    startup_error = None

    def __init__(self, _device, parent):
        super().__init__(parent)
        self.active = False
        self.instances.append(self)

    def start(self):
        if self.startup_error:
            self.errorOccurred.emit(self.Error.CameraError, self.startup_error)
            return
        self.active = True
        self.activeChanged.emit(True)

    def stop(self):
        self.active = False

    def isActive(self):
        return self.active

    def error(self):
        return self.Error.NoError


@pytest.fixture
def capture(monkeypatch, qapp):
    application = FakeApplication()
    FakeCamera.instances = []
    monkeypatch.setattr(camera_module, "QCamera", FakeCamera)
    monkeypatch.setattr(
        camera_module, "QCoreApplication", SimpleNamespace(instance=lambda: application)
    )
    monkeypatch.setattr(
        camera_module,
        "QMediaCaptureSession",
        lambda _parent: SimpleNamespace(setCamera=lambda _camera: None, setVideoSink=lambda _sink: None),
    )
    controller = CameraController()
    devices = [CameraInfo("test-camera", "Test camera", None)]
    monkeypatch.setattr(controller, "devices", lambda: devices)
    errors = []
    controller.error.connect(errors.append)
    yield controller, application, devices, errors
    controller.stop()


def test_camera_is_only_opened_after_permission_and_active_only_after_frame(capture):
    controller, application, _, _ = capture
    assert controller.start("test-camera")
    assert controller.state == "permission"
    assert not controller.is_active
    assert not FakeCamera.instances

    application.reply(Qt.PermissionStatus.Granted)
    assert len(FakeCamera.instances) == 1
    assert controller.state == "starting"
    image = QImage(32, 32, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.black)
    controller._on_frame(QVideoFrame(image))
    assert controller.state == "streaming"
    assert not controller._startup_timer.isActive()


def test_denial_does_not_open_camera_and_permission_can_be_retried(capture):
    controller, application, _, errors = capture
    controller.start("test-camera")
    application.reply(Qt.PermissionStatus.Denied)
    assert not FakeCamera.instances
    assert not controller.is_requested
    assert "Privacy & Security" in errors[-1]
    application.permission = Qt.PermissionStatus.Granted
    assert controller.start("test-camera")
    assert controller.is_active


def test_cancelled_permission_does_not_turn_on_camera_later(capture):
    controller, application, _, _ = capture
    controller.start("test-camera")
    controller.stop()
    application.reply(Qt.PermissionStatus.Granted)
    assert not controller.is_requested
    assert not FakeCamera.instances


def test_unplug_while_waiting_for_permission_cancels_request(capture):
    controller, application, devices, errors = capture
    controller.start("test-camera")
    devices.clear()
    controller._on_devices_changed()
    application.reply(Qt.PermissionStatus.Granted)
    assert not FakeCamera.instances
    assert "disconnected" in errors[-1]


def test_backend_error_resets_startup_and_remains_visible(capture, monkeypatch):
    controller, application, _, errors = capture
    application.permission = Qt.PermissionStatus.Granted
    monkeypatch.setattr(FakeCamera, "startup_error", "Camera is busy")
    assert not controller.start("test-camera")
    assert controller.state == "stopped"
    assert errors == ["Camera is busy"]
    assert not controller._startup_timer.isActive()


def test_no_frames_times_out_and_releases_device(capture, qtbot):
    controller, application, _, errors = capture
    application.permission = Qt.PermissionStatus.Granted
    controller._startup_timer.setInterval(20)
    controller.start("test-camera")
    qtbot.waitUntil(lambda: bool(errors))
    assert "No camera frames" in errors[-1]
    assert not controller.is_requested
    assert not FakeCamera.instances[-1].isActive()


def test_frame_timestamp_survives_more_than_25_days_uptime(capture, monkeypatch):
    controller, application, _, _ = capture
    application.permission = Qt.PermissionStatus.Granted
    controller.start("test-camera")
    timestamp = 3_000_000_000
    monkeypatch.setattr(camera_module.time, "monotonic_ns", lambda: timestamp * 1_000_000)
    received = []
    controller.frame_ready.connect(lambda _image, stamp: received.append(stamp))
    image = QImage(32, 32, QImage.Format.Format_RGB888)
    image.fill(Qt.GlobalColor.black)
    controller._on_frame(QVideoFrame(image))
    assert received == [timestamp]
