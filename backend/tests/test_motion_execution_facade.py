# execution_facade: motion tabanlı tek giriş noktası testleri
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
    PenCommand,
    SpeedCommand,
    TurnCommand,
    WaitCommand,
)
from app.motion.execution_facade import (
    MotionExecutionResult,
    default_base_controller_config,
    execute_command_sequence_motion,
)
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig


def test_facade_mixed_program() -> None:
    cmds = [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(0.4, 0.0),
        WaitCommand(0.05),
        ForwardCommand(0.15),
    ]
    r = execute_command_sequence_motion(
        cmds,
        max_motion_steps_total=25_000,
        collect_history=True,
    )
    assert isinstance(r, MotionExecutionResult)
    assert r.done is True
    assert r.stop_reason == "completed"
    assert r.commands_executed == 5
    assert r.pen_down is True
    assert math.isclose(r.current_speed, 1.0)
    assert math.isclose(r.simulated_time_s, 0.05)
    assert len(r.history) == 5
    assert math.isclose(r.final_pose.x, 0.55, abs_tol=0.15)


def test_facade_preserves_pen_and_speed_semantics() -> None:
    cmds = [SpeedCommand(0.25), PenCommand(is_down=False), PenCommand(is_down=True)]
    r = execute_command_sequence_motion(cmds)
    assert r.done is True
    assert r.pen_down is True
    assert math.isclose(r.current_speed, 0.25)


def test_facade_surfaces_stop_reason_budget() -> None:
    cmds = [MoveCommand(50.0, 0.0)]
    r = execute_command_sequence_motion(cmds, max_motion_steps_total=8)
    assert r.done is False
    assert r.stop_reason == "motion_step_budget_exhausted"
    assert r.failed_command_index == 0


def test_facade_custom_pose_and_config() -> None:
    custom = SegmentControllerConfig(
        heading_tolerance_deg=2.0,
        distance_tolerance_m=0.08,
        angular_speed_deg_s=40.0,
        linear_speed_m_s=0.3,
    )
    r = execute_command_sequence_motion(
        [ForwardCommand(0.2)],
        initial_pose=Pose2D(1.0, -1.0, 90.0),
        base_controller_config=custom,
        max_motion_steps_total=15_000,
    )
    assert r.done is True
    assert math.isclose(r.final_pose.x, 1.0, abs_tol=0.12)
    assert math.isclose(r.final_pose.y, -0.8, abs_tol=0.12)


def test_facade_sequence_result_roundtrip() -> None:
    r = execute_command_sequence_motion([WaitCommand(1.0)])
    back = r.sequence_result
    assert back.pose == r.final_pose
    assert back.commands_executed == 1


def test_default_config_matches_helper() -> None:
    assert isinstance(default_base_controller_config(), SegmentControllerConfig)


def test_driver_context_ignored() -> None:
    r = execute_command_sequence_motion([WaitCommand(0.01)], driver_context={"future": True})
    assert r.done is True
