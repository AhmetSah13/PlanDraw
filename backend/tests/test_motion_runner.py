# motion_runner: kapalı döngü simülasyon testleri
from __future__ import annotations

import math
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.motion.command_to_segments import wrap_angle_difference_deg
from app.motion.motion_runner import (
    integrate_pose_euler,
    run_rotate_then_go_segments,
    run_single_segment,
)
from app.motion.motion_segment import RotateThenGoSegment
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig


def test_integrate_pose_euler_forward() -> None:
    p0 = Pose2D(0.0, 0.0, 0.0)
    p1 = integrate_pose_euler(p0, linear_velocity_m_s=1.0, angular_velocity_deg_s=0.0, dt=0.1)
    assert math.isclose(p1.x, 0.1, rel_tol=0.0, abs_tol=1e-9)
    assert math.isclose(p1.y, 0.0)
    assert math.isclose(p1.theta_deg, 0.0)


def test_integrate_pose_euler_turn() -> None:
    p0 = Pose2D(0.0, 0.0, 0.0)
    p1 = integrate_pose_euler(p0, linear_velocity_m_s=0.0, angular_velocity_deg_s=90.0, dt=1.0)
    assert math.isclose(p1.x, 0.0)
    assert math.isclose(p1.y, 0.0)
    assert math.isclose(p1.theta_deg, 90.0)


def test_zero_segment_completes_immediately() -> None:
    cfg = SegmentControllerConfig()
    r = run_single_segment(
        Pose2D(1.0, 2.0, 3.0),
        RotateThenGoSegment(0.0, 0.0),
        controller_config=cfg,
        dt=0.01,
        max_steps=100,
    )
    assert r.done is True
    assert r.total_steps == 0
    assert math.isclose(r.final_pose.x, 1.0)
    assert math.isclose(r.final_pose.y, 2.0)


def test_pure_forward_reaches_expected_xy() -> None:
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=2.0,
        distance_tolerance_m=0.05,
        angular_speed_deg_s=60.0,
        linear_speed_m_s=0.5,
    )
    r = run_single_segment(
        Pose2D(0.0, 0.0, 0.0),
        RotateThenGoSegment(0.0, 2.0),
        controller_config=cfg,
        dt=0.05,
        max_steps=20_000,
    )
    assert r.done is True
    assert math.isclose(r.final_pose.x, 2.0, abs_tol=0.08)
    assert math.isclose(r.final_pose.y, 0.0, abs_tol=0.08)


def test_pure_turn_reaches_expected_heading() -> None:
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=1.5,
        distance_tolerance_m=0.05,
        angular_speed_deg_s=45.0,
        linear_speed_m_s=0.2,
    )
    r = run_single_segment(
        Pose2D(0.0, 0.0, 0.0),
        RotateThenGoSegment(90.0, 0.0),
        controller_config=cfg,
        dt=0.05,
        max_steps=10_000,
    )
    assert r.done is True
    err = abs(wrap_angle_difference_deg(r.final_pose.theta_deg, 90.0))
    assert err < 2.0


def test_rotate_then_go_near_expected_pose() -> None:
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=1.5,
        distance_tolerance_m=0.06,
        angular_speed_deg_s=50.0,
        linear_speed_m_s=0.4,
    )
    r = run_single_segment(
        Pose2D(0.0, 0.0, 0.0),
        RotateThenGoSegment(90.0, 1.0),
        controller_config=cfg,
        dt=0.05,
        max_steps=30_000,
    )
    assert r.done is True
    assert math.isclose(r.final_pose.x, 0.0, abs_tol=0.1)
    assert math.isclose(r.final_pose.y, 1.0, abs_tol=0.1)
    assert abs(wrap_angle_difference_deg(r.final_pose.theta_deg, 90.0)) < 2.5


def test_two_segments_sequential() -> None:
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=1.5,
        distance_tolerance_m=0.06,
        angular_speed_deg_s=60.0,
        linear_speed_m_s=0.35,
    )
    r = run_rotate_then_go_segments(
        Pose2D(0.0, 0.0, 0.0),
        [RotateThenGoSegment(0.0, 1.0), RotateThenGoSegment(90.0, 0.5)],
        controller_config=cfg,
        dt=0.05,
        max_steps=50_000,
    )
    assert r.done is True
    assert math.isclose(r.final_pose.x, 1.0, abs_tol=0.12)
    assert math.isclose(r.final_pose.y, 0.5, abs_tol=0.12)


def test_history_collected_when_requested() -> None:
    cfg = SegmentControllerConfig(
        heading_tolerance_deg=2.0,
        distance_tolerance_m=0.05,
        angular_speed_deg_s=90.0,
        linear_speed_m_s=0.5,
    )
    r = run_single_segment(
        Pose2D(0.0, 0.0, 0.0),
        RotateThenGoSegment(0.0, 0.5),
        controller_config=cfg,
        dt=0.05,
        max_steps=5000,
        collect_history=True,
    )
    assert r.done is True
    assert len(r.history) > 0
    assert r.history[-1].step_index == r.total_steps - 1
