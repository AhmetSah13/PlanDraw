from __future__ import annotations

from typing import List, Literal, Optional, Tuple

ExportFormat = Literal["robot_v1", "gcode_lite"]
from pydantic import BaseModel, Field

Severity = Literal["ERROR", "WARN"]


class DiagnosticOut(BaseModel):
    severity: Severity
    line: int
    message: str
    text: str


class StatsOut(BaseModel):
    bounds: Optional[Tuple[float, float, float, float]] = None
    move_count: int = 0
    wait_total: float = 0.0
    path_length: float = 0.0
    estimated_time: Optional[float] = None
    path_points: Optional[List[Tuple[float, float]]] = None
    original_move_count: Optional[int] = None
    optimized_move_count: Optional[int] = None
    reduction_ratio: Optional[float] = None
    collision_count: int = 0
    # collisions_sample: ilk N örnek; W2 UI'da hızlı gösterim için.
    # kind: "touch" | "proper" | "overlap"
    collisions_sample: List["CollisionOut"] = []


class CollisionOut(BaseModel):
    kind: Literal["touch", "proper", "overlap"]
    x: Optional[float] = None
    y: Optional[float] = None
    wall_index: int
    seg_index: int
    message: str


class OptimizeConfigOut(BaseModel):
    enabled: bool = False
    min_segment_length: float = 0.5
    collinear_angle_eps_deg: float = 1.0
    rdp_epsilon: float = 0.0


class MotionConfigOut(BaseModel):
    enabled: bool = False
    drift_deg_per_sec: float = 1.0
    position_noise_std_per_sec: float = 2.0
    seed: Optional[int] = None


class AnalyzeRequest(BaseModel):
    commands_text: str = Field(default="", description="Scenario script")
    start: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None
    walls: Optional[List[List[float]]] = None
    collision_mode: Literal["warn", "error"] = "warn"


class AnalyzeResponse(BaseModel):
    blocked: bool
    commands_unrolled: str
    parser: List[DiagnosticOut]
    analysis: List[DiagnosticOut]
    stats: StatsOut


class SimulateRequest(BaseModel):
    text: str = Field(default="", description="Scenario script (commands.txt content)")
    dt: float = Field(default=0.016, description="Simulation time step (s)")
    speed_multiplier: float = Field(default=1.0, ge=0.1, le=5.0, description="Speed multiplier")
    start: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None
    motion: Optional[MotionConfigOut] = None
    walls: Optional[List[List[float]]] = None
    collision_mode: Literal["warn", "error"] = "warn"


class CompilePlanRequest(BaseModel):
    plan_text: str = Field(default="", description="Plan (LINE x1 y1 x2 y2 satırları)")
    step_size: float = Field(default=5.0, gt=0, description="Path adım boyutu")
    speed: float = Field(default=120.0, gt=0, description="Robot hızı")
    world_scale: float = Field(default=1.0, gt=0, description="Dünya ölçeği")
    world_offset: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None


class ExportRequest(BaseModel):
    text: str = Field(default="", description="Komut metni")
    start: Optional[Tuple[float, float]] = None
    format: ExportFormat = Field(default="robot_v1", description="robot_v1 | gcode_lite")
    limits: Optional[dict] = None
    optimize: Optional[OptimizeConfigOut] = None


class ExportResponse(BaseModel):
    ok: bool
    blocked: bool
    content: str
    filename: str
    parser_diags: List[DiagnosticOut]
    analysis_diags: List[DiagnosticOut]
    stats: StatsOut
