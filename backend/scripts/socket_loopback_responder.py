#!/usr/bin/env python3
"""
Driver-free TCP loopback responder for hardware-prep protocol tests.

Default bind target is 127.0.0.1:9000. This script does not use COM ports,
firmware, robot hardware, or motor controllers.
"""

from __future__ import annotations

import argparse
import socketserver
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from scripts.serial_loopback_responder import LoopbackResponder


class _LoopbackRequestHandler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        mode = getattr(self.server, "responder_mode", "normal")
        self.responder = LoopbackResponder(mode=mode)

    def handle(self) -> None:
        peer = f"{self.client_address[0]}:{self.client_address[1]}"
        print("client connected:", peer)
        while True:
            raw = self.rfile.readline()
            if not raw:
                print("client disconnected:", peer)
                return
            text = raw.decode("utf-8", errors="replace").strip()
            print("RX:", text)
            response = self.responder.handle_line(text)
            if response is None:
                continue
            print("TX:", response)
            self.wfile.write((response + "\n").encode("utf-8"))
            self.wfile.flush()


class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def run_server(host: str, port: int, mode: str) -> int:
    with _ThreadingTCPServer((host, port), _LoopbackRequestHandler) as server:
        server.responder_mode = mode
        print("Socket loopback responder started.")
        print("Host:", host)
        print("Port:", port)
        print("Mode:", mode)
        print("Safety: localhost protocol test only; no COM port or hardware is used.")
        print("Press Ctrl+C to stop.")
        try:
            server.serve_forever(poll_interval=0.2)
        except KeyboardInterrupt:
            print("Stopping socket responder.")
            return 0
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Driver-free TCP responder for serial protocol loopback tests."
    )
    parser.add_argument("--host", default="127.0.0.1", help="bind host, default 127.0.0.1")
    parser.add_argument("--port", type=int, default=9000, help="bind port, default 9000")
    parser.add_argument(
        "--mode",
        choices=("normal", "malformed"),
        default="normal",
        help="normal: DONE/STATUS/STOP responses; malformed: force ERR for completed batches",
    )
    args = parser.parse_args()
    return run_server(args.host, args.port, args.mode)


if __name__ == "__main__":
    raise SystemExit(main())
