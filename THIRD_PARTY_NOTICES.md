# Third-party notices

Guitar Face depends on software distributed under its own licenses:

- MediaPipe 0.10.21 — Apache-2.0. Its Tasks APIs process frames on-device; Google documents collection of performance and utilization metrics for current Tasks releases.
- Qt for Python / PySide6 — LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only. Guitar Face uses the dynamically linked PyPI distribution.
- NumPy — BSD-3-Clause.
- python-rtmidi and RtMidi — MIT-style licenses.
- platformdirs — MIT.
- PyInstaller — GPL-2.0-or-later with an exception permitting distribution of bundled applications.

The downloaded `face_landmarker.task` model is a separate Google-provided asset. It is not covered by Guitar Face’s MIT license and is intentionally excluded from source control. Review each dependency’s installed license text before distributing binaries beyond a local development build.
