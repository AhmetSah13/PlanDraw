# segment_controller: rotate-then-go iskeleti deterministik testler
from __future__ import annotations

import math
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.motion.motion_segment import RotateThenGoSegment
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import (
    SegmentControlPhase,
    SegmentControllerConfig,
    SegmentControllerState,
    initial_segment_controller_state,
    step_segment_controller,
)


def test_zero_segment_immediate_done() -> None:
    seg = RotateThenGoSegment(0.0, 0.0)
    pose = Pose2D(1.0, 2.0, 30.0)
    st = initial_segment_controller_state(pose)
    cfg = SegmentControllerConfig()
    out, new_st = step_segment_controller(pose, seg, st, cfg)
    assert out.done is True
    assert out.phase == SegmentControlPhase.DONE
    assert math.isclose(out.linear_velocity_m_s, 0.0)
    assert math.isclose(out.angular_velocity_deg_s, 0.0)
    assert new_st.phase == SegmentControlPhase.DONE


def test_turn_only_outputs_angular_first() -> None:
    seg = RotateThenGoSegment(40.0, 0.0)
    start = Pose2D(0.0, 0.0, 0.0)
    st = initial_segment_controller_state(start)
    cfg = SegmentControllerConfig(heading_tolerance_deg=1.0, angular_speed_deg_s=25.0)
    out, _ = step_segment_controller(start, seg, st, cfg)
    assert out.done is False
    assert out.phase == SegmentControlPhase.ROTATING
    assert math.isclose(out.linear_velocity_m_s, 0.0)
    assert out.angular_velocity_deg_s > 0.0
    assert math.isclose(out.angular_velocity_deg_s, 25.0)


def test_turn_only_aligned_then_done() -> None:
    seg = RotateThenGoSegment(40.0, 0.0)
    start = Pose2D(0.0, 0.0, 0.0)
    st = initial_segment_controller_state(start)
    cfg = SegmentControllerConfig(heading_tolerance_deg=1.0)
    pose_ok = Pose2D(0.0, 0.0, 40.0)
    out, new_st = step_segment_controller(pose_ok, seg, st, cfg)
    assert out.done is True
    assert new_st.phase == SegmentControlPhase.DONE
    assert math.isclose(out.angular_velocity_deg_s, 0.0)


def test_forward_only_outputs_linear_when_heading_ok() -> None:
    seg = RotateThenGoSegment(0.0, 3.0)
    start = Pose2D(0.0, 0.0, 0.0)
    st = initial_segment_controller_state(start)
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=1.0,
        distance_tolerance_m=0.05,
        linear_speed_m_s=0.15,
    )
    out, _ = step_segment_controller(start, seg, st, cfg)
    assert out.done is False
    assert out.phase == SegmentControlPhase.FORWARDING
    assert math.isclose(out.linear_velocity_m_s, 0.15)
    assert math.isclose(out.angular_velocity_deg_s, 0.0)


def test_forwarding_within_distance_tolerance_done() -> None:
    seg = RotateThenGoSegment(0.0, 2.0)
    start = Pose2D(0.0, 0.0, 0.0)
    st = SegmentControllerState(
        phase=SegmentControlPhase.FORWARDING,
        segment_start_pose=start,
    )
    cfg = SegmentControllerConfig(distance_tolerance_m=0.05)
    # Hedef (2, 0); tolerans içinde
    pose_near = Pose2D(1.99, 0.0, 0.0)
    out, new_st = step_segment_controller(pose_near, seg, st, cfg)
    assert out.done is True
    assert new_st.phase == SegmentControlPhase.DONE


def test_done_phase_stable() -> None:
    seg = RotateThenGoSegment(0.0, 1.0)
    start = Pose2D(0.0, 0.0, 0.0)
    st_done = SegmentControllerState(phase=SegmentControlPhase.DONE, segment_start_pose=start)
    cfg = SegmentControllerConfig()
    out, st2 = step_segment_controller(Pose2D(5.0, 5.0, 90.0), seg, st_done, cfg)
    assert out.done is True
    assert st2.phase == SegmentControlPhase.DONE
    assert math.isclose(out.linear_velocity_m_s, 0.0)
