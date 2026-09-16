from __future__ import annotations

import pytest

from guitar_face.mapping import MappingSettings, OutputMapper


def test_linear_full_range_and_deadzone() -> None:
    mapper = OutputMapper(MappingSettings(smoothing_ms=0, deadzone=0.05))
    assert mapper.process(0.0, 1000)[1] == 0
    assert mapper.process(0.05, 1010)[1] == 0
    assert mapper.process(1.0, 1020)[1] == 127


def test_range_curve_sensitivity_and_inversion() -> None:
    settings = MappingSettings(
        smoothing_ms=0,
        deadzone=0.0,
        sensitivity=2.0,
        curve_gamma=2.0,
        inverted=True,
        output_min=10,
        output_max=110,
    )
    mapper = OutputMapper(settings)
    assert mapper.neutral_value() == 110
    # 0.25 * sensitivity => 0.5; gamma => 0.25; inverted => 0.75.
    smoothed, value = mapper.process(0.25, 1000)
    assert smoothed == pytest.approx(0.25)
    assert value == 85


def test_time_based_smoothing_moves_without_jumping() -> None:
    mapper = OutputMapper(MappingSettings(smoothing_ms=100, deadzone=0.0))
    mapper.process(0.0, 1000)
    smoothed, value = mapper.process(1.0, 1100)
    assert smoothed == pytest.approx(0.6321, rel=1e-3)
    assert value == 80


@pytest.mark.parametrize(
    "settings",
    [
        MappingSettings(sensitivity=4.0),
        MappingSettings(smoothing_ms=300),
        MappingSettings(deadzone=0.8),
        MappingSettings(curve_gamma=3.0),
        MappingSettings(output_min=100, output_max=50),
    ],
)
def test_invalid_settings(settings: MappingSettings) -> None:
    with pytest.raises(ValueError):
        settings.validate()
