from __future__ import annotations

from collections import deque
from pathlib import Path

import pytest

from app.drivers.file_driver import FileDriver
from app.drivers.serial_driver import SerialDriver
from app.execution.commands import PenCommand, SpeedCommand
from app.execution.job_model import ExecutionContext, ExecutionJobOptions
from app.execution.job_runner import run_command_execution_job


class _RecordingDriver:
    """RobotDriver protokolü için minimal test çifti."""

    def __init__(self) -> None:
        self.send_calls = 0
        self._connected = False

    def connect(self) -> None:
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def stop(self) -> None:
        pass

    def get_status(self) -> dict:
        return {"driver_name": "recording", "connected": self._connected}

    def send_commands(self, commands, *, start=(0.0, 0.0), metadata=None) -> None:
        self.send_calls += 1


def test_blocked_skips_driver():
    cmds = [SpeedCommand(1.0), PenCommand(is_down=False)]
    drv = _RecordingDriver()
    res = run_command_execution_job(
        cmds,
        driver=drv,
        context=ExecutionContext(alignment_blocked=True),
        options=ExecutionJobOptions(dry_run=False, allow_execution_when_alignment_blocked=False),
    )
    assert res.status == "blocked"
    assert drv.send_calls == 0


def test_empty_skipped():
    res = run_command_execution_job([], driver=_RecordingDriver())
    assert res.status == "skipped"
    assert res.command_count == 0


def test_dry_run_writes_artifact(tmp_path: Path):
    cmds = [SpeedCommand(10.0)]
    res = run_command_execution_job(
        cmds,
        driver=None,
        options=ExecutionJobOptions(
            dry_run=True,
            artifact_dir=str(tmp_path),
            artifact_basename="t",
        ),
    )
    assert res.status == "dry_run"
    assert len(res.artifact_paths) == 2
    assert (tmp_path / "t_commands.dsl.txt").exists()
    assert (tmp_path / "t_summary.json").read_text(encoding="utf-8")


def test_dry_run_allowed_when_blocked(tmp_path: Path):
    cmds = [SpeedCommand(1.0)]
    res = run_command_execution_job(
        cmds,
        driver=None,
        context=ExecutionContext(alignment_blocked=True),
        options=ExecutionJobOptions(
            dry_run=True,
            artifact_dir=str(tmp_path),
            allow_execution_when_alignment_blocked=False,
        ),
    )
    assert res.status == "dry_run"
    assert res.artifact_paths


def test_file_driver_sent(tmp_path: Path):
    out = tmp_path / "out.dsl.txt"
    cmds = [SpeedCommand(5.0), PenCommand(is_down=True)]
    fd = FileDriver(out, mode="dsl")
    res = run_command_execution_job(
        cmds,
        driver=fd,
        options=ExecutionJobOptions(
            dry_run=False,
            artifact_dir=str(tmp_path / "bak"),
            artifact_basename="job",
        ),
    )
    assert res.status == "sent"
    assert out.exists()
    assert res.driver_kind == "file"


def test_driver_none_fails_when_not_dry_run():
    res = run_command_execution_job(
        [SpeedCommand(1.0)],
        driver=None,
        options=ExecutionJobOptions(dry_run=False),
    )
    assert res.status == "failed"
    assert "Driver verilmedi" in res.message


class _FakeSerialPort:
    def __init__(self, responses: list[bytes] | None = None) -> None:
        self.is_open = True
        self._q: deque[bytes] = deque(responses or [])

    def write(self, data: bytes) -> int:
        return len(data)

    def readline(self) -> bytes:
        return self._q.popleft() if self._q else b""

    def close(self) -> None:
        self.is_open = False


def test_serial_driver_job_runner_smoke(tmp_path: Path):
    fake = _FakeSerialPort([b"DONE\n"])
    sd = SerialDriver("COM1", serial_connection=fake)
    res = run_command_execution_job(
        [SpeedCommand(1.0)],
        driver=sd,
        options=ExecutionJobOptions(dry_run=False, artifact_dir=str(tmp_path)),
    )
    assert res.status == "sent"
    assert res.driver_kind == "serial"
