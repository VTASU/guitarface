# Architecture

Guitar Face keeps platform edges separate from the expression-control engine:

1. `camera.py` uses Qt Multimedia to discover hot-pluggable cameras and produce timestamped `QImage` frames.
2. `vision.py` creates MediaPipe's graph on the macOS main thread, as required by its graphics context, then uses its asynchronous live-stream API. Its capacity-one pending slot replaces stale frames so load increases frame drops instead of latency.
3. `calibration.py` computes robust neutral medians/noise and a personal neutral-to-expression direction from semantic blendshapes.
4. `mapping.py` applies dead zone, sensitivity, curve, time-based smoothing, inversion, and MIDI range.
5. `tracking.py` holds for 500 ms after face loss and then returns to neutral over 500 ms.
6. `midi.py` owns the virtual `Guitar Face` CoreMIDI source and suppresses duplicate CC messages.
7. `ui.py` coordinates these components without placing image processing or calibration math in widgets.

Camera frames live only long enough to render the preview and run inference. The saved calibration contains numeric blendshape medians, scales, and a direction vector—not images or identity data.

The pure calibration, mapping, tracking, MIDI-message, and configuration modules are platform-independent. A future Windows port can replace the MIDI backend with an existing loopMIDI destination; Windows’ standard RtMidi backend cannot create its own virtual MIDI port.
