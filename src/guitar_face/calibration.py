"""Personal neutral-to-guitar-face calibration and scoring."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

import numpy as np

from .features import CANDIDATE_FEATURES, FEATURE_TO_FAMILY

CALIBRATION_SCHEMA_VERSION = 1
MODEL_ID = "mediapipe-face-landmarker-float16-v1"
MIN_FRAMES = 15
MIN_ABSOLUTE_DELTA = 0.04
MIN_NOISE_MULTIPLIER = 3.0
NOISE_FLOOR = 0.02


class CalibrationError(ValueError):
    """Raised when calibration samples do not contain a useful expression."""


@dataclass(slots=True)
class CalibrationProfile:
    camera_id: str
    neutral: dict[str, float]
    scales: dict[str, float]
    direction: dict[str, float]
    active_features: list[str]
    active_families: list[str]
    schema_version: int = CALIBRATION_SCHEMA_VERSION
    model_id: str = MODEL_ID

    def score(self, blendshapes: Mapping[str, float]) -> float:
        if not self.active_features:
            return 0.0
        current = np.array(
            [float(blendshapes.get(name, self.neutral[name])) for name in self.active_features],
            dtype=np.float64,
        )
        neutral = np.array([self.neutral[name] for name in self.active_features])
        scales = np.array([self.scales[name] for name in self.active_features])
        direction = np.array([self.direction[name] for name in self.active_features])
        observed = (current - neutral) / scales
        denominator = float(np.dot(direction, direction))
        if denominator <= 1e-12:
            return 0.0
        return float(np.clip(np.dot(observed, direction) / denominator, 0.0, 1.0))

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> CalibrationProfile:
        if data.get("schema_version") != CALIBRATION_SCHEMA_VERSION:
            raise CalibrationError("Calibration schema has changed; recalibration is required.")
        if data.get("model_id") != MODEL_ID:
            raise CalibrationError("Face model has changed; recalibration is required.")
        return cls(
            camera_id=str(data["camera_id"]),
            neutral={str(k): float(v) for k, v in dict(data["neutral"]).items()},
            scales={str(k): float(v) for k, v in dict(data["scales"]).items()},
            direction={str(k): float(v) for k, v in dict(data["direction"]).items()},
            active_features=[str(v) for v in list(data["active_features"])],
            active_families=[str(v) for v in list(data["active_families"])],
            schema_version=int(data["schema_version"]),
            model_id=str(data["model_id"]),
        )


def _matrix(frames: Iterable[Mapping[str, float]]) -> np.ndarray:
    rows = [
        [float(frame.get(feature, 0.0)) for feature in CANDIDATE_FEATURES]
        for frame in frames
    ]
    if len(rows) < MIN_FRAMES:
        raise CalibrationError(
            f"Not enough clear face samples ({len(rows)} received, {MIN_FRAMES} required)."
        )
    return np.asarray(rows, dtype=np.float64)


def build_profile(
    neutral_frames: Iterable[Mapping[str, float]],
    expression_frames: Iterable[Mapping[str, float]],
    camera_id: str,
) -> CalibrationProfile:
    neutral_matrix = _matrix(neutral_frames)
    expression_matrix = _matrix(expression_frames)

    neutral = np.median(neutral_matrix, axis=0)
    expression = np.median(expression_matrix, axis=0)
    median_absolute_deviation = np.median(np.abs(neutral_matrix - neutral), axis=0)
    robust_noise = 1.4826 * median_absolute_deviation
    raw_delta = expression - neutral

    active_mask = (np.abs(raw_delta) >= MIN_ABSOLUTE_DELTA) & (
        np.abs(raw_delta) >= MIN_NOISE_MULTIPLIER * np.maximum(robust_noise, 0.005)
    )
    active_indices = np.flatnonzero(active_mask)
    active_features = [CANDIDATE_FEATURES[index] for index in active_indices]
    active_families = sorted({FEATURE_TO_FAMILY[name] for name in active_features})

    if len(active_families) < 2:
        raise CalibrationError(
            "The guitar face was not distinct enough. Change at least two of brows, eyes, and mouth."
        )

    scales = np.maximum(robust_noise, NOISE_FLOOR)
    direction = raw_delta / scales

    return CalibrationProfile(
        camera_id=camera_id,
        neutral={name: float(neutral[index]) for index, name in enumerate(CANDIDATE_FEATURES)},
        scales={name: float(scales[index]) for index, name in enumerate(CANDIDATE_FEATURES)},
        direction={name: float(direction[index]) for index, name in enumerate(CANDIDATE_FEATURES)},
        active_features=active_features,
        active_families=active_families,
    )
