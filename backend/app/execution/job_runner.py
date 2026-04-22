from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.drivers.base import RobotDriver
from app.execution.commands import Command, serialize_commands
from app.execution.job_model import ExecutionContext, ExecutionJobOptions, ExecutionResult


def _default_artifact_dir(opts: ExecutionJobOptions) -> Path:
    if opts.artifact_dir:
        return Path(opts.artifact_dir)
    return Path.cwd() / "reports" / "execution_job"


def _write_artifacts(
    commands: list[Command],
    *,
    out_dir: Path,
    basename: str,
    ctx: ExecutionContext,
    opts: ExecutionJobOptions,
    driver_kind: str | None,
) -> tuple[str, ...]:
    out_dir.mkdir(parents=True, exist_ok=True)
    dsl_path = out_dir / f"{basename}_commands.dsl.txt"
    summary_path = out_dir / f"{basename}_summary.json"

    dsl_path.write_text(serialize_commands(commands), encoding="utf-8")

    summary: dict[str, Any] = {
        "command_count": len(commands),
        "alignment_blocked": ctx.alignment_blocked,
        "allow_execution_when_alignment_blocked": opts.allow_execution_when_alignment_blocked,
        "dry_run": opts.dry_run,
        "start_xy": list(opts.start_xy),
        "stroke_count": ctx.stroke_count,
        "total_draw_m": ctx.total_draw_m,
        "total_travel_m": ctx.total_travel_m,
        "driver_kind": driver_kind,
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return (str(dsl_path), str(summary_path))


def run_command_execution_job(
    commands: list[Command],
    *,
    driver: RobotDriver | None,
    options: ExecutionJobOptions | None = None,
    context: ExecutionContext | None = None,
) -> ExecutionResult:
    """
    List[Command] -> (gate) -> dry-run artifact ve/veya RobotDriver.send_commands.

    - alignment_blocked=True ve allow_execution_when_alignment_blocked=False ise
      gerçek driver gönderimi yapılmaz (dry_run ise sadece artifact yazılır).
    - Boş liste: skipped; driver çağrılmaz.
    - dry_run: driver'a göndermeden DSL + özet JSON yazar.
    """
    opts = options or ExecutionJobOptions()
    ctx = context or ExecutionContext()
    n = len(commands)

    base_notes: list[str] = []

    if n == 0:
        return ExecutionResult(
            status="skipped",
            message="Komut listesi boş; gönderim yapılmadı.",
            notes=("Gate: boş command listesi.",),
            command_count=0,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            alignment_blocked=ctx.alignment_blocked,
            execution_allowed=False,
        )

    blocked = ctx.alignment_blocked is True
    real_send_blocked = blocked and not opts.allow_execution_when_alignment_blocked

    if real_send_blocked and not opts.dry_run:
        return ExecutionResult(
            status="blocked",
            message="Hizalama blocked=True; gerçek execution varsayılan olarak başlatılmadı.",
            notes=(
                "Gate: alignment_blocked ve allow_execution_when_alignment_blocked=False.",
                "İnceleme için --dry-run veya allow_execution_when_alignment_blocked kullanın.",
            ),
            command_count=n,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            alignment_blocked=True,
            execution_allowed=False,
        )

    out_dir = _default_artifact_dir(opts)
    paths: tuple[str, ...] = ()

    if opts.dry_run:
        paths = _write_artifacts(
            commands,
            out_dir=out_dir,
            basename=opts.artifact_basename,
            ctx=ctx,
            opts=opts,
            driver_kind="dry_run",
        )
        base_notes.append(f"Dry-run artifact: {paths[0]}, {paths[1]}")
        if real_send_blocked:
            base_notes.append("Not: alignment blocked; yalnızca artifact üretildi, driver yok.")
        return ExecutionResult(
            status="dry_run",
            message="Dry-run: komutlar dosyaya yazıldı; driver çağrılmadı.",
            notes=tuple(base_notes),
            command_count=n,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            driver_kind="dry_run",
            alignment_blocked=ctx.alignment_blocked,
            execution_allowed=not real_send_blocked,
            artifact_paths=paths,
        )

    if driver is None:
        return ExecutionResult(
            status="failed",
            message="Driver verilmedi; gerçek gönderim için RobotDriver gerekli.",
            notes=("dry_run=False iken driver=None.",),
            command_count=n,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            alignment_blocked=ctx.alignment_blocked,
            execution_allowed=True,
        )

    meta: dict[str, Any] = {
        "alignment_blocked": ctx.alignment_blocked,
        "stroke_count": ctx.stroke_count,
        "total_draw_m": ctx.total_draw_m,
        "total_travel_m": ctx.total_travel_m,
    }

    try:
        driver.connect()
        driver.send_commands(commands, start=opts.start_xy, metadata=meta)
        st = driver.get_status()
        kind = str(st.get("driver_name", "unknown"))
        paths = _write_artifacts(
            commands,
            out_dir=out_dir,
            basename=opts.artifact_basename,
            ctx=ctx,
            opts=opts,
            driver_kind=kind,
        )
        base_notes.append(f"Yedek artifact: {paths[0]}, {paths[1]}")
        return ExecutionResult(
            status="sent",
            message="Komutlar driver üzerinden gönderildi.",
            notes=tuple(base_notes),
            command_count=n,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            driver_kind=kind,
            alignment_blocked=ctx.alignment_blocked,
            execution_allowed=True,
            artifact_paths=paths,
            driver_status=st,
        )
    except Exception as exc:
        return ExecutionResult(
            status="failed",
            message=f"Driver hatası: {exc!s}",
            notes=tuple(base_notes),
            command_count=n,
            stroke_count=ctx.stroke_count,
            total_draw_m=ctx.total_draw_m,
            total_travel_m=ctx.total_travel_m,
            alignment_blocked=ctx.alignment_blocked,
            execution_allowed=True,
            error_detail=str(exc),
        )
    finally:
        try:
            driver.disconnect()
        except Exception:
            pass
