"""
Motion tabanlı komut yürütme için tek üst seviye giriş noktası (facade).

``command_sequence_runner`` düşük seviye yorumlayıcıdır; bu modül dışarıya
stabil bir API sunar. HTTP, dışa aktarma ve sürücü çağrıları yoktur.

İleride bir sürücü veya farklı yürütme hedefi eklenebilir; ``driver_context``
şimdilik yok sayılır (bağlama yok).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from app.execution.commands import Command
from app.motion.command_sequence_runner import (
    CommandSequenceHistoryEntry,
    CommandSequenceResult,
    StopReason,
    run_command_sequence,
)
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig


def default_base_controller_config() -> SegmentControllerConfig:
    """Facade varsayılanı; testlerdeki tipik taban kontrolör ile uyumlu."""
    return SegmentControllerConfig(
        heading_tolerance_deg=1.5,
        distance_tolerance_m=0.06,
        angular_speed_deg_s=55.0,
        linear_speed_m_s=0.45,
    )


@dataclass(frozen=True)
class MotionExecutionResult:
    """
    Motion yürütme özeti (``CommandSequenceResult`` ile aynı bilgi, facade adları).

    Alanlar ``CommandSequenceResult`` ile birebir eşlenir; ``final_pose`` =
    yorumlayıcıdaki ``pose``.
    """

    final_pose: Pose2D
    pen_down: bool
    current_speed: float
    simulated_time_s: float
    commands_executed: int
    motion_integration_steps: int
    done: bool
    stop_reason: StopReason
    failed_command_index: Optional[int]
    history: Tuple[CommandSequenceHistoryEntry, ...]

    @classmethod
    def from_sequence(cls, r: CommandSequenceResult) -> MotionExecutionResult:
        return cls(
            final_pose=r.pose,
            pen_down=r.pen_down,
            current_speed=r.current_speed,
            simulated_time_s=r.simulated_time_s,
            commands_executed=r.commands_executed,
            motion_integration_steps=r.motion_integration_steps,
            done=r.done,
            stop_reason=r.stop_reason,
            failed_command_index=r.failed_command_index,
            history=r.history,
        )

    @property
    def sequence_result(self) -> CommandSequenceResult:
        """Alt seviye sonuç (orijinal alan adları ile)."""
        return CommandSequenceResult(
            pose=self.final_pose,
            pen_down=self.pen_down,
            current_speed=self.current_speed,
            simulated_time_s=self.simulated_time_s,
            commands_executed=self.commands_executed,
            motion_integration_steps=self.motion_integration_steps,
            done=self.done,
            stop_reason=self.stop_reason,
            failed_command_index=self.failed_command_index,
            history=self.history,
        )


def execute_command_sequence_motion(
    commands: Sequence[Command],
    *,
    initial_pose: Optional[Pose2D] = None,
    pen_down_initial: bool = False,
    initial_speed_factor: float = 1.0,
    base_controller_config: Optional[SegmentControllerConfig] = None,
    dt: float = 0.05,
    max_motion_steps_total: int = 100_000,
    collect_history: bool = False,
    driver_context: object | None = None,
) -> MotionExecutionResult:
    """
    Resmi komut listesini motion katmanında yürütür.

    Parametreler:
        commands: Yürütülecek komutlar.
        initial_pose: Başlangıç pozu; ``None`` ise ``(0, 0, 0)``.
        pen_down_initial / initial_speed_factor: Başlangıç durumu.
        base_controller_config: ``None`` ise :func:`default_base_controller_config`.
        dt: Simülasyon zaman adımı.
        max_motion_steps_total: Toplam entegrasyon adım üst sınırı.
        collect_history: Komut sonrası durum geçmişi.
        driver_context: Ayrılmış; bu sürümde kullanılmaz (ileride sürücü köprüsü).

    ``driver_context`` şu an yok sayılır; gerçek donanım veya ``dispatch`` çağrısı yoktur.
    """
    _ = driver_context
    base = base_controller_config or default_base_controller_config()
    pose = initial_pose if initial_pose is not None else Pose2D(0.0, 0.0, 0.0)
    raw = run_command_sequence(
        commands,
        initial_pose=pose,
        pen_down_initial=pen_down_initial,
        initial_speed_factor=initial_speed_factor,
        base_controller_config=base,
        dt=dt,
        max_motion_steps_total=max_motion_steps_total,
        collect_history=collect_history,
    )
    return MotionExecutionResult.from_sequence(raw)
