# Guitar Face

Guitar Face turns your personal “guitar face” into a MIDI expression controller for a wah pedal. It watches a camera locally, learns the difference between your relaxed face and your full performance face, and publishes a virtual MIDI source named **Guitar Face**.

The first release targets Apple-silicon Macs and AmpliTube 5 in standalone mode. Frames are processed in memory and are never recorded or uploaded by Guitar Face. MediaPipe 0.10.21 is deliberately pinned because its successor's native macOS task runtime aborts during model initialization on the target system.

## Features

- Personal two-pose calibration for your own facial expression
- Built-in, USB, and iPhone Continuity Camera support
- Live expression and MIDI output meters
- Adjustable sensitivity, smoothing, response curve, inversion, channel, CC, and range
- Virtual CoreMIDI source for MIDI Learn in AmpliTube
- Automatic hold and smooth return to neutral when face tracking is lost
- Camera-specific calibration profiles stored locally

## Quick start

Requirements: macOS 13 or newer, Apple silicon, a connected camera, [uv](https://docs.astral.sh/uv/), and AmpliTube 5.

```sh
uv sync --group dev
uv run python scripts/fetch_model.py
uv run guitar-face
```

The first camera start prompts for macOS camera permission. If permission was previously denied, enable it in **System Settings → Privacy & Security → Camera**. When running from source, macOS may list the terminal or Python host rather than Guitar Face.

## Calibrate your guitar face

1. Select a built-in camera, USB webcam, or available iPhone Continuity Camera.
2. Press **Start** and keep one face clearly visible.
3. Capture a relaxed neutral face.
4. Capture your full guitar face: scrunch your eyes, work your eyebrows, and stank up your mouth.
5. Use Sensitivity, Smoothing, and Curve to tune the feel.

Calibration is saved separately for every camera. Ordinary eye blinks and gaze direction are deliberately excluded from the control signal.

## Connect AmpliTube 5

1. Launch Guitar Face before opening AmpliTube, or reopen AmpliTube’s MIDI settings after Guitar Face launches.
2. In AmpliTube 5 settings, enable **Guitar Face** as a MIDI input.
3. Load and enable a wah pedal.
4. Select MIDI Learn for the wah pedal-position parameter.
5. While AmpliTube says it is waiting for input, press **Send MIDI Learn pulse** in Guitar Face.

Guitar Face defaults to MIDI channel 1, CC11, and values 0–127. It controls pedal position only; wah bypass remains under your control in AmpliTube.

## Build `Guitar Face.app`

```sh
bash scripts/build_app.sh
```

The locally ad-hoc-signed application is written to `dist/Guitar Face.app`. It contains Python, Qt, MediaPipe, the verified face model, and the CoreMIDI adapter, so it does not require a Python environment at runtime. It is not notarized for redistribution.

## Test

```sh
uv run pytest
```

Hardware acceptance checks are documented in [docs/TESTING.md](docs/TESTING.md). Architecture and extension points are described in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Privacy and third-party software

Guitar Face does not include analytics, save camera frames, or send frames over the network. MediaPipe states that input data is processed on-device, while its Tasks APIs may send performance and utilization metrics to Google. See the [MediaPipe privacy notice](https://github.com/google-ai-edge/mediapipe#privacy-notice) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

The model download is pinned to Google’s versioned Face Landmarker asset and checked against a committed SHA-256 value. The model itself is excluded from this MIT-licensed repository because its redistribution terms have not been independently confirmed.

## License

Guitar Face source code is available under the [MIT License](LICENSE).
