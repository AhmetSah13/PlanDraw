"""
HTTP job / simulate için tek canonical komut hazırlığı.

parse_commands → (isteğe bağlı) optimize_commands → executor / analiz / FileDriver
aynı ``List[Command]`` listesini kullanır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.execution.commands import (
    Command,
    CommandParseError,
    Diagnostic,
    ForwardCommand,
    MoveCommand,
    MoveRelCommand,
    parse_commands,
)
from app.pathing.path_optimizer import OptimizeConfig, optimize_commands


def _move_command_count(commands: List[Command]) -> int:
    return sum(
        1
        for c in commands
        if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
    )


def _find_start_from_commands(commands: List[Command]) -> Optional[Tuple[float, float]]:
    for cmd in commands:
        if isinstance(cmd, MoveCommand):
            return (float(cmd.x), float(cmd.y))
    return None


def apply_optional_optimize_to_commands(
    commands: List[Command],
    *,
    start_pt: Tuple[float, float],
    optimize_cfg: Optional[OptimizeConfig] = None,
) -> Tuple[List[Command], Optional[int], Optional[int], Optional[float]]:
    """
    ``compile_path_to_commands`` veya benzeri kaynaktan gelen listeye tek optimize geçişi.

    DSL parse içermez; analizde ``optimize_cfg=None`` kullanılmalıdır (çift optimize yok).
    """
    st = (float(start_pt[0]), float(start_pt[1]))
    if optimize_cfg is None or not getattr(optimize_cfg, "enabled", False):
        return commands, None, None, None

    original_move_count = _move_command_count(commands)
    optimized_list = optimize_commands(commands, st, optimize_cfg)
    optimized_move_count = _move_command_count(optimized_list)
    reduction_ratio: Optional[float] = None
    if original_move_count > 0:
        reduction_ratio = (1.0 - optimized_move_count / original_move_count) * 100.0
    return optimized_list, original_move_count, optimized_move_count, reduction_ratio


@dataclass(frozen=True)
class JobCommandPrepResult:
    """DSL + optimize sonrası çalıştırma/analiz için tek komut listesi."""

    commands: List[Command]
    parser_diags: List[Diagnostic]
    start_pt: Tuple[float, float]
    original_move_count: Optional[int] = None
    optimized_move_count: Optional[int] = None
    reduction_ratio: Optional[float] = None


def prepare_job_commands(
    text: str,
    *,
    explicit_start: Optional[Tuple[float, float]] = None,
    optimize_cfg: Optional[OptimizeConfig] = None,
) -> JobCommandPrepResult:
    """
    Job ve simulate için ortak hazırlık.

    - ``explicit_start`` verilmezse ilk ``MOVE`` hedefi; yoksa (0, 0).
    - ``optimize_cfg.enabled`` ise ``optimize_commands`` burada uygulanır;
      analiz tarafında ``analyze_commands(..., optimize_cfg=None)`` kullanılmalıdır
      (çift optimize önlenir).
    """
    try:
        commands, parser_diags = parse_commands(text or "", strict=False)
    except CommandParseError as e:
        return JobCommandPrepResult(
            commands=[],
            parser_diags=[e.diagnostic],
            start_pt=(0.0, 0.0),
        )

    start_pt = explicit_start if explicit_start is not None else _find_start_from_commands(commands)
    if start_pt is None:
        start_pt = (0.0, 0.0)

    start_t = (float(start_pt[0]), float(start_pt[1]))
    commands, original_move_count, optimized_move_count, reduction_ratio = apply_optional_optimize_to_commands(
        commands,
        start_pt=start_t,
        optimize_cfg=optimize_cfg,
    )

    return JobCommandPrepResult(
        commands=commands,
        parser_diags=parser_diags,
        start_pt=start_t,
        original_move_count=original_move_count,
        optimized_move_count=optimized_move_count,
        reduction_ratio=reduction_ratio,
    )
