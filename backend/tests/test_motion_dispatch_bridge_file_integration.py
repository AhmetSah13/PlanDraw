# Köprü + FileDriver entegrasyonu (tmp_path, HTTP yok)
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.file_driver import FileDriver
from app.execution.commands import MoveCommand, PenCommand, SpeedCommand
from app.motion.motion_dispatch_bridge import execute_and_optionally_dispatch


def _cmds():
    return [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(1.0, 0.0),
    ]


def test_bridge_dispatch_off_file_driver_no_artifact(tmp_path: Path) -> None:
    out = tmp_path / "dispatch_off.dsl"
    fd = FileDriver(out, mode="dsl")
    r = execute_and_optionally_dispatch(
        _cmds(),
        driver=fd,
        dispatch_enabled=False,
        max_motion_steps_total=25_000,
    )
    assert r.motion_result.done is True
    assert r.dispatch_attempted is False
    assert r.dispatch_succeeded is None
    assert not out.exists()
    assert r.driver_status is None


def test_bridge_dispatch_on_file_dsl_writes_and_status(tmp_path: Path) -> None:
    out = tmp_path / "out.dsl"
    fd = FileDriver(out, mode="dsl")
    r = execute_and_optionally_dispatch(
        _cmds(),
        driver=fd,
        dispatch_enabled=True,
        max_motion_steps_total=25_000,
    )
    assert r.motion_result.done is True
    assert r.dispatch_attempted is True
    assert r.dispatch_succeeded is True
    assert r.dispatch_error is None
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert len(text.strip()) > 0
    upper = text.upper()
    assert "SPEED" in upper or "MOVE" in upper or "PEN" in upper
    ds = r.driver_status
    assert ds is not None
    assert ds.get("driver_name") == "file"
    assert ds.get("output_path") == str(out)
    assert ds.get("output_mode") == "dsl"
    assert ds.get("last_write_succeeded") is True
    assert ds.get("last_command_count") == 3


def test_bridge_dispatch_on_file_robot_v1_writes_and_status(tmp_path: Path) -> None:
    out = tmp_path / "rob.robot_v1.txt"
    fd = FileDriver(out, mode="robot_v1")
    r = execute_and_optionally_dispatch(
        _cmds(),
        driver=fd,
        dispatch_enabled=True,
        dispatch_start=(0.0, 0.0),
        max_motion_steps_total=25_000,
    )
    assert r.motion_result.done is True
    assert r.dispatch_attempted is True
    assert r.dispatch_succeeded is True
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert len(text) > 20
    assert "generated:" in text.lower() or "move" in text.lower() or "bounds" in text.lower()
    ds = r.driver_status
    assert ds is not None
    assert ds.get("driver_name") == "file"
    assert ds.get("output_path") == str(out)
    assert ds.get("output_mode") == "robot_v1"
    assert ds.get("last_write_succeeded") is True
    assert ds.get("last_command_count") == 3


def test_combined_result_motion_fields_present(tmp_path: Path) -> None:
    out = tmp_path / "c.dsl"
    fd = FileDriver(out, mode="dsl")
    r = execute_and_optionally_dispatch(
        [MoveCommand(0.2, 0.0)],
        driver=fd,
        dispatch_enabled=True,
        max_motion_steps_total=20_000,
    )
    assert hasattr(r, "motion_result")
    assert r.motion_result.commands_executed == 1
    assert r.motion_result.motion_integration_steps >= 0
    assert r.dispatch_succeeded is True
