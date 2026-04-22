from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ExecutionStatus = Literal["blocked", "skipped", "dry_run", "sent", "failed"]


@dataclass(frozen=True)
class ExecutionContext:
    """Opsiyonel gate ve özet için (alignment / path plan metrikleri)."""

    alignment_blocked: bool | None = None
    stroke_count: int | None = None
    total_draw_m: float | None = None
    total_travel_m: float | None = None


@dataclass(frozen=True)
class ExecutionJobOptions:
    """İlk entegrasyon: dry-run ve alignment gate."""

    dry_run: bool = False
    allow_execution_when_alignment_blocked: bool = False
    start_xy: tuple[float, float] = (0.0, 0.0)
    # dry_run veya artifact yedekleme için çıktı klasörü (yoksa cwd altı kullanılmaz)
    artifact_dir: str | None = None
    artifact_basename: str = "execution_job"


@dataclass
class ExecutionResult:
    status: ExecutionStatus
    message: str
    notes: tuple[str, ...] = ()
    command_count: int = 0
    stroke_count: int | None = None
    total_draw_m: float | None = None
    total_travel_m: float | None = None
    driver_kind: str | None = None
    alignment_blocked: bool | None = None
    execution_allowed: bool = False
    artifact_paths: tuple[str, ...] = ()
    driver_status: dict[str, Any] | None = None
    error_detail: str | None = None
