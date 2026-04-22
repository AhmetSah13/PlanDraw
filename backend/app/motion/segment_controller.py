"""
Rotate-then-go için minimal saf kontrolör iskeleti (donanım yok).

Zaman entegrasyonu, tekerlek kinematiği veya motor sürücü yoktur. Her adımda
mevcut ``Pose2D`` ve segment başlangıcına göre faz (dönüş / ileri / bitti) ve
basit hız komutları üretilir.

Durum modeli (düşük risk):
- Segment başladığında ``segment_start_pose`` sabitlenir (yerel başlangıç).
- Hedef başlık: ``segment_start_pose.theta_deg + segment.turn_delta_deg``.
- Hedef nokta (yerinde dönüş varsayımı): başlangıç (x, y) üzerinden hedef
  başlıkta ``forward_distance_m`` kadar dünya çerçevesinde ileri.
- Tamamlanma: kalan başlık hatası ve kalan mesafe, bu mutlak hedeflere göre
  ölçülür (her adımda pozdan yeniden hesaplanır; entegrasyonla “kalan skalar”
  taşınmaz).

Bu, ``command_to_segments`` ile üretilen ``(turn_delta, distance)`` ile doğrudan
uyumludur ve HTTP/sürücüden bağımsızdır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from app.motion.command_to_segments import wrap_angle_difference_deg
from app.motion.motion_segment import RotateThenGoSegment
from app.motion.motion_state import Pose2D


class SegmentControlPhase(str, Enum):
    """Segment yürütme fazı."""

    ROTATING = "rotating"
    FORWARDING = "forwarding"
    DONE = "done"


@dataclass(frozen=True)
class SegmentControllerConfig:
    """İlk iskelet için minimal eşik ve komut büyüklükleri."""

    heading_tolerance_deg: float = 1.0
    distance_tolerance_m: float = 0.02
    angular_speed_deg_s: float = 30.0
    linear_speed_m_s: float = 0.2
    geometry_epsilon: float = 1e-9


@dataclass(frozen=True)
class SegmentControllerState:
    """Tek segment için faz ve segment başlangıç pozu (sabit)."""

    phase: SegmentControlPhase
    segment_start_pose: Pose2D


@dataclass(frozen=True)
class SegmentControlOutput:
    linear_velocity_m_s: float
    angular_velocity_deg_s: float
    phase: SegmentControlPhase
    done: bool


def initial_segment_controller_state(segment_start_pose: Pose2D) -> SegmentControllerState:
    """Yeni segmente başlarken çağrılır; başlangıç pozu o anda dondurulur."""
    return SegmentControllerState(
        phase=SegmentControlPhase.ROTATING,
        segment_start_pose=segment_start_pose,
    )


def _theta_target_deg(segment_start: Pose2D, segment: RotateThenGoSegment) -> float:
    return float(segment_start.theta_deg) + float(segment.turn_delta_deg)


def _forward_target_xy(
    segment_start: Pose2D, segment: RotateThenGoSegment, theta_target_deg: float
) -> tuple[float, float]:
    r = math.radians(theta_target_deg)
    fx = float(segment.forward_distance_m) * math.cos(r)
    fy = float(segment.forward_distance_m) * math.sin(r)
    return segment_start.x + fx, segment_start.y + fy


def _segment_is_trivial(segment: RotateThenGoSegment, eps: float) -> bool:
    return abs(segment.turn_delta_deg) < eps and abs(segment.forward_distance_m) < eps


def step_segment_controller(
    pose: Pose2D,
    segment: RotateThenGoSegment,
    state: SegmentControllerState,
    config: SegmentControllerConfig,
) -> tuple[SegmentControlOutput, SegmentControllerState]:
    """
    Tek adımlık saf kontrol: mevcut poza göre faz ve hız komutları.

    Zaman adımı veya poz güncellemesi burada yapılmaz; çağıran simülasyon veya
    ileride donanım katmanı pose'u günceller.
    """
    eps = config.geometry_epsilon

    if state.phase == SegmentControlPhase.DONE:
        out = SegmentControlOutput(
            linear_velocity_m_s=0.0,
            angular_velocity_deg_s=0.0,
            phase=SegmentControlPhase.DONE,
            done=True,
        )
        return out, state

    if _segment_is_trivial(segment, eps):
        out = SegmentControlOutput(
            linear_velocity_m_s=0.0,
            angular_velocity_deg_s=0.0,
            phase=SegmentControlPhase.DONE,
            done=True,
        )
        new_state = SegmentControllerState(
            phase=SegmentControlPhase.DONE,
            segment_start_pose=state.segment_start_pose,
        )
        return out, new_state

    theta_t = _theta_target_deg(state.segment_start_pose, segment)
    heading_err = wrap_angle_difference_deg(pose.theta_deg, theta_t)
    tx, ty = _forward_target_xy(state.segment_start_pose, segment, theta_t)
    dist_err = math.hypot(tx - pose.x, ty - pose.y)

    if state.phase == SegmentControlPhase.ROTATING:
        if abs(heading_err) <= config.heading_tolerance_deg:
            if segment.forward_distance_m <= eps:
                out = SegmentControlOutput(
                    linear_velocity_m_s=0.0,
                    angular_velocity_deg_s=0.0,
                    phase=SegmentControlPhase.DONE,
                    done=True,
                )
                new_state = SegmentControllerState(
                    phase=SegmentControlPhase.DONE,
                    segment_start_pose=state.segment_start_pose,
                )
                return out, new_state
            new_state = SegmentControllerState(
                phase=SegmentControlPhase.FORWARDING,
                segment_start_pose=state.segment_start_pose,
            )
            # Aynı pozda bir sonraki faz: ileri komut
            return step_segment_controller(pose, segment, new_state, config)

        w = math.copysign(config.angular_speed_deg_s, heading_err)
        out = SegmentControlOutput(
            linear_velocity_m_s=0.0,
            angular_velocity_deg_s=w,
            phase=SegmentControlPhase.ROTATING,
            done=False,
        )
        return out, state

    # FORWARDING
    if dist_err <= config.distance_tolerance_m:
        out = SegmentControlOutput(
            linear_velocity_m_s=0.0,
            angular_velocity_deg_s=0.0,
            phase=SegmentControlPhase.DONE,
            done=True,
        )
        new_state = SegmentControllerState(
            phase=SegmentControlPhase.DONE,
            segment_start_pose=state.segment_start_pose,
        )
        return out, new_state

    out = SegmentControlOutput(
        linear_velocity_m_s=config.linear_speed_m_s,
        angular_velocity_deg_s=0.0,
        phase=SegmentControlPhase.FORWARDING,
        done=False,
    )
    return out, state

