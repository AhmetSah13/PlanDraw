# command_sequence_runner: resmi Command listesi + motion katmanı testleri
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
    PenCommand,
    SpeedCommand,
    TurnCommand,
    WaitCommand,
)
from app.motion.command_sequence_runner import (
    run_command_sequence,
    scaled_segment_controller_config,
)
from app.motion.command_to_segments import wrap_angle_difference_deg
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig


def _base_cfg() -> SegmentControllerConfig:
    return SegmentControllerConfig(
        heading_tolerance_deg=1.5,
        distance_tolerance_m=0.06,
        angular_speed_deg_s=55.0,
        linear_speed_m_s=0.45,
    )


def test_speed_pen_move_updates_pose_and_pen() -> None:
    cmds = [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(1.5, 0.0),
    ]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(0.0, 0.0, 0.0),
        pen_down_initial=False,
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=40_000,
    )
    assert r.done is True
    assert r.stop_reason == "completed"
    assert r.commands_executed == 3
    assert r.pen_down is True
    assert math.isclose(r.current_speed, 1.0)
    assert math.isclose(r.pose.x, 1.5, abs_tol=0.1)
    assert math.isclose(r.pose.y, 0.0, abs_tol=0.08)


def test_turn_forward_near_expected() -> None:
    cmds = [TurnCommand(deg=90.0), ForwardCommand(dist=0.8)]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(0.0, 0.0, 0.0),
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=50_000,
    )
    assert r.done is True
    assert r.commands_executed == 2
    assert math.isclose(r.pose.x, 0.0, abs_tol=0.12)
    assert math.isclose(r.pose.y, 0.8, abs_tol=0.12)
    assert abs(wrap_angle_difference_deg(r.pose.theta_deg, 90.0)) < 2.5


def test_wait_advances_simulated_time_only() -> None:
    cmds = [WaitCommand(seconds=2.5), SpeedCommand(0.5)]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(0.0, 0.0, 0.0),
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=1000,
    )
    assert r.done is True
    assert math.isclose(r.simulated_time_s, 2.5)
    assert r.motion_integration_steps == 0
    assert math.isclose(r.current_speed, 0.5)


def test_mixed_short_program_executed_count_and_history() -> None:
    cmds = [
        SpeedCommand(1.0),
        PenCommand(is_down=False),
        MoveCommand(0.3, 0.0),
        WaitCommand(0.1),
        ForwardCommand(0.2),
    ]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(0.0, 0.0, 0.0),
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=30_000,
        collect_history=True,
    )
    assert r.done is True
    assert r.commands_executed == 5
    assert len(r.history) == 5
    assert r.history[-1].command_index == 4


def test_scaled_config_respects_speed() -> None:
    base = _base_cfg()
    s = scaled_segment_controller_config(base, 2.0)
    assert math.isclose(s.linear_speed_m_s, base.linear_speed_m_s * 2.0)
    assert math.isclose(s.angular_speed_deg_s, base.angular_speed_deg_s * 2.0)


def test_move_rel_sequence() -> None:
    cmds = [MoveRelCommand(0.0, 0.4)]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(1.0, 1.0, 0.0),
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=20_000,
    )
    assert r.done is True
    assert math.isclose(r.pose.x, 1.0, abs_tol=0.1)
    assert math.isclose(r.pose.y, 1.4, abs_tol=0.1)


def test_motion_budget_stops_deterministically() -> None:
    cmds = [MoveCommand(100.0, 0.0)]
    r = run_command_sequence(
        cmds,
        initial_pose=Pose2D(0.0, 0.0, 0.0),
        base_controller_config=_base_cfg(),
        dt=0.05,
        max_motion_steps_total=5,
    )
    assert r.done is False
    assert r.stop_reason == "motion_step_budget_exhausted"
    assert r.failed_command_index == 0
    assert r.commands_executed == 0
