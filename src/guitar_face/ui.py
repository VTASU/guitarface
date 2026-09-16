"""Compact Qt interface for camera, calibration, mapping, and MIDI status."""

from __future__ import annotations

import time
from collections import deque
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSignalBlocker, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCloseEvent, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .calibration import CalibrationError, CalibrationProfile, build_profile
from .camera import CameraController
from .config import AppSettings, SettingsStore
from .mapping import OutputMapper
from .midi import MidiOutput
from .tracking import TrackingLossController, TrackingState
from .vision import InferenceWorker, VisionResult


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings_store: SettingsStore,
        model: Path | None,
        midi_output: MidiOutput | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Guitar Face")
        self.setMinimumSize(920, 620)
        self.resize(1020, 690)

        self.store = settings_store
        self.settings: AppSettings = self.store.load()
        self.midi = midi_output or MidiOutput()
        self.mapper = OutputMapper(self.settings.mapping)
        self.loss = TrackingLossController(self.mapper.neutral_value())
        self.camera = CameraController(self)
        self.worker = InferenceWorker(model, self) if model else None

        self.profile: CalibrationProfile | None = None
        self._latest_image: QImage | None = None
        self._camera_started_ms: int | None = None
        self._camera_error: str | None = None
        self._latest_landmarks: list[tuple[float, float]] = []
        self._last_face_ms: int | None = None
        self._latencies: deque[int] = deque(maxlen=120)
        self._pending_neutral: list[dict[str, float]] | None = None
        self._calibration_kind: str | None = None
        self._calibration_stage: str | None = None
        self._calibration_deadline_ms = 0
        self._calibration_frames: list[dict[str, float]] = []
        self._pulse_values: deque[int] = deque()
        self._pulse_active = False

        self._build_ui()
        self._load_settings_into_controls()
        self._connect_signals()
        self._refresh_cameras()
        self._update_profile()

        self.control_timer = QTimer(self)
        self.control_timer.setInterval(25)
        self.control_timer.timeout.connect(self._control_tick)
        self.control_timer.start()
        self.calibration_timer = QTimer(self)
        self.calibration_timer.setInterval(50)
        self.calibration_timer.timeout.connect(self._calibration_tick)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(250)
        self.save_timer.timeout.connect(self._save_settings)
        self.pulse_timer = QTimer(self)
        self.pulse_timer.setInterval(160)
        self.pulse_timer.timeout.connect(self._pulse_tick)

        self._open_midi()
        if self.worker is not None:
            self.worker.start()
        else:
            self.model_status.setText("Model: missing — run the model download command")
            self.start_button.setEnabled(False)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(16)

        preview_column = QVBoxLayout()
        title = QLabel("Guitar Face")
        title.setStyleSheet("font-size: 25px; font-weight: 700;")
        subtitle = QLabel("Your guitar face is the expression pedal.")
        subtitle.setStyleSheet("color: #777;")
        self.preview = QLabel("No camera connected")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(600, 420)
        self.preview.setStyleSheet(
            "background: #161616; color: #aaa; border-radius: 10px; font-size: 16px;"
        )
        self.preview.setScaledContents(False)
        preview_column.addWidget(title)
        preview_column.addWidget(subtitle)
        preview_column.addSpacing(6)
        preview_column.addWidget(self.preview, 1)

        meter_row = QHBoxLayout()
        raw_label = QLabel("Expression")
        self.raw_meter = QProgressBar()
        self.raw_meter.setRange(0, 100)
        self.raw_meter.setValue(0)
        self.raw_meter.setFormat("%p%")
        midi_label = QLabel("MIDI")
        self.midi_meter = QProgressBar()
        self.midi_meter.setRange(0, 127)
        self.midi_meter.setValue(self.mapper.neutral_value())
        self.midi_meter.setFormat("%v")
        meter_row.addWidget(raw_label)
        meter_row.addWidget(self.raw_meter, 1)
        meter_row.addWidget(midi_label)
        meter_row.addWidget(self.midi_meter, 1)
        preview_column.addLayout(meter_row)

        status_row = QHBoxLayout()
        self.tracking_status = QLabel("Stopped")
        self.performance_status = QLabel("Latency: —")
        self.performance_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_row.addWidget(self.tracking_status)
        status_row.addStretch()
        status_row.addWidget(self.performance_status)
        preview_column.addLayout(status_row)
        root_layout.addLayout(preview_column, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(300)
        scroll.setMaximumWidth(360)
        panel = QWidget()
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(4, 4, 8, 4)
        controls.setSpacing(12)

        camera_box = QGroupBox("Camera")
        camera_layout = QVBoxLayout(camera_box)
        self.camera_combo = QComboBox()
        self.start_button = QPushButton("Start")
        self.start_button.setMinimumHeight(34)
        self.camera_status = QLabel("Camera: checking…")
        self.camera_status.setWordWrap(True)
        camera_layout.addWidget(self.camera_combo)
        camera_layout.addWidget(self.start_button)
        camera_layout.addWidget(self.camera_status)
        controls.addWidget(camera_box)

        calibration_box = QGroupBox("Personal calibration")
        calibration_layout = QVBoxLayout(calibration_box)
        self.neutral_button = QPushButton("1. Capture neutral face")
        self.neutral_button.setEnabled(False)
        self.expression_button = QPushButton("2. Capture full guitar face")
        self.expression_button.setEnabled(False)
        self.calibration_status = QLabel("Choose a camera and start tracking.")
        self.calibration_status.setWordWrap(True)
        calibration_layout.addWidget(self.neutral_button)
        calibration_layout.addWidget(self.expression_button)
        calibration_layout.addWidget(self.calibration_status)
        controls.addWidget(calibration_box)

        response_box = QGroupBox("Response")
        response_form = QFormLayout(response_box)
        self.sensitivity = QDoubleSpinBox()
        self.sensitivity.setRange(0.25, 3.0)
        self.sensitivity.setSingleStep(0.05)
        self.sensitivity.setDecimals(2)
        self.smoothing = QSpinBox()
        self.smoothing.setRange(0, 250)
        self.smoothing.setSuffix(" ms")
        self.gamma = QDoubleSpinBox()
        self.gamma.setRange(0.5, 2.0)
        self.gamma.setSingleStep(0.05)
        self.gamma.setDecimals(2)
        self.inverted = QCheckBox("Reverse heel and toe")
        response_form.addRow("Sensitivity", self.sensitivity)
        response_form.addRow("Smoothing", self.smoothing)
        response_form.addRow("Curve", self.gamma)
        response_form.addRow("Invert", self.inverted)
        controls.addWidget(response_box)

        midi_box = QGroupBox("MIDI output")
        midi_layout = QVBoxLayout(midi_box)
        midi_form = QFormLayout()
        self.midi_channel = QSpinBox()
        self.midi_channel.setRange(1, 16)
        self.midi_cc = QSpinBox()
        self.midi_cc.setRange(0, 127)
        self.output_min = QSpinBox()
        self.output_min.setRange(0, 126)
        self.output_max = QSpinBox()
        self.output_max.setRange(1, 127)
        midi_form.addRow("Channel", self.midi_channel)
        midi_form.addRow("CC", self.midi_cc)
        midi_form.addRow("Minimum", self.output_min)
        midi_form.addRow("Maximum", self.output_max)
        self.learn_button = QPushButton("Send MIDI Learn pulse")
        self.reconnect_button = QPushButton("Reconnect MIDI")
        self.midi_status = QLabel("MIDI: connecting…")
        self.midi_status.setWordWrap(True)
        midi_layout.addLayout(midi_form)
        midi_layout.addWidget(self.learn_button)
        midi_layout.addWidget(self.reconnect_button)
        midi_layout.addWidget(self.midi_status)
        controls.addWidget(midi_box)

        self.model_status = QLabel("Model: loading…")
        self.model_status.setWordWrap(True)
        self.privacy_status = QLabel("Video stays in memory and is never recorded by Guitar Face.")
        self.privacy_status.setWordWrap(True)
        self.privacy_status.setStyleSheet("color: #777; font-size: 11px;")
        controls.addWidget(self.model_status)
        controls.addWidget(self.privacy_status)
        controls.addStretch()
        scroll.setWidget(panel)
        root_layout.addWidget(scroll)

    def _connect_signals(self) -> None:
        self.camera.devices_changed.connect(self._refresh_cameras)
        self.camera.frame_ready.connect(self._on_camera_frame)
        self.camera.error.connect(self._on_camera_error)
        self.camera.state_changed.connect(self._on_camera_state)
        self.camera_combo.currentIndexChanged.connect(self._camera_selected)
        self.start_button.clicked.connect(self._toggle_camera)
        self.neutral_button.clicked.connect(lambda: self._begin_calibration("neutral"))
        self.expression_button.clicked.connect(lambda: self._begin_calibration("expression"))
        self.learn_button.clicked.connect(self._start_learn_pulse)
        self.reconnect_button.clicked.connect(self._open_midi)

        for control in (
            self.sensitivity,
            self.smoothing,
            self.gamma,
            self.midi_channel,
            self.midi_cc,
            self.output_min,
            self.output_max,
        ):
            control.valueChanged.connect(self._settings_changed)
        self.inverted.toggled.connect(self._settings_changed)

        if self.worker is not None:
            self.worker.ready.connect(lambda: self.model_status.setText("Model: ready"))
            self.worker.failed.connect(self._on_model_error)
            self.worker.result_ready.connect(self._on_vision_result)

    def _load_settings_into_controls(self) -> None:
        mapping = self.settings.mapping
        self.sensitivity.setValue(mapping.sensitivity)
        self.smoothing.setValue(mapping.smoothing_ms)
        self.gamma.setValue(mapping.curve_gamma)
        self.inverted.setChecked(mapping.inverted)
        self.midi_channel.setValue(self.settings.midi_channel)
        self.midi_cc.setValue(self.settings.midi_cc)
        self.output_min.setValue(mapping.output_min)
        self.output_max.setValue(mapping.output_max)

    def _refresh_cameras(self) -> None:
        devices = self.camera.devices()
        desired = self.camera.current_id or self.settings.camera_id
        with QSignalBlocker(self.camera_combo):
            self.camera_combo.clear()
            for item in devices:
                self.camera_combo.addItem(item.description, item.identifier)
            selected = self.camera_combo.findData(desired) if desired else -1
            if selected < 0 and devices:
                selected = 0
            if selected >= 0:
                self.camera_combo.setCurrentIndex(selected)
        self.camera_combo.setEnabled(bool(devices) and not self.camera.is_requested)
        self.start_button.setEnabled(bool(devices) and self.worker is not None)
        if not devices:
            if self.camera.is_requested:
                self._stop_camera()
            if not self._camera_error:
                self.camera_status.setText("Camera: none detected. Connect a webcam or enable Continuity Camera.")
            self.preview.setText("No camera connected")
        elif not self.camera.is_requested and not self._camera_error:
            self.camera_status.setText("Camera: ready")
            self.preview.setText("Press Start to open the camera")
        self._camera_selected()

    def _camera_selected(self, *_args) -> None:
        camera_id = self.camera_combo.currentData()
        if not camera_id:
            self.profile = None
            return
        changed = camera_id != self.settings.camera_id
        self.settings.camera_id = camera_id
        if changed:
            self._pending_neutral = None
            self._schedule_save()
        self._update_profile()
        if changed and self.camera.is_active:
            self.camera.start(camera_id)

    def _update_profile(self) -> None:
        camera_id = self.camera_combo.currentData() or self.settings.camera_id
        self.profile = self.settings.profiles.get(camera_id) if camera_id else None
        if self.profile:
            families = ", ".join(self.profile.active_families)
            self.calibration_status.setText(f"Calibrated: {families}")
        elif camera_id:
            self.calibration_status.setText("Not calibrated for this camera.")

    def _toggle_camera(self) -> None:
        if self.camera.is_requested:
            self._stop_camera()
            return
        camera_id = self.camera_combo.currentData()
        if camera_id:
            self._camera_error = None
            self._latest_image = None
            self._latest_landmarks = []
            self.camera.start(camera_id)

    def _on_camera_state(self, state: str) -> None:
        self.camera_combo.setEnabled(state == "stopped" and self.camera_combo.count() > 0)
        if state in ("permission", "starting"):
            self.start_button.setText("Cancel" if state == "permission" else "Stop")
            self.neutral_button.setEnabled(False)
            self.expression_button.setEnabled(False)
            message = (
                "Waiting for camera permission…"
                if state == "permission" else "Opening camera…"
            )
            self.preview.setText(message)
            self.camera_status.setText(message)
            self.tracking_status.setText("Waiting for camera")
            if state == "starting":
                self._camera_started_ms = time.monotonic_ns() // 1_000_000
        elif state == "streaming":
            self.start_button.setText("Stop")
            self.camera_status.setText("Camera: active")
            self.neutral_button.setEnabled(True)
            self.expression_button.setEnabled(self._pending_neutral is not None)
            self.tracking_status.setText("Looking for face…")
        elif state == "stopped":
            self.start_button.setText("Start")
            self._cancel_calibration()
            self._last_face_ms = None
            self._camera_started_ms = None
            self._latest_image = None
            self._latest_landmarks = []
            self.mapper.reset(0.0)
            self.loss.reset(self.mapper.neutral_value())
            self._send_neutral(force=True)
            self.raw_meter.setValue(0)
            self.midi_meter.setValue(self.mapper.neutral_value())
            self.tracking_status.setText("Stopped")
            self.camera_status.setText("Camera: ready")
            self.preview.setText("Press Start to open the camera")

    def _stop_camera(self) -> None:
        self.camera.stop()

    def _on_camera_error(self, message: str) -> None:
        self._camera_error = message
        self.camera_status.setText(f"Camera error: {message}")
        self.preview.setText("Camera could not start\nSee the camera status for details")

    def _on_model_error(self, message: str) -> None:
        self.model_status.setText(f"Model error: {message}")
        self.start_button.setEnabled(False)
        if self.camera.is_active:
            self._stop_camera()

    def _on_camera_frame(self, image: QImage, timestamp_ms: int) -> None:
        if not self.camera.is_requested:
            return
        first_frame = self._latest_image is None
        self._latest_image = image
        if first_frame:
            self.camera_status.setText("Camera: active")
        self._render_preview()
        if self.worker is None or not self.camera.is_active or not self.worker.is_running:
            return
        inference_image = image
        if image.width() > 1280 or image.height() > 720:
            inference_image = image.scaled(
                QSize(1280, 720),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
        try:
            self.worker.submit(self._qimage_to_rgb(inference_image), timestamp_ms)
        except Exception as exc:
            self.camera_status.setText(f"Frame conversion error: {exc}")

    @staticmethod
    def _qimage_to_rgb(image: QImage) -> np.ndarray:
        converted = image.convertToFormat(QImage.Format.Format_RGB888)
        height, width = converted.height(), converted.width()
        buffer = np.frombuffer(converted.constBits(), dtype=np.uint8, count=converted.sizeInBytes())
        rows = buffer.reshape(height, converted.bytesPerLine())
        return rows[:, : width * 3].reshape(height, width, 3).copy()

    def _render_preview(self) -> None:
        if self._latest_image is None or self._latest_image.isNull():
            return
        image = self._latest_image.mirrored(True, False)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(66, 214, 164, 210), 3))
        for x, y in self._latest_landmarks:
            painter.drawPoint(round((1.0 - x) * image.width()), round(y * image.height()))
        painter.end()
        pixmap = QPixmap.fromImage(image)
        self.preview.setPixmap(
            pixmap.scaled(
                self.preview.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_preview()

    def _on_vision_result(self, result: VisionResult) -> None:
        if (
            not self.camera.is_requested
            or self._camera_started_ms is None
            or result.timestamp_ms < self._camera_started_ms
        ):
            return
        self._latest_landmarks = result.landmarks
        self._latencies.append(result.latency_ms)
        if self._latencies:
            p95_index = max(round(0.95 * (len(self._latencies) - 1)), 0)
            p95 = sorted(self._latencies)[p95_index]
            dropped = self.worker.dropped_frames if self.worker else 0
            self.performance_status.setText(f"Latency p95: {p95} ms · dropped: {dropped}")

        if not result.face_found:
            self.tracking_status.setText("Face not found")
            return

        self._last_face_ms = result.received_ms
        if self._calibration_stage == "capturing":
            self._calibration_frames.append(dict(result.blendshapes))

        if self.profile is None:
            self.raw_meter.setValue(0)
            self.tracking_status.setText("Face found · calibration required")
            return

        raw = self.profile.score(result.blendshapes)
        smoothed, midi_value = self.mapper.process(raw, result.received_ms)
        output = self.loss.detected(midi_value, result.received_ms)
        self.raw_meter.setValue(round(raw * 100))
        self.midi_meter.setValue(output.value)
        self.tracking_status.setText(output.state.value)
        if not self._pulse_active:
            self._send_value(output.value)

    def _control_tick(self) -> None:
        now = time.monotonic_ns() // 1_000_000
        if not self.camera.is_active or self.profile is None or self._pulse_active:
            return
        if self._last_face_ms is not None and now - self._last_face_ms < 100:
            return
        output = self.loss.missing(now)
        self.midi_meter.setValue(output.value)
        self.tracking_status.setText(output.state.value)
        self._send_value(output.value)

    def _begin_calibration(self, kind: str) -> None:
        if not self.camera.is_active or self._last_face_ms is None:
            self.calibration_status.setText("Start the camera and keep your face clearly visible first.")
            return
        if kind == "expression" and self._pending_neutral is None:
            self.calibration_status.setText("Capture your neutral face first.")
            return
        self._calibration_kind = kind
        self._calibration_stage = "countdown"
        self._calibration_deadline_ms = time.monotonic_ns() // 1_000_000 + 3000
        self._calibration_frames = []
        self.neutral_button.setEnabled(False)
        self.expression_button.setEnabled(False)
        self.calibration_timer.start()
        prompt = "Relax your face" if kind == "neutral" else "Get your guitar face ready"
        self.calibration_status.setText(f"{prompt} — 3")

    def _calibration_tick(self) -> None:
        now = time.monotonic_ns() // 1_000_000
        remaining = self._calibration_deadline_ms - now
        if self._calibration_stage == "countdown":
            if remaining > 0:
                seconds = max((remaining + 999) // 1000, 1)
                prompt = "Relax your face" if self._calibration_kind == "neutral" else "Get stanky"
                self.calibration_status.setText(f"{prompt} — {seconds}")
                return
            self._calibration_stage = "capturing"
            self._calibration_deadline_ms = now + 2000
            self._calibration_frames = []
            prompt = "Hold neutral…" if self._calibration_kind == "neutral" else "Hold that guitar face…"
            self.calibration_status.setText(prompt)
            return
        if self._calibration_stage == "capturing":
            self.calibration_status.setText(
                f"Capturing… {len(self._calibration_frames)} clear frames"
            )
            if remaining > 0:
                return
            self._finish_calibration()

    def _finish_calibration(self) -> None:
        kind = self._calibration_kind
        frames = self._calibration_frames
        self._cancel_calibration(reset_status=False)
        if kind == "neutral":
            if len(frames) < 15:
                self.calibration_status.setText("Neutral capture failed: keep your face visible and try again.")
                return
            self._pending_neutral = frames
            self.expression_button.setEnabled(self.camera.is_active)
            self.calibration_status.setText(
                f"Neutral captured ({len(frames)} frames). Now capture your full guitar face."
            )
            return
        if kind == "expression" and self._pending_neutral is not None:
            camera_id = self.camera_combo.currentData()
            try:
                profile = build_profile(self._pending_neutral, frames, camera_id)
            except CalibrationError as exc:
                self.calibration_status.setText(str(exc))
                self.expression_button.setEnabled(self.camera.is_active)
                return
            self.settings.profiles[camera_id] = profile
            self.profile = profile
            self._pending_neutral = None
            self.mapper.reset(0.0)
            self.loss.reset(self.mapper.neutral_value())
            families = ", ".join(profile.active_families)
            self.calibration_status.setText(
                f"Calibrated with {len(profile.active_features)} signals across {families}."
            )
            self._schedule_save()

    def _cancel_calibration(self, *, reset_status: bool = True) -> None:
        self.calibration_timer.stop()
        self._calibration_kind = None
        self._calibration_stage = None
        self._calibration_frames = []
        self.neutral_button.setEnabled(self.camera.is_active)
        self.expression_button.setEnabled(
            self.camera.is_active and self._pending_neutral is not None
        )
        if reset_status:
            self._update_profile()

    def _settings_changed(self, *_args) -> None:
        old_neutral = self.mapper.neutral_value()
        if self.midi.is_open:
            self.midi.send(
                self.settings.midi_channel, self.settings.midi_cc, old_neutral, force=True
            )
        minimum, maximum = self.output_min.value(), self.output_max.value()
        if minimum >= maximum:
            if minimum < 127:
                maximum = minimum + 1
                with QSignalBlocker(self.output_max):
                    self.output_max.setValue(maximum)
            else:
                minimum = maximum - 1
                with QSignalBlocker(self.output_min):
                    self.output_min.setValue(minimum)
        self.settings.midi_channel = self.midi_channel.value()
        self.settings.midi_cc = self.midi_cc.value()
        mapping = self.settings.mapping
        mapping.sensitivity = self.sensitivity.value()
        mapping.smoothing_ms = self.smoothing.value()
        mapping.curve_gamma = self.gamma.value()
        mapping.inverted = self.inverted.isChecked()
        mapping.output_min = minimum
        mapping.output_max = maximum
        self.mapper.reset(0.0)
        self.loss.reset(self.mapper.neutral_value())
        self.midi_meter.setValue(self.mapper.neutral_value())
        self._send_neutral(force=True)
        self._schedule_save()

    def _schedule_save(self) -> None:
        if hasattr(self, "save_timer"):
            self.save_timer.start()

    def _save_settings(self) -> None:
        if not self.store.save(self.settings) and self.store.last_error:
            self.camera_status.setText(self.store.last_error)

    def _open_midi(self) -> None:
        self.midi.close()
        if self.midi.open():
            self.midi_status.setText("MIDI: Guitar Face virtual source ready")
            self.learn_button.setEnabled(True)
            self._send_neutral(force=True)
        else:
            self.midi_status.setText(f"MIDI error: {self.midi.error}")
            self.learn_button.setEnabled(False)

    def _send_value(self, value: int, *, force: bool = False) -> None:
        if not self.midi.send(
            self.settings.midi_channel, self.settings.midi_cc, value, force=force
        ):
            self.midi_status.setText(f"MIDI error: {self.midi.error}")
        else:
            self.midi_status.setText("MIDI: Guitar Face virtual source ready")

    def _send_neutral(self, *, force: bool = False) -> None:
        self._send_value(self.mapper.neutral_value(), force=force)

    def _start_learn_pulse(self) -> None:
        if not self.midi.is_open and not self.midi.open():
            self.midi_status.setText(f"MIDI error: {self.midi.error}")
            return
        low = self.settings.mapping.output_min
        high = self.settings.mapping.output_max
        self._pulse_values = deque([low, high, low, high, self.mapper.neutral_value()])
        self._pulse_active = True
        self.learn_button.setEnabled(False)
        self.midi_status.setText("MIDI: sending learn pulse…")
        self._pulse_tick()
        self.pulse_timer.start()

    def _pulse_tick(self) -> None:
        if self._pulse_values:
            value = self._pulse_values.popleft()
            self._send_value(value, force=True)
            self.midi_meter.setValue(value)
            return
        self.pulse_timer.stop()
        self._pulse_active = False
        self.learn_button.setEnabled(True)
        self.midi_status.setText("MIDI: learn pulse sent")

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cancel_calibration()
        self.camera.stop()
        self._send_neutral(force=True)
        self._save_settings()
        if self.worker is not None:
            self.worker.stop()
        self.midi.close()
        event.accept()


def show_startup_error(message: str) -> None:
    QMessageBox.critical(None, "Guitar Face", message)
