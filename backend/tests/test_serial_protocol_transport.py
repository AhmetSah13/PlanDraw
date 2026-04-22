# serial_protocol + fake_serial_transport birim testleri
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.fake_serial_transport import FakeSerialTransport
from app.drivers.serial_protocol import (
    ParsedResponse,
    SerialWireProfile,
    frame_dsl_payload,
    frame_stop_line,
    parse_response_line,
    wire_text_to_bytes,
)


def test_frame_profile_a_plain_dsl() -> None:
    dsl = "SPEED 1\nMOVE 10 0"
    wire = frame_dsl_payload(dsl, profile=SerialWireProfile.A)
    assert wire == "SPEED 1\nMOVE 10 0\n"


def test_frame_profile_b_begin_end() -> None:
    dsl = "SPEED 1\nMOVE 10 0"
    wire = frame_dsl_payload(dsl, profile=SerialWireProfile.B)
    assert wire == "BEGIN\nSPEED 1\nMOVE 10 0\nEND\n"


def test_frame_empty_dsl_profile_b() -> None:
    assert frame_dsl_payload("", profile=SerialWireProfile.B) == "BEGIN\nEND\n"


def test_frame_stop_line() -> None:
    assert frame_stop_line() == "STOP\n"


def test_parse_ok_done_err() -> None:
    assert parse_response_line("OK\n").kind == "ok"
    assert parse_response_line("DONE").kind == "done"
    r = parse_response_line("ERR parse")
    assert r.kind == "err"
    assert r.text == "parse"
    r2 = parse_response_line(b"ERR bad input\n")
    assert r2.kind == "err"
    assert r2.text == "bad input"


def test_parse_status_unknown() -> None:
    s = parse_response_line("STATUS idle=1")
    assert s.kind == "status"
    assert "idle" in (s.text or "")
    u = parse_response_line("weird")
    assert u.kind == "unknown"
    assert u.text == "weird"


def test_fake_transport_write_and_read() -> None:
    t = FakeSerialTransport()
    t.enqueue_line("OK")
    t.enqueue_line("DONE")
    payload = wire_text_to_bytes("MOVE 1 1\n")
    t.write(payload)
    assert t.readline() == b"OK\n"
    assert t.readline() == b"DONE\n"
    assert t.readline() == b""
    assert "MOVE 1 1" in t.written_text()


def test_fake_transport_empty_readline() -> None:
    t = FakeSerialTransport()
    assert t.readline() == b""


def test_wire_bytes_roundtrip() -> None:
    w = wire_text_to_bytes(frame_dsl_payload("PEN DOWN", profile=SerialWireProfile.A))
    assert w.decode("utf-8") == "PEN DOWN\n"
