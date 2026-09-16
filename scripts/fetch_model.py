"""Download the pinned MediaPipe model without adding it to source control."""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import urllib.request
from pathlib import Path

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_SHA256 = "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DESTINATION = PROJECT_ROOT / "assets" / "face_landmarker.task"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main() -> int:
    if DESTINATION.exists() and digest(DESTINATION) == MODEL_SHA256:
        print(f"Model already verified: {DESTINATION}")
        return 0
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="guitar-face-model-", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        print(f"Downloading {MODEL_URL}")
        with urllib.request.urlopen(MODEL_URL, timeout=60) as response, temporary.open("wb") as out:
            shutil.copyfileobj(response, out)
        actual = digest(temporary)
        if actual != MODEL_SHA256:
            print(
                f"Checksum mismatch: expected {MODEL_SHA256}, received {actual}",
                file=sys.stderr,
            )
            return 1
        temporary.replace(DESTINATION)
        print(f"Verified model: {DESTINATION}")
        return 0
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
