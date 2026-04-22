"""
Kapalı döngü motion runner: kontrolör çıktısı + basit Euler ile poz güncelleme.

Resmi ``CommandExecutor`` veya sürücülerle bağlantısı yoktur; salt simülasyon
tarzı deterministik adımlar. Tekerlek kinematiği, gürültü ve PID yoktur.

Entegrasyon (dünya çerçevesi, basit Euler):
- ``theta`` güncellemesi: ``theta_deg += angular_velocity_deg_s * dt``
- ``x, y`` güncellemesi: mevcut başlıkta ileri: ``v * cos/sin(theta) * dt``
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence

from app.motion.motion_segment import RotateThenGoSegment
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import (
    SegmentControlOutput,
    SegmentControllerConfig,
    SegmentControllerState,
    initial_segment_controller_state,
    step_segment_controller,
)


@dataclass(frozen=True)
class MotionRunSnapshot:
    """Hata ayıklama için tek adım sonrası durum (entegrasyondan sonra)."""

    step_index: int
    pose: Pose2D
    last_output: SegmentControlOutput


@dataclass(frozen=True)
class MotionRunResult:
    """Runner çıktısı."""

    final_pose: Pose2D
    done: bool
    total_steps: int
    history: tuple[MotionRunSnapshot, ...]


def integrate_pose_euler(
    pose: Pose2D,
    linear_velocity_m_s: float,
    angular_velocity_deg_s: float,
    dt: float,
) -> Pose2D:
    """
    Bir zaman adımı için basit Euler entegrasyonu (deterministik).

    İleri hız, entegrasyon anındaki başlık doğrultusunda uygulanır.
    """
    th = math.radians(pose.theta_deg)
    x = pose.x + float(linear_velocity_m_s) * math.cos(th) * dt
    y = pose.y + float(linear_velocity_m_s) * math.sin(th) * dt
    theta = pose.theta_deg + float(angular_velocity_deg_s) * dt
    return Pose2D(x, y, theta)


def run_rotate_then_go_segments(
    initial_pose: Pose2D,
    segments: Sequence[RotateThenGoSegment],
    *,
    controller_config: SegmentControllerConfig,
    dt: float,
    max_steps: int,
    collect_history: bool = False,
    max_history: int = 10_000,
) -> MotionRunResult:
    """
    Segmentleri sırayla yürütür: kontrolör adımı → (tamamlanmadıysa) entegrasyon.

    Her yeni segment için ``initial_segment_controller_state`` o segmentin
    başladığı andaki poz ile sıfırlanır.

    ``max_steps`` tüm segmentler için toplam adım limitidir; aşılırsa
    ``done=False`` ile durur.
    """
    if dt <= 0.0:
        raise ValueError("dt pozitif olmalıdır")
    if max_steps < 0:
        raise ValueError("max_steps negatif olamaz")

    pose = initial_pose
    total_steps = 0
    history_list: List[MotionRunSnapshot] = []

    for segment in segments:
        ctrl_state: SegmentControllerState = initial_segment_controller_state(pose)

        while True:
            out, ctrl_state = step_segment_controller(
                pose, segment, ctrl_state, controller_config
            )
            if out.done:
                break

            pose = integrate_pose_euler(
                pose,
                out.linear_velocity_m_s,
                out.angular_velocity_deg_s,
                dt,
            )
            total_steps += 1

            if collect_history and len(history_list) < max_history:
                history_list.append(
                    MotionRunSnapshot(
                        step_index=total_steps - 1,
                        pose=pose,
                        last_output=out,
                    )
                )

            if total_steps >= max_steps:
                return MotionRunResult(
                    final_pose=pose,
                    done=False,
                    total_steps=total_steps,
                    history=tuple(history_list),
                )

    return MotionRunResult(
        final_pose=pose,
        done=True,
        total_steps=total_steps,
        history=tuple(history_list),
    )


def run_single_segment(
    initial_pose: Pose2D,
    segment: RotateThenGoSegment,
    *,
    controller_config: SegmentControllerConfig,
    dt: float,
    max_steps: int,
    collect_history: bool = False,
    max_history: int = 10_000,
) -> MotionRunResult:
    """Tek segment için ``run_rotate_then_go_segments`` sarmalayıcısı."""
    return run_rotate_then_go_segments(
        initial_pose,
        (segment,),
        controller_config=controller_config,
        dt=dt,
        max_steps=max_steps,
        collect_history=collect_history,
        max_history=max_history,
    )
