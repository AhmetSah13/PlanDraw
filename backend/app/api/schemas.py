from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

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
    # Debug: duvar–çizim overlap/touch (beklenen); collision_count yalnızca proper kesişim
    wall_overlap_count: int = 0
    wall_touch_count: int = 0
    wall_proper_cross_count: int = 0


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
    join_epsilon_m: float = 0.001
    max_2opt_iterations: int = 50
    time_budget_ms: float = 5000.0
    preserve_order_for_layers: bool = False
    deterministic_seed: Optional[int] = None


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


class JobFileArtifactRequest(BaseModel):
    """Job bittiğinde, simülasyonda kullanılan komut listesi FileDriver ile diske yazılsın."""

    enabled: bool = Field(default=False, description="True ise done öncesi artifact üretilir")
    mode: Literal["dsl", "robot_v1"] = Field(
        default="dsl",
        description="FileDriver modu: dsl (serialize_commands) veya robot_v1 (export_commands_to_string)",
    )


class SimulateRequest(BaseModel):
    text: str = Field(default="", description="Scenario script (commands.txt content)")
    dt: float = Field(default=0.016, description="Simulation time step (s)")
    speed_multiplier: float = Field(default=1.0, ge=0.1, le=5.0, description="Speed multiplier")
    start: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None
    motion: Optional[MotionConfigOut] = None
    walls: Optional[List[List[float]]] = None
    collision_mode: Literal["warn", "error"] = "warn"
    file_artifact: Optional[JobFileArtifactRequest] = Field(
        default=None,
        description="İsteğe bağlı: job tamamlanınca aynı List[Command] FileDriver çıktısı",
    )


class CompilePlanRequest(BaseModel):
    plan_text: str = Field(default="", description="Plan (LINE x1 y1 x2 y2 satırları)")
    step_size: float = Field(default=5.0, gt=0, description="Path adım boyutu")
    speed: float = Field(default=120.0, gt=0, description="Robot hızı")
    world_scale: float = Field(default=1.0, gt=0, description="Dünya ölçeği")
    world_offset: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None


class ExecuteSerialRequest(BaseModel):
    """Seri porta gönderim: port/baudrate istemciden gelmez (yalnızca env)."""

    text: str = Field(default="", description="DSL senaryo metni")
    start: Optional[Tuple[float, float]] = None
    optimize: Optional[OptimizeConfigOut] = None
    dry_run: bool = Field(
        default=True,
        description="True: UART açılmaz; yalnızca artifact + özet. False: SERIAL_PORT gerekir.",
    )


class ExecuteSerialResponse(BaseModel):
    status: str
    message: str
    command_count: int = 0
    driver_status: Optional[Dict[str, Any]] = None
    error_detail: Optional[str] = None
    artifact_paths: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


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


# --- NormalizedPlan import (Milestone 1) ---


class SegmentIn(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: Optional[float] = None


class OriginIn(BaseModel):
    x: float = 0.0
    y: float = 0.0


class NormalizedPlanIn(BaseModel):
    """JSON ile gelen plan; POST /api/import_plan body. Boş segments endpoint içinde reddedilir (200 + ok=False)."""

    version: str = "v1"
    units: str = "mm"
    scale: float = Field(default=1.0, gt=0)
    origin: OriginIn = Field(default_factory=OriginIn)
    segments: List[SegmentIn] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
    normalize: bool = Field(default=False, description="Normalizasyon uygula (Milestone 2)")
    normalize_options: Optional["NormalizeOptionsIn"] = None
    return_plan_text: bool = Field(default=True, description="Yanıtta plan_text (LINE format) dönsün (M3)")
    return_commands_text: bool = Field(default=True, description="Yanıtta commands_text dönsün (M3)")
    return_raw_path: bool = Field(default=False, description="Yanıtta raw_path_points dönsün (M3)")
    step_size: float = Field(default=5.0, gt=0, description="Path adım boyutu (commands_text için)")
    speed: float = Field(default=120.0, gt=0, description="Robot hızı (commands_text için)")


class NormalizeOptionsIn(BaseModel):
    """Normalizasyon seçenekleri; API'de normalize_options olarak gelebilir."""

    merge_endpoints_tol: float = Field(default=1e-6, ge=0)
    merge_collinear: bool = True
    collinear_angle_eps_deg: float = Field(default=1.0, ge=0, le=180)
    drop_zero_length: bool = True


class ImportPlanResponse(BaseModel):
    ok: bool
    error: Optional[str] = None
    normalized: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
    plan_text: Optional[str] = None
    commands_text: Optional[str] = None
    walls: Optional[List[List[float]]] = None
    raw_path_points: Optional[List[List[float]]] = None


# --- DXF import (POST /api/import_dxf) ---


class ImportDxfOptions(BaseModel):
    """DXF import multipart options (options_json)."""

    normalize: bool = True
    normalize_options: Optional[NormalizeOptionsIn] = None
    return_plan_text: bool = True
    return_commands_text: bool = True
    return_raw_path: bool = False
    step_size: float = 5.0
    speed: float = 120.0
    layer_whitelist: Optional[List[str]] = None
    layer_blacklist: Optional[List[str]] = None
    units_override: Optional[str] = None  # "mm" | "cm" | "m"
    scale_override: Optional[float] = None
    # DWG import için: dönüştürücü subprocess zaman aşımı (saniye). Sadece /api/import_dwg kullanır.
    convert_timeout_seconds: float = Field(
        default=60.0,
        gt=0,
        le=3600,
        description="DWG→DXF dönüştürme zaman aşımı (s)",
    )
    preview_layers: bool = False
    selected_layers: Optional[List[str]] = None
    recenter: bool = True
    recenter_mode: Literal["center", "min_corner"] = "center"
    min_segment_len: float = 0.0
    segment_budget: Optional[int] = None
    budget_strategy: Literal["keep_longest", "error"] = "keep_longest"
    auto_step_target_moves: Optional[int] = 800
    # Gerçek DXF desteği: preprocess/discretize ayarları (opsiyonel, geriye uyumlu)
    chord_tolerance_m: Optional[float] = Field(
        default=None,
        gt=0,
        description="Eğri discretization toleransı (metre). None ise adaptif.",
    )
    preprocess_target_max_segments: int = Field(
        default=15000,
        gt=100,
        description="Preprocess hedef maksimum segment sayısı (discretize guard).",
    )
    explode_blocks: bool = Field(default=True, description="INSERT blok patlatma (virtual_entities)")
    max_insert_depth: int = Field(default=8, ge=0, le=20, description="INSERT recursion depth limiti")


class LayerStats(BaseModel):
    name: str
    entities: int
    segments: int
    total_length: float
    bbox: Optional[List[float]] = None  # [minx,miny,maxx,maxy]


class DxfInsightReport(BaseModel):
    """DXF Insight Report — preview yanıtında opsiyonel."""

    entity_counts_total: Optional[Dict[str, int]] = None
    entity_counts_supported: Optional[Dict[str, int]] = None
    entity_counts_unsupported: Optional[Dict[str, int]] = None
    unsupported_samples: Optional[List[Dict[str, Any]]] = None
    layer_entity_counts: Optional[Dict[str, Dict[str, int]]] = None
    layer_scores: Optional[List[Dict[str, Any]]] = None
    suggested_layers_reasons: Optional[List[Dict[str, Any]]] = None
    parse_warnings: Optional[List[Any]] = None  # string veya {code, message, user_action}
    warning_codes: Optional[List[str]] = None
    recommended_action: Optional[str] = None  # Kısa öneri cümlesi


class ImportDxfResponse(ImportPlanResponse):
    """Aynı şekil; endpoint response_model için açık tip."""

    layers: Optional[List[LayerStats]] = None
    suggested_layers: Optional[List[str]] = None
    recommended_step_size: Optional[float] = None
    # Önizleme ve debug için ek alanlar (opsiyonel; mevcut istemcileri bozmaz).
    dxf_units_detected: Optional[str] = None
    world_scale: Optional[float] = None
    world_bbox_m: Optional[List[float]] = None  # [minx,miny,maxx,maxy] metre cinsinden
    world_total_length_m: Optional[float] = None  # metre cinsinden toplam yol uzunluğu
    # DXF Insight Report (preview_layers=true ise)
    dxf_insight: Optional[DxfInsightReport] = None
    # DWG -> DXF adapter debug alanları (sadece /api/import_dwg kullanabilir)
    dwg_convert_runtime_ms: Optional[float] = None
    dxf_size_bytes: Optional[int] = None


class ControlPointIn(BaseModel):
    cad_x: float
    cad_y: float
    site_x: float
    site_y: float
    label: Optional[str] = None
    weight: Optional[float] = None


class AlignRigid2dRequest(BaseModel):
    """Duvar segmentleri (dünya m) + kontrol noktaları → rijit 2D hizalama."""

    walls: List[List[float]] = Field(default_factory=list, description="Her satır [x1,y1,x2,y2]")
    control_points: List[ControlPointIn] = Field(default_factory=list)
    tolerance_m: float = Field(default=0.05, gt=0, description="İzin verilen max residual (m)")
