from __future__ import annotations

import pytest

from guitar_face.calibration import CalibrationError, build_profile
from guitar_face.features import CANDIDATE_FEATURES


def frame(**changes: float) -> dict[str, float]:
    values = {feature: 0.05 for feature in CANDIDATE_FEATURES}
    values.update(changes)
    return values


def repeated(value: dict[str, float], count: int = 30, jitter: float = 0.0):
    output = []
    for index in range(count):
        sign = -1 if index % 2 else 1
        output.append({key: val + sign * jitter for key, val in value.items()})
    return output


def test_calibration_projects_neutral_midpoint_and_full_expression() -> None:
    neutral = frame()
    expressive = frame(
        browDownLeft=0.65,
        browDownRight=0.55,
        eyeSquintLeft=0.75,
        eyeSquintRight=0.65,
        jawOpen=0.85,
        noseSneerLeft=0.55,
    )
    profile = build_profile(repeated(neutral, jitter=0.002), repeated(expressive), "camera-a")

    midpoint = {
        key: neutral[key] + (expressive[key] - neutral[key]) * 0.5
        for key in neutral
    }
    opposite = {
        key: neutral[key] - (expressive[key] - neutral[key])
        for key in neutral
    }

    assert profile.score(neutral) == pytest.approx(0.0, abs=0.01)
    assert profile.score(midpoint) == pytest.approx(0.5, abs=0.01)
    assert profile.score(expressive) == pytest.approx(1.0, abs=0.01)
    assert profile.score(opposite) == 0.0
    assert set(profile.active_families) == {"brows", "eyes", "mouth"}


def test_noise_is_rejected() -> None:
    neutral = frame()
    noisy_expression = frame(browDownLeft=0.07, eyeSquintLeft=0.07, jawOpen=0.07)
    with pytest.raises(CalibrationError, match="not distinct enough"):
        build_profile(repeated(neutral, jitter=0.02), repeated(noisy_expression), "camera-a")


def test_requires_two_feature_families() -> None:
    neutral = frame()
    mouth_only = frame(jawOpen=0.9, mouthPucker=0.8, noseSneerLeft=0.6)
    with pytest.raises(CalibrationError, match="at least two"):
        build_profile(repeated(neutral), repeated(mouth_only), "camera-a")


def test_requires_enough_frames() -> None:
    with pytest.raises(CalibrationError, match="Not enough"):
        build_profile(repeated(frame(), 3), repeated(frame(jawOpen=1.0), 3), "camera-a")


def test_profile_round_trip() -> None:
    profile = build_profile(
        repeated(frame()),
        repeated(frame(browDownLeft=0.6, eyeSquintLeft=0.7, jawOpen=0.8)),
        "camera-a",
    )
    restored = type(profile).from_dict(profile.to_dict())
    assert restored == profile
