"""Virtual MIDI output with an injectable backend for tests."""

from __future__ import annotations

import platform
from collections.abc import Callable
from typing import Protocol


class MidiBackend(Protocol):
    def open_virtual_port(self, name: str) -> None: ...

    def send_message(self, message: list[int]) -> None: ...

    def close_port(self) -> None: ...


def build_cc_message(channel: int, controller: int, value: int) -> list[int]:
    if not 1 <= channel <= 16:
        raise ValueError("MIDI channel must be between 1 and 16.")
    if not 0 <= controller <= 127 or not 0 <= value <= 127:
        raise ValueError("MIDI controller and value must be between 0 and 127.")
    return [0xB0 | (channel - 1), controller, value]


class MidiOutput:
    def __init__(
        self,
        port_name: str = "Guitar Face",
        backend_factory: Callable[[], MidiBackend] | None = None,
    ) -> None:
        self.port_name = port_name
        self._backend_factory = backend_factory
        self._backend: MidiBackend | None = None
        self._last_key: tuple[int, int, int] | None = None
        self.error: str | None = None

    @property
    def is_open(self) -> bool:
        return self._backend is not None

    def _default_backend(self) -> MidiBackend:
        import rtmidi

        system = platform.system()
        if system == "Darwin":
            return rtmidi.MidiOut(rtmidi.API_MACOSX_CORE, name=self.port_name)
        if system == "Linux":
            return rtmidi.MidiOut(rtmidi.API_UNSPECIFIED, name=self.port_name)
        raise RuntimeError(
            "This platform cannot create a virtual MIDI source without an external driver."
        )

    def open(self) -> bool:
        if self.is_open:
            return True
        try:
            backend = (
                self._backend_factory() if self._backend_factory else self._default_backend()
            )
            backend.open_virtual_port(self.port_name)
            self._backend = backend
            self._last_key = None
            self.error = None
            return True
        except Exception as exc:  # backend failures must remain recoverable in the UI
            self._backend = None
            self.error = str(exc)
            return False

    def send(self, channel: int, controller: int, value: int, *, force: bool = False) -> bool:
        if not self.is_open and not self.open():
            return False
        key = (channel, controller, value)
        if key == self._last_key and not force:
            return True
        try:
            assert self._backend is not None
            self._backend.send_message(build_cc_message(*key))
            self._last_key = key
            self.error = None
            return True
        except Exception as exc:
            self.error = str(exc)
            self.close()
            return False

    def close(self) -> None:
        backend, self._backend = self._backend, None
        self._last_key = None
        if backend is not None:
            try:
                backend.close_port()
            except Exception:
                pass
