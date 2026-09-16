"""Qt Multimedia camera discovery and frame capture."""

from __future__ import annotations

import time
from dataclasses import dataclass

from PySide6.QtCore import QCameraPermission, QCoreApplication, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QImage, QTransform
from PySide6.QtMultimedia import (
    QCamera,
    QCameraDevice,
    QMediaCaptureSession,
    QMediaDevices,
    QVideoFrame,
    QVideoSink,
)


@dataclass(frozen=True, slots=True)
class CameraInfo:
    identifier: str
    description: str
    device: QCameraDevice


class CameraController(QObject):
    devices_changed = Signal()
    # Python's monotonic milliseconds can exceed the range of Qt's 32-bit int.
    frame_ready = Signal(object, "qint64")
    error = Signal(str)
    active_changed = Signal(bool)
    state_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.media_devices = QMediaDevices(self)
        self.media_devices.videoInputsChanged.connect(self._on_devices_changed)
        self.capture_session = QMediaCaptureSession(self)
        self.video_sink = QVideoSink(self)
        self.capture_session.setVideoSink(self.video_sink)
        self.video_sink.videoFrameChanged.connect(self._on_frame)
        self.camera: QCamera | None = None
        self.current_id: str | None = None
        self.state = "stopped"
        self._request_generation = 0
        self._startup_timer = QTimer(self)
        self._startup_timer.setSingleShot(True)
        self._startup_timer.setInterval(5000)
        self._startup_timer.timeout.connect(self._on_startup_timeout)

    @staticmethod
    def _identifier(device: QCameraDevice) -> str:
        return bytes(device.id()).hex()

    def devices(self) -> list[CameraInfo]:
        return [
            CameraInfo(self._identifier(device), device.description(), device)
            for device in QMediaDevices.videoInputs()
        ]

    @property
    def is_active(self) -> bool:
        return bool(self.camera and self.camera.isActive())

    @property
    def is_requested(self) -> bool:
        return self.state != "stopped"

    def _set_state(self, state: str) -> None:
        self.state = state
        self.state_changed.emit(state)

    def start(self, identifier: str) -> bool:
        self.stop()
        self.current_id = identifier
        generation = self._request_generation
        application = QCoreApplication.instance()
        if application is None:
            self._fail("Camera capture needs a running application.")
            return False
        permission = QCameraPermission()
        status = application.checkPermission(permission)
        if status == Qt.PermissionStatus.Undetermined:
            self._set_state("permission")
            # Modern Qt Multimedia expects the application to request permission.
            # Do this before constructing QCamera; a denied instance may stay inert.
            application.requestPermission(
                permission,
                self,
                lambda result: self._permission_resolved(generation, result.status()),
            )
            return True
        return self._permission_resolved(generation, status)

    def _permission_resolved(self, generation: int, status: Qt.PermissionStatus) -> bool:
        if generation != self._request_generation or self.current_id is None:
            return False  # Stop, disconnect, or another Start cancelled this request.
        if status != Qt.PermissionStatus.Granted:
            self._fail(
                "Camera access is not allowed. Enable Guitar Face in System Settings → "
                "Privacy & Security → Camera, then press Start again."
            )
            return False
        match = next((item for item in self.devices() if item.identifier == self.current_id), None)
        if match is None:
            self._fail("The selected camera is no longer connected.")
            return False
        self._set_state("starting")
        try:
            camera = QCamera(match.device, self)
            self.camera = camera
            camera.errorOccurred.connect(self._on_error)
            camera.activeChanged.connect(self._on_active_changed)
            # Use the camera's default format; cap resolution before inference.
            self.capture_session.setCamera(camera)
            self._startup_timer.start()
            camera.start()
            if self.camera is camera and camera.error() != QCamera.Error.NoError:
                self._fail(camera.errorString() or "Camera capture failed.")
        except Exception as exc:
            self._fail(f"Camera capture failed: {exc}")
        return self.is_requested

    def stop(self) -> None:
        self._request_generation += 1
        self._startup_timer.stop()
        camera, self.camera = self.camera, None
        if camera is not None:
            camera.errorOccurred.disconnect(self._on_error)
            camera.activeChanged.disconnect(self._on_active_changed)
            camera.stop()
            self.capture_session.setCamera(None)
            camera.deleteLater()
        self.current_id = None
        self.active_changed.emit(False)
        self._set_state("stopped")

    def _fail(self, message: str) -> None:
        self.stop()
        self.error.emit(message)

    def _on_devices_changed(self) -> None:
        if self.current_id and not any(
            device.identifier == self.current_id for device in self.devices()
        ):
            self._fail("The selected camera was disconnected. Reconnect it and press Start.")
        self.devices_changed.emit()

    def _on_active_changed(self, active: bool) -> None:
        self.active_changed.emit(active)
        if not active and self.is_requested:
            self._fail("Camera capture stopped. Check camera access and press Start to retry.")

    def _on_startup_timeout(self) -> None:
        if self.state == "starting":
            self._fail("No camera frames arrived. Close other camera apps and press Start to retry.")

    def _on_error(self, _error, description: str) -> None:
        if _error != QCamera.Error.NoError:
            self._fail(description or "Camera capture failed.")

    def _on_frame(self, frame: QVideoFrame) -> None:
        if not self.is_requested or not frame.isValid():
            return
        image = frame.toImage()
        if image.isNull():
            self._fail("The camera returned an unreadable frame.")
            return
        angle = self._rotation_degrees(frame)
        if angle:
            image = image.transformed(QTransform().rotate(angle))
        self._startup_timer.stop()
        if self.state != "streaming":
            self._set_state("streaming")
        self.frame_ready.emit(image, time.monotonic_ns() // 1_000_000)

    @staticmethod
    def _rotation_degrees(frame: QVideoFrame) -> int:
        rotation = None
        if hasattr(frame, "rotationAngle"):
            rotation = frame.rotationAngle()
        elif hasattr(frame, "rotation"):
            rotation = frame.rotation()
        if rotation is None:
            return 0
        try:
            return int(rotation)
        except (TypeError, ValueError):
            return int(getattr(rotation, "value", 0))
