from __future__ import annotations

import asyncio
import hashlib
import functools
import json
import math
import random
import secrets
import os
import sys
import threading
import time
import uuid
from pathlib import Path

# backend/ klasörünü path'e ekle (app paketi için)
_root = Path(__file__).resolve().parents[2]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import Any, List, Optional, Tuple

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import ValidationError

from app.execution.commands import (
    Command,
    CommandParseError,
    Diagnostic,
    MoveCommand,
    parse_commands,
    serialize_commands,
)
from app.analysis.scenario_analysis import analyze_commands, export_commands_to_string, ScenarioLimits
from app.analysis.geometry_graph import enrich_plan_with_graph_metrics
from app.execution.executor import CommandExecutor
from app.core.plan_module import load_plan_from_string
from app.pathing.path_generator import PathGenerator
from app.execution.compiler import compile_segments_pen_safe
from app.execution.pen_safe_validator import PenSafeValidationError, validate_pen_safe_commands
from app.pathing.path_optimizer import OptimizeConfig

from app.normalization.normalized_plan import import_plan_from_json
from app.normalization.plan_normalizer import NormalizeOptions, normalize_plan
from app.importers.plan_importer import normalized_to_plan, normalized_to_plan_text, normalized_to_walls_array
from app.importers.dxf_importer import (
    dxf_bytes_to_normalized_plan,
    dxf_to_normalized_plan,
    inspect_dxf_layers,
    inspect_dxf_layers_bytes,
    analyze_dxf_structure,
    select_plan_layers,
)
from app.importers.dwg_converter import (
    convert_dwg_bytes_to_dxf_bytes,
    convert_dwg_bytes_to_dxf_text,
    DwgConversionError,
)

from app.utils.motion_model import MotionConfig, MotionState, apply_motion
from app.api.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DiagnosticOut,
    DxfInsightReport,
    StatsOut,
    SimulateRequest,
    JobFileArtifactRequest,
    CompilePlanRequest,
    OptimizeConfigOut,
    MotionConfigOut,
    ExecuteSerialRequest,
    ExecuteSerialResponse,
    ExportRequest,
    ExportResponse,
    CollisionOut,
    ImportPlanResponse,
    ImportDxfResponse,
    ImportDxfOptions,
    NormalizedPlanIn,
    LayerStats,
    AlignRigid2dRequest,
)


from app.utils.step_size_utils import preview_recommended_step_size as _preview_recommended_step_size

from app.alignment.aligner import align_printable_layout_rigid_2d
from app.alignment.alignment_model import ControlPoint, alignment_report_to_jsonable
from app.alignment.walls_to_layout import walls_list_to_printable_layout
from app.preview.preview_svg import render_post_alignment_svg, render_pre_alignment_svg
from app.drivers.file_driver import FileDriver
from app.execution.driver_dispatch import dispatch_commands
from app.execution.job_model import ExecutionContext, ExecutionJobOptions, ExecutionResult
from app.execution.job_runner import run_command_execution_job
from app.api.job_command_prep import apply_optional_optimize_to_commands, prepare_job_commands

app = FastAPI(title="PlanDraw Web Backend", version="0.1.0")

jobs: dict = {}  # job_id -> {"task": asyncio.Task, "queue": asyncio.Queue}

# Upload güvenliği: maksimum dosya boyutu (bytes). Varsayılan 20 MB.
# Not: Bu bir “ürün güvenliği” değil, demo/DoS koruması için basit bir guard.
MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", "20000000"))

# Job FileDriver çıktıları (POST /api/jobs, file_artifact.enabled). Varsayılan: backend/out/job_artifacts/
JOB_FILE_ARTIFACT_ROOT_ENV = "JOB_FILE_ARTIFACT_ROOT"


def _job_file_artifact_root() -> Path:
    raw = os.getenv(JOB_FILE_ARTIFACT_ROOT_ENV)
    if raw:
        return Path(raw).expanduser().resolve()
    return (_root / "out" / "job_artifacts").resolve()


def _write_job_file_artifact_sync(
    commands: List[Command],
    start_pt: Tuple[float, float],
    job_id: str,
    mode: str,
    artifact_root: Path,
) -> dict:
    """FileDriver + dispatch_commands; bloklayıcı I/O — run_in_executor içinde çağrılmalı."""
    artifact_root.mkdir(parents=True, exist_ok=True)
    suffix = ".dsl.txt" if mode == "dsl" else ".robot_v1.txt"
    out_path = (artifact_root / f"{job_id}{suffix}").resolve()
    driver = FileDriver(out_path, mode=mode)
    dispatch_commands(commands, start=start_pt, driver=driver, metadata={"job_id": job_id})
    st = driver.get_status()
    return {
        "path": str(out_path),
        "mode": mode,
        "last_write_succeeded": bool(st.get("last_write_succeeded")),
        "last_error": st.get("last_error"),
        "last_command_count": st.get("last_command_count"),
    }


# POST /api/execute_serial: gerçek UART için SERIAL_PORT / SERIAL_BAUD (yalnızca env).
EXECUTE_SERIAL_ARTIFACT_DIR_ENV = "EXECUTE_SERIAL_ARTIFACT_DIR"
EXECUTE_SERIAL_ALLOW_REMOTE_ENV = "EXECUTE_SERIAL_ALLOW_REMOTE"
EXECUTE_SERIAL_ADMIN_TOKEN_ENV = "EXECUTE_SERIAL_ADMIN_TOKEN"
EXECUTE_SERIAL_TOKEN_HEADER = "x-execute-token"


def _execute_serial_artifact_dir() -> Optional[str]:
    raw = os.getenv(EXECUTE_SERIAL_ARTIFACT_DIR_ENV)
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip()


def _execute_serial_allow_remote_from_env() -> bool:
    """True ise istemci IP kısıtı uygulanmaz (ters proxy / uzak erişim senaryosu)."""
    v = os.getenv(EXECUTE_SERIAL_ALLOW_REMOTE_ENV, "false").strip().lower()
    return v in ("1", "true", "yes", "on")


def _execute_serial_admin_token_expected() -> Optional[str]:
    """Tanımlı ve boş değilse tüm isteklerde X-Execute-Token zorunlu."""
    raw = os.getenv(EXECUTE_SERIAL_ADMIN_TOKEN_ENV)
    if raw is None:
        return None
    s = str(raw).strip()
    return s if s else None


def _execute_serial_peer_host(request: Request) -> str:
    if request.client is None:
        return ""
    return (request.client.host or "").strip().lower()


def _execute_serial_is_trusted_local_host(host: str) -> bool:
    """Loopback + Starlette TestClient varsayılanı ``testclient``."""
    h = (host or "").strip().lower()
    if h in ("127.0.0.1", "localhost", "::1", "testclient"):
        return True
    if h.startswith("::ffff:127.0.0.1"):
        return True
    return False


def _execute_serial_host_check_passes(request: Request) -> bool:
    if _execute_serial_allow_remote_from_env():
        return True
    return _execute_serial_is_trusted_local_host(_execute_serial_peer_host(request))


def _execute_serial_token_check_passes(request: Request) -> bool:
    expected = _execute_serial_admin_token_expected()
    if expected is None:
        return True
    got = request.headers.get("X-Execute-Token") or request.headers.get(EXECUTE_SERIAL_TOKEN_HEADER)
    if got is None:
        return False
    try:
        return secrets.compare_digest(got.encode("utf-8"), expected.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _execute_serial_access_guard(request: Request) -> Optional[JSONResponse]:
    """
    1) Loopback / allow_remote
    2) Opsiyonel admin token

    Başarısızda 403 ve ``ExecuteSerialResponse`` gövdesi (command_count=0).
    """
    if not _execute_serial_host_check_passes(request):
        body = ExecuteSerialResponse(
            status="failed",
            message="Bu uç yalnızca yerel (loopback) isteklere açıktır; EXECUTE_SERIAL_ALLOW_REMOTE ile genişletilebilir.",
            command_count=0,
            error_detail="EXECUTE_SERIAL_LOCALHOST_ONLY",
        )
        return JSONResponse(status_code=403, content=body.model_dump())
    if not _execute_serial_token_check_passes(request):
        body = ExecuteSerialResponse(
            status="failed",
            message="Geçerli X-Execute-Token başlığı gerekli (EXECUTE_SERIAL_ADMIN_TOKEN).",
            command_count=0,
            error_detail="EXECUTE_SERIAL_INVALID_TOKEN",
        )
        return JSONResponse(status_code=403, content=body.model_dump())
    return None


# dry_run=False: aynı anda tek canlı gönderim (UART çakışmasını önler).
_execute_serial_live_lock = threading.Lock()
_execute_serial_active_driver_lock = threading.Lock()
_execute_serial_active_driver: Any | None = None


def _set_execute_serial_active_driver(driver: Any | None) -> None:
    global _execute_serial_active_driver
    with _execute_serial_active_driver_lock:
        _execute_serial_active_driver = driver


def _get_execute_serial_active_driver() -> Any | None:
    with _execute_serial_active_driver_lock:
        return _execute_serial_active_driver


def _serial_live_env_ok() -> tuple[bool, str]:
    """dry_run=False için SERIAL_PORT zorunlu; istek gövdesinde port kabul edilmez."""
    port = os.getenv("SERIAL_PORT", "").strip()
    if not port:
        return False, "SERIAL_PORT tanımlı değil; gerçek gönderim reddedildi."
    return True, port


def _parse_serial_baud_from_env() -> tuple[int | None, str | None]:
    """
    SERIAL_BAUD: pozitif ondalık tamsayı. Tanımsızsa 115200.
    Geçersiz veya boş string → (None, açıklama).
    """
    raw = os.getenv("SERIAL_BAUD")
    if raw is None:
        return 115200, None
    s = str(raw).strip()
    if not s:
        return None, "SERIAL_BAUD boş; geçerli pozitif bir tam sayı beklenir."
    try:
        v = int(s, 10)
    except ValueError:
        return None, f"SERIAL_BAUD geçersiz: {raw!r}"
    if v <= 0:
        return None, "SERIAL_BAUD pozitif olmalıdır."
    return v, None


def _build_serial_driver_for_execute(*, baudrate: int) -> "SerialDriver":
    """_serial_live_env_ok ve baud doğrulaması sonrası; kilitleme altında çağrılmalı."""
    from app.drivers.serial_driver import SerialDriver

    port = os.environ["SERIAL_PORT"].strip()
    return SerialDriver(port, baudrate=int(baudrate))


def _driver_send_stop(driver: Any) -> None:
    send_stop = getattr(driver, "send_stop", None)
    if callable(send_stop):
        send_stop(require_connected=True)
        return
    driver.stop()


def _execute_serial_stop_response(
    *,
    ok: bool,
    stopped: bool,
    mode: str,
    message: str,
    trace_id: str,
    driver_status: dict | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    notes: list[str] | None = None,
    http_status: int = 200,
) -> ExecuteSerialResponse | JSONResponse:
    body = ExecuteSerialResponse(
        status="sent" if ok and stopped else "failed",
        message=message,
        command_count=0,
        driver_status=driver_status,
        error_detail=error_detail or error_code,
        trace_id=trace_id,
        notes=list(notes or []),
        ok=ok,
        stopped=stopped,
        mode=mode,
        error_code=error_code,
    )
    if http_status == 200:
        return body
    return JSONResponse(status_code=http_status, content=body.model_dump())


def _execution_result_to_serial_response(
    r: ExecutionResult,
    *,
    trace_id: str | None = None,
    commands_sha256: str | None = None,
    preflight_summary: dict | None = None,
) -> ExecuteSerialResponse:
    return ExecuteSerialResponse(
        status=r.status,
        message=r.message,
        command_count=r.command_count,
        driver_status=r.driver_status,
        error_detail=r.error_detail,
        artifact_paths=list(r.artifact_paths),
        notes=list(r.notes),
        trace_id=trace_id,
        commands_sha256=commands_sha256,
        preflight_summary=preflight_summary,
    )


def _commands_sha256(commands: List[Command]) -> str:
    return hashlib.sha256(serialize_commands(commands).encode("utf-8")).hexdigest()


def _execute_serial_preflight_rejection(
    req: ExecuteSerialRequest,
    commands: List[Command],
    parser_diags: List[Diagnostic],
    start_pt: Tuple[float, float],
) -> tuple[ExecuteSerialResponse | None, dict]:
    """
    dry_run=False için donanım öncesi final gate.

    İstemciden gelen /api/analyze preflight sonucu zorunlu tutulur, ayrıca backend aynı
    komut listesini collision_mode="error" ile yeniden analiz eder. Böylece frontend
    hatası veya eski UI akışı tek başına canlı UART gönderimine yetmez.
    """
    command_text = serialize_commands(commands)
    command_hash = _commands_sha256(commands)
    preflight = req.preflight

    summary = {
        "required": True,
        "provided": preflight is not None,
        "commands_sha256": command_hash,
        "server_collision_mode": "error",
        "walls_provided": bool(req.walls),
    }

    if preflight is None:
        return (
            ExecuteSerialResponse(
                status="failed",
                message="Canlı gönderim için /api/analyze preflight sonucu zorunludur.",
                command_count=len(commands),
                error_detail="PREFLIGHT_REQUIRED",
                preflight_summary=summary,
                commands_sha256=command_hash,
            ),
            summary,
        )

    summary.update(
        {
            "client_blocked": bool(preflight.blocked),
            "client_collision_count": int(getattr(preflight.stats, "collision_count", 0) or 0),
            "client_parser_count": len(preflight.parser),
            "client_analysis_count": len(preflight.analysis),
        }
    )

    if preflight.commands_unrolled.strip() != command_text.strip():
        return (
            ExecuteSerialResponse(
                status="failed",
                message="Preflight komut metni canlı gönderilecek komutla eşleşmiyor.",
                command_count=len(commands),
                error_detail="PREFLIGHT_COMMAND_MISMATCH",
                preflight_summary=summary,
                commands_sha256=command_hash,
            ),
            summary,
        )

    client_has_diagnostics = bool(preflight.parser or preflight.analysis)
    client_collision_count = int(getattr(preflight.stats, "collision_count", 0) or 0)
    client_proper_cross = int(getattr(preflight.stats, "wall_proper_cross_count", 0) or 0)
    if preflight.blocked or client_has_diagnostics or client_collision_count > 0 or client_proper_cross > 0:
        return (
            ExecuteSerialResponse(
                status="failed",
                message="Preflight sonucu canlı gönderime uygun değil; blocked, bulgu veya çarpışma riski var.",
                command_count=len(commands),
                error_detail="PREFLIGHT_BLOCKED",
                preflight_summary=summary,
                commands_sha256=command_hash,
            ),
            summary,
        )

    stats, analysis_diags = analyze_commands(
        commands,
        start=start_pt,
        limits=None,
        walls=req.walls,
        collision_mode="error",
        optimize_cfg=None,
    )
    server_parser_count = len(parser_diags)
    server_analysis_count = len(analysis_diags)
    summary.update(
        {
            "server_blocked": bool(parser_diags or analysis_diags),
            "server_collision_count": int(getattr(stats, "collision_count", 0) or 0),
            "server_wall_proper_cross_count": int(getattr(stats, "wall_proper_cross_count", 0) or 0),
            "server_parser_count": server_parser_count,
            "server_analysis_count": server_analysis_count,
            "move_count": int(getattr(stats, "move_count", 0) or 0),
            "path_length": float(getattr(stats, "path_length", 0.0) or 0.0),
        }
    )

    if parser_diags or analysis_diags or stats.collision_count > 0 or stats.wall_proper_cross_count > 0:
        notes = [d.message for d in [*parser_diags, *analysis_diags][:8]]
        return (
            ExecuteSerialResponse(
                status="failed",
                message="Backend final analizi canlı gönderimi engelledi.",
                command_count=len(commands),
                error_detail="SERVER_PREFLIGHT_BLOCKED",
                notes=notes,
                preflight_summary=summary,
                commands_sha256=command_hash,
            ),
            summary,
        )

    return None, summary


# Resmi yerel standart:
# - Operator V2: http://127.0.0.1:5173 (ve localhost eşdeğeri)
# CORS listesi tek kaynaktan yönetilir; env ile ek origin verilebilir.
DEFAULT_CORS_ORIGINS = ["http://127.0.0.1:5173", "http://localhost:5173"]
extra_cors = [s.strip() for s in os.getenv("BACKEND_CORS_ORIGINS_EXTRA", "").split(",") if s.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_CORS_ORIGINS + extra_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _diag_to_out(d: Diagnostic) -> DiagnosticOut:
    return DiagnosticOut(
        severity=d.severity,
        line=int(d.line),
        message=str(d.message),
        text=str(d.text),
    )


def _find_start_from_commands(commands: List[object]) -> Optional[Tuple[float, float]]:
    for cmd in commands:
        if isinstance(cmd, MoveCommand):
            return (float(cmd.x), float(cmd.y))
    return None


def _optimize_cfg_from_request(o: Optional[OptimizeConfigOut]) -> Optional[OptimizeConfig]:
    if o is None or not getattr(o, "enabled", False):
        return None
    return OptimizeConfig(
        enabled=True,
        collinear_angle_eps_deg=float(getattr(o, "collinear_angle_eps_deg", 1.0)),
        min_segment_length=float(getattr(o, "min_segment_length", 0.5)),
        rdp_epsilon=float(getattr(o, "rdp_epsilon", 0.0)),
        preserve_pen_lifts=True,
        join_epsilon_m=float(getattr(o, "join_epsilon_m", 0.001)),
        max_2opt_iterations=int(getattr(o, "max_2opt_iterations", 50)),
        time_budget_ms=float(getattr(o, "time_budget_ms", 5000.0)),
        preserve_order_for_layers=bool(getattr(o, "preserve_order_for_layers", False)),
        deterministic_seed=int(o.deterministic_seed) if getattr(o, "deterministic_seed", None) is not None else None,
    )


def _motion_cfg_from_request(o: Optional[MotionConfigOut]) -> Optional[MotionConfig]:
    if o is None or not getattr(o, "enabled", False):
        return None
    seed = getattr(o, "seed", None)
    return MotionConfig(
        enabled=True,
        drift_deg_per_sec=float(getattr(o, "drift_deg_per_sec", 1.0)),
        position_noise_std_per_sec=float(getattr(o, "position_noise_std_per_sec", 2.0)),
        seed=int(seed) if seed is not None else None,
    )


def _limits_from_text(text: str) -> Optional[ScenarioLimits]:
    """Metin başındaki # key: value satırlarından ScenarioLimits üretir."""
    md = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("#") or ":" not in s:
            continue
        rest = s[1:].strip()
        k, _, v = rest.partition(":")
        key, val = k.strip(), v.strip()
        if key and key.isidentifier():
            md[key] = val
    if not md:
        return None
    base = ScenarioLimits()
    def f(key: str, default: float):
        if key not in md:
            return default
        try:
            return float(md[key])
        except ValueError:
            return default
    def i(key: str, default: int):
        if key not in md:
            return default
        try:
            return int(md[key])
        except ValueError:
            return default
    return ScenarioLimits(
        max_total_time=f("max_time", base.max_total_time),
        max_path_length=f("max_path", base.max_path_length),
        max_moves=i("max_moves", base.max_moves),
        max_bounds_size=f("max_bounds", base.max_bounds_size),
        max_abs_coord=f("max_abs_coord", base.max_abs_coord),
    )


def _read_upload_bytes_limited(file: UploadFile, *, max_bytes: int) -> bytes:
    """
    UploadFile içeriğini limitli okur.
    Limit aşılırsa ValueError fırlatır (endpoint bunu ok=False ile döndürür).
    """
    if max_bytes <= 0:
        raise ValueError("Sunucu dosya yüklemeyi kapattı (MAX_UPLOAD_BYTES=0).")
    buf = bytearray()
    chunk_size = 1024 * 1024  # 1 MB
    try:
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
            buf.extend(chunk)
            if len(buf) > max_bytes:
                raise ValueError(
                    f"Dosya boyutu çok büyük: {len(buf)} bayt > {max_bytes} bayt (limit)."
                )
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Dosya okunamadı: {e!s}") from e
    return bytes(buf)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/api/status")
def status():
    """
    Demo güvenilirliği için küçük durum endpoint'i.
    Not: Endpoint sözleşmelerini bozmak için değil; sadece "DWG hazır mı?" bilgisini görünür kılmak için.
    """
    dwg_path = os.getenv("DWG_CONVERTER_PATH") or ""
    dwg_args = os.getenv("DWG_CONVERTER_ARGS") or ""

    available = False
    reason = ""
    converter_hint = None

    if not dwg_path.strip():
        reason = "DWG dönüştürücü yapılandırılmadı (DWG_CONVERTER_PATH yok)."
    else:
        p = Path(dwg_path)
        if p.exists():
            available = True
            reason = "DWG dönüştürücü hazır."
            # Güvenlik: tam path döndürmek yerine sadece isim/hint.
            converter_hint = p.name
        else:
            reason = "DWG dönüştürücü dosyası bulunamadı (DWG_CONVERTER_PATH geçersiz)."
            converter_hint = p.name

    payload = {
        "ok": True,
        "dwg_converter_available": bool(available),
        "dwg_converter_reason": str(reason),
        "dwg_converter_hint": converter_hint,
        "dwg_converter_args_configured": bool(bool(dwg_args.strip())),
    }
    return payload


@app.post("/api/import_plan", response_model=ImportPlanResponse)
def import_plan(req: NormalizedPlanIn) -> ImportPlanResponse:
    """
    JSON plan verisini doğrular ve NormalizedPlan olarak döndürür (Milestone 1).
    normalize=True ise plan_normalizer ile sadeleştirilir (Milestone 2).
    Hata durumunda da HTTP 200, ok=False ve error mesajı.
    """
    try:
        normalized = import_plan_from_json(req.model_dump(exclude={
            "normalize", "normalize_options",
            "return_plan_text", "return_commands_text", "return_raw_path", "step_size", "speed",
        }))
        warnings: List[str] = []

        if getattr(req, "normalize", False):
            opts = None
            if getattr(req, "normalize_options", None) is not None:
                o = req.normalize_options
                opts = NormalizeOptions(
                    merge_endpoints_tol=float(getattr(o, "merge_endpoints_tol", 1e-6)),
                    merge_collinear=bool(getattr(o, "merge_collinear", True)),
                    collinear_angle_eps_deg=float(getattr(o, "collinear_angle_eps_deg", 1.0)),
                    drop_zero_length=bool(getattr(o, "drop_zero_length", True)),
                )
            normalized, norm_warnings = normalize_plan(normalized, opts)
            warnings.extend(norm_warnings)

        normalized = enrich_plan_with_graph_metrics(normalized)

        plan_text_out: Optional[str] = None
        commands_text_out: Optional[str] = None
        walls_out: Optional[List[List[float]]] = None
        raw_path_points_out: Optional[List[List[float]]] = None

        return_plan_text = getattr(req, "return_plan_text", True)
        return_commands_text = getattr(req, "return_commands_text", True)
        return_raw_path = getattr(req, "return_raw_path", False)
        step_size = max(0.01, float(getattr(req, "step_size", 5.0)))
        speed = max(0.1, float(getattr(req, "speed", 120.0)))

        if return_plan_text or return_commands_text:
            walls_out = normalized_to_walls_array(normalized)
        if return_plan_text:
            plan_text_out = normalized_to_plan_text(normalized)
        if return_commands_text or return_raw_path:
            plan = normalized_to_plan(normalized)
            path_gen = PathGenerator(plan, step_size=step_size)
            path_segments = path_gen.generate_path_segments()
            raw_path = path_gen.generate_path()
            if not raw_path:
                return ImportPlanResponse(
                    ok=False,
                    error="Plan çizilebilir nokta üretmedi; segmentleri veya step_size değerini kontrol edin.",
                    normalized=None,
                    warnings=warnings,
                )
            if return_raw_path:
                raw_path_points_out = [[float(x), float(y)] for x, y in raw_path]
            if return_commands_text:
                try:
                    commands = compile_segments_pen_safe(path_segments, speed=speed)
                except PenSafeValidationError as e:
                    return ImportPlanResponse(
                        ok=False,
                        error=str(e),
                        normalized=None,
                        warnings=warnings,
                    )
                commands_text_out = serialize_commands(commands)

        return ImportPlanResponse(
            ok=True,
            normalized=normalized.model_dump(),
            warnings=warnings,
            plan_text=plan_text_out,
            commands_text=commands_text_out,
            walls=walls_out,
            raw_path_points=raw_path_points_out,
        )
    except ValueError as e:
        return ImportPlanResponse(ok=False, error=str(e), normalized=None, warnings=[])
    except ValidationError as e:
        errs = e.errors()
        msg = errs[0].get("msg", str(e)) if errs else str(e)
        loc = errs[0].get("loc", ())
        if loc:
            msg = f"{'.'.join(str(x) for x in loc)}: {msg}"
        return ImportPlanResponse(ok=False, error=msg, normalized=None, warnings=[])
    except Exception as e:
        return ImportPlanResponse(
            ok=False,
            error=f"Doğrulama hatası: {e!s}",
            normalized=None,
            warnings=[],
        )


@app.post("/api/import_dxf", response_model=ImportDxfResponse)
def import_dxf(
    file: UploadFile = File(...),
    options_json: Optional[str] = Form(None),
) -> ImportDxfResponse:
    """
    DXF dosyası yükler (multipart). ezdxf varsa ASCII/Binary destekler.
    /api/import_plan ile aynı yanıt şekli: ok/error/normalized/warnings + plan_text/commands_text/walls/raw_path_points.
    """
    try:
        raw = _read_upload_bytes_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    except ValueError as e:
        return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])
    # Not: Eski sürüm UTF-8 metin zorunluydu. Artık ezdxf varsa ASCII/Binary fark etmez.
    # Bu yüzden importer'a ham bytes veriyoruz; ezdxf yoksa importer UTF-8 decode ile fallback yapar.
    try:
        if options_json:
            opts_dict = json.loads(options_json)
            options = ImportDxfOptions.model_validate(opts_dict)
        else:
            options = ImportDxfOptions()
    except (json.JSONDecodeError, ValidationError) as e:
        errs = getattr(e, "errors", lambda: None)()
        if errs:
            msg = errs[0].get("msg", str(e)) if errs else str(e)
            loc = errs[0].get("loc", ())
            if loc:
                msg = f"{'.'.join(str(x) for x in loc)}: {msg}"
        else:
            msg = str(e)
        return ImportDxfResponse(ok=False, error=msg, normalized=None, warnings=[])

    # Önce sadece layer önizleme istenmiş mi kontrol et
    if options.preview_layers:
        try:
            info = inspect_dxf_layers_bytes(
                raw,
                units=options.units_override,
                scale=options.scale_override,
                origin=(0.0, 0.0),
                chord_tolerance_m=options.chord_tolerance_m,
                target_max_segments=options.preprocess_target_max_segments,
                max_insert_depth=options.max_insert_depth,
                explode_blocks=options.explode_blocks,
            )
        except ValueError as e:
            return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])

        layers_dict = info.get("layers", {})
        layers_list: List[LayerStats] = []
        # total_length desc, sonra name asc
        for name, stats in sorted(
            layers_dict.items(),
            key=lambda item: (-float(item[1].get("total_length", 0.0)), item[0]),
        ):
            layers_list.append(
                LayerStats(
                    name=name,
                    entities=int(stats.get("entities", 0)),
                    segments=int(stats.get("segments", 0)),
                    total_length=float(stats.get("total_length", 0.0)),
                    bbox=stats.get("bbox"),
                )
            )
        total_length = float(info.get("total_length", 0.0) or 0.0)
        recommended_step_size = _preview_recommended_step_size(
            total_length,
            options.auto_step_target_moves,
            info.get("bbox"),
        )

        dxf_insight = DxfInsightReport(
            entity_counts_total=info.get("entity_counts_total"),
            entity_counts_supported=info.get("entity_counts_supported"),
            entity_counts_unsupported=info.get("entity_counts_unsupported"),
            unsupported_samples=info.get("unsupported_samples"),
            layer_entity_counts=info.get("layer_entity_counts"),
            layer_scores=info.get("layer_scores"),
            suggested_layers_reasons=info.get("suggested_layers_reasons"),
            parse_warnings=info.get("parse_warnings"),
            warning_codes=info.get("warning_codes"),
            recommended_action=info.get("recommended_action"),
        )
        return ImportDxfResponse(
            ok=True,
            error=None,
            normalized=None,
            warnings=[],
            plan_text=None,
            commands_text=None,
            walls=None,
            raw_path_points=None,
            layers=layers_list,
            suggested_layers=info.get("suggested_layers") or [],
            recommended_step_size=recommended_step_size,
            dxf_units_detected=info.get("dxf_units_detected"),
            world_scale=info.get("world_scale"),
            world_bbox_m=info.get("bbox"),
            world_total_length_m=info.get("total_length"),
            dxf_insight=dxf_insight,
        )

    # Normal DXF import (plan üretimi)
    layer_whitelist = options.layer_whitelist
    if options.selected_layers:
        if isinstance(options.selected_layers, list) and len(options.selected_layers) > 0:
            layer_whitelist = options.selected_layers
    # Kullanıcı katman seçmemişse: layer intelligence ile otomatik seçim
    if layer_whitelist is None or (isinstance(layer_whitelist, list) and len(layer_whitelist) == 0):
        try:
            diagnostics = analyze_dxf_structure(raw)
            li = select_plan_layers(diagnostics)
            auto_layers = li.get("selected_layers") or []
            if auto_layers:
                layer_whitelist = auto_layers
        except Exception:
            pass

    try:
        normalized = dxf_bytes_to_normalized_plan(
            raw,
            units=options.units_override,
            scale=options.scale_override,
            origin=(0.0, 0.0),
            layer_whitelist=layer_whitelist,
            layer_blacklist=options.layer_blacklist,
            chord_tolerance_m=options.chord_tolerance_m,
            target_max_segments=options.preprocess_target_max_segments,
            max_insert_depth=options.max_insert_depth,
            explode_blocks=options.explode_blocks,
        )
    except ValueError as e:
        return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])
    except Exception as e:
        # Ezdxf seviyesinde bozuk/uyumsuz dosyalar 500 üretmek yerine
        # operatöre açıklayıcı bir kullanıcı hatası döndürülür.
        return ImportDxfResponse(
            ok=False,
            error=(
                "DXF dosyası okunamadı veya yapısı desteklenmiyor. "
                "Mümkünse dosyayı CAD aracında onarıp yeniden kaydedin "
                "(tercihen R12/R2000 ASCII DXF) ve tekrar deneyin."
            ),
            normalized=None,
            warnings=[f"Teknik detay: {str(e)}"] if str(e) else [],
        )

    warnings: List[str] = []
    if options.normalize:
        opts = None
        if options.normalize_options is not None:
            o = options.normalize_options
            opts = NormalizeOptions(
                merge_endpoints_tol=float(getattr(o, "merge_endpoints_tol", 1e-6)),
                merge_collinear=bool(getattr(o, "merge_collinear", True)),
                collinear_angle_eps_deg=float(getattr(o, "collinear_angle_eps_deg", 1.0)),
                drop_zero_length=bool(getattr(o, "drop_zero_length", True)),
            )
        if opts is None:
            opts = NormalizeOptions()
        # Yeni knob'ları ImportDxfOptions üzerinden uygula
        opts.recenter = bool(getattr(options, "recenter", opts.recenter))
        opts.recenter_mode = getattr(options, "recenter_mode", opts.recenter_mode)
        opts.min_segment_len = float(getattr(options, "min_segment_len", opts.min_segment_len))
        sb = getattr(options, "segment_budget", None)
        opts.segment_budget = int(sb) if sb is not None else None
        opts.budget_strategy = getattr(options, "budget_strategy", opts.budget_strategy)
        normalized, norm_warnings = normalize_plan(normalized, opts)
        warnings.extend(norm_warnings)

    normalized = enrich_plan_with_graph_metrics(normalized)

    plan_text_out: Optional[str] = None
    commands_text_out: Optional[str] = None
    walls_out: Optional[List[List[float]]] = None
    raw_path_points_out: Optional[List[List[float]]] = None

    step_size = max(0.01, float(options.step_size))
    speed = max(0.1, float(options.speed))

    # Toplam segment uzunluğu (önerilen step_size için)
    total_seg_length = 0.0
    for seg in normalized.segments:
        total_seg_length += math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)
    recommended_step_size = None
    target_moves = options.auto_step_target_moves
    if target_moves is not None and target_moves > 0 and total_seg_length > 0.0:
        recommended_step_size = max(0.01, total_seg_length / float(target_moves))

    if options.return_plan_text or options.return_commands_text:
        walls_out = normalized_to_walls_array(normalized)
    if options.return_plan_text:
        plan_text_out = normalized_to_plan_text(normalized)
    if options.return_commands_text or options.return_raw_path:
        plan = normalized_to_plan(normalized)
        path_gen = PathGenerator(plan, step_size=step_size)
        path_segments = path_gen.generate_path_segments()
        raw_path = path_gen.generate_path()
        if not raw_path:
            return ImportDxfResponse(
                ok=False,
                error="Plan çizilebilir nokta üretmedi; segmentleri veya step_size değerini kontrol edin.",
                normalized=None,
                warnings=warnings,
            )
        if options.return_raw_path:
            raw_path_points_out = [[float(x), float(y)] for x, y in raw_path]
        if options.return_commands_text:
            try:
                commands = compile_segments_pen_safe(path_segments, speed=speed)
            except PenSafeValidationError as e:
                return ImportDxfResponse(
                    ok=False,
                    error=str(e),
                    normalized=None,
                    warnings=warnings,
                )
            commands_text_out = serialize_commands(commands)

    return ImportDxfResponse(
        ok=True,
        normalized=normalized.model_dump(),
        warnings=warnings,
        plan_text=plan_text_out,
        commands_text=commands_text_out,
        walls=walls_out,
        raw_path_points=raw_path_points_out,
        recommended_step_size=recommended_step_size,
    )


@app.post("/api/import_dwg", response_model=ImportDxfResponse)
def import_dwg(
    file: UploadFile = File(...),
    options_json: Optional[str] = Form(None),
) -> ImportDxfResponse:
    """
    DWG dosyası yükler (multipart), harici dönüştürücü ile DXF'e çevirir ve
    /api/import_dxf ile aynı pipeline'ı kullanarak NormalizedPlan üretir.
    """
    # options_json önce parse edilir (convert_timeout_seconds dönüştürmede kullanılır)
    try:
        if options_json:
            opts_dict = json.loads(options_json)
            options = ImportDxfOptions.model_validate(opts_dict)
        else:
            options = ImportDxfOptions()
    except (json.JSONDecodeError, ValidationError) as e:
        errs = getattr(e, "errors", lambda: None)()
        if errs:
            msg = errs[0].get("msg", str(e)) if errs else str(e)
            loc = errs[0].get("loc", ())
            if loc:
                msg = f"{'.'.join(str(x) for x in loc)}: {msg}"
        else:
            msg = str(e)
        return ImportDxfResponse(ok=False, error=msg, normalized=None, warnings=[])

    try:
        raw = _read_upload_bytes_limited(file, max_bytes=MAX_UPLOAD_BYTES)
    except ValueError as e:
        return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])

    timeout = max(1.0, min(3600.0, float(options.convert_timeout_seconds)))
    dxf_bytes: bytes
    dwg_runtime_ms: float | None = None
    dxf_size_bytes: int | None = None
    try:
        import time as _time

        t0 = _time.perf_counter()
        dxf_bytes = convert_dwg_bytes_to_dxf_bytes(raw, timeout_seconds=timeout)
        dwg_runtime_ms = (_time.perf_counter() - t0) * 1000.0
        dxf_size_bytes = len(dxf_bytes)
    except DwgConversionError as e:
        return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])
    except Exception as e:
        return ImportDxfResponse(
            ok=False,
            error=f"DWG dönüştürme hatası: {e!s}",
            normalized=None,
            warnings=[],
        )

    # DWG için de preview_layers desteği (DXF bytes üzerinden)
    if options.preview_layers:
        try:
            info = inspect_dxf_layers_bytes(
                dxf_bytes,
                units=options.units_override,
                scale=options.scale_override,
                origin=(0.0, 0.0),
            )
        except ValueError as e:
            return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])

        layers_dict = info.get("layers", {})
        layers_list: List[LayerStats] = []
        for name, stats in sorted(
            layers_dict.items(),
            key=lambda item: (-float(item[1].get("total_length", 0.0)), item[0]),
        ):
            layers_list.append(
                LayerStats(
                    name=name,
                    entities=int(stats.get("entities", 0)),
                    segments=int(stats.get("segments", 0)),
                    total_length=float(stats.get("total_length", 0.0)),
                    bbox=stats.get("bbox"),
                )
            )
        total_length = float(info.get("total_length", 0.0) or 0.0)
        recommended_step_size = _preview_recommended_step_size(
            total_length,
            options.auto_step_target_moves,
            info.get("bbox"),
        )

        dxf_insight = DxfInsightReport(
            entity_counts_total=info.get("entity_counts_total"),
            entity_counts_supported=info.get("entity_counts_supported"),
            entity_counts_unsupported=info.get("entity_counts_unsupported"),
            unsupported_samples=info.get("unsupported_samples"),
            layer_entity_counts=info.get("layer_entity_counts"),
            layer_scores=info.get("layer_scores"),
            suggested_layers_reasons=info.get("suggested_layers_reasons"),
            parse_warnings=info.get("parse_warnings"),
            warning_codes=info.get("warning_codes"),
            recommended_action=info.get("recommended_action"),
        )
        return ImportDxfResponse(
            ok=True,
            error=None,
            normalized=None,
            warnings=[],
            plan_text=None,
            commands_text=None,
            walls=None,
            raw_path_points=None,
            layers=layers_list,
            suggested_layers=info.get("suggested_layers") or [],
            recommended_step_size=recommended_step_size,
            dxf_units_detected=info.get("dxf_units_detected"),
            world_scale=info.get("world_scale"),
            world_bbox_m=info.get("bbox"),
            world_total_length_m=info.get("total_length"),
            dxf_insight=dxf_insight,
            dwg_convert_runtime_ms=dwg_runtime_ms,
            dxf_size_bytes=dxf_size_bytes,
        )

    # options_json -> ImportDxfOptions (zaten yukarıda yapıldı)
    # DXF bytes pipeline'ı aynen /api/import_dxf ile aynı
    layer_whitelist = options.layer_whitelist
    if options.selected_layers:
        if isinstance(options.selected_layers, list) and len(options.selected_layers) > 0:
            layer_whitelist = options.selected_layers
    if layer_whitelist is None or (isinstance(layer_whitelist, list) and len(layer_whitelist) == 0):
        try:
            diagnostics = analyze_dxf_structure(dxf_bytes)
            li = select_plan_layers(diagnostics)
            auto_layers = li.get("selected_layers") or []
            if auto_layers:
                layer_whitelist = auto_layers
        except Exception:
            pass

    try:
        normalized = dxf_bytes_to_normalized_plan(
            dxf_bytes,
            units=options.units_override,
            scale=options.scale_override,
            origin=(0.0, 0.0),
            layer_whitelist=layer_whitelist,
            layer_blacklist=options.layer_blacklist,
            chord_tolerance_m=options.chord_tolerance_m,
            target_max_segments=options.preprocess_target_max_segments,
            max_insert_depth=options.max_insert_depth,
            explode_blocks=options.explode_blocks,
        )
    except ValueError as e:
        return ImportDxfResponse(ok=False, error=str(e), normalized=None, warnings=[])
    except Exception as e:
        # Bozuk/uyumsuz DXF içeriğini 500 ile düşürmek yerine
        # operatöre açıklayıcı bir kullanıcı hatası döndür.
        return ImportDxfResponse(
            ok=False,
            error=(
                "DXF dosyası okunamadı veya yapısı desteklenmiyor. "
                "Mümkünse dosyayı CAD aracında onarıp yeniden kaydedin "
                "(tercihen R12/R2000 ASCII DXF) ve tekrar deneyin."
            ),
            normalized=None,
            warnings=[f"Teknik detay: {str(e)}"] if str(e) else [],
        )

    warnings: List[str] = []
    if options.normalize:
        opts = None
        if options.normalize_options is not None:
            o = options.normalize_options
            opts = NormalizeOptions(
                merge_endpoints_tol=float(getattr(o, "merge_endpoints_tol", 1e-6)),
                merge_collinear=bool(getattr(o, "merge_collinear", True)),
                collinear_angle_eps_deg=float(getattr(o, "collinear_angle_eps_deg", 1.0)),
                drop_zero_length=bool(getattr(o, "drop_zero_length", True)),
            )
        if opts is None:
            opts = NormalizeOptions()
        opts.recenter = bool(getattr(options, "recenter", opts.recenter))
        opts.recenter_mode = getattr(options, "recenter_mode", opts.recenter_mode)
        opts.min_segment_len = float(getattr(options, "min_segment_len", opts.min_segment_len))
        sb = getattr(options, "segment_budget", None)
        opts.segment_budget = int(sb) if sb is not None else None
        opts.budget_strategy = getattr(options, "budget_strategy", opts.budget_strategy)
        normalized, norm_warnings = normalize_plan(normalized, opts)
        warnings.extend(norm_warnings)

    normalized = enrich_plan_with_graph_metrics(normalized)

    plan_text_out: Optional[str] = None
    commands_text_out: Optional[str] = None
    walls_out: Optional[List[List[float]]] = None
    raw_path_points_out: Optional[List[List[float]]] = None

    step_size = max(0.01, float(options.step_size))
    speed = max(0.1, float(options.speed))

    if options.return_plan_text or options.return_commands_text:
        walls_out = normalized_to_walls_array(normalized)
    if options.return_plan_text:
        plan_text_out = normalized_to_plan_text(normalized)
    if options.return_commands_text or options.return_raw_path:
        plan = normalized_to_plan(normalized)
        path_gen = PathGenerator(plan, step_size=step_size)
        path_segments = path_gen.generate_path_segments()
        raw_path = path_gen.generate_path()
        if not raw_path:
            return ImportDxfResponse(
                ok=False,
                error="Plan çizilebilir nokta üretmedi; segmentleri veya step_size değerini kontrol edin.",
                normalized=None,
                warnings=warnings,
            )
        if options.return_raw_path:
            raw_path_points_out = [[float(x), float(y)] for x, y in raw_path]
        if options.return_commands_text:
            try:
                commands = compile_segments_pen_safe(path_segments, speed=speed)
            except PenSafeValidationError as e:
                return ImportDxfResponse(
                    ok=False,
                    error=str(e),
                    normalized=None,
                    warnings=warnings,
                )
            commands_text_out = serialize_commands(commands)

    # Toplam segment uzunluğu (önerilen step_size için)
    total_seg_length = 0.0
    for seg in normalized.segments:
        total_seg_length += math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)
    recommended_step_size = None
    target_moves = options.auto_step_target_moves
    if target_moves is not None and target_moves > 0 and total_seg_length > 0.0:
        recommended_step_size = max(0.01, total_seg_length / float(target_moves))

    return ImportDxfResponse(
        ok=True,
        normalized=normalized.model_dump(),
        warnings=warnings,
        plan_text=plan_text_out,
        commands_text=commands_text_out,
        walls=walls_out,
        raw_path_points=raw_path_points_out,
        recommended_step_size=recommended_step_size,
        dwg_convert_runtime_ms=dwg_runtime_ms,
        dxf_size_bytes=dxf_size_bytes,
    )


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    text = req.commands_text or ""
    optimize_cfg = _optimize_cfg_from_request(req.optimize)
    prep = prepare_job_commands(text, explicit_start=req.start, optimize_cfg=optimize_cfg)
    commands = prep.commands
    parser_diags = prep.parser_diags
    start_pt = prep.start_pt

    walls = getattr(req, "walls", None)
    collision_mode = getattr(req, "collision_mode", "warn")
    analysis_diags: List[Diagnostic] = []
    stats_out = StatsOut()

    if commands:
        stats, analysis_diags = analyze_commands(
            commands,
            start=start_pt,
            optimize_cfg=None,
            walls=walls,
            collision_mode=collision_mode,
        )
        stats_out = StatsOut(
            bounds=stats.bounds,
            move_count=stats.move_count,
            wait_total=stats.wait_total,
            path_length=stats.path_length,
            estimated_time=stats.estimated_time,
            path_points=stats.path_points,
            original_move_count=prep.original_move_count
            if prep.original_move_count is not None
            else stats.original_move_count,
            optimized_move_count=prep.optimized_move_count
            if prep.optimized_move_count is not None
            else stats.optimized_move_count,
            reduction_ratio=prep.reduction_ratio if prep.reduction_ratio is not None else stats.reduction_ratio,
            collision_count=stats.collision_count,
            collisions_sample=[
                CollisionOut(
                    kind=k,
                    x=x,
                    y=y,
                    wall_index=-1,
                    seg_index=-1,
                    message="",
                )
                for (x, y, k) in (stats.collisions_sample or [])
            ],
            wall_overlap_count=getattr(stats, "wall_overlap_count", 0),
            wall_touch_count=getattr(stats, "wall_touch_count", 0),
            wall_proper_cross_count=getattr(stats, "wall_proper_cross_count", 0),
        )

    parser_error_count = sum(1 for d in parser_diags if d.severity == "ERROR")
    analysis_error_count = sum(1 for d in analysis_diags if d.severity == "ERROR")
    blocked = (parser_error_count > 0) or (analysis_error_count > 0)

    commands_unrolled = serialize_commands(commands)

    return AnalyzeResponse(
        blocked=blocked,
        commands_unrolled=commands_unrolled,
        parser=[_diag_to_out(d) for d in parser_diags],
        analysis=[_diag_to_out(d) for d in analysis_diags],
        stats=stats_out,
    )


MAX_SIM_STEPS = 200_000
JOB_QUEUE_MAXSIZE = int(os.getenv("JOB_QUEUE_MAXSIZE", "1024"))
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "900"))


def _drop_one_tick_if_possible(queue: asyncio.Queue) -> bool:
    """
    Queue dolduğunda önce eski tick event'lerini düşürmeyi dener.
    Not: asyncio.Queue iç yapısındaki deque kullanımı, minimum-risk demo guard'ı için tercih edildi.
    """
    inner = getattr(queue, "_queue", None)
    if inner is None:
        return False
    try:
        for idx, item in enumerate(inner):
            if isinstance(item, tuple) and len(item) >= 1 and item[0] == "tick":
                del inner[idx]
                return True
    except Exception:
        return False
    return False


async def _safe_enqueue_event(
    queue: asyncio.Queue,
    event_type: Optional[str],
    data: Optional[dict],
) -> None:
    """
    Queue'ya güvenli event yazar.
    - tick için: doluysa eski tick düşürüp yeniyi alır.
    - done/error/sentinel için: mümkünse tick düşürür; gerekirse en eskiyi düşürüp terminal event'i yazar.
    """
    item = (event_type, data)
    while True:
        try:
            queue.put_nowait(item)
            return
        except asyncio.QueueFull:
            dropped = _drop_one_tick_if_possible(queue)
            if not dropped:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    await asyncio.sleep(0)
                    continue


def _sweep_jobs_ttl(now_ts: float) -> None:
    """Biten veya TTL'i aşan job kayıtlarını temizler (hafif, create_job sırasında çağrılır)."""
    for jid, job in list(jobs.items()):
        task = job.get("task")
        created_at = float(job.get("created_at", now_ts))
        expired = (now_ts - created_at) > float(JOB_TTL_SECONDS)
        done = task.done() if task is not None else True
        if done or expired:
            if task is not None and (not task.done()) and expired:
                task.cancel()
            jobs.pop(jid, None)


async def _simulate_event_stream(
    commands: List[Command],
    dt: float,
    speed_multiplier: float,
    start_pt: Tuple[float, float],
    motion_cfg: Optional[MotionConfig] = None,
):
    """SSE event stream: tick (ideal/real/error) + done. motion_cfg ile drift/noise uygulanır."""
    mult = max(0.1, min(5.0, float(speed_multiplier)))
    executor = CommandExecutor(commands)
    ideal_pos = (float(start_pt[0]), float(start_pt[1]))
    real_pos = (float(start_pt[0]), float(start_pt[1]))
    t = 0.0
    steps = 0
    error_sum = 0.0
    error_count = 0
    error_max = 0.0
    motion_state = MotionState(
        rng=random.Random(motion_cfg.seed) if motion_cfg and motion_cfg.seed is not None else random.Random()
    )

    try:
        while steps < MAX_SIM_STEPS:
            effective_speed = executor.current_speed * mult
            new_ideal_pos, drew = executor.update(dt, ideal_pos, speed_override=effective_speed)
            state = executor.debug_state()

            ideal_dx = new_ideal_pos[0] - ideal_pos[0]
            ideal_dy = new_ideal_pos[1] - ideal_pos[1]
            if motion_cfg and motion_cfg.enabled:
                real_dx, real_dy = apply_motion(ideal_dx, ideal_dy, dt, motion_cfg, motion_state)
            else:
                real_dx, real_dy = ideal_dx, ideal_dy
            real_pos = (real_pos[0] + real_dx, real_pos[1] + real_dy)
            error = math.hypot(real_pos[0] - new_ideal_pos[0], real_pos[1] - new_ideal_pos[1])
            error_sum += error
            error_count += 1
            error_max = max(error_max, error)
            error_mean = error_sum / error_count if error_count else 0.0

            payload = {
                "t": round(t, 6),
                "x": real_pos[0],
                "y": real_pos[1],
                "ideal_x": new_ideal_pos[0],
                "ideal_y": new_ideal_pos[1],
                "real_x": real_pos[0],
                "real_y": real_pos[1],
                "error": round(error, 6),
                "error_mean": round(error_mean, 6),
                "error_max": round(error_max, 6),
                "pen": state["pen"],
                "drew": drew,
                "idx": state["index"],
                "wait": state["wait"],
                "heading_deg": state["heading_deg"],
                "target": state["target"],
                "finished": state["finished"],
            }
            yield f"event: tick\ndata: {json.dumps(payload)}\n\n"

            ideal_pos = new_ideal_pos
            t += dt
            steps += 1

            if state["finished"]:
                yield f"event: done\ndata: {json.dumps({'t': round(t, 6), 'x': real_pos[0], 'y': real_pos[1], 'ideal_x': ideal_pos[0], 'ideal_y': ideal_pos[1], 'real_x': real_pos[0], 'real_y': real_pos[1], 'error': round(error, 6), 'error_mean': round(error_mean, 6), 'error_max': round(error_max, 6)})}\n\n"
                return

            await asyncio.sleep(dt)

        yield f"event: error\ndata: {json.dumps({'message': 'max_steps exceeded', 't': round(t, 6), 'x': real_pos[0], 'y': real_pos[1]})}\n\n"
    except (asyncio.CancelledError, GeneratorExit, BrokenPipeError):
        pass


async def _run_sim_to_queue(
    commands: List[Command],
    dt: float,
    speed_multiplier: float,
    start_pt: Tuple[float, float],
    queue: asyncio.Queue,
    motion_cfg: Optional[MotionConfig] = None,
    *,
    job_id: Optional[str] = None,
    file_artifact_opt: Optional[JobFileArtifactRequest] = None,
) -> None:
    """Simülasyonu queue'ya event olarak yazar. ``commands`` canonical hazırlık çıktısıdır."""
    mult = max(0.1, min(5.0, float(speed_multiplier)))
    executor = CommandExecutor(commands)
    ideal_pos = (float(start_pt[0]), float(start_pt[1]))
    real_pos = (float(start_pt[0]), float(start_pt[1]))
    t = 0.0
    steps = 0
    error_sum = 0.0
    error_count = 0
    error_max = 0.0
    motion_state = MotionState(
        rng=random.Random(motion_cfg.seed) if motion_cfg and motion_cfg.seed is not None else random.Random()
    )
    try:
        while steps < MAX_SIM_STEPS:
            effective_speed = executor.current_speed * mult
            new_ideal_pos, drew = executor.update(dt, ideal_pos, speed_override=effective_speed)
            state = executor.debug_state()
            ideal_dx = new_ideal_pos[0] - ideal_pos[0]
            ideal_dy = new_ideal_pos[1] - ideal_pos[1]
            if motion_cfg and motion_cfg.enabled:
                real_dx, real_dy = apply_motion(ideal_dx, ideal_dy, dt, motion_cfg, motion_state)
            else:
                real_dx, real_dy = ideal_dx, ideal_dy
            real_pos = (real_pos[0] + real_dx, real_pos[1] + real_dy)
            error = math.hypot(real_pos[0] - new_ideal_pos[0], real_pos[1] - new_ideal_pos[1])
            error_sum += error
            error_count += 1
            error_max = max(error_max, error)
            error_mean = error_sum / error_count if error_count else 0.0
            payload = {
                "t": round(t, 6),
                "x": real_pos[0],
                "y": real_pos[1],
                "ideal_x": new_ideal_pos[0],
                "ideal_y": new_ideal_pos[1],
                "real_x": real_pos[0],
                "real_y": real_pos[1],
                "error": round(error, 6),
                "error_mean": round(error_mean, 6),
                "error_max": round(error_max, 6),
                "pen": state["pen"],
                "drew": drew,
                "idx": state["index"],
                "wait": state["wait"],
                "heading_deg": state["heading_deg"],
                "target": state["target"],
                "finished": state["finished"],
            }
            await _safe_enqueue_event(queue, "tick", payload)
            ideal_pos = new_ideal_pos
            t += dt
            steps += 1
            if state["finished"]:
                done_payload: dict = {
                    "t": round(t, 6),
                    "x": real_pos[0],
                    "y": real_pos[1],
                    "ideal_x": ideal_pos[0],
                    "ideal_y": ideal_pos[1],
                    "real_x": real_pos[0],
                    "real_y": real_pos[1],
                    "error": round(error, 6),
                    "error_mean": round(error_mean, 6),
                    "error_max": round(error_max, 6),
                }
                if (
                    file_artifact_opt
                    and file_artifact_opt.enabled
                    and job_id
                    and commands
                ):
                    loop = asyncio.get_running_loop()
                    root = _job_file_artifact_root()
                    try:
                        writer = functools.partial(
                            _write_job_file_artifact_sync,
                            list(commands),
                            (float(start_pt[0]), float(start_pt[1])),
                            job_id,
                            file_artifact_opt.mode,
                            root,
                        )
                        file_meta = await loop.run_in_executor(None, writer)
                        done_payload["file_artifact"] = file_meta
                    except Exception as ex:
                        done_payload["file_artifact"] = {
                            "path": None,
                            "mode": file_artifact_opt.mode,
                            "last_write_succeeded": False,
                            "last_error": str(ex),
                            "last_command_count": len(commands),
                        }
                await _safe_enqueue_event(queue, "done", done_payload)
                return
            await asyncio.sleep(dt)
        await _safe_enqueue_event(
            queue,
            "error",
            {"message": "max_steps exceeded", "t": round(t, 6), "x": real_pos[0], "y": real_pos[1]},
        )
    except asyncio.CancelledError:
        pass
    finally:
        await _safe_enqueue_event(queue, None, None)


async def _stream_from_queue(job_id: str):
    """Job queue'dan okuyup SSE yield eder."""
    job = jobs.get(job_id)
    if not job:
        yield f"event: error\ndata: {json.dumps({'message': 'job not found'})}\n\n"
        return
    queue = job["queue"]
    try:
        while True:
            try:
                event_type, data = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield "event: ping\ndata: {}\n\n"
                continue
            if event_type is None:
                break
            if data is not None:
                yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
            if event_type in ("done", "error"):
                break
    finally:
        # Stream kapanırsa job'u deterministik temizle.
        latest = jobs.get(job_id)
        if latest:
            task = latest.get("task")
            if task is not None and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            jobs.pop(job_id, None)


@app.post("/api/jobs")
async def create_job(req: SimulateRequest):
    """Job oluşturur. Blocked ise 409. Yoksa { job_id } döner."""
    _sweep_jobs_ttl(time.time())
    text = (req.text or "").strip()
    dt = max(0.001, min(0.1, float(req.dt)))
    speed_multiplier = max(0.1, min(5.0, float(req.speed_multiplier)))
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    prep = prepare_job_commands(text, explicit_start=req.start, optimize_cfg=optimize_cfg)
    commands = prep.commands
    parser_diags = prep.parser_diags
    start_pt = prep.start_pt
    limits = _limits_from_text(text)
    stats_out = StatsOut()
    analysis_diags: List[Diagnostic] = []
    if commands:
        walls = getattr(req, "walls", None)
        collision_mode = getattr(req, "collision_mode", "warn")
        st, analysis_diags = analyze_commands(
            commands,
            start=start_pt,
            limits=limits,
            walls=walls,
            collision_mode=collision_mode,
            optimize_cfg=None,
        )
        stats_out = StatsOut(
            bounds=st.bounds,
            move_count=st.move_count,
            wait_total=st.wait_total,
            path_length=st.path_length,
            estimated_time=st.estimated_time,
            path_points=st.path_points,
            original_move_count=prep.original_move_count
            if prep.original_move_count is not None
            else st.original_move_count,
            optimized_move_count=prep.optimized_move_count
            if prep.optimized_move_count is not None
            else st.optimized_move_count,
            reduction_ratio=prep.reduction_ratio if prep.reduction_ratio is not None else st.reduction_ratio,
            collision_count=st.collision_count,
            collisions_sample=[
                CollisionOut(
                    kind=k,
                    x=x,
                    y=y,
                    wall_index=-1,
                    seg_index=-1,
                    message="",
                )
                for (x, y, k) in (st.collisions_sample or [])
            ],
            wall_overlap_count=getattr(st, "wall_overlap_count", 0),
            wall_touch_count=getattr(st, "wall_touch_count", 0),
            wall_proper_cross_count=getattr(st, "wall_proper_cross_count", 0),
        )
    parser_errors = sum(1 for d in parser_diags if d.severity == "ERROR")
    analysis_errors = sum(1 for d in analysis_diags if d.severity == "ERROR")
    if parser_errors > 0 or analysis_errors > 0:
        return JSONResponse(
            status_code=409,
            content={
                "blocked": True,
                "parser_diags": [_diag_to_out(d).model_dump() for d in parser_diags],
                "analysis_diags": [_diag_to_out(d).model_dump() for d in analysis_diags],
                "stats": stats_out.model_dump(),
            },
        )
    motion_cfg = _motion_cfg_from_request(getattr(req, "motion", None))
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=max(16, JOB_QUEUE_MAXSIZE))
    task = asyncio.create_task(
        _run_sim_to_queue(
            list(commands),
            dt,
            speed_multiplier,
            (float(start_pt[0]), float(start_pt[1])),
            queue,
            motion_cfg=motion_cfg,
            job_id=job_id,
            file_artifact_opt=req.file_artifact,
        )
    )
    jobs[job_id] = {"task": task, "queue": queue}

    task.add_done_callback(lambda _: jobs.pop(job_id, None))
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}/stream")
async def job_stream(job_id: str):
    """SSE stream: tick / done / error."""
    return StreamingResponse(
        _stream_from_queue(job_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@app.post("/api/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    """Job'u iptal eder."""
    job = jobs.get(job_id)
    if not job:
        return JSONResponse(status_code=404, content={"error": "job not found"})
    job["task"].cancel()
    try:
        await job["task"]
    except asyncio.CancelledError:
        pass
    jobs.pop(job_id, None)
    return {"stopped": True}


@app.post("/api/simulate")
async def simulate(req: SimulateRequest):
    """SSE stream: canlı simülasyon (tick + done). Blocked ise 409."""
    text = (req.text or "").strip()
    dt = max(0.001, min(0.1, float(req.dt)))
    speed_multiplier = max(0.1, min(5.0, float(req.speed_multiplier)))
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    prep = prepare_job_commands(text, explicit_start=req.start, optimize_cfg=optimize_cfg)
    commands = prep.commands
    parser_diags = prep.parser_diags
    start_pt = prep.start_pt

    limits = _limits_from_text(text)
    stats_out = StatsOut()
    analysis_diags: List[Diagnostic] = []
    if commands:
        st, analysis_diags = analyze_commands(
            commands, start=start_pt, limits=limits, optimize_cfg=None
        )
        stats_out = StatsOut(
            bounds=st.bounds,
            move_count=st.move_count,
            wait_total=st.wait_total,
            path_length=st.path_length,
            estimated_time=st.estimated_time,
            path_points=st.path_points,
            original_move_count=prep.original_move_count
            if prep.original_move_count is not None
            else st.original_move_count,
            optimized_move_count=prep.optimized_move_count
            if prep.optimized_move_count is not None
            else st.optimized_move_count,
            reduction_ratio=prep.reduction_ratio if prep.reduction_ratio is not None else st.reduction_ratio,
        )

    parser_errors = sum(1 for d in parser_diags if d.severity == "ERROR")
    analysis_errors = sum(1 for d in analysis_diags if d.severity == "ERROR")
    if parser_errors > 0 or analysis_errors > 0:
        return JSONResponse(
            status_code=409,
            content={
                "blocked": True,
                "parser_diags": [_diag_to_out(d).model_dump() for d in parser_diags],
                "analysis_diags": [_diag_to_out(d).model_dump() for d in analysis_diags],
                "stats": stats_out.model_dump(),
            },
        )

    motion_cfg = _motion_cfg_from_request(getattr(req, "motion", None))
    return StreamingResponse(
        _simulate_event_stream(
            list(commands),
            dt,
            speed_multiplier,
            (float(start_pt[0]), float(start_pt[1])),
            motion_cfg=motion_cfg,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/compile_plan")
def compile_plan(req: CompilePlanRequest):
    """
    Plan metninden yol üretir, komut senaryosuna çevirir.
    Döner: ok, raw_path_points (opsiyonel), commands_text, stats, parser_diags, analysis_diags.
    """
    print("[compile_plan] request geldi, plan_text len:", len(req.plan_text or ""))
    try:
        plan = load_plan_from_string(req.plan_text or "")
    except ValueError as e:
        print("[compile_plan] response dönüyor, ok=False (parse hatası):", str(e))
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": str(e),
                "commands_text": "",
                "stats": StatsOut().model_dump(),
                "parser_diags": [],
                "analysis_diags": [],
            },
        )
    step_size = max(0.01, float(req.step_size))
    speed = max(0.1, float(req.speed))
    scale = max(0.01, float(req.world_scale))
    ox, oy = (0.0, 0.0) if req.world_offset is None else (float(req.world_offset[0]), float(req.world_offset[1]))

    path_gen = PathGenerator(plan, step_size=step_size)
    path_segments = path_gen.generate_path_segments()
    raw_path = path_gen.generate_path()
    if not raw_path:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": "Plan çizilebilir nokta üretmedi; plan boş veya step_size değerini kontrol edin.",
                "commands_text": "",
                "raw_path_points": [],
                "walls": [],
                "stats": StatsOut().model_dump(),
                "parser_diags": [],
                "analysis_diags": [],
            },
        )
    world_path: List[Tuple[float, float]] = [(x * scale + ox, y * scale + oy) for x, y in raw_path]
    world_segments: List[List[Tuple[float, float]]] = [
        [(x * scale + ox, y * scale + oy) for x, y in seg] for seg in path_segments
    ]
    walls_world: List[List[float]] = [
        [w.x1 * scale + ox, w.y1 * scale + oy, w.x2 * scale + ox, w.y2 * scale + oy]
        for w in plan.walls
    ]

    # Kaynak gerçeği: stroke-aware pen-safe derleyici; isteğe bağlı tek optimize sonrası ``working``.
    try:
        commands_raw = compile_segments_pen_safe(world_segments, speed=speed)
    except PenSafeValidationError as e:
        return JSONResponse(
            status_code=200,
            content={
                "ok": False,
                "error": str(e),
                "commands_text": "",
                "raw_path_points": world_path,
                "walls": walls_world,
                "stats": StatsOut().model_dump(),
                "parser_diags": [],
                "analysis_diags": [],
            },
        )
    commands_text_raw = serialize_commands(commands_raw)
    start_pt = (0.0, 0.0)
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    working, omc, optmc, rr = apply_optional_optimize_to_commands(
        commands_raw,
        start_pt=start_pt,
        optimize_cfg=optimize_cfg,
    )
    if optimize_cfg is not None and getattr(optimize_cfg, "enabled", False):
        try:
            validate_pen_safe_commands(working, start_pos=start_pt)
            commands_text_optimized = serialize_commands(working)
        except PenSafeValidationError:
            working = commands_raw
            commands_text_optimized = commands_text_raw
    else:
        commands_text_optimized = commands_text_raw

    # ``commands_text_raw`` üzerinden parse yalnızca serileştirme doğrulaması içindir.
    parser_diags: List[Diagnostic] = []
    try:
        _, parser_diags = parse_commands(commands_text_raw, strict=False)
    except CommandParseError as e:
        parser_diags = [e.diagnostic]

    stats_out = StatsOut()
    analysis_diags: List[Diagnostic] = []
    if working:
        st, analysis_diags = analyze_commands(
            working,
            start=start_pt,
            limits=None,
            optimize_cfg=None,
            walls=walls_world,
            collision_mode="warn",
        )
        stats_out = StatsOut(
            bounds=st.bounds,
            move_count=st.move_count,
            wait_total=st.wait_total,
            path_length=st.path_length,
            estimated_time=st.estimated_time,
            path_points=st.path_points,
            original_move_count=omc if omc is not None else st.original_move_count,
            optimized_move_count=optmc if optmc is not None else st.optimized_move_count,
            reduction_ratio=rr if rr is not None else st.reduction_ratio,
            collision_count=st.collision_count,
            collisions_sample=[
                CollisionOut(
                    kind=k,
                    x=x,
                    y=y,
                    wall_index=-1,
                    seg_index=-1,
                    message="",
                )
                for (x, y, k) in (st.collisions_sample or [])
            ],
            wall_overlap_count=getattr(st, "wall_overlap_count", 0),
            wall_touch_count=getattr(st, "wall_touch_count", 0),
            wall_proper_cross_count=getattr(st, "wall_proper_cross_count", 0),
        )

    out = {
        "ok": True,
        "raw_path_points": world_path,
        "walls": walls_world,
        "commands_text": commands_text_raw,
        "commands_text_raw": commands_text_raw,
        "commands_text_optimized": commands_text_optimized,
        "stats": stats_out.model_dump(),
        "parser_diags": [_diag_to_out(d).model_dump() for d in parser_diags],
        "analysis_diags": [_diag_to_out(d).model_dump() for d in analysis_diags],
    }
    print("[compile_plan] response dönüyor, ok=True")
    return out


@app.post("/api/export", response_model=ExportResponse)
def export_robot(req: ExportRequest) -> ExportResponse:
    """
    Komut metnini robot export formatında döndürür (robot_v1 veya gcode_lite).
    Blocked olsa bile content üretilir; ok=false ve header'da BLOCKED: true.
    """
    text = (req.text or "").strip()
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    prep = prepare_job_commands(text, explicit_start=req.start, optimize_cfg=optimize_cfg)
    commands = prep.commands
    parser_diags = prep.parser_diags
    start_pt = prep.start_pt

    limits = _limits_from_text(text)
    fmt = getattr(req, "format", "robot_v1")
    if fmt not in ("robot_v1", "gcode_lite"):
        fmt = "robot_v1"

    content, blocked, stats, analysis_diags = export_commands_to_string(
        commands,
        start_pt,
        limits=limits,
        format=fmt,
        optimize_cfg=None,
    )
    filename = "robot_export.robot_v1.txt" if fmt == "robot_v1" else "robot_export.gcode"
    stats_out = StatsOut(
        bounds=stats.bounds,
        move_count=stats.move_count,
        wait_total=stats.wait_total,
        path_length=stats.path_length,
        estimated_time=stats.estimated_time,
        path_points=stats.path_points,
        original_move_count=prep.original_move_count
        if prep.original_move_count is not None
        else stats.original_move_count,
        optimized_move_count=prep.optimized_move_count
        if prep.optimized_move_count is not None
        else stats.optimized_move_count,
        reduction_ratio=prep.reduction_ratio if prep.reduction_ratio is not None else stats.reduction_ratio,
        collision_count=stats.collision_count,
        collisions_sample=[
            CollisionOut(
                kind=k,
                x=x,
                y=y,
                wall_index=-1,
                seg_index=-1,
                message="",
            )
            for (x, y, k) in (stats.collisions_sample or [])
        ],
        wall_overlap_count=getattr(stats, "wall_overlap_count", 0),
        wall_touch_count=getattr(stats, "wall_touch_count", 0),
        wall_proper_cross_count=getattr(stats, "wall_proper_cross_count", 0),
    )
    return ExportResponse(
        ok=not blocked,
        blocked=blocked,
        content=content,
        filename=filename,
        parser_diags=[_diag_to_out(d) for d in parser_diags],
        analysis_diags=[_diag_to_out(d) for d in analysis_diags],
        stats=stats_out,
    )


@app.post(
    "/api/execute_serial/stop",
    response_model=ExecuteSerialResponse,
    responses={
        400: {"model": ExecuteSerialResponse},
        403: {"model": ExecuteSerialResponse},
        500: {"model": ExecuteSerialResponse},
    },
)
def stop_execute_serial(request: Request):
    """Canli serial execution icin tekil STOP komutu gonderir (sim job stop degil)."""
    guard = _execute_serial_access_guard(request)
    if guard is not None:
        return guard

    trace_id = uuid.uuid4().hex[:12]
    active_driver = _get_execute_serial_active_driver()

    if active_driver is not None:
        try:
            _driver_send_stop(active_driver)
            return _execute_serial_stop_response(
                ok=True,
                stopped=True,
                mode="active_driver",
                message="Aktif seri driver'a STOP komutu gonderildi.",
                trace_id=trace_id,
                driver_status=active_driver.get_status(),
                notes=["target=active_serial_driver"],
            )
        except Exception as exc:
            return _execute_serial_stop_response(
                ok=False,
                stopped=False,
                mode="active_driver",
                message=f"STOP komutu aktif seri driver'a gonderilemedi: {exc!s}",
                trace_id=trace_id,
                error_code="STOP_SEND_FAILED",
                error_detail=str(exc),
                http_status=500,
            )

    live_ok, live_msg = _serial_live_env_ok()
    if not live_ok:
        return _execute_serial_stop_response(
            ok=False,
            stopped=False,
            mode="no_driver",
            message=live_msg,
            trace_id=trace_id,
            error_code="SERIAL_PORT_MISSING",
            http_status=400,
        )

    baud, baud_err = _parse_serial_baud_from_env()
    if baud is None:
        return _execute_serial_stop_response(
            ok=False,
            stopped=False,
            mode="no_driver",
            message=baud_err or "SERIAL_BAUD gecersiz.",
            trace_id=trace_id,
            error_code="INVALID_SERIAL_BAUD",
            http_status=400,
        )

    driver = None
    try:
        driver = _build_serial_driver_for_execute(baudrate=baud)
        driver.connect()
        _driver_send_stop(driver)
        return _execute_serial_stop_response(
            ok=True,
            stopped=True,
            mode="temporary_driver",
            message="Seri porta STOP komutu gonderildi.",
            trace_id=trace_id,
            driver_status=driver.get_status(),
            notes=["target=serial_port"],
        )
    except Exception as exc:
        return _execute_serial_stop_response(
            ok=False,
            stopped=False,
            mode="temporary_driver",
            message=f"STOP komutu gonderilemedi: {exc!s}",
            trace_id=trace_id,
            error_code="STOP_SEND_FAILED",
            error_detail=str(exc),
            http_status=500,
        )
    finally:
        if driver is not None:
            try:
                driver.disconnect()
            except Exception:
                pass


@app.post(
    "/api/execute_serial",
    response_model=ExecuteSerialResponse,
    responses={
        400: {"model": ExecuteSerialResponse},
        403: {"model": ExecuteSerialResponse},
        409: {"model": ExecuteSerialResponse},
    },
)
def execute_serial(req: ExecuteSerialRequest, request: Request):
    """
    **Donanım etkisi:** DSL derlenir; ``dry_run=false`` iken UART üzerinden batch gönderim yapılabilir.

    Canonical DSL → ``prepare_job_commands`` → ``run_command_execution_job``.

    **Erişim:** Varsayılan yalnızca loopback (127.0.0.1, ::1, localhost; testte ``testclient``).
    ``EXECUTE_SERIAL_ALLOW_REMOTE=true`` ile IP kısıtı kaldırılır (ters proxy / uzman senaryosu).
    ``EXECUTE_SERIAL_ADMIN_TOKEN`` tanımlıysa ``X-Execute-Token`` başlığı zorunludur.

    - ``dry_run`` varsayılan True: UART açılmaz, artifact + özet.
    - ``dry_run=False``: ``SERIAL_PORT`` (zorunlu) ve ``SERIAL_BAUD`` (varsayılan 115200) yalnızca env;
      geçersiz baud → 400 ``INVALID_SERIAL_BAUD``; eşzamanlı canlı gönderim → 409 ``SERIAL_EXECUTION_BUSY``.
    """
    guard = _execute_serial_access_guard(request)
    if guard is not None:
        return guard

    optimize_cfg = _optimize_cfg_from_request(req.optimize)
    prep = prepare_job_commands((req.text or "").strip(), explicit_start=req.start, optimize_cfg=optimize_cfg)

    parser_errors = [d for d in prep.parser_diags if d.severity == "ERROR"]
    if parser_errors:
        body = ExecuteSerialResponse(
            status="failed",
            message="DSL parse hatası; gönderim yapılmadı.",
            command_count=len(prep.commands),
            error_detail=parser_errors[0].message,
            notes=[d.message for d in parser_errors[:8]],
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    if not prep.commands:
        return ExecuteSerialResponse(status="skipped", message="Komut listesi boş.", command_count=0)

    trace_id = uuid.uuid4().hex[:12]
    command_hash = _commands_sha256(prep.commands)
    opts = ExecutionJobOptions(
        dry_run=req.dry_run,
        start_xy=(float(prep.start_pt[0]), float(prep.start_pt[1])),
        artifact_dir=_execute_serial_artifact_dir(),
        artifact_basename=f"execute_serial_{trace_id}",
    )
    ctx = ExecutionContext()

    if req.dry_run:
        result = run_command_execution_job(prep.commands, driver=None, options=opts, context=ctx)
        return _execution_result_to_serial_response(
            result,
            trace_id=trace_id,
            commands_sha256=command_hash,
            preflight_summary={"required": False, "commands_sha256": command_hash},
        )

    live_ok, live_msg = _serial_live_env_ok()
    if not live_ok:
        body = ExecuteSerialResponse(
            status="failed",
            message=live_msg,
            command_count=len(prep.commands),
            error_detail="SERIAL_PORT_MISSING",
            trace_id=trace_id,
            commands_sha256=command_hash,
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    baud, baud_err = _parse_serial_baud_from_env()
    if baud is None:
        body = ExecuteSerialResponse(
            status="failed",
            message=baud_err or "SERIAL_BAUD geçersiz.",
            command_count=len(prep.commands),
            error_detail="INVALID_SERIAL_BAUD",
            trace_id=trace_id,
            commands_sha256=command_hash,
        )
        return JSONResponse(status_code=400, content=body.model_dump())

    preflight_rejection, preflight_summary = _execute_serial_preflight_rejection(
        req,
        prep.commands,
        prep.parser_diags,
        prep.start_pt,
    )
    if preflight_rejection is not None:
        preflight_rejection.trace_id = trace_id
        preflight_rejection.commands_sha256 = command_hash
        return JSONResponse(status_code=409, content=preflight_rejection.model_dump())

    if not _execute_serial_live_lock.acquire(blocking=False):
        body = ExecuteSerialResponse(
            status="failed",
            message="Başka bir seri gönderim sürüyor; bitince tekrar deneyin.",
            command_count=len(prep.commands),
            error_detail="SERIAL_EXECUTION_BUSY",
            trace_id=trace_id,
            commands_sha256=command_hash,
            preflight_summary=preflight_summary,
        )
        return JSONResponse(status_code=409, content=body.model_dump())

    try:
        driver = _build_serial_driver_for_execute(baudrate=baud)
        _set_execute_serial_active_driver(driver)
        try:
            result = run_command_execution_job(prep.commands, driver=driver, options=opts, context=ctx)
            return _execution_result_to_serial_response(
                result,
                trace_id=trace_id,
                commands_sha256=command_hash,
                preflight_summary=preflight_summary,
            )
        finally:
            _set_execute_serial_active_driver(None)
    finally:
        _execute_serial_live_lock.release()


@app.post("/api/alignment/rigid_2d")
def alignment_rigid_2d(req: AlignRigid2dRequest) -> JSONResponse:
    """
    Prepare/Plan anlığındaki duvar segmentleri + kontrol noktaları ile rijit 2D hizalama.
    Ön/son SVG ve alignment raporu döner (mevcut aligner hattı).
    """
    try:
        layout = walls_list_to_printable_layout(list(req.walls or []))
        cps = [
            ControlPoint(
                cad_x=float(p.cad_x),
                cad_y=float(p.cad_y),
                site_x=float(p.site_x),
                site_y=float(p.site_y),
                label=p.label,
                weight=float(p.weight) if p.weight is not None else None,
            )
            for p in req.control_points
        ]
        aligned, report = align_printable_layout_rigid_2d(
            layout, cps, tolerance_m=float(req.tolerance_m)
        )
        pre_svg = render_pre_alignment_svg(layout)
        post_svg = render_post_alignment_svg(aligned)
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "alignment": alignment_report_to_jsonable(report),
                "pre_svg": pre_svg,
                "post_svg": post_svg,
            },
        )
    except Exception as ex:
        return JSONResponse(status_code=400, content={"ok": False, "error": str(ex)})
