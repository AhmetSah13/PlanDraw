"""POST /api/execute_serial — dry_run, env guard, mock UART."""
from __future__ import annotations

import sys
from collections import deque
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi.testclient import TestClient

from app.drivers.serial_driver import SerialDriver


class _FakeSerialPort:
    def __init__(self, responses: list[bytes] | None = None) -> None:
        self._written = bytearray()
        self._queue: deque[bytes] = deque(responses or [])
        self.is_open = True

    def write(self, data: bytes) -> int:
        n = len(data)
        self._written.extend(data)
        return n

    def readline(self) -> bytes:
        if not self._queue:
            return b""
        return self._queue.popleft()

    def close(self) -> None:
        self.is_open = False


def test_execute_serial_dry_run_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 10\nMOVE 0 0\n", "dry_run": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "dry_run"
    assert data["command_count"] >= 1
    assert len(data["artifact_paths"]) == 2
    for p in data["artifact_paths"]:
        assert Path(p).is_file()


def test_execute_serial_live_rejected_without_serial_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERIAL_PORT", raising=False)
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 10\nMOVE 0 0\n", "dry_run": False},
    )
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("error_detail") == "SERIAL_PORT_MISSING"
    assert "SERIAL_PORT" in (data.get("message") or "")


def test_execute_serial_live_with_mock_driver(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_TEST_ONLY")
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    import app.api.main as api_main

    fake = _FakeSerialPort([b"DONE\n"])
    driver = SerialDriver("COM_TEST_ONLY", serial_connection=fake)
    monkeypatch.setattr(api_main, "_build_serial_driver_for_execute", lambda baudrate: driver)

    client = TestClient(api_main.app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 1 1\n", "dry_run": False},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "sent"
    assert data["command_count"] >= 1
    assert data.get("driver_status", {}).get("driver_name") == "serial"
    assert len(data["artifact_paths"]) == 2


def test_execute_serial_invalid_baud_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_BAUD_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "not_an_int")
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": False},
    )
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("error_detail") == "INVALID_SERIAL_BAUD"
    assert "SERIAL_BAUD" in (data.get("message") or "")


def test_execute_serial_negative_baud_returns_400(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_BAUD_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "-1")
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": False},
    )
    assert r.status_code == 400
    assert r.json().get("error_detail") == "INVALID_SERIAL_BAUD"


def test_execute_serial_concurrent_live_rejected_with_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_BUSY_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "115200")
    import app.api.main as api_main

    assert api_main._execute_serial_live_lock.acquire(blocking=False)
    try:
        client = TestClient(api_main.app)
        r = client.post(
            "/api/execute_serial",
            json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": False},
        )
        assert r.status_code == 409
        data = r.json()
        assert data["status"] == "failed"
        assert data.get("error_detail") == "SERIAL_EXECUTION_BUSY"
    finally:
        api_main._execute_serial_live_lock.release()


def test_execute_serial_localhost_like_client_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """TestClient ``testclient`` host'u loopback ile aynı güven sınıfında kabul edilir."""
    monkeypatch.delenv("EXECUTE_SERIAL_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("EXECUTE_SERIAL_ALLOW_REMOTE", "false")
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dry_run"


def test_execute_serial_remote_host_rejected_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXECUTE_SERIAL_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("EXECUTE_SERIAL_ALLOW_REMOTE", "false")
    import app.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_serial_peer_host", lambda _r: "198.51.100.2")

    client = TestClient(api_main.app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
    )
    assert r.status_code == 403
    data = r.json()
    assert data["status"] == "failed"
    assert data["command_count"] == 0
    assert data.get("error_detail") == "EXECUTE_SERIAL_LOCALHOST_ONLY"


def test_execute_serial_allow_remote_bypasses_host_check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EXECUTE_SERIAL_ADMIN_TOKEN", raising=False)
    monkeypatch.setenv("EXECUTE_SERIAL_ALLOW_REMOTE", "true")
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    import app.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_serial_peer_host", lambda _r: "198.51.100.3")

    client = TestClient(api_main.app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dry_run"


def test_execute_serial_missing_token_rejected_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTE_SERIAL_ADMIN_TOKEN", "gizli-anahtar")
    monkeypatch.delenv("EXECUTE_SERIAL_ALLOW_REMOTE", raising=False)
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
    )
    assert r.status_code == 403
    assert r.json().get("error_detail") == "EXECUTE_SERIAL_INVALID_TOKEN"


def test_execute_serial_wrong_token_rejected_403(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTE_SERIAL_ADMIN_TOKEN", "dogru")
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
        headers={"X-Execute-Token": "yanlis"},
    )
    assert r.status_code == 403
    assert r.json().get("error_detail") == "EXECUTE_SERIAL_INVALID_TOKEN"


def test_execute_serial_correct_token_accepted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("EXECUTE_SERIAL_ADMIN_TOKEN", "dogru")
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
        headers={"X-Execute-Token": "dogru"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "dry_run"


def test_execute_serial_both_guards_require_host_and_token(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Uzak host + token doğru olsa bile allow_remote=false iken host reddedilir."""
    monkeypatch.setenv("EXECUTE_SERIAL_ADMIN_TOKEN", "t1")
    monkeypatch.setenv("EXECUTE_SERIAL_ALLOW_REMOTE", "false")
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    import app.api.main as api_main

    monkeypatch.setattr(api_main, "_execute_serial_peer_host", lambda _r: "10.0.0.1")

    client = TestClient(api_main.app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 0 0\n", "dry_run": True},
        headers={"X-Execute-Token": "t1"},
    )
    assert r.status_code == 403
    assert r.json().get("error_detail") == "EXECUTE_SERIAL_LOCALHOST_ONLY"
