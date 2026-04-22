# FileDriver: dosyaya yazma ve durum testleri (HTTP yok)
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

from pathlib import Path as PathType

_root = PathType(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.file_driver import FileDriver
from app.execution.commands import MoveCommand, PenCommand, SpeedCommand
from app.execution.commands import serialize_commands


def test_writes_nonempty_dsl_file(tmp_path: PathType) -> None:
    out = tmp_path / "out.dsl.txt"
    cmds = [SpeedCommand(1.0), PenCommand(is_down=True), MoveCommand(1.0, 2.0)]
    d = FileDriver(out, mode="dsl")
    d.connect()
    d.send_commands(cmds, start=(0.0, 0.0))
    d.disconnect()
    assert out.is_file()
    body = out.read_text(encoding="utf-8")
    assert body == serialize_commands(cmds)
    assert len(body) > 0
    st = d.get_status()
    assert st["driver_name"] == "file"
    assert st["last_write_succeeded"] is True
    assert st["last_command_count"] == 3
    assert st["output_path"] == str(out)
    assert st["output_mode"] == "dsl"
    assert st["last_error"] is None


def test_status_reflects_successful_write(tmp_path: PathType) -> None:
    out = tmp_path / "a.txt"
    d = FileDriver(out)
    assert d.get_status()["last_write_succeeded"] is False
    d.connect()
    assert d.get_status()["connected"] is True
    d.send_commands([MoveCommand(0.0, 0.0)])
    assert d.get_status()["last_write_succeeded"] is True
    d.disconnect()
    assert d.get_status()["connected"] is False


def test_robot_v1_mode_uses_export_helper(tmp_path: PathType) -> None:
    out = tmp_path / "rob.txt"
    d = FileDriver(out, mode="robot_v1")
    d.connect()
    d.send_commands([MoveCommand(3.0, 4.0)], start=(0.0, 0.0))
    text = out.read_text(encoding="utf-8")
    assert "generated:" in text
    assert "MOVE" in text or "G1" in text or len(text) > 50
    assert d.get_status()["output_mode"] == "robot_v1"
    assert d.get_status()["last_write_succeeded"] is True


def test_write_failure_sets_status_without_raising(tmp_path: PathType) -> None:
    out = tmp_path / "out.txt"
    d = FileDriver(out)
    d.connect()
    with mock.patch.object(PathType, "write_text", side_effect=OSError("simüle_disk")):
        d.send_commands([MoveCommand(1.0, 0.0)])
    st = d.get_status()
    assert st["last_write_succeeded"] is False
    assert st["last_error"] is not None
    assert "simüle" in st["last_error"] or "sim" in (st["last_error"] or "").lower()
