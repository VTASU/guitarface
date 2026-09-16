# Hardware acceptance checklist

Automated tests do not require a camera or AmpliTube. Before calling a local build performance-ready, verify:

- The application starts cleanly with no camera and notices a camera connected afterward.
- Built-in, USB, and Continuity cameras appear by name when available.
- Denying camera permission produces a recoverable error; granting permission and restarting capture works.
- A relaxed calibrated face stays below 5% aside from momentary noise.
- The held guitar face reaches at least 90%, and ordinary blinks do not move the meter materially.
- Covering or leaving the camera holds the last output for 500 ms, then returns smoothly to neutral over 500 ms.
- The displayed p95 capture-to-result latency stays below 100 ms during normal use.
- `Guitar Face` appears in AmpliTube’s MIDI input list and **Send MIDI Learn pulse** completes MIDI Learn.
- The full configured output range reaches the wah pedal without toggling bypass.
- Settings and the camera-specific calibration survive an app relaunch.
- `codesign --verify --deep --strict "dist/Guitar Face.app"` exits successfully.
