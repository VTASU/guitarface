from __future__ import annotations

import pytest

from guitar_face.resources import model_path


def test_face_landmarker_model_initializes(qapp) -> None:
    try:
        model = model_path()
    except FileNotFoundError:
        pytest.skip("Model is fetched separately")

    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision

    options = vision.FaceLandmarkerOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(model), delegate=python.BaseOptions.Delegate.CPU
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_faces=1,
        output_face_blendshapes=True,
    )
    try:
        landmarker = vision.FaceLandmarker.create_from_options(options)
    except RuntimeError as exc:
        if "NSOpenGLPixelFormat" in str(exc):
            pytest.skip("The headless test host cannot create MediaPipe's macOS graphics service")
        raise
    landmarker.close()
