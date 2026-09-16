"""Locate resources in source trees and frozen PyInstaller bundles."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def model_path() -> Path:
    override = os.environ.get("GUITAR_FACE_MODEL_PATH")
    candidates = []
    if override:
        candidates.append(Path(override).expanduser())
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / "assets" / "face_landmarker.task")
    candidates.append(project_root() / "assets" / "face_landmarker.task")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "face_landmarker.task is missing. Run: uv run python scripts/fetch_model.py"
    )
