# motion katmanı: komut → rotate-then-go segmentleri (deterministik testler)
from __future__ import annotations

import math
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import (
    ForwardCommand,
    MoveCommand,
    MoveRelCommand,
    TurnCommand,
)
from app.motion.command_to_segments import (
    forward_command_to_rotate_then_go,
    move_command_to_rotate_then_go,
    move_rel_command_to_rotate_then_go,
    turn_command_to_rotate_then_go,
    wrap_angle_difference_deg,
)
from app.motion.motion_state import Pose2D


def test_wrap_angle_difference_deg() -> None:
    assert math.isclose(wrap_angle_difference_deg(0.0, 90.0), 90.0)
    assert math.isclose(wrap_angle_difference_deg(350.0, 10.0), 20.0)
    assert math.isclose(wrap_angle_difference_deg(0.0, 180.0), 180.0)
    assert math.isclose(wrap_angle_difference_deg(0.0, -90.0), -90.0)


def test_move_command_from_origin_to_right() -> None:
    pose = Pose2D(0.0, 0.0, 0.0)
    cmd = MoveCommand(x=1.0, y=0.0)
    turn_d, fwd = move_command_to_rotate_then_go(pose, cmd)
    assert math.isclose(turn_d, 0.0, abs_tol=1e-9)
    assert math.isclose(fwd, 1.0, rel_tol=1e-9)


def test_move_rel_up_from_zero_heading() -> None:
    pose = Pose2D(0.0, 0.0, 0.0)
    cmd = MoveRelCommand(dx=0.0, dy=1.0)
    turn_d, fwd = move_rel_command_to_rotate_then_go(pose, cmd)
    assert math.isclose(turn_d, 90.0, abs_tol=1e-9)
    assert math.isclose(fwd, 1.0, rel_tol=1e-9)


def test_turn_command() -> None:
    t, f = turn_command_to_rotate_then_go(TurnCommand(deg=-45.0))
    assert math.isclose(t, -45.0)
    assert math.isclose(f, 0.0)


def test_forward_command() -> None:
    t, f = forward_command_to_rotate_then_go(ForwardCommand(dist=2.5))
    assert math.isclose(t, 0.0)
    assert math.isclose(f, 2.5)


def test_move_zero_distance() -> None:
    pose = Pose2D(1.0, 1.0, 0.0)
    cmd = MoveCommand(x=1.0, y=1.0)
    turn_d, fwd = move_command_to_rotate_then_go(pose, cmd)
    assert math.isclose(turn_d, 0.0)
    assert math.isclose(fwd, 0.0)
