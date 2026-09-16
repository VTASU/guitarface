from __future__ import annotations

import hashlib

import pytest

from guitar_face.resources import model_path


def test_model_override(monkeypatch, tmp_path) -> None:
    model = tmp_path / "model.task"
    model.write_bytes(b"model")
    monkeypatch.setenv("GUITAR_FACE_MODEL_PATH", str(model))
    assert model_path() == model


def test_missing_override_falls_back_or_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GUITAR_FACE_MODEL_PATH", str(tmp_path / "missing"))
    try:
        found = model_path()
        assert found.name == "face_landmarker.task"
    except FileNotFoundError as exc:
        assert "fetch_model.py" in str(exc)


def test_checked_in_model_checksum_if_present(monkeypatch) -> None:
    monkeypatch.delenv("GUITAR_FACE_MODEL_PATH", raising=False)
    try:
        model = model_path()
    except FileNotFoundError:
        pytest.skip("Model is fetched separately")
    assert hashlib.sha256(model.read_bytes()).hexdigest() == (
        "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
    )
