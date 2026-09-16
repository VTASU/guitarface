"""Bounded asynchronous MediaPipe inference worker."""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Generic, TypeVar

import numpy as np
from PySide6.QtCore import QObject, Signal

from .features import OVERLAY_LANDMARK_INDICES

T = TypeVar("T")


class LatestValueQueue(Generic[T]):
    """A capacity-one queue that replaces stale work with the newest value."""

    def __init__(self) -> None:
        self._queue: queue.Queue[T] = queue.Queue(maxsize=1)

    def put_latest(self, value: T) -> bool:
        dropped = False
        try:
            self._queue.put_nowait(value)
            return dropped
        except queue.Full:
            dropped = True
        try:
            self._queue.get_nowait()
        except queue.Empty:
            pass
        self._queue.put_nowait(value)
        return dropped

    def get(self, timeout: float | None = None) -> T:
        return self._queue.get(timeout=timeout)

    def empty(self) -> bool:
        return self._queue.empty()


@dataclass(slots=True)
class FrameInput:
    rgb: np.ndarray
    timestamp_ms: int


@dataclass(slots=True)
class VisionResult:
    timestamp_ms: int
    received_ms: int
    blendshapes: dict[str, float]
    landmarks: list[tuple[float, float]]

    @property
    def face_found(self) -> bool:
        return bool(self.blendshapes)

    @property
    def latency_ms(self) -> int:
        return max(self.received_ms - self.timestamp_ms, 0)


class InferenceWorker(QObject):
    result_ready = Signal(object)
    ready = Signal()
    failed = Signal(str)
    _native_result = Signal(object)

    def __init__(self, model: Path, parent=None) -> None:
        super().__init__(parent)
        self.model = model
        self._pending: FrameInput | None = None
        self._busy = False
        self._landmarker = None
        self._mp = None
        self._running = False
        self._last_timestamp_ms = -1
        self.dropped_frames = 0
        self._native_result.connect(self._on_native_result)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        """Create the graph on the macOS main thread, then use its async API."""
        if self._running:
            return
        try:
            import mediapipe as mp
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision

            options = vision.FaceLandmarkerOptions(
                base_options=python.BaseOptions(
                    model_asset_path=str(self.model),
                    delegate=python.BaseOptions.Delegate.CPU,
                ),
                running_mode=vision.RunningMode.LIVE_STREAM,
                num_faces=1,
                min_face_detection_confidence=0.5,
                min_face_presence_confidence=0.5,
                min_tracking_confidence=0.5,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=False,
                result_callback=self._callback,
            )
            self._mp = mp
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
            self._running = True
            self.ready.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def submit(self, rgb: np.ndarray, timestamp_ms: int) -> None:
        if not self._running:
            return
        frame = FrameInput(np.ascontiguousarray(rgb), timestamp_ms)
        if self._busy:
            if self._pending is not None:
                self.dropped_frames += 1
            self._pending = frame
            return
        self._dispatch(frame)

    def _dispatch(self, frame: FrameInput) -> None:
        if not self._running or self._landmarker is None or self._mp is None:
            return
        timestamp_ms = max(frame.timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        try:
            image = self._mp.Image(
                image_format=self._mp.ImageFormat.SRGB,
                data=frame.rgb,
            )
            self._busy = True
            self._landmarker.detect_async(image, timestamp_ms)
        except Exception as exc:
            self._busy = False
            self.failed.emit(str(exc))

    def _callback(self, detected, _output_image, timestamp_ms: int) -> None:
        blendshapes: dict[str, float] = {}
        if detected.face_blendshapes:
            blendshapes = {
                category.category_name: float(category.score)
                for category in detected.face_blendshapes[0]
            }
        landmarks: list[tuple[float, float]] = []
        if detected.face_landmarks:
            face = detected.face_landmarks[0]
            landmarks = [
                (float(face[index].x), float(face[index].y))
                for index in OVERLAY_LANDMARK_INDICES
                if index < len(face)
            ]
        self._native_result.emit(
            VisionResult(
                timestamp_ms=timestamp_ms,
                received_ms=time.monotonic_ns() // 1_000_000,
                blendshapes=blendshapes,
                landmarks=landmarks,
            )
        )

    def _on_native_result(self, result: VisionResult) -> None:
        self._busy = False
        if not self._running:
            return
        self.result_ready.emit(result)
        pending, self._pending = self._pending, None
        if pending is not None:
            self._dispatch(pending)

    def stop(self) -> None:
        self._running = False
        self._pending = None
        self._busy = False
        landmarker, self._landmarker = self._landmarker, None
        if landmarker is not None:
            try:
                landmarker.close()
            except Exception:
                pass
