from __future__ import annotations

import asyncio
import json
import math
import random
import sys
import uuid
from pathlib import Path

# Proje kökünü path'e ekle (commands, scenario_analysis orada)
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from typing import List, Optional, Tuple

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

from commands import (
    CommandParseError,
    Diagnostic,
    MoveCommand,
    parse_commands,
    serialize_commands,
)
from scenario_analysis import analyze_commands, export_commands_to_string, ScenarioLimits
from executor import CommandExecutor
from plan_module import load_plan_from_string
from path_generator import PathGenerator
from compiler import compile_path_to_commands
from path_optimizer import optimize_commands, OptimizeConfig

from .motion_model import MotionConfig, MotionState, apply_motion
from .schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    DiagnosticOut,
    StatsOut,
    SimulateRequest,
    CompilePlanRequest,
    OptimizeConfigOut,
    MotionConfigOut,
    ExportRequest,
    ExportResponse,
    CollisionOut,
)


app = FastAPI(title="PlanDraw Web Backend", version="0.1.0")

jobs: dict = {}  # job_id -> {"task": asyncio.Task, "queue": asyncio.Queue}

# Frontend: Vite default port 5173 (localhost + 127.0.0.1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
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


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    text = req.commands_text or ""

    # 1) Parse (strict=False => diagnostics ile döner)
    try:
        commands, parser_diags = parse_commands(text, strict=False)
    except CommandParseError as e:
        commands = []
        parser_diags = [e.diagnostic]

    # 2) Start noktası (request'ten veya ilk MOVE'dan; yoksa default (0,0))
    start = req.start
    if start is None:
        start = _find_start_from_commands(commands)
    if start is None:
        start = (0.0, 0.0)

    # 3) Analysis (opsiyonel optimize ile)
    optimize_cfg = _optimize_cfg_from_request(req.optimize)
    walls = getattr(req, "walls", None)
    collision_mode = getattr(req, "collision_mode", "warn")
    analysis_diags: List[Diagnostic] = []
    stats_out = StatsOut()

    if commands:
        stats, analysis_diags = analyze_commands(
            commands,
            start=start,
            optimize_cfg=optimize_cfg,
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
            original_move_count=stats.original_move_count,
            optimized_move_count=stats.optimized_move_count,
            reduction_ratio=stats.reduction_ratio,
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
        )

    # 4) Blocked kararı
    parser_error_count = sum(1 for d in parser_diags if d.severity == "ERROR")
    analysis_error_count = sum(1 for d in analysis_diags if d.severity == "ERROR")
    blocked = (parser_error_count > 0) or (analysis_error_count > 0)

    # 5) Unrolled komutları UI'de göstermek için (optimize açıksa optimize edilmiş liste)
    commands_to_show = (
        optimize_commands(commands, start, optimize_cfg)
        if optimize_cfg and optimize_cfg.enabled
        else commands
    )
    commands_unrolled = serialize_commands(commands_to_show)

    return AnalyzeResponse(
        blocked=blocked,
        commands_unrolled=commands_unrolled,
        parser=[_diag_to_out(d) for d in parser_diags],
        analysis=[_diag_to_out(d) for d in analysis_diags],
        stats=stats_out,
    )


MAX_SIM_STEPS = 200_000


async def _simulate_event_stream(
    text: str,
    dt: float,
    speed_multiplier: float,
    start_pt: Tuple[float, float],
    optimize_cfg: Optional[OptimizeConfig] = None,
    motion_cfg: Optional[MotionConfig] = None,
):
    """SSE event stream: tick (ideal/real/error) + done. motion_cfg ile drift/noise uygulanır."""
    try:
        commands, _ = parse_commands(text or "", strict=False)
    except CommandParseError:
        commands = []
    if optimize_cfg and optimize_cfg.enabled:
        commands = optimize_commands(commands, start_pt, optimize_cfg)

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
    text: str,
    dt: float,
    speed_multiplier: float,
    start_pt: Tuple[float, float],
    queue: asyncio.Queue,
    optimize_cfg: Optional[OptimizeConfig] = None,
    motion_cfg: Optional[MotionConfig] = None,
) -> None:
    """Simülasyonu queue'ya event olarak yazar. tick (ideal/real/error) / done / error."""
    try:
        commands, _ = parse_commands(text or "", strict=False)
    except CommandParseError:
        commands = []
    if optimize_cfg and optimize_cfg.enabled:
        commands = optimize_commands(commands, start_pt, optimize_cfg)
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
            await queue.put(("tick", payload))
            ideal_pos = new_ideal_pos
            t += dt
            steps += 1
            if state["finished"]:
                await queue.put(("done", {"t": round(t, 6), "x": real_pos[0], "y": real_pos[1], "ideal_x": ideal_pos[0], "ideal_y": ideal_pos[1], "real_x": real_pos[0], "real_y": real_pos[1], "error": round(error, 6), "error_mean": round(error_mean, 6), "error_max": round(error_max, 6)}))
                return
            await asyncio.sleep(dt)
        await queue.put(("error", {"message": "max_steps exceeded", "t": round(t, 6), "x": real_pos[0], "y": real_pos[1]}))
    except asyncio.CancelledError:
        pass
    finally:
        await queue.put((None, None))


async def _stream_from_queue(job_id: str):
    """Job queue'dan okuyup SSE yield eder."""
    job = jobs.get(job_id)
    if not job:
        yield f"event: error\ndata: {json.dumps({'message': 'job not found'})}\n\n"
        return
    queue = job["queue"]
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


@app.post("/api/jobs")
async def create_job(req: SimulateRequest):
    """Job oluşturur. Blocked ise 409. Yoksa { job_id } döner."""
    text = (req.text or "").strip()
    dt = max(0.001, min(0.1, float(req.dt)))
    speed_multiplier = max(0.1, min(5.0, float(req.speed_multiplier)))
    start = req.start
    try:
        commands, parser_diags = parse_commands(text, strict=False)
    except CommandParseError as e:
        commands = []
        parser_diags = [e.diagnostic]
    start_pt = start if start is not None else _find_start_from_commands(commands)
    if start_pt is None:
        start_pt = (0.0, 0.0)
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
        )
        stats_out = StatsOut(
            bounds=st.bounds,
            move_count=st.move_count,
            wait_total=st.wait_total,
            path_length=st.path_length,
            estimated_time=st.estimated_time,
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
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    motion_cfg = _motion_cfg_from_request(getattr(req, "motion", None))
    job_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(
        _run_sim_to_queue(
            text, dt, speed_multiplier,
            (float(start_pt[0]), float(start_pt[1])),
            queue,
            optimize_cfg=optimize_cfg,
            motion_cfg=motion_cfg,
        )
    )
    jobs[job_id] = {"task": task, "queue": queue}

    async def cleanup():
        try:
            task.cancel()
            await task
        except asyncio.CancelledError:
            pass
        jobs.pop(job_id, None)

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
    start = req.start

    try:
        commands, parser_diags = parse_commands(text, strict=False)
    except CommandParseError as e:
        commands = []
        parser_diags = [e.diagnostic]

    start_pt = start if start is not None else _find_start_from_commands(commands)
    if start_pt is None:
        start_pt = (0.0, 0.0)

    limits = _limits_from_text(text)
    stats_out = StatsOut()
    analysis_diags: List[Diagnostic] = []
    if commands:
        st, analysis_diags = analyze_commands(commands, start=start_pt, limits=limits)
        stats_out = StatsOut(
            bounds=st.bounds,
            move_count=st.move_count,
            wait_total=st.wait_total,
            path_length=st.path_length,
            estimated_time=st.estimated_time,
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

    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    motion_cfg = _motion_cfg_from_request(getattr(req, "motion", None))
    return StreamingResponse(
        _simulate_event_stream(
            text, dt, speed_multiplier,
            (float(start_pt[0]), float(start_pt[1])),
            optimize_cfg=optimize_cfg,
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
    raw_path = path_gen.generate_path()
    world_path: List[Tuple[float, float]] = [(x * scale + ox, y * scale + oy) for x, y in raw_path]
    walls_world: List[List[float]] = [
        [w.x1 * scale + ox, w.y1 * scale + oy, w.x2 * scale + ox, w.y2 * scale + oy]
        for w in plan.walls
    ]

    commands = compile_path_to_commands(world_path, speed=speed)
    commands_text_raw = serialize_commands(commands)
    commands_text_optimized = commands_text_raw

    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    if optimize_cfg and optimize_cfg.enabled:
        start_pt = (0.0, 0.0)
        commands_opt = optimize_commands(commands, start_pt, optimize_cfg)
        commands_text_optimized = serialize_commands(commands_opt)

    parser_diags: List[Diagnostic] = []
    try:
        commands_parsed, parser_diags = parse_commands(commands_text_raw, strict=False)
    except CommandParseError as e:
        commands_parsed = []
        parser_diags = [e.diagnostic]

    start_pt = (0.0, 0.0)
    stats_out = StatsOut()
    analysis_diags: List[Diagnostic] = []
    if commands_parsed:
        st, analysis_diags = analyze_commands(
            commands_parsed,
            start=start_pt,
            limits=None,
            optimize_cfg=optimize_cfg,
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
            original_move_count=st.original_move_count,
            optimized_move_count=st.optimized_move_count,
            reduction_ratio=st.reduction_ratio,
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
    try:
        commands, parser_diags = parse_commands(text, strict=False)
    except CommandParseError as e:
        commands = []
        parser_diags = [e.diagnostic]

    start_pt = req.start if req.start is not None else _find_start_from_commands(commands)
    if start_pt is None:
        start_pt = (0.0, 0.0)

    limits = _limits_from_text(text)
    optimize_cfg = _optimize_cfg_from_request(getattr(req, "optimize", None))
    fmt = getattr(req, "format", "robot_v1")
    if fmt not in ("robot_v1", "gcode_lite"):
        fmt = "robot_v1"

    content, blocked, stats, analysis_diags = export_commands_to_string(
        commands,
        start_pt,
        limits=limits,
        format=fmt,
        optimize_cfg=optimize_cfg,
    )
    filename = "robot_export.robot_v1.txt" if fmt == "robot_v1" else "robot_export.gcode"
    stats_out = StatsOut(
        bounds=stats.bounds,
        move_count=stats.move_count,
        wait_total=stats.wait_total,
        path_length=stats.path_length,
        estimated_time=stats.estimated_time,
        path_points=stats.path_points,
        original_move_count=stats.original_move_count,
        optimized_move_count=stats.optimized_move_count,
        reduction_ratio=stats.reduction_ratio,
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
