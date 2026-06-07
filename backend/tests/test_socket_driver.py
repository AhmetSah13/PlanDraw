from __future__ import annotations

import socket
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.socket_driver import SocketDriver
from app.execution.commands import ForwardCommand, SpeedCommand
from scripts.socket_loopback_responder import _LoopbackRequestHandler, _ThreadingTCPServer


@contextmanager
def _server(mode: str = "normal") -> Iterator[tuple[str, int]]:
    server = _ThreadingTCPServer(("127.0.0.1", 0), _LoopbackRequestHandler)
    server.responder_mode = mode
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield str(host), int(port)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _recv_line(sock: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while True:
        b = sock.recv(1)
        if not b:
            return b"".join(chunks)
        chunks.append(b)
        if b == b"\n":
            return b"".join(chunks)


def test_socket_driver_done() -> None:
    with _server() as (host, port):
        driver = SocketDriver(host=host, port=port)
        driver.connect()
        try:
            driver.send_commands([SpeedCommand(1.0), ForwardCommand(0.05)])
            status = driver.get_status()
            assert status["last_send_succeeded"] is True
            assert status["last_command_count"] == 2
        finally:
            driver.disconnect()


def test_socket_driver_err() -> None:
    with _server(mode="malformed") as (host, port):
        driver = SocketDriver(host=host, port=port)
        driver.connect()
        try:
            with pytest.raises(RuntimeError, match="responder ERR"):
                driver.send_commands([SpeedCommand(1.0)])
        finally:
            driver.disconnect()


def test_socket_driver_status() -> None:
    with _server() as (host, port):
        driver = SocketDriver(host=host, port=port)
        driver.connect()
        try:
            status = driver.query_status()
            assert "responder=1" in status
            assert "idle=1" in status
        finally:
            driver.disconnect()


def test_socket_driver_stop() -> None:
    with _server() as (host, port):
        driver = SocketDriver(host=host, port=port)
        driver.connect()
        try:
            driver.stop()
            assert driver.get_status()["stopped"] is True
        finally:
            driver.disconnect()


def test_socket_responder_parse_err_for_bad_payload() -> None:
    with _server() as (host, port):
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b"BEGIN\n")
            assert _recv_line(sock) == b"OK\n"
            sock.sendall(b"MOVE\n")
            raw = _recv_line(sock)
        assert raw.startswith(b"ERR")
