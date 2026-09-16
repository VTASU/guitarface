# Contributing

Use Python 3.12 through `uv`, keep platform-specific camera and MIDI behavior behind their existing modules, and do not add camera images or the downloaded MediaPipe model to commits.

```sh
uv sync --group dev
uv run python scripts/fetch_model.py
uv run pytest
uv run guitar-face
```

New control behavior should have deterministic tests using synthetic blendshape dictionaries. Hardware changes should include corresponding manual checks in `docs/TESTING.md`.

Before opening a pull request, make sure `uv run pytest` passes and avoid committing generated app bundles, the downloaded model, caches, camera images, or local settings.
