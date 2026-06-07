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
from app.execution.commands import parse_commands, serialize_commands


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

    @property
    def written_text(self) -> str:
        return self._written.decode("utf-8")


def _preflight_for_text(
    text: str,
    *,
    blocked: bool = False,
    parser: list[dict] | None = None,
    analysis: list[dict] | None = None,
    stats: dict | None = None,
) -> dict:
    commands, _diags = parse_commands(text, strict=False)
    return {
        "blocked": blocked,
        "commands_unrolled": serialize_commands(commands),
        "parser": parser or [],
        "analysis": analysis or [],
        "stats": {
            "move_count": 1,
            "path_length": 1.0,
            "collision_count": 0,
            "wall_proper_cross_count": 0,
            **(stats or {}),
        },
    }


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

    text = "SPEED 1\nMOVE 1 1\n"
    fake = _FakeSerialPort([b"DONE\n"])
    driver = SerialDriver("COM_TEST_ONLY", serial_connection=fake)
    monkeypatch.setattr(api_main, "_build_serial_driver_for_execute", lambda baudrate: driver)

    client = TestClient(api_main.app)
    r = client.post(
        "/api/execute_serial",
        json={
            "text": text,
            "dry_run": False,
            "walls": [[0, 0, 10, 0]],
            "preflight": _preflight_for_text(text),
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "sent"
    assert data["command_count"] >= 1
    assert data.get("driver_status", {}).get("driver_name") == "serial"
    assert len(data["artifact_paths"]) == 2
    assert data.get("trace_id")
    assert data.get("commands_sha256")
    assert data.get("preflight_summary", {}).get("server_collision_mode") == "error"


def test_execute_serial_live_rejected_without_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_PREFLIGHT_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "115200")
    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 1\nMOVE 1 1\n", "dry_run": False},
    )
    assert r.status_code == 409
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("error_detail") == "PREFLIGHT_REQUIRED"


def test_execute_serial_live_rejected_with_blocked_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_PREFLIGHT_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "115200")
    from app.api.main import app

    text = "SPEED 1\nMOVE 1 1\n"
    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={
            "text": text,
            "dry_run": False,
            "preflight": _preflight_for_text(text, blocked=True),
        },
    )
    assert r.status_code == 409
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("error_detail") == "PREFLIGHT_BLOCKED"


def test_execute_serial_live_server_final_analysis_blocks_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_PREFLIGHT_TEST")
    monkeypatch.setenv("SERIAL_BAUD", "115200")
    from app.api.main import app

    text = "SPEED 1\nPEN DOWN\nMOVE 0 0\nMOVE 10 0\nPEN UP\n"
    client = TestClient(app)
    r = client.post(
        "/api/execute_serial",
        json={
            "text": text,
            "dry_run": False,
            "walls": [[5, -1, 5, 1]],
            "preflight": _preflight_for_text(text),
        },
    )
    assert r.status_code == 409
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("error_detail") == "SERVER_PREFLIGHT_BLOCKED"
    assert data.get("preflight_summary", {}).get("server_collision_count", 0) > 0


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
        text = "SPEED 1\nMOVE 0 0\n"
        client = TestClient(api_main.app)
        r = client.post(
            "/api/execute_serial",
            json={
                "text": text,
                "dry_run": False,
                "preflight": _preflight_for_text(text),
            },
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


def test_execute_serial_stop_rejected_without_serial_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SERIAL_PORT", raising=False)
    import app.api.main as api_main

    api_main._set_execute_serial_active_driver(None)
    client = TestClient(api_main.app)
    r = client.post("/api/execute_serial/stop")
    assert r.status_code == 400
    data = r.json()
    assert data["status"] == "failed"
    assert data.get("ok") is False
    assert data.get("stopped") is False
    assert data.get("mode") == "no_driver"
    assert data.get("error_code") == "SERIAL_PORT_MISSING"
    assert data.get("error_detail") == "SERIAL_PORT_MISSING"


def test_execute_serial_stop_sends_to_active_driver_while_live_lock_held(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_STOP_TEST")
    import app.api.main as api_main

    fake = _FakeSerialPort([b"DONE\n"])
    driver = SerialDriver("COM_STOP_TEST", serial_connection=fake)
    driver.connect()
    assert api_main._execute_serial_live_lock.acquire(blocking=False)
    api_main._set_execute_serial_active_driver(driver)
    try:
        client = TestClient(api_main.app)
        r = client.post("/api/execute_serial/stop")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "sent"
        assert data.get("ok") is True
        assert data.get("stopped") is True
        assert data.get("mode") == "active_driver"
        assert "STOP\n" == fake.written_text
        assert data.get("driver_status", {}).get("last_stop_succeeded") is True
        assert data.get("notes") == ["target=active_serial_driver"]
    finally:
        api_main._set_execute_serial_active_driver(None)
        api_main._execute_serial_live_lock.release()
        driver.disconnect()


def test_execute_serial_stop_auth_guard_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXECUTE_SERIAL_ADMIN_TOKEN", "secret-stop")
    import app.api.main as api_main

    client = TestClient(api_main.app)
    r = client.post("/api/execute_serial/stop")
    assert r.status_code == 403
    assert r.json().get("error_detail") == "EXECUTE_SERIAL_INVALID_TOKEN"


def test_execute_serial_stop_direct_serial_driver(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_DIRECT_STOP")
    import app.api.main as api_main

    fake = _FakeSerialPort([b"DONE\n"])
    driver = SerialDriver("COM_DIRECT_STOP", serial_connection=fake)
    monkeypatch.setattr(api_main, "_build_serial_driver_for_execute", lambda baudrate: driver)
    api_main._set_execute_serial_active_driver(None)

    client = TestClient(api_main.app)
    r = client.post("/api/execute_serial/stop")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "sent"
    assert data.get("ok") is True
    assert data.get("stopped") is True
    assert data.get("mode") == "temporary_driver"
    assert fake.written_text == "STOP\n"
    assert data.get("notes") == ["target=serial_port"]


def test_execute_serial_stop_active_driver_failure_returns_clear_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SERIAL_PORT", "COM_STOP_FAIL")
    import app.api.main as api_main

    fake = _FakeSerialPort([b"ERR stop_rejected\n"])
    driver = SerialDriver("COM_STOP_FAIL", serial_connection=fake)
    driver.connect()
    api_main._set_execute_serial_active_driver(driver)
    try:
        client = TestClient(api_main.app)
        r = client.post("/api/execute_serial/stop")
        assert r.status_code == 500
        data = r.json()
        assert data["status"] == "failed"
        assert data.get("ok") is False
        assert data.get("stopped") is False
        assert data.get("mode") == "active_driver"
        assert data.get("error_code") == "STOP_SEND_FAILED"
        assert "MCU ERR" in (data.get("error_detail") or "")
    finally:
        api_main._set_execute_serial_active_driver(None)
        driver.disconnect()


def test_execute_serial_stop_does_not_touch_simulation_job_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Live serial stop, dry-run execute_serial ve job stop akışlarından ayrıdır."""
    monkeypatch.setenv("EXECUTE_SERIAL_ARTIFACT_DIR", str(tmp_path))
    monkeypatch.setenv("SERIAL_PORT", "COM_JOB_SEP")
    import app.api.main as api_main

    api_main._set_execute_serial_active_driver(None)
    client = TestClient(api_main.app)

    dry = client.post(
        "/api/execute_serial",
        json={"text": "SPEED 10\nMOVE 0 0\n", "dry_run": True},
    )
    assert dry.status_code == 200
    assert dry.json().get("status") in ("sent", "completed", "ok", "dry_run")

    fake = _FakeSerialPort([b"DONE\n"])
    driver = SerialDriver("COM_JOB_SEP", serial_connection=fake)
    monkeypatch.setattr(api_main, "_build_serial_driver_for_execute", lambda baudrate: driver)

    stop = client.post("/api/execute_serial/stop")
    assert stop.status_code == 200
    assert stop.json().get("mode") == "temporary_driver"
    assert stop.json().get("stopped") is True
