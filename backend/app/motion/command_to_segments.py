"""
Tek komut ve mevcut pozdan rotate-then-go geometrik hedefleri üretir.

Motor, PID, tekerlek hızı veya zaman entegrasyonu yoktur; çıktı
``(turn_delta_deg, forward_distance_m)`` çiftisidir.
"""

from __future__ import annotations

import math

from app.execution.commands import ForwardCommand, MoveCommand, MoveRelCommand, TurnCommand
from app.motion.motion_state import Pose2D


def wrap_angle_difference_deg(from_deg: float, to_deg: float) -> float:
    """``from_deg`` ile ``to_deg`` arasındaki en kısa dönüş (derece, yaklaşık [-180, 180])."""
    d = (to_deg - from_deg) % 360.0
    if d > 180.0:
        d -= 360.0
    return d


def move_command_to_rotate_then_go(pose: Pose2D, cmd: MoveCommand) -> tuple[float, float]:
    """
    Mutlak hedef: önce ``turn_delta_deg``, sonra ``forward_distance_m``.
    Başlangıç ``pose``; hedef ``(cmd.x, cmd.y)``.
    """
    dx = float(cmd.x) - pose.x
    dy = float(cmd.y) - pose.y
    dist = math.hypot(dx, dy)
    if dist < 1e-12:
        return (0.0, 0.0)
    theta_target_deg = math.degrees(math.atan2(dy, dx))
    turn_delta = wrap_angle_difference_deg(pose.theta_deg, theta_target_deg)
    return (turn_delta, dist)


def move_rel_command_to_rotate_then_go(pose: Pose2D, cmd: MoveRelCommand) -> tuple[float, float]:
    """Göreli ofset dünya ekseninde; hedef ``(pose.x + dx, pose.y + dy)``."""
    dx = float(cmd.dx)
    dy = float(cmd.dy)
    dist = math.hypot(dx, dy)
    if dist < 1e-12:
        return (0.0, 0.0)
    theta_target_deg = math.degrees(math.atan2(dy, dx))
    turn_delta = wrap_angle_difference_deg(pose.theta_deg, theta_target_deg)
    return (turn_delta, dist)


def turn_command_to_rotate_then_go(cmd: TurnCommand) -> tuple[float, float]:
    """Yalnızca dönüş; ileri mesafe sıfır."""
    return (float(cmd.deg), 0.0)


def forward_command_to_rotate_then_go(cmd: ForwardCommand) -> tuple[float, float]:
    """Mevcut başlıkta ileri; dönüş sıfır."""
    return (0.0, float(cmd.dist))
