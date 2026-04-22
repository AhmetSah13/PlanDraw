"""
Resmi ``List[Command]`` yorumlayıcısı: motion haritalama + runner ile sıralı yürütme.

Mevcut ``CommandExecutor`` ile aynı değildir; HTTP, sürücü ve dışa aktarma
yoktur. Salt deterministik simülasyon durumu üretir.

``SpeedCommand.speed`` pozitif bir **ölçek çarpanı** olarak ele alınır (taban
``SegmentControllerConfig`` hızları ile çarpılır). Başlangıç çarpanı 1.0’dır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple, Union

from app.execution.commands import (
    Command,
    ForwardCommand,
    MoveCommand,
    MoveRelCommand,
    PenCommand,
    SpeedCommand,
    TurnCommand,
    WaitCommand,
)
from app.motion.command_to_segments import (
    forward_command_to_rotate_then_go,
    move_command_to_rotate_then_go,
    move_rel_command_to_rotate_then_go,
    turn_command_to_rotate_then_go,
)
from app.motion.motion_runner import run_single_segment
from app.motion.motion_segment import RotateThenGoSegment
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig

StopReason = Literal["completed", "motion_step_budget_exhausted", "unknown_command"]


def scaled_segment_controller_config(
    base: SegmentControllerConfig, speed_factor: float
) -> SegmentControllerConfig:
    """``SpeedCommand`` çarpanı: doğrusal ve açısal komut büyüklüklerini ölçekler."""
    s = max(float(speed_factor), 1e-9)
    return SegmentControllerConfig(
        heading_tolerance_deg=base.heading_tolerance_deg,
        distance_tolerance_m=base.distance_tolerance_m,
        angular_speed_deg_s=base.angular_speed_deg_s * s,
        linear_speed_m_s=base.linear_speed_m_s * s,
        geometry_epsilon=base.geometry_epsilon,
    )


def command_to_rotate_then_go_segment(
    pose: Pose2D, cmd: Union[MoveCommand, MoveRelCommand, TurnCommand, ForwardCommand]
) -> RotateThenGoSegment:
    """Hareket komutunu mevcut pozdan ``RotateThenGoSegment``e çevirir."""
    if isinstance(cmd, MoveCommand):
        t, d = move_command_to_rotate_then_go(pose, cmd)
    elif isinstance(cmd, MoveRelCommand):
        t, d = move_rel_command_to_rotate_then_go(pose, cmd)
    elif isinstance(cmd, TurnCommand):
        t, d = turn_command_to_rotate_then_go(cmd)
    elif isinstance(cmd, ForwardCommand):
        t, d = forward_command_to_rotate_then_go(cmd)
    else:
        raise TypeError("Beklenen hareket komutu değil")
    return RotateThenGoSegment(turn_delta_deg=t, forward_distance_m=d)


@dataclass(frozen=True)
class CommandSequenceHistoryEntry:
    """Komut sonrası anlık durum (isteğe bağlı hata ayıklama)."""

    command_index: int
    pose: Pose2D
    pen_down: bool
    current_speed: float
    simulated_time_s: float


@dataclass(frozen=True)
class CommandSequenceResult:
    """Yürütme özeti."""

    pose: Pose2D
    pen_down: bool
    current_speed: float
    simulated_time_s: float
    commands_executed: int
    motion_integration_steps: int
    done: bool
    stop_reason: StopReason
    failed_command_index: Optional[int]
    history: Tuple[CommandSequenceHistoryEntry, ...]


def run_command_sequence(
    commands: Sequence[Command],
    *,
    initial_pose: Pose2D,
    pen_down_initial: bool = False,
    initial_speed_factor: float = 1.0,
    base_controller_config: SegmentControllerConfig,
    dt: float,
    max_motion_steps_total: int,
    collect_history: bool = False,
) -> CommandSequenceResult:
    """
    Komutları sırayla uygular.

    - Hareket: ``command_to_rotate_then_go_segment`` + ``run_single_segment``
    - ``WaitCommand``: ``simulated_time_s`` += ``max(0, seconds)`` (iş parçacığı yok)
    - ``SpeedCommand``: ``current_speed`` güncellenir (pozitif alt sınır)
    - ``PenCommand``: yalnızca kalem durumu

    ``max_motion_steps_total`` tüm hareket komutları için paylaşılan entegrasyon
    adım bütçesidir.
    """
    if dt <= 0.0:
        raise ValueError("dt pozitif olmalıdır")
    if max_motion_steps_total < 0:
        raise ValueError("max_motion_steps_total negatif olamaz")

    pose = initial_pose
    pen_down = pen_down_initial
    current_speed = max(float(initial_speed_factor), 1e-9)
    simulated_time_s = 0.0
    motion_steps = 0
    history_list: List[CommandSequenceHistoryEntry] = []

    for idx, cmd in enumerate(commands):
        if isinstance(cmd, SpeedCommand):
            current_speed = max(float(cmd.speed), 1e-9)
        elif isinstance(cmd, PenCommand):
            pen_down = bool(cmd.is_down)
        elif isinstance(cmd, WaitCommand):
            simulated_time_s += max(0.0, float(cmd.seconds))
        elif isinstance(
            cmd,
            (MoveCommand, MoveRelCommand, TurnCommand, ForwardCommand),
        ):
            segment = command_to_rotate_then_go_segment(pose, cmd)
            cfg = scaled_segment_controller_config(base_controller_config, current_speed)
            remaining = max_motion_steps_total - motion_steps
            if remaining <= 0:
                return CommandSequenceResult(
                    pose=pose,
                    pen_down=pen_down,
                    current_speed=current_speed,
                    simulated_time_s=simulated_time_s,
                    commands_executed=idx,
                    motion_integration_steps=motion_steps,
                    done=False,
                    stop_reason="motion_step_budget_exhausted",
                    failed_command_index=idx,
                    history=tuple(history_list),
                )
            mr = run_single_segment(
                pose,
                segment,
                controller_config=cfg,
                dt=dt,
                max_steps=remaining,
            )
            motion_steps += mr.total_steps
            pose = mr.final_pose
            if not mr.done:
                return CommandSequenceResult(
                    pose=pose,
                    pen_down=pen_down,
                    current_speed=current_speed,
                    simulated_time_s=simulated_time_s,
                    commands_executed=idx,
                    motion_integration_steps=motion_steps,
                    done=False,
                    stop_reason="motion_step_budget_exhausted",
                    failed_command_index=idx,
                    history=tuple(history_list),
                )
        else:
            return CommandSequenceResult(
                pose=pose,
                pen_down=pen_down,
                current_speed=current_speed,
                simulated_time_s=simulated_time_s,
                commands_executed=idx,
                motion_integration_steps=motion_steps,
                done=False,
                stop_reason="unknown_command",
                failed_command_index=idx,
                history=tuple(history_list),
            )

        if collect_history:
            history_list.append(
                CommandSequenceHistoryEntry(
                    command_index=idx,
                    pose=pose,
                    pen_down=pen_down,
                    current_speed=current_speed,
                    simulated_time_s=simulated_time_s,
                )
            )

    n = len(commands)
    return CommandSequenceResult(
        pose=pose,
        pen_down=pen_down,
        current_speed=current_speed,
        simulated_time_s=simulated_time_s,
        commands_executed=n,
        motion_integration_steps=motion_steps,
        done=True,
        stop_reason="completed",
        failed_command_index=None,
        history=tuple(history_list),
    )
