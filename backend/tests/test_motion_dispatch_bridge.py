# motion_dispatch_bridge: motion + isteğe bağlı dispatch köprü testleri
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import ForwardCommand, MoveCommand, PenCommand, SpeedCommand
from app.execution.commands import Command
from app.motion.motion_dispatch_bridge import (
    MotionDispatchBridgeResult,
    execute_and_optionally_dispatch,
)
from app.drivers.null_driver import NullDriver


class _FailingDriver:
    """Test için protokole uygun; connect'te hata."""

    def connect(self) -> None:
        raise RuntimeError("baglanti_yok")

    def disconnect(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def get_status(self) -> dict[str, Any]:
        return {"driver_name": "failing"}

    def send_commands(
        self,
        commands: list[Command],
        *,
        start: tuple[float, float] = (0.0, 0.0),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass


def test_no_dispatch_when_disabled() -> None:
    cmds = [SpeedCommand(1.0), MoveCommand(0.2, 0.0)]
    r = execute_and_optionally_dispatch(cmds, dispatch_enabled=False)
    assert isinstance(r, MotionDispatchBridgeResult)
    assert r.motion_result.done is True
    assert r.dispatch_attempted is False
    assert r.dispatch_succeeded is None
    assert r.dispatch_error is None


def test_motion_runs_driver_provided_dispatch_off() -> None:
    d = NullDriver()
    cmds = [ForwardCommand(0.1)]
    r = execute_and_optionally_dispatch(cmds, driver=d, dispatch_enabled=False)
    assert r.motion_result.done is True
    assert r.dispatch_attempted is False
    assert len(d.last_commands) == 0


def test_null_driver_dispatch_enabled() -> None:
    d = NullDriver()
    cmds = [PenCommand(is_down=True), ForwardCommand(0.05)]
    r = execute_and_optionally_dispatch(
        cmds,
        driver=d,
        dispatch_enabled=True,
        max_motion_steps_total=15_000,
    )
    assert r.motion_result.done is True
    assert r.dispatch_attempted is True
    assert r.dispatch_succeeded is True
    assert r.dispatch_error is None
    assert r.driver_status is not None
    assert r.driver_status.get("driver_name") == "null"
    assert len(d.last_commands) == 2


def test_dispatch_enabled_without_driver_skips() -> None:
    r = execute_and_optionally_dispatch([MoveCommand(0.1, 0.0)], dispatch_enabled=True, driver=None)
    assert r.dispatch_attempted is False
    assert r.dispatch_succeeded is None


def test_failing_driver_captures_error_motion_unchanged() -> None:
    cmds = [MoveCommand(0.15, 0.0)]
    r = execute_and_optionally_dispatch(
        cmds,
        driver=_FailingDriver(),
        dispatch_enabled=True,
        max_motion_steps_total=20_000,
    )
    assert r.motion_result.done is True
    assert r.dispatch_attempted is True
    assert r.dispatch_succeeded is False
    assert r.dispatch_error is not None
    assert "RuntimeError" in (r.dispatch_error or "")
    assert math.isclose(r.motion_result.final_pose.x, 0.15, abs_tol=0.12)
