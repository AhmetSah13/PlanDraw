# test_driver_dispatch.py — driver_dispatch birim testleri
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.null_driver import NullDriver
from app.execution.commands import MoveCommand, SpeedCommand
from app.execution.driver_dispatch import dispatch_commands


def test_dispatch_no_driver_no_op() -> None:
    dispatch_commands([], driver=None)
    dispatch_commands([MoveCommand(x=1.0, y=2.0)], driver=None, start=(0.0, 0.0))


def test_dispatch_null_driver_stores_commands() -> None:
    d = NullDriver()
    cmds = [SpeedCommand(speed=50.0), MoveCommand(x=0.0, y=1.0)]
    dispatch_commands(cmds, driver=d, start=(0.1, 0.2), metadata={"k": "v"})
    st = d.get_status()
    assert st["last_command_count"] == 2
    assert st["connected"] is False
    assert d.last_metadata == {"k": "v"}


def test_dispatch_mock_driver_lifecycle() -> None:
    m = MagicMock()
    cmds = [MoveCommand(x=0.0, y=0.0)]
    dispatch_commands(cmds, driver=m, start=(3.0, 4.0), metadata={"a": 1})

    m.connect.assert_called_once()
    m.send_commands.assert_called_once()
    call_kw = m.send_commands.call_args
    assert call_kw[0][0] == cmds
    assert call_kw[1]["start"] == (3.0, 4.0)
    assert call_kw[1]["metadata"] == {"a": 1}
    m.disconnect.assert_called_once()


def test_dispatch_send_failure_disconnect_still_called() -> None:
    m = MagicMock()

    def _boom(*_a, **_k):
        raise RuntimeError("send failed")

    m.send_commands.side_effect = _boom

    with pytest.raises(RuntimeError, match="send failed"):
        dispatch_commands([MoveCommand(x=0.0, y=0.0)], driver=m)

    m.connect.assert_called_once()
    m.send_commands.assert_called_once()
    m.disconnect.assert_called_once()
