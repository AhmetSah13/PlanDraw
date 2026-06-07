#!/usr/bin/env python3
"""
Development-only serial protocol responder for safe loopback testing.

This script is not firmware and must not be used with a robot or motor controller.
It opens only the port explicitly provided by the operator. If no port is provided,
it exits without opening any serial connection.

Expected safe setup:
- virtual COM pair, or
- USB-serial adapter connected only in a non-robot loopback/responder setup.

Never point this script at a robot, motor controller, or production firmware port.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import parse_commands

ResponderMode = Literal["normal", "malformed"]


@dataclass
class LoopbackResponder:
    """Small line-based responder for SERIAL_PROTOCOL_V1 profile B smoke tests."""

    mode: ResponderMode = "normal"
    max_commands: int = 256
    in_batch: bool = False
    batch_lines: list[str] = field(default_factory=list)
    batch_count: int = 0

    def handle_line(self, line: str) -> str | None:
        text = line.strip()
        if not text:
            return None
        if len(text) >= 160:
            self._reset_batch()
            return "ERR line_too_long"

        upper = text.upper()
        if upper == "STATUS":
            state = "RECEIVING" if self.in_batch else "IDLE"
            idle = 0 if self.in_batch else 1
            return (
                f"STATUS responder=1 idle={idle} state={state} queued={len(self.batch_lines)} "
                f"batches={self.batch_count}"
            )
        if upper == "STOP":
            self._reset_batch()
            return "DONE"
        if upper == "BEGIN":
            self.in_batch = True
            self.batch_lines.clear()
            return "OK"
        if upper == "END":
            if not self.in_batch:
                return "ERR end_without_begin"
            payload = "\n".join(self.batch_lines)
            self._reset_batch()
            return self._finish_batch(payload)

        if self.in_batch:
            validation = self._validate_single_command(text)
            if validation is not None:
                self._reset_batch()
                return validation
            if len(self.batch_lines) >= self.max_commands:
                self._reset_batch()
                return "ERR queue_full"
            self.batch_lines.append(text)
            return None

        # Profile A style single command is accepted for manual probing.
        return self._finish_batch(text, done_response="OK")

    def _finish_batch(self, payload: str, *, done_response: str = "DONE") -> str:
        if self.mode == "malformed":
            return "ERR forced_malformed"

        commands, diagnostics = parse_commands(payload)
        errors = [diag for diag in diagnostics if diag.severity == "ERROR"]
        if errors:
            first = errors[0]
            return f"ERR parse line={first.line} message={_safe_message(first.message)}"
        if not commands and payload.strip():
            return "ERR parse no_commands"

        self.batch_count += 1
        return done_response

    def _reset_batch(self) -> None:
        self.in_batch = False
        self.batch_lines.clear()

    def _validate_single_command(self, text: str) -> str | None:
        commands, diagnostics = parse_commands(text)
        errors = [diag for diag in diagnostics if diag.severity == "ERROR"]
        if errors:
            first = errors[0]
            return f"ERR parse line={first.line} message={_safe_message(first.message)}"
        if not commands and text.strip():
            return "ERR parse no_commands"
        return None


def _safe_message(message: str) -> str:
    safe = " ".join(str(message).split())
    return safe[:120] if safe else "unknown"


def _open_serial(port: str, baudrate: int, timeout: float):
    try:
        import serial
    except ImportError as exc:
        raise SystemExit("pyserial is not installed in this environment.") from exc

    return serial.Serial(port=port, baudrate=baudrate, timeout=timeout)


def run_responder(port: str, baudrate: int, timeout: float, mode: ResponderMode) -> int:
    responder = LoopbackResponder(mode=mode)
    ser = _open_serial(port, baudrate, timeout)
    print("Serial loopback responder started.")
    print("Port:", port)
    print("Baud:", baudrate)
    print("Timeout (s):", timeout)
    print("Mode:", mode)
    print("Safety: use only virtual COM or non-robot USB-serial loopback.")
    print("Press Ctrl+C to stop.")

    try:
        while True:
            raw = ser.readline()
            if not raw:
                continue
            text = raw.decode("utf-8", errors="replace").strip()
            print("RX:", text)
            response = responder.handle_line(text)
            if response is None:
                continue
            print("TX:", response)
            ser.write((response + "\n").encode("utf-8"))
    except KeyboardInterrupt:
        print("Stopping responder.")
        return 0
    finally:
        ser.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Development-only serial responder for safe loopback tests. "
            "Do not use robot, motor controller, or production firmware ports."
        )
    )
    parser.add_argument("port", help="Explicit safe loopback port, e.g. COM11 or /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--timeout", type=float, default=0.2, help="serial read timeout in seconds")
    parser.add_argument(
        "--mode",
        choices=("normal", "malformed"),
        default="normal",
        help="normal: DONE/STATUS/STOP responses; malformed: force ERR for completed batches",
    )
    args = parser.parse_args()
    return run_responder(args.port, args.baudrate, args.timeout, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
