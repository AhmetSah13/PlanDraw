"""
Motion facade ile mevcut ``dispatch_commands`` sınırı arasında ince köprü.

Önce her zaman ``execute_command_sequence_motion`` çalışır (motion anlamları
değişmez). İsteğe bağlı olarak aynı komut listesi ``dispatch_commands`` ile
sürücüye iletilir.

**Dispatch hataları:** ``dispatch_commands`` içinde oluşan istisnalar yakalanır,
``dispatch_error`` alanına yazılır; **yeniden fırlatılmaz**. Böylece motion
sonucu her zaman döner ve üst katman tek birleşik sonuçla karar verebilir.
Bu, ilk sürüm için açık ve güvenli bir ayrımdır; HTTP veya export yoktur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from app.drivers.base import RobotDriver
from app.execution.commands import Command
from app.execution.driver_dispatch import dispatch_commands
from app.motion.execution_facade import MotionExecutionResult, execute_command_sequence_motion
from app.motion.motion_state import Pose2D
from app.motion.segment_controller import SegmentControllerConfig


@dataclass(frozen=True)
class MotionDispatchBridgeResult:
    """Motion yürütme + isteğe bağlı sürücü iletiminin birleşik özeti."""

    motion_result: MotionExecutionResult
    dispatch_attempted: bool
    dispatch_succeeded: Optional[bool]
    """``True``/``False`` deneme yapıldıysa; ``None`` = iletim denenmedi."""
    driver_status: Optional[dict[str, Any]]
    dispatch_error: Optional[str]


def execute_and_optionally_dispatch(
    commands: Sequence[Command],
    *,
    driver: RobotDriver | None = None,
    dispatch_enabled: bool = False,
    dispatch_start: tuple[float, float] = (0.0, 0.0),
    dispatch_metadata: dict[str, Any] | None = None,
    initial_pose: Optional[Pose2D] = None,
    pen_down_initial: bool = False,
    initial_speed_factor: float = 1.0,
    base_controller_config: Optional[SegmentControllerConfig] = None,
    dt: float = 0.05,
    max_motion_steps_total: int = 100_000,
    collect_history: bool = False,
    driver_context: object | None = None,
) -> MotionDispatchBridgeResult:
    """
    Komut listesini motion katmanında yürütür; istenirse aynı listeyi sürücüye iletir.

    ``dispatch_enabled`` ve ``driver`` birlikte verilmezse iletim **denenmez**
    (``dispatch_attempted=False``). Motion parametreleri
    :func:`execute_command_sequence_motion` ile aynıdır; ``driver_context``
    motion facade için ayrılmıştır (gerçek ``RobotDriver`` ile karıştırılmamalıdır).

    İletim başarılı bittiyse ``driver.get_status()`` güvenli biçimde okunmaya
    çalışılır (okunamazsa ``driver_status`` ``None`` olabilir).
    """
    motion_result = execute_command_sequence_motion(
        commands,
        initial_pose=initial_pose,
        pen_down_initial=pen_down_initial,
        initial_speed_factor=initial_speed_factor,
        base_controller_config=base_controller_config,
        dt=dt,
        max_motion_steps_total=max_motion_steps_total,
        collect_history=collect_history,
        driver_context=driver_context,
    )

    dispatch_attempted = bool(dispatch_enabled and driver is not None)
    if not dispatch_attempted:
        return MotionDispatchBridgeResult(
            motion_result=motion_result,
            dispatch_attempted=False,
            dispatch_succeeded=None,
            driver_status=None,
            dispatch_error=None,
        )

    try:
        dispatch_commands(
            list(commands),
            start=dispatch_start,
            metadata=dispatch_metadata,
            driver=driver,
        )
    except Exception as exc:
        return MotionDispatchBridgeResult(
            motion_result=motion_result,
            dispatch_attempted=True,
            dispatch_succeeded=False,
            driver_status=None,
            dispatch_error=f"{type(exc).__name__}: {exc}",
        )

    driver_status: Optional[dict[str, Any]] = None
    try:
        driver_status = driver.get_status()
    except Exception:
        driver_status = None

    return MotionDispatchBridgeResult(
        motion_result=motion_result,
        dispatch_attempted=True,
        dispatch_succeeded=True,
        driver_status=driver_status,
        dispatch_error=None,
    )
