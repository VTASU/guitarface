from __future__ import annotations

from guitar_face.midi import MidiOutput, build_cc_message


class FakeBackend:
    def __init__(self) -> None:
        self.port_name = None
        self.messages: list[list[int]] = []
        self.closed = False

    def open_virtual_port(self, name: str) -> None:
        self.port_name = name

    def send_message(self, message: list[int]) -> None:
        self.messages.append(message)

    def close_port(self) -> None:
        self.closed = True


def test_cc_message() -> None:
    assert build_cc_message(1, 11, 64) == [0xB0, 11, 64]
    assert build_cc_message(16, 127, 127) == [0xBF, 127, 127]


def test_virtual_output_suppresses_duplicates_unless_forced() -> None:
    backend = FakeBackend()
    output = MidiOutput(backend_factory=lambda: backend)
    assert output.open()
    assert backend.port_name == "Guitar Face"
    assert output.send(1, 11, 64)
    assert output.send(1, 11, 64)
    assert output.send(1, 11, 64, force=True)
    assert backend.messages == [[0xB0, 11, 64], [0xB0, 11, 64]]
    output.close()
    assert backend.closed


def test_open_failure_is_recoverable() -> None:
    def failing_factory():
        raise RuntimeError("CoreMIDI unavailable")

    output = MidiOutput(backend_factory=failing_factory)
    assert not output.open()
    assert output.error == "CoreMIDI unavailable"
