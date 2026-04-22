# verify_dxf_drawability.py — DXF yükleme → önizleme → import → analiz → çizim/export doğrulama
# Spec: backend/reports/<run>/summary.json + files/<file>.json; original_*, drawn/travel, retention, suite.

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

# Backend kökünü path'e ekle (repo kökünden veya backend'den çalıştırılabilir)
_script_dir = Path(__file__).resolve().parent
_backend_root = _script_dir.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

# App importları (pydantic/fastapi gerekir)
try:
    from app.importers.dxf_importer import (
        dxf_bytes_to_normalized_plan,
        get_dxf_all_segments_before_filter,
        inspect_dxf_layers_bytes,
        analyze_dxf_structure,
        select_plan_layers,
    )
    from app.analysis.geometry_graph import (
        enrich_plan_with_graph_metrics,
        build_graph,
        compute_graph_metrics,
    )
    from app.analysis.wall_centerline import (
        WallCenterlineConfig,
        apply_wall_centerline_to_plan,
    )
    from app.analysis.wall_filter import apply_wall_filter, WALL_FILTER_SNAP_TOL_M
    from app.importers.dwg_converter import convert_dwg_bytes_to_dxf_bytes, DwgConversionError
    from app.utils.step_size_utils import preview_recommended_step_size
    from app.normalization.plan_normalizer import NormalizeOptions, normalize_plan
    from app.importers.plan_importer import normalized_to_plan
    from app.pathing.path_generator import (
        PathGenerator,
        order_segments_nearest_neighbor,
        compute_travel_distance,
        _bbox_center,
    )
    from app.core.plan_module import Wall
    from app.execution.compiler import compile_path_to_commands, compile_path_to_commands_from_segments
    from app.pathing.path_optimizer import optimize_commands, OptimizeConfig
    from app.analysis.scenario_analysis import (
        analyze_commands,
        export_commands_to_string,
        ScenarioLimits,
    )
    from app.execution.commands import parse_commands, serialize_commands
    from app.execution.commands import (
        Command,
        MoveCommand,
        MoveRelCommand,
        ForwardCommand,
        TurnCommand,
        PenCommand,
    )
    from app.normalization.normalized_plan import SegmentIn
    from app.pathing.graph_traversal import generate_graph_traversal_path, build_components_with_candidates
except ImportError as e:
    print(f"Hata: app modülleri yüklenemedi (pydantic/fastapi gerekebilir): {e}", file=sys.stderr)
    sys.exit(1)

# Sabitler (API ile uyumlu)
TARGET_MOVES = 800
STEP_MIN, STEP_MAX = 0.05, 0.50
SPEED_DEFAULT = 120.0
WALL_KEYWORDS = ("wall", "walls", "duvar", "a-wall", "m-wall")
EPS = 1e-12
RETENTION_PLAN_FAIL = 0.7
RETENTION_DRAWN_FAIL = 0.6
TOP_FAIL_REASON_CODES = 10
# Bbox world (metre) bu eşiği aşarsa birim/ölçek uyumsuzluğu uyarısı (m→mm karışıklığı)
BBOX_WORLD_M_MAX_REASONABLE = 10000.0  # 10 km
BBOX_REASONABLE_MIN_M = 0.5
BBOX_REASONABLE_MAX_M = 200.0
SCOPE_SUPPORTED = "SUPPORTED_WALL_ONLY"
SCOPE_COMPLEX = "OUT_OF_SCOPE_COMPLEX"
SCOPE_ANNOTATION = "OUT_OF_SCOPE_ANNOTATION_HEAVY"
SCOPE_BLOCK = "OUT_OF_SCOPE_BLOCK_HEAVY"
SCOPE_UNITS = "OUT_OF_SCOPE_UNITS_UNCERTAIN"
SCOPE_OTHER = "OUT_OF_SCOPE_OTHER"


def _check_units_scale_mismatch(report: dict) -> None:
    """Bbox metre bazında aşırı büyükse UNITS_SCALE_MISMATCH uyarısı ve öneri ekler."""
    bbox_size = report.get("bbox_size")
    units = report.get("dxf_units_detected")
    if not bbox_size or len(bbox_size) < 2 or units is None:
        return
    max_side_m = max(float(bbox_size[0]), float(bbox_size[1]))
    if units == "m" and max_side_m > BBOX_WORLD_M_MAX_REASONABLE:
        report["units_scale_mismatch"] = True
        if not report.get("fail_reason_code"):
            report["fail_reason_code"] = "UNITS_SCALE_MISMATCH"
        report.setdefault("recommended_actions", []).append(
            "Plan boyutu metre bazında çok büyük (%.0f m); DXF gerçekte mm ise import'ta units=mm deneyin." % max_side_m
        )


def _bbox_reasonable(bbox_size: list | None) -> bool:
    """World bbox (metre) 0.5–200 m aralığında mı?"""
    if not bbox_size or len(bbox_size) < 2:
        return False
    lo = min(float(bbox_size[0]), float(bbox_size[1]))
    hi = max(float(bbox_size[0]), float(bbox_size[1]))
    return BBOX_REASONABLE_MIN_M < lo and hi < BBOX_REASONABLE_MAX_M


def _classify_scope(report: dict) -> str:
    """
    DXF dosyasını MVP scope açısından sınıflandırır.
    scope_class enum:
      - SUPPORTED_WALL_ONLY
      - OUT_OF_SCOPE_COMPLEX
      - OUT_OF_SCOPE_ANNOTATION_HEAVY
      - OUT_OF_SCOPE_BLOCK_HEAVY
      - OUT_OF_SCOPE_UNITS_UNCERTAIN
      - OUT_OF_SCOPE_OTHER
    """
    diag = report.get("dxf_diagnostics") or {}
    entity_counts = diag.get("entity_counts") or {}
    if not isinstance(entity_counts, dict):
        entity_counts = {}

    def _cnt(key: str) -> int:
        v = entity_counts.get(key, 0)
        try:
            return int(v)
        except Exception:
            return 0

    total_entities = sum(_cnt(k) for k in entity_counts.keys())
    total_entities = max(total_entities, 0)

    text_like = _cnt("TEXT") + _cnt("MTEXT") + _cnt("DIMENSION")
    insert_cnt = _cnt("INSERT")
    spline_cnt = _cnt("SPLINE")
    arc_cnt = _cnt("ARC")
    hatch_cnt = _cnt("HATCH")

    text_ratio = (text_like / float(total_entities)) if total_entities > 0 else 0.0
    insert_ratio = (insert_cnt / float(total_entities)) if total_entities > 0 else 0.0
    complex_ratio = ((spline_cnt + arc_cnt + hatch_cnt) / float(total_entities)) if total_entities > 0 else 0.0

    graph = report.get("graph_metrics") or {}
    wall_score = float(graph.get("wall_likeliness_score") or 0.0)

    # 1) Units belirsizliği (öncelikli, fakat başarılı retry durumunda scope dışı sayma)
    if report.get("units_retry_used"):
        metrics = report.get("units_retry_metrics") or {}
        m_info = metrics.get("m") or {}
        mm_info = metrics.get("mm") or {}
        chosen = report.get("units_chosen")
        chosen_info = metrics.get(chosen) or {}
        chosen_bbox_ok = _bbox_reasonable(chosen_info.get("bbox_size"))
        chosen_analyze_ok = (chosen_info.get("analyze_result") or "") != "BLOCKED"
        successful_retry = bool(chosen) and chosen_bbox_ok and chosen_analyze_ok

        if not successful_retry:
            # Sadece units retry başarısızsa veya bbox hâlâ mantıksızsa "units uncertain" say.
            cls = SCOPE_UNITS
            recs = report.setdefault("recommended_actions", [])
            if "DXF export ederken units=mm veya units=m ayarını netleştirin ve aynı birimi pipeline'da kullanın." not in recs:
                recs.append(
                    "DXF export ederken units=mm veya units=m ayarını netleştirin ve aynı birimi pipeline'da kullanın."
                )
            msg_units_retry = (
                "Bu dosyayı units override ile tekrar deneyin "
                "(örneğin backend/scripts/verify_dxf_drawability.py içinde units=mm)."
            )
            if msg_units_retry not in recs:
                recs.append(msg_units_retry)
            return cls

    # 2) Annotation heavy
    if text_ratio > 0.30:
        cls = SCOPE_ANNOTATION
        recs = report.setdefault("recommended_actions", [])
        if "CAD'de TEXT/DIM/MTEXT layer'larını kapatıp sadece duvar layer'larını içerir şekilde yeniden DXF export edin." not in recs:
            recs.append(
                "CAD'de TEXT/DIM/MTEXT layer'larını kapatıp sadece duvar layer'larını içerir şekilde yeniden DXF export edin."
            )
        if "Ölçü/detay anotasyonlarını ayrı bir dosyada tutup sadece duvar konturlarını export edin." not in recs:
            recs.append(
                "Ölçü/detay anotasyonlarını ayrı bir dosyada tutup sadece duvar konturlarını export edin."
            )
        return cls

    # 3) Block heavy
    if insert_ratio > 0.20 or insert_cnt >= 50:
        cls = SCOPE_BLOCK
        recs = report.setdefault("recommended_actions", [])
        if "CAD içinde INSERT (block) objelerini EXPLODE komutu ile LINE/LWPOLYLINE'a çevirip tekrar DXF export edin." not in recs:
            recs.append(
                "CAD içinde INSERT (block) objelerini EXPLODE komutu ile LINE/LWPOLYLINE'a çevirip tekrar DXF export edin."
            )
        if "Mobilya/ikon/detay block'larını ayrı layer'lara alıp bu layer'ları export sırasında kapatın." not in recs:
            recs.append(
                "Mobilya/ikon/detay block'larını ayrı layer'lara alıp bu layer'ları export sırasında kapatın."
            )
        return cls

    # 4) Geometrik karmaşıklık
    if complex_ratio > 0.30 and wall_score < 0.4:
        cls = SCOPE_COMPLEX
        recs = report.setdefault("recommended_actions", [])
        if "SPLINE/ARC/HATCH objelerini mümkünse polyline (LWPOLYLINE) duvar konturlarına çevirip tekrar export edin." not in recs:
            recs.append(
                "SPLINE/ARC/HATCH objelerini mümkünse polyline (LWPOLYLINE) duvar konturlarına çevirip tekrar export edin."
            )
        if "Çok detaylı süsleme/cephe geometri içeren planlar yerine sadeleştirilmiş bir duvar-only DXF üretip kullanın." not in recs:
            recs.append(
                "Çok detaylı süsleme/cephe geometri içeren planlar yerine sadeleştirilmiş bir duvar-only DXF üretip kullanın."
            )
        return cls

    # 5) SUPPORTED_WALL_ONLY (pozitif MVP scope)
    scope = SCOPE_OTHER
    layer_scores = report.get("layer_graph_scores") or []
    if isinstance(layer_scores, list) and layer_scores:
        layer_scores_sorted = sorted(
            [x for x in layer_scores if isinstance(x, dict) and "layer" in x and "score" in x],
            key=lambda d: (-float(d["score"]), str(d["layer"])),
        )
        if layer_scores_sorted:
            top = layer_scores_sorted[0]
            top_score = float(top.get("score") or 0.0)
            metrics = top.get("metrics") or {}
            top_len = float(metrics.get("total_length_m") or 0.0)
            ret_walls = report.get("retention_vs_walls_candidate")
            try:
                ret_walls_val = float(ret_walls) if ret_walls is not None else 0.0
            except Exception:
                ret_walls_val = 0.0

            # Güçlü duvar katmanı + anlamlı duvar graph skoru + iyi retention
            if (
                top_score >= 5.0
                and top_len >= 1.0
                and wall_score >= 0.6
                and ret_walls_val >= 0.85
            ):
                scope = SCOPE_SUPPORTED

    if scope == SCOPE_SUPPORTED:
        return scope

    # 6) Diğer tüm durumlar MVP kapsamı dışında sayılır
    cls = SCOPE_OTHER
    recs = report.setdefault("recommended_actions", [])
    if "Bu plan şimdilik MVP kapsamı dışında; duvar-only sadeleştirilmiş bir DXF üretip tekrar deneyin." not in recs:
        recs.append(
            "Bu plan şimdilik MVP kapsamı dışında; duvar-only sadeleştirilmiş bir DXF üretip tekrar deneyin."
        )
    if "Duvar layer'larını netleştirip (örneğin WALL/A-WALL) diğer layer'ları export sırasında kapatmayı deneyin." not in recs:
        recs.append(
            "Duvar layer'larını netleştirip (örneğin WALL/A-WALL) diğer layer'ları export sırasında kapatmayı deneyin."
        )
    return cls


def _extract_units_metrics(report: dict, label: str) -> dict:
    """Rapordan units_retry_metrics için satır çıkarır."""
    return {
        "bbox_size": report.get("bbox_size"),
        "path_length_m": report.get("path_length_m"),
        "move_count": report.get("move_count"),
        "shape_retention_plan": report.get("shape_retention_plan"),
        "shape_retention_drawn": report.get("shape_retention_drawn"),
        "analyze_result": report.get("analyze_result"),
    }


def _choose_units_result(report_m: dict, report_mm: dict) -> tuple[str, dict, dict]:
    """
    İki rapor arasında seçim: 1) LIMITS_EXCEEDED yok tercih, 2) bbox_reasonable tercih, 3) retention yüksek tercih.
    Döner: (chosen "m"|"mm", metrics_m, metrics_mm).
    """
    limits_m = report_m.get("fail_reason_code") == "LIMITS_EXCEEDED"
    limits_mm = report_mm.get("fail_reason_code") == "LIMITS_EXCEEDED"
    reasonable_m = _bbox_reasonable(report_m.get("bbox_size"))
    reasonable_mm = _bbox_reasonable(report_mm.get("bbox_size"))
    ret_m = report_m.get("shape_retention_drawn") or 0.0
    ret_mm = report_mm.get("shape_retention_drawn") or 0.0

    if not limits_mm and limits_m:
        return ("mm", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))
    if not limits_m and limits_mm:
        return ("m", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))
    if reasonable_mm and not reasonable_m:
        return ("mm", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))
    if reasonable_m and not reasonable_mm:
        return ("m", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))
    if ret_mm > ret_m:
        return ("mm", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))
    return ("m", _extract_units_metrics(report_m, "m"), _extract_units_metrics(report_mm, "mm"))


def _merge_units_retry_report(report_m: dict, report_mm: dict) -> dict:
    """units_scale_mismatch sonrası m vs mm seçip tek rapor döndürür."""
    chosen, metrics_m, metrics_mm = _choose_units_result(report_m, report_mm)
    base = report_mm if chosen == "mm" else report_m
    out = dict(base)
    out["units_retry_used"] = True
    out["units_retry_reason"] = "UNITS_SCALE_MISMATCH"
    out["units_candidates"] = ["m", "mm"]
    out["units_chosen"] = chosen
    out["units_retry_metrics"] = {"m": metrics_m, "mm": metrics_mm}
    # Units scale mismatch bayrağını, seçilen adayın bbox'ına ve analiz sonucuna göre güncelle
    chosen_metrics = metrics_mm if chosen == "mm" else metrics_m
    chosen_bbox_ok = _bbox_reasonable(chosen_metrics.get("bbox_size"))
    chosen_analyze_ok = (chosen_metrics.get("analyze_result") or "") != "BLOCKED"
    # Başarılı retry ise mismatch artık geçerli değil
    out["units_scale_mismatch"] = not (chosen_bbox_ok and chosen_analyze_ok)
    if isinstance(out.get("dxf_diagnostics"), dict):
        out["dxf_diagnostics"].setdefault("units", {})["units_retry_used"] = True
        out["dxf_diagnostics"]["units"]["units_chosen"] = chosen
    return out


def _seg_len(seg: SegmentIn) -> float:
    """Segment uzunluğu (metre)."""
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def measure_drawn_travel(
    commands: list[Command],
    start_xy: tuple[float, float] = (0.0, 0.0),
) -> dict:
    """
    Komut listesini absolute koordinata unroll edip drawn_length_m / travel_length_m hesaplar.
    Başlangıçta pen_down=False; ilk PEN DOWN'a kadar tüm hareketler travel.
    """
    x, y = float(start_xy[0]), float(start_xy[1])
    heading_deg = 0.0
    pen_down = False
    drawn_length_m = 0.0
    travel_length_m = 0.0
    has_pen_down = False
    for cmd in commands:
        if isinstance(cmd, PenCommand):
            pen_down = cmd.is_down
            if cmd.is_down:
                has_pen_down = True
            continue
        if isinstance(cmd, TurnCommand):
            heading_deg += cmd.deg
            continue
        x_prev, y_prev = x, y
        if isinstance(cmd, MoveCommand):
            x, y = cmd.x, cmd.y
        elif isinstance(cmd, MoveRelCommand):
            x, y = x + cmd.dx, y + cmd.dy
        elif isinstance(cmd, ForwardCommand):
            rad = math.radians(heading_deg)
            x += cmd.dist * math.cos(rad)
            y += cmd.dist * math.sin(rad)
        else:
            continue
        dist = math.hypot(x - x_prev, y - y_prev)
        if pen_down:
            drawn_length_m += dist
        else:
            travel_length_m += dist
    path_length_m = drawn_length_m + travel_length_m
    path_overhead = path_length_m / max(drawn_length_m, EPS) if drawn_length_m > 0 else (0.0 if path_length_m == 0 else 1e9)
    return {
        "drawn_length_m": round(drawn_length_m, 12),
        "travel_length_m": round(travel_length_m, 12),
        "path_length_m": round(path_length_m, 12),
        "path_overhead": round(path_overhead, 6),
        "has_pen_down": has_pen_down,
    }


def detect_suite(file_path: Path) -> str | None:
    """Dosya yolundan suite: A_expected_pass->A, B_realistic->B, C_stress->C, real_world->REAL."""
    s = str(file_path).replace("\\", "/")
    if "A_expected_pass" in s:
        return "A"
    if "B_realistic" in s:
        return "B"
    if "C_stress" in s:
        return "C"
    if "benchmarks/real_world" in s or "benchmarks\\real_world" in str(file_path):
        return "REAL"
    return None


def _clamp_step(raw: float | None) -> float:
    """Önerilen step'i [0.05, 0.50] aralığına kıstırır."""
    if raw is None or raw <= 0:
        return STEP_MAX
    return max(STEP_MIN, min(STEP_MAX, float(raw)))


LAYER_GRAPH_TIE_DELTA = 0.5


def _compute_layer_graph_scores(
    dxf_bytes: bytes,
    dxf_diag: dict | None,
) -> list[dict]:
    """
    Her layer için graph + geometri tabanlı wall-likeness skoru hesaplar.
    Döner: [{ "layer": name, "score": float, "metrics": {...} }, ...]
    """
    if not dxf_diag:
        return []

    layers_info = dxf_diag.get("layers") or []
    if not isinstance(layers_info, list):
        return []

    from app.importers.dxf_importer import get_dxf_all_segments_before_filter

    out: list[dict] = []
    for ly in layers_info:
        if not isinstance(ly, dict):
            continue
        name = ly.get("name") or ly.get("layer_name")
        if not name or not isinstance(name, str):
            continue

        try:
            segments, stats = get_dxf_all_segments_before_filter(
                dxf_bytes,
                units=None,
                scale=None,
                origin=(0.0, 0.0),
                layer_whitelist=[name],
            )
        except Exception:
            continue

        if not segments:
            continue

        total_len = float(stats.get("total_length", 0.0) or 0.0)
        if total_len <= 0.0:
            continue

        # Short segment oranı
        short_thresh = 0.05
        seg_lengths = [math.hypot(s.x2 - s.x1, s.y2 - s.y1) for s in segments]
        total_segments = len(seg_lengths)
        short_count = sum(1 for L in seg_lengths if L < short_thresh)
        short_ratio = short_count / float(total_segments or 1)

        # Graph metrikleri
        graph = build_graph(segments)
        gm = compute_graph_metrics(graph)
        edge_count = int(gm.get("edge_count") or 0)
        dangling_edges = int(gm.get("dangling_edges_count") or 0)
        closed_cycles = int(gm.get("closed_cycles_count") or 0)
        degree_hist = gm.get("degree_histogram") or {}
        dominant_angles = gm.get("dominant_angles") or {}

        axis0 = int(dominant_angles.get("0") or 0)
        axis90 = int(dominant_angles.get("90") or 0)
        other = int(dominant_angles.get("other") or 0)
        total_edges_for_angle = axis0 + axis90 + other + int(dominant_angles.get("45") or 0) + int(
            dominant_angles.get("135") or 0
        )
        axis_ratio = (axis0 + axis90) / float(total_edges_for_angle or 1)

        cycles_norm = min(1.0, closed_cycles / 4.0)
        low_dangling = 1.0 - (dangling_edges / float(edge_count or 1))

        wall_length_score = math.log(total_len + 1.0)

        score = (
            1.5 * wall_length_score
            + 2.0 * axis_ratio
            + 1.0 * cycles_norm
            + 1.0 * low_dangling
            - 1.0 * short_ratio
        )

        out.append(
            {
                "layer": name,
                "score": round(float(score), 4),
                "metrics": {
                    "total_length_m": round(total_len, 6),
                    "edge_count": edge_count,
                    "dangling_edges_count": dangling_edges,
                    "closed_cycles_count": closed_cycles,
                    "degree_histogram": degree_hist,
                    "dominant_angles": dominant_angles,
                    "short_segment_ratio": round(float(short_ratio), 4),
                },
            }
        )

    out.sort(key=lambda d: (-d["score"], d["layer"]))
    return out


def select_layers(info: dict) -> list[str]:
    """
    Önizleme bilgisinden çizim için kullanılacak katmanları seçer.
    suggested_layers varsa onu kullanır; yoksa total_length'a göre en fazla 2 katman.
    """
    suggested = info.get("suggested_layers") or []
    if suggested:
        return list(suggested)[:5]  # UI ile uyumlu, en fazla 5
    layers = info.get("layers") or {}
    by_length = [
        (name, stats.get("total_length", 0.0))
        for name, stats in layers.items()
        if stats.get("total_length", 0.0) > 0
    ]
    by_length.sort(key=lambda x: (-x[1], x[0]))
    return [name for name, _ in by_length[:2]]


def _resolve_layers(report: dict, info: dict) -> list[str]:
    """
    Önce graph tabanlı layer_graph_scores kullanır; yoksa
    layer_intelligence.selected_layers; o da yoksa select_layers(info) fallback.
    """
    # 1) Graph tabanlı skorlar
    lg = report.get("layer_graph_scores") or []
    if isinstance(lg, list) and lg:
        scored = [x for x in lg if isinstance(x, dict) and "layer" in x and "score" in x]
        if scored:
            scored.sort(key=lambda d: (-float(d["score"]), str(d["layer"])))
            top1 = scored[0]
            selected = [str(top1["layer"])]
            if len(scored) >= 2:
                top2 = scored[1]
                s1 = float(top1["score"])
                s2 = float(top2["score"])
                if s2 > 0.0 and (s1 - s2) < LAYER_GRAPH_TIE_DELTA:
                    selected = [str(top1["layer"]), str(top2["layer"])]
            return selected

    # 2) Mevcut layer_intelligence
    li = report.get("layer_intelligence") or {}
    selected = li.get("selected_layers") or []
    if selected:
        return list(selected)
    # 3) Preview tabanlı fallback
    return select_layers(info)


def layers_for_walls_only(info: dict) -> list[str]:
    """Sadece duvar anahtar kelimesi içeren katmanları döndürür (retry stratejisi)."""
    suggested = info.get("suggested_layers") or []
    if suggested:
        return [n for n in suggested if any(kw in n.lower() for kw in WALL_KEYWORDS)]
    layers = info.get("layers") or {}
    return [
        name for name in layers
        if any(kw in name.lower() for kw in WALL_KEYWORDS)
    ]


def run_stage(name: str, fn, *args, **kwargs):
    """Bir aşamayı çalıştırır, süreyi ms olarak ölçer ve (sonuç, runtime_ms) döner."""
    t0 = time.perf_counter()
    try:
        out = fn(*args, **kwargs)
        return out, (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        return (None, str(e)), (time.perf_counter() - t0) * 1000.0


def run_one(
    dxf_path: Path,
    mode: str = "auto",
    *,
    step_override: float | None = None,
    layers_override: list[str] | None = None,
    units_override: str | None = None,
    optimize_enabled: bool = False,
    centerline_enabled: bool = False,
    path_mode: str = "baseline",
) -> dict:
    """
    Tek bir DXF dosyası için tam pipeline çalıştırır.
    Döner: rapor sözlüğü (result: PASS/WARN/FAIL/PASS_AFTER_RETRY/FAIL_AFTER_RETRY, ...).
    """
    report = {
        "file": str(dxf_path),
        "result": "FAIL",
        "failure_reason": None,
        "recommended_actions": [],
        "dxf_units_detected": None,
        "bbox": None,
        "bbox_size": None,
        "total_length_m": None,
        "selected_layers": None,
        "recommended_step_size_raw": None,
        "final_step_size_used": None,
        "move_count": None,
        "collision_count": None,
        "pen_up_travel_distance": None,
        "analyze_result": None,
        "retry_attempts": [],
        "strategy_succeeded": None,
        "runtime_ms": {},
        "export_roundtrip_ok": None,
        "dwg_convert_runtime_ms": None,
        "dxf_size_bytes": None,
        "error": None,
        "fail_reason_code": None,
        "suite": None,
        "original_total_segments": 0,
        "original_total_length_m": 0.0,
        "post_budget_total_segments": None,
        "post_budget_total_length_m": None,
        "plan_length_m": None,
        "drawn_length_m": 0.0,
        "travel_length_m": 0.0,
        "path_length_m": 0.0,
        "path_overhead": None,
        "shape_retention_plan": None,
        "shape_retention_drawn": None,
        "original_walls_candidate_length_m": 0.0,
        "original_drawable_length_m": 0.0,
        "retention_vs_all": None,
        "retention_vs_walls_candidate": None,
        "retention_vs_drawable": None,
        "segment_budget_applied": False,
        "units_retry_used": False,
        "units_retry_reason": None,
        "units_candidates": None,
        "units_chosen": None,
        "units_retry_metrics": None,
        "dxf_diagnostics": None,
        "layer_intelligence": None,
        "graph_metrics": None,
        "room_candidates_count": None,
        "wall_candidates_count": None,
        "move_count_before_optimize": None,
        "move_count_after_optimize": None,
        "travel_length_before_optimize": None,
        "travel_length_after_optimize": None,
        "path_overhead_before_optimize": None,
        "path_overhead_after_optimize": None,
        "travel_reduction_pct": None,
        "commands_baseline_metrics": None,
        "commands_optimized_metrics": None,
        "optimizer_decision": None,
    }
    report["suite"] = detect_suite(dxf_path)

    try:
        raw = dxf_path.read_bytes()
    except Exception as e:
        report["error"] = str(e)
        report["failure_reason"] = "Dosya okunamadı"
        report["recommended_actions"].append("Dosya yolunu ve encoding'i kontrol edin.")
        return report

    # DWG ise önce DXF'e çevir
    dxf_bytes = raw
    if dxf_path.suffix.lower() == ".dwg":
        try:
            t0 = time.perf_counter()
            dxf_bytes = convert_dwg_bytes_to_dxf_bytes(raw, timeout_seconds=60.0)
            report["dwg_convert_runtime_ms"] = round((time.perf_counter() - t0) * 1000.0, 2)
            report["dxf_size_bytes"] = len(dxf_bytes)
        except DwgConversionError as e:
            report["error"] = str(e)
            report["failure_reason"] = "DWG→DXF dönüştürme hatası"
            report["recommended_actions"].append("DWG dönüştürücü yapılandırmasını (DWG_CONVERTER_PATH) kontrol edin.")
            return report

    # DXF Diagnostics: ham bytes üzerinden yapı analizi (pipeline'ı değiştirmez)
    try:
        report["dxf_diagnostics"] = analyze_dxf_structure(dxf_bytes)
    except Exception:
        report["dxf_diagnostics"] = {}
    # Layer intelligence: diagnostics'tan otomatik katman seçimi
    try:
        diag = report.get("dxf_diagnostics") or {}
        report["layer_intelligence"] = select_plan_layers(diag) if diag else {}
    except Exception:
        report["layer_intelligence"] = {}

    # Graph + geometri tabanlı layer skorları
    try:
        report["layer_graph_scores"] = _compute_layer_graph_scores(dxf_bytes, report.get("dxf_diagnostics"))
    except Exception:
        report["layer_graph_scores"] = []

    # --- Preview ---
    preview_result, rt_preview = run_stage(
        "preview",
        inspect_dxf_layers_bytes,
        dxf_bytes,
        units=units_override,
        scale=None,
        origin=(0.0, 0.0),
    )
    report["runtime_ms"]["preview"] = round(rt_preview, 2)

    if preview_result is None or isinstance(preview_result, tuple):
        err = preview_result[1] if isinstance(preview_result, tuple) else "inspect_dxf_layers hata"
        report["error"] = err
        report["failure_reason"] = "Önizleme hatası"
        report["recommended_actions"].append("DXF ASCII ve ENTITIES bölümüne sahip mi kontrol edin.")
        return report

    info = preview_result
    report["dxf_units_detected"] = info.get("dxf_units_detected")
    report["bbox"] = info.get("bbox")
    if report["bbox"] and len(report["bbox"]) >= 4:
        report["bbox_size"] = [
            report["bbox"][2] - report["bbox"][0],
            report["bbox"][3] - report["bbox"][1],
        ]
    report["total_length_m"] = info.get("total_length")
    _check_units_scale_mismatch(report)

    # Spec: original_* = preprocess sonrası, filtre/budget öncesi
    try:
        all_before, all_stats = get_dxf_all_segments_before_filter(
            dxf_bytes,
            units=units_override,
            scale=None,
            origin=(0.0, 0.0),
        )
        report["original_total_segments"] = len(all_before)
        total_len_all = sum(_seg_len(s) for s in all_before)
        report["original_total_length_m"] = round(total_len_all, 12)
        # Wall-only drawable toplam uzunluk (tüm katmanlar, budget/normalize öncesi)
        # Ezdxf yolunda stats["total_length"] bu değeri zaten metre cinsinden tutar.
        if isinstance(all_stats, dict) and "total_length" in all_stats:
            report["original_drawable_length_m"] = round(float(all_stats.get("total_length") or 0.0), 12)
        else:
            report["original_drawable_length_m"] = report["original_total_length_m"]
    except Exception:
        report["original_total_segments"] = 0
        report["original_total_length_m"] = 0.0
        report["original_drawable_length_m"] = 0.0

    raw_step = preview_recommended_step_size(
        float(info.get("total_length") or 0),
        TARGET_MOVES,
        info.get("bbox"),
    )
    report["recommended_step_size_raw"] = raw_step
    step = _clamp_step(step_override if step_override is not None else raw_step)
    report["final_step_size_used"] = step

    layers = layers_override if layers_override is not None else _resolve_layers(report, info)
    report["selected_layers"] = layers

    if not layers:
        report["failure_reason"] = "Hiç katman seçilemedi"
        report["recommended_actions"].append("DXF'te LINE/LWPOLYLINE/POLYLINE katmanları ekleyin.")
        return report

    # Wall-only candidate (seçilen duvar katmanları) için orijinal toplam uzunluk
    try:
        walls_before, walls_stats = get_dxf_all_segments_before_filter(
            dxf_bytes,
            units=units_override,
            scale=None,
            origin=(0.0, 0.0),
            layer_whitelist=layers,
        )
        total_len_walls = sum(_seg_len(s) for s in walls_before)
        if isinstance(walls_stats, dict) and "total_length" in walls_stats:
            total_len_walls = float(walls_stats.get("total_length") or 0.0)
        report["original_walls_candidate_length_m"] = round(total_len_walls, 12)
    except Exception:
        report["original_walls_candidate_length_m"] = 0.0

    # --- Import (normalize + recenter) ---
    import_result, rt_import = run_stage(
        "import",
        _import_dxf,
        dxf_bytes,
        layers=layers,
        step_size=step,
        units=units_override,
    )
    report["runtime_ms"]["import"] = round(rt_import, 2)

    if import_result is None or (isinstance(import_result, tuple) and len(import_result) == 2 and import_result[0] is None):
        report["error"] = import_result[1] if isinstance(import_result, tuple) else "Import hata"
        report["failure_reason"] = "Import hatası"
        report["recommended_actions"].append("Seçili katmanlarda desteklenen entity var mı kontrol edin.")
        return report

    normalized, norm_warnings = import_result
    if norm_warnings:
        report.setdefault("warnings", []).extend(norm_warnings)
    normalized = enrich_plan_with_graph_metrics(normalized)
    meta = normalized.metadata or {}
    report["graph_metrics"] = meta.get("graph_metrics")
    report["room_candidates_count"] = len(meta.get("room_candidates") or [])
    report["wall_candidates_count"] = len(meta.get("wall_candidates") or [])
    report["room_candidates"] = (meta.get("room_candidates") or [])[:5]
    report["wall_candidates"] = (meta.get("wall_candidates") or [])[:5]

    # Wall centerline: double-wall → tek orta çizgi (isteğe bağlı)
    if centerline_enabled:
        cl_cfg = WallCenterlineConfig()
        normalized, cl_metrics = apply_wall_centerline_to_plan(normalized, cfg=cl_cfg)
        report["centerline_metrics"] = cl_metrics
        report["detected_double_wall_pairs_count"] = cl_metrics.get("detected_double_wall_pairs_count")
        report["centerline_segments_count"] = cl_metrics.get("centerline_segments_count")
        report["dropped_as_non_wall_count"] = cl_metrics.get("dropped_as_non_wall_count")
        report["centerline_success_ratio"] = cl_metrics.get("centerline_success_ratio")
        report["centerline_fallback_used"] = cl_metrics.get("fallback_used")
        report["centerline_fallback_reason"] = cl_metrics.get("fallback_reason")

    # --- Wall filter (gated) ---
    # Filtre öncesi aday uzunluk
    wall_candidate_length = sum(_seg_len(s) for s in normalized.segments)
    report["wall_candidate_length_m"] = round(wall_candidate_length, 12)

    # Filtre uygula
    filtered_plan, wf_metrics = _apply_wall_filter(normalized, snap_tol=WALL_FILTER_SNAP_TOL_M)
    drops = (wf_metrics or {}).get("drops") or {}
    report["wall_filter_drops"] = {
        "short_segment": int(drops.get("short_segment", 0)),
        "small_component": int(drops.get("small_component", 0)),
        "angle_noise": int(drops.get("angle_noise", 0)),
    }
    report["wall_filter_snap_tol_m"] = float(
        (wf_metrics or {}).get("snap_tol_m", WALL_FILTER_SNAP_TOL_M)
    )

    # Gating: filtre öncesi / sonrası path metrikleri
    before_metrics, ok_before = _measure_plan_for_filter(normalized, step)
    after_metrics, ok_after = _measure_plan_for_filter(filtered_plan, step)
    thresholds = {
        "drawn_min_ratio": 0.98,
        "travel_max_ratio": 1.05,
    }
    used = False
    reason = "FILTER_NOT_APPLIED"

    if not ok_after:
        used = False
        reason = "FILTER_PATH_FAILED"
    elif not ok_before:
        # Referans path üretilemediyse, filtreli geometriyi kullan
        used = True
        reason = "UNFILTERED_PATH_FAILED"
    else:
        drawn_before = before_metrics["drawn_length_m"]
        drawn_after = after_metrics["drawn_length_m"]
        travel_before = before_metrics["travel_length_m"]
        travel_after = after_metrics["travel_length_m"]

        if drawn_after < drawn_before * thresholds["drawn_min_ratio"]:
            used = False
            reason = "DRAWN_TOO_LOW"
        elif travel_after > travel_before * thresholds["travel_max_ratio"]:
            used = False
            reason = "TRAVEL_TOO_HIGH"
        else:
            used = True
            reason = "FILTER_OK"

    report["wall_filter_metrics_before"] = before_metrics
    report["wall_filter_metrics_after"] = after_metrics
    report["wall_filter_decision"] = {
        "used": used,
        "reason": reason,
        "thresholds": thresholds,
    }

    # Nihai plan: gating kararı ile seçilen
    normalized_final = filtered_plan if used else normalized
    report["wall_final_length_m"] = round(
        sum(_seg_len(s) for s in normalized_final.segments), 12
    )

    report["post_budget_total_segments"] = len(normalized_final.segments)
    report["post_budget_total_length_m"] = round(
        sum(_seg_len(s) for s in normalized_final.segments), 12
    )
    report["plan_length_m"] = report["post_budget_total_length_m"]
    report["segment_budget_applied"] = bool(
        (normalized_final.metadata or {}).get("extraction_summary", {}).get(
            "segment_budget_applied", False
        )
    )

    # Aşağıdaki aşamalar için seçilen planı kullan
    normalized = normalized_final

    # --- Path (baseline vs graph traversal) ---
    plan = normalized_to_plan(normalized)

    # Her zaman baseline path üret (graph modu için de gating'e referans)
    baseline_result, rt_path = run_stage(
        "path",
        _generate_path,
        plan,
        step_size=step,
    )
    report["runtime_ms"]["path"] = round(rt_path, 2)

    if not baseline_result or (isinstance(baseline_result, tuple) and baseline_result[0] is None):
        report["failure_reason"] = "Yol üretilemedi"
        report["recommended_actions"].append("step_size değerini artırmayı deneyin (Fast mode).")
        return report

    baseline_segments = (
        baseline_result
        if baseline_result and isinstance(baseline_result[0], list)
        else ([baseline_result] if baseline_result else [])
    )
    if not baseline_segments or not baseline_segments[0]:
        report["failure_reason"] = "Yol boş"
        return report

    baseline_commands = compile_path_to_commands_from_segments(baseline_segments, speed=SPEED_DEFAULT)
    baseline_start = (baseline_segments[0][0][0], baseline_segments[0][0][1])
    baseline_dt = measure_drawn_travel(baseline_commands, start_xy=baseline_start)
    baseline_move_count = sum(
        1 for c in baseline_commands if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
    )

    # Varsayılan: baseline path
    commands = baseline_commands
    path_segments = baseline_segments
    start = baseline_start
    dt = baseline_dt

    # Graph tabanlı traversal modu: sadece path_mode == "graph" ise dene
    graph_path_decision = None
    graph_metrics = None
    if path_mode == "graph":
        graph_segments, graph_metrics = generate_graph_traversal_path(normalized, snap_tol=WALL_FILTER_SNAP_TOL_M)
        if graph_segments:
            graph_commands = compile_path_to_commands_from_segments(graph_segments, speed=SPEED_DEFAULT)
            graph_start = (graph_segments[0][0][0], graph_segments[0][0][1])
            graph_dt = measure_drawn_travel(graph_commands, start_xy=graph_start)
            graph_move_count = sum(
                1 for c in graph_commands if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
            )

            # Gating kriterleri (travel ve move)
            baseline_travel = baseline_dt["travel_length_m"]
            graph_travel = graph_dt["travel_length_m"]
            travel_ok = (graph_travel <= baseline_travel * 0.6) or (graph_travel <= 10.0)
            moves_ok = graph_move_count <= baseline_move_count * 1.2

            if travel_ok and moves_ok:
                commands = graph_commands
                path_segments = graph_segments
                start = graph_start
                dt = graph_dt
                graph_path_decision = {
                    "used": True,
                    "reason": "GRAPH_PATH_OK",
                    "baseline_travel_m": round(baseline_travel, 12),
                    "graph_travel_m": round(graph_travel, 12),
                    "baseline_move_count": baseline_move_count,
                    "graph_move_count": graph_move_count,
                }
            else:
                graph_path_decision = {
                    "used": False,
                    "reason": "TRAVEL_OR_MOVES_WORSE",
                    "baseline_travel_m": round(baseline_travel, 12),
                    "graph_travel_m": round(graph_travel, 12),
                    "baseline_move_count": baseline_move_count,
                    "graph_move_count": graph_move_count,
                }
        if graph_metrics is not None:
            report["graph_path_metrics"] = {
                "components_count": int(graph_metrics.get("components_count", 0)),
                "duplicated_edge_length_m": float(graph_metrics.get("duplicated_edge_length_m", 0.0)),
                "traversal_mode_used": graph_metrics.get("traversal_mode_used", "unknown"),
            }
        if graph_path_decision is not None:
            report["graph_path_decision"] = graph_path_decision

    # Component-order path modu: baseline path'i component centroid'lerine göre yeniden sırala
    component_path_decision = None
    component_metrics = None
    if path_mode == "component":
        comp_info = build_components_with_candidates(list(normalized.segments or []), WALL_FILTER_SNAP_TOL_M, k=6)
        centroids = comp_info.get("centroids") or []
        candidates = comp_info.get("candidates") or []
        if centroids and candidates and len(centroids) == len(candidates):
            # Her baseline stroke'ı en yakın component centroid'ine ata
            comp_groups: Dict[int, List[List[Tuple[float, float]]]] = {i: [] for i in range(len(centroids))}
            comp_has_strokes: Dict[int, bool] = {i: False for i in range(len(centroids))}

            def _poly_centroid(poly: List[Tuple[float, float]]) -> Tuple[float, float]:
                sx = sy = 0.0
                n = len(poly)
                for (x, y) in poly:
                    sx += x
                    sy += y
                return (sx / float(n), sy / float(n)) if n > 0 else (0.0, 0.0)

            for poly in baseline_segments:
                cx, cy = _poly_centroid(poly)
                best_idx = 0
                best_d2 = float("inf")
                for idx, (px, py) in enumerate(centroids):
                    dx = cx - px
                    dy = cy - py
                    d2 = dx * dx + dy * dy
                    if d2 < best_d2:
                        best_d2 = d2
                        best_idx = idx
                comp_groups[best_idx].append(poly)
                comp_has_strokes[best_idx] = True

            # Componentler arası mesafe: endpoint adayları üzerinden
            def _comp_cost(a: int, b: int) -> Tuple[float, Tuple[Tuple[float, float], Tuple[float, float]]]:
                cand_a = candidates[a]
                cand_b = candidates[b]
                best_d2 = float("inf")
                best_pair = ((0.0, 0.0), (0.0, 0.0))
                for (ax, ay) in cand_a:
                    for (bx, by) in cand_b:
                        dx = ax - bx
                        dy = ay - by
                        d2 = dx * dx + dy * dy
                        if d2 < best_d2:
                            best_d2 = d2
                            best_pair = ((ax, ay), (bx, by))
                return math.sqrt(best_d2), best_pair

            # Component sırasını endpoint-cost ile nearest-neighbor üzerinden seç
            remaining = [i for i in range(len(centroids)) if comp_has_strokes[i]]
            if len(remaining) > 1:
                order: List[int] = []
                # Başlangıç: orijine en yakın centroid
                start_idx = min(
                    remaining,
                    key=lambda i: centroids[i][0] * centroids[i][0] + centroids[i][1] * centroids[i][1],
                )
                order.append(start_idx)
                remaining_set = set(remaining)
                remaining_set.remove(start_idx)
                while remaining_set:
                    last = order[-1]
                    best_j = None
                    best_cost = float("inf")
                    for j in remaining_set:
                        cost, _ = _comp_cost(last, j)
                        if cost < best_cost:
                            best_cost = cost
                            best_j = j
                    order.append(best_j)  # type: ignore[arg-type]
                    remaining_set.remove(best_j)  # type: ignore[arg-type]
            else:
                order = remaining

            # Yeni path: component sırasına göre stroke'ları diz
            reordered_segments: List[List[Tuple[float, float]]] = []
            for idx in order:
                reordered_segments.extend(comp_groups[idx])

            if reordered_segments:
                comp_commands = compile_path_to_commands_from_segments(reordered_segments, speed=SPEED_DEFAULT)
                comp_start = (reordered_segments[0][0][0], reordered_segments[0][0][1])
                comp_dt = measure_drawn_travel(comp_commands, start_xy=comp_start)
                comp_move_count = sum(
                    1 for c in comp_commands if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
                )

                # Component geçişleri için candidate entry/exit çiftleri ve toplam pen-up mesafesi
                transitions: List[Dict[str, object]] = []
                pen_up_between = 0.0
                if len(order) > 1:
                    for i in range(len(order) - 1):
                        a = order[i]
                        b = order[i + 1]
                        dist, pair = _comp_cost(a, b)
                        pen_up_between += dist
                        transitions.append(
                            {
                                "from_component": int(a),
                                "to_component": int(b),
                                "from_point": [round(pair[0][0], 6), round(pair[0][1], 6)],
                                "to_point": [round(pair[1][0], 6), round(pair[1][1], 6)],
                                "distance_m": round(dist, 6),
                            }
                        )

                # Gating kriterleri
                baseline_travel = baseline_dt["travel_length_m"]
                comp_travel = comp_dt["travel_length_m"]
                travel_ok = (comp_travel <= baseline_travel * 0.9) or (comp_travel <= 10.0)

                if travel_ok:
                    commands = comp_commands
                    path_segments = reordered_segments
                    start = comp_start
                    dt = comp_dt
                    component_path_decision = {
                        "used": True,
                        "reason": "COMPONENT_PATH_OK",
                        "baseline_travel_m": round(baseline_travel, 12),
                        "component_travel_m": round(comp_travel, 12),
                        "baseline_move_count": baseline_move_count,
                        "component_move_count": comp_move_count,
                    }
                else:
                    component_path_decision = {
                        "used": False,
                        "reason": "TRAVEL_TOO_HIGH",
                        "baseline_travel_m": round(baseline_travel, 12),
                        "component_travel_m": round(comp_travel, 12),
                        "baseline_move_count": baseline_move_count,
                        "component_move_count": comp_move_count,
                    }

                # Component metrikleri
                lengths: List[float] = []
                for idx in order:
                    polys = comp_groups[idx]
                    if not polys:
                        continue
                    comp_len = 0.0
                    for poly in polys:
                        for i in range(1, len(poly)):
                            x1, y1 = poly[i - 1]
                            x2, y2 = poly[i]
                            comp_len += math.hypot(x2 - x1, y2 - y1)
                    lengths.append(comp_len)
                avg_len = sum(lengths) / len(lengths) if lengths else 0.0
                reduction_pct = 0.0
                if baseline_travel > 0:
                    reduction_pct = (1.0 - comp_travel / baseline_travel) * 100.0

                component_metrics = {
                    "component_count": len(order),
                    "avg_component_length_m": round(avg_len, 6),
                    "pen_up_between_components_distance_m": round(pen_up_between, 6),
                    "baseline_travel_length_m": round(baseline_travel, 12),
                    "component_travel_length_m": round(comp_travel, 12),
                    "component_order_travel_reduction_pct": round(reduction_pct, 2),
                    "transitions": transitions,
                }

    if component_metrics is not None:
        report["component_path_metrics"] = component_metrics
    if component_path_decision is not None:
        report["component_path_decision"] = component_path_decision

    dt = measure_drawn_travel(commands, start_xy=start)
    report["drawn_length_m"] = dt["drawn_length_m"]
    report["travel_length_m"] = dt["travel_length_m"]
    report["path_length_m"] = dt["path_length_m"]
    report["path_overhead"] = dt["path_overhead"]
    report["pen_up_travel_distance"] = round(dt["travel_length_m"], 6)

    if optimize_enabled:
        # Baz çizgi metrikleri (gerçek yürütülen komutlar)
        baseline_metrics = measure_drawn_travel(commands, start_xy=start)
        move_count_before = sum(
            1 for c in commands if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
        )

        # Optimize edilmiş aday komutlar (travel fallback kararı bu fonksiyonda verilir)
        cfg = OptimizeConfig(enabled=True, require_travel_improvement=False)
        commands_opt = optimize_commands(commands, start, cfg)
        candidate_metrics = measure_drawn_travel(commands_opt, start_xy=start)
        move_count_after = sum(
            1 for c in commands_opt if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
        )

        report["commands_baseline_metrics"] = baseline_metrics
        report["commands_optimized_metrics"] = candidate_metrics
        report["move_count_before_optimize"] = move_count_before
        report["move_count_after_optimize"] = move_count_after
        report["travel_length_before_optimize"] = round(baseline_metrics["travel_length_m"], 12)
        report["travel_length_after_optimize"] = round(candidate_metrics["travel_length_m"], 12)
        report["path_overhead_before_optimize"] = baseline_metrics["path_overhead"]
        report["path_overhead_after_optimize"] = candidate_metrics["path_overhead"]

        if baseline_metrics["travel_length_m"] > 0:
            report["travel_reduction_pct"] = round(
                (1.0 - candidate_metrics["travel_length_m"] / baseline_metrics["travel_length_m"]) * 100.0,
                2,
            )
        else:
            report["travel_reduction_pct"] = 0.0

        # Karar: travel iyileşiyorsa optimize edilmiş komutları kullan, yoksa fallback
        if candidate_metrics["travel_length_m"] < baseline_metrics["travel_length_m"]:
            commands = commands_opt
            dt = candidate_metrics
            report["optimizer_decision"] = {
                "used": True,
                "reason": "TRAVEL_IMPROVED",
            }
        else:
            # Travel kötüleşti; baseline komutları koru
            dt = baseline_metrics
            report["optimizer_decision"] = {
                "used": False,
                "reason": "TRAVEL_WORSE_FALLBACK",
            }

    orig_m = max(report["original_total_length_m"] or 0.0, EPS)
    report["shape_retention_plan"] = round((report["plan_length_m"] or 0.0) / orig_m, 6)
    report["shape_retention_drawn"] = round(report["drawn_length_m"] / orig_m, 6)

    # Yeni retention metrikleri
    orig_walls = report.get("original_walls_candidate_length_m") or 0.0
    orig_drawable = report.get("original_drawable_length_m") or 0.0

    report["retention_vs_all"] = round(report["drawn_length_m"] / orig_m, 6) if orig_m > 0 else None
    report["retention_vs_walls_candidate"] = (
        round(report["drawn_length_m"] / orig_walls, 6) if orig_walls > 0 else None
    )
    report["retention_vs_drawable"] = (
        round(report["drawn_length_m"] / orig_drawable, 6) if orig_drawable > 0 else None
    )
    if not dt["has_pen_down"]:
        report["fail_reason_code"] = "NO_PEN_DOWN_COMMANDS"
        report["failure_reason"] = "Hiç PEN DOWN komutu yok"
        report["recommended_actions"].append("Path/compiler çıktısında PEN DOWN üretildiğini kontrol edin.")
        report["result"] = "FAIL"
        return report

    analyze_result, rt_analyze = run_stage(
        "analyze",
        analyze_commands,
        commands,
        start,
        limits=ScenarioLimits(),
    )
    report["runtime_ms"]["analyze"] = round(rt_analyze, 2)

    if analyze_result is None or (
        isinstance(analyze_result, tuple)
        and len(analyze_result) == 2
        and analyze_result[0] is None
        and isinstance(analyze_result[1], str)
    ):
        report["analyze_result"] = "ERROR"
        report["failure_reason"] = "Analiz istisnası"
        return report

    stats, diags = analyze_result
    report["move_count"] = stats.move_count
    report["collision_count"] = getattr(stats, "collision_count", 0)
    blocked = any(d.severity == "ERROR" for d in diags)
    report["analyze_result"] = "BLOCKED" if blocked else "SAFE"

    # --- Export + roundtrip ---
    export_result, rt_export = run_stage(
        "export",
        export_commands_to_string,
        commands,
        start,
        limits=ScenarioLimits(),
    )
    report["runtime_ms"]["export"] = round(rt_export, 2)

    if export_result is None or (
        isinstance(export_result, tuple)
        and len(export_result) >= 2
        and export_result[0] is None
    ):
        report["failure_reason"] = "Export hatası"
        return report

    content_out, blocked_export, _stats2, _diags2 = export_result
    report["export_roundtrip_ok"] = False
    if content_out and content_out.strip():
        # Roundtrip: gövde satırlarını parse et (yorum satırlarını atla)
        body_lines = [
            line for line in content_out.splitlines()
            if line.strip() and not line.strip().startswith(";")
        ]
        body = "\n".join(body_lines)
        try:
            parsed, parse_diags = parse_commands(body, strict=False)
            report["export_roundtrip_ok"] = len(parsed) > 0 and not any(d.severity == "ERROR" for d in parse_diags)
        except Exception:
            pass

    if blocked or blocked_export:
        report["result"] = "FAIL"
        report["fail_reason_code"] = "LIMITS_EXCEEDED"
        report["failure_reason"] = "BLOCKED (limit aşımı veya analiz hatası)"
        report["recommended_actions"].extend([
            "Step artırın (Fast mode): step = min(mevcut*2, 0.50)",
            "Sadece duvar katmanlarını deneyin (Walls only).",
            "Step azaltın (Detail): step = max(mevcut*0.75, 0.05)",
        ])
        return report

    # Eşikler (WARN)
    warn_moves = 40000
    warn_collisions = 100
    if stats.move_count > warn_moves or report["collision_count"] > warn_collisions:
        report["result"] = "WARN"
        report["failure_reason"] = "Metrikler eşiği aştı (çok hareket veya çakışma)"
        report["recommended_actions"].append("Step size veya katman seçimini iyileştirin.")
    else:
        report["result"] = "PASS"

    # Spec: SEGMENT_BUDGET_TRUNCATED_TOO_MUCH — suite A/B = FAIL, C = WARN
    budget_applied = report.get("segment_budget_applied", False)
    r_plan = report.get("shape_retention_plan") or 0.0
    r_drawn = report.get("shape_retention_drawn") or 0.0
    if budget_applied and (r_plan < RETENTION_PLAN_FAIL or r_drawn < RETENTION_DRAWN_FAIL):
        report["fail_reason_code"] = "SEGMENT_BUDGET_TRUNCATED_TOO_MUCH"
        report["recommended_actions"].extend([
            "segment_budget artır",
            "detail mod dene",
            "toleransı düşür",
            "Daha az katman seçerek tekrar dene",
        ])
        suite = report.get("suite")
        if suite == "C":
            report["result"] = "WARN"
        else:
            report["result"] = "FAIL"
            report["failure_reason"] = "Segment bütçesi çok fazla geometri kesti (retention düşük)"

    return report


def _import_dxf(
    dxf_bytes: bytes,
    *,
    layers: list[str],
    step_size: float,
    units: str | None = None,
) -> tuple:
    """DXF içeriğini import eder, normalize + recenter uygular. (normalized, warnings) döner."""
    normalized = dxf_bytes_to_normalized_plan(
        dxf_bytes,
        units=units,
        scale=None,
        origin=(0.0, 0.0),
        layer_whitelist=layers,
        layer_blacklist=None,
    )
    opts = NormalizeOptions(recenter=True, recenter_mode="center")
    normalized, warnings = normalize_plan(normalized, opts)
    return (normalized, warnings)


def _generate_path(plan, step_size: float):
    """Plan için segment bazlı yol üretir (her segment = bir duvar, pen-up travel ayrışır)."""
    pg = PathGenerator(plan, step_size=step_size, order_walls=True)
    return pg.generate_path_segments()


def _measure_plan_for_filter(normalized_plan, step_size: float) -> tuple[dict, bool]:
    """
    Wall filter gating için path üretip temel metrikleri ölçer.
    Döner: (metrics, ok_flag)
    """
    try:
        plan = normalized_to_plan(normalized_plan)
        path_segments = _generate_path(plan, step_size=step_size)
        if not path_segments or not path_segments[0]:
            return {
                "drawn_length_m": 0.0,
                "travel_length_m": 0.0,
                "path_overhead": 0.0,
                "move_count": 0,
            }, False
        commands = compile_path_to_commands_from_segments(path_segments, speed=SPEED_DEFAULT)
        start = (path_segments[0][0][0], path_segments[0][0][1])
        dt = measure_drawn_travel(commands, start_xy=start)
        move_count = sum(
            1 for c in commands if isinstance(c, (MoveCommand, MoveRelCommand, ForwardCommand))
        )
        return {
            "drawn_length_m": dt["drawn_length_m"],
            "travel_length_m": dt["travel_length_m"],
            "path_overhead": dt["path_overhead"],
            "move_count": move_count,
        }, True
    except Exception:
        return {
            "drawn_length_m": 0.0,
            "travel_length_m": 0.0,
            "path_overhead": 0.0,
            "move_count": 0,
        }, False


def _apply_wall_filter(normalized_plan, *, snap_tol: float = WALL_FILTER_SNAP_TOL_M):
    """Geriye dönük uyum için app.analysis.wall_filter.apply_wall_filter wrapper'ı."""
    return apply_wall_filter(normalized_plan, snap_tol=snap_tol)


def run_retries(
    dxf_path: Path,
    content: str,
    report: dict,
    info_preview: dict,
    mode: str,
    optimize_enabled: bool = False,
    centerline_enabled: bool = False,
    path_mode: str = "baseline",
) -> dict:
    """
    BLOCKED durumunda UI ile aynı fallback stratejilerini dener.
    Döner: güncellenmiş rapor (result: PASS_AFTER_RETRY veya FAIL_AFTER_RETRY).
    """
    step = _clamp_step(report.get("recommended_step_size_raw"))
    layers = report.get("selected_layers") or select_layers(info_preview)

    strategies = [
        ("fast", {"step_override": min(step * 2, STEP_MAX), "layers_override": None}),
        ("walls_only", {"step_override": step, "layers_override": layers_for_walls_only(info_preview) or layers}),
        ("detail", {"step_override": max(step * 0.75, STEP_MIN), "layers_override": None}),
    ]

    for strategy_name, overrides in strategies:
        report = run_one(
            dxf_path,
            mode,
            step_override=overrides.get("step_override"),
            layers_override=overrides.get("layers_override"),
            optimize_enabled=optimize_enabled,
            centerline_enabled=centerline_enabled,
            path_mode=path_mode,
        )
        report["retry_attempts"] = report.get("retry_attempts", [])
        report["retry_attempts"].append({"strategy": strategy_name, "result": report["result"]})

        if report["result"] == "PASS" or report["result"] == "WARN":
            report["result"] = "PASS_AFTER_RETRY"
            report["strategy_succeeded"] = strategy_name
            return report

    report["result"] = "FAIL_AFTER_RETRY"
    report["strategy_succeeded"] = None
    return report


def collect_dxf_paths(input_path: Path, suite_filter: str | None) -> list[Path]:
    """Tek dosya veya klasör içindeki .dxf/.dwg dosyalarını toplar. suite_filter A|B|C|REAL|ALL."""
    if input_path.is_file():
        if input_path.suffix.lower() in (".dxf", ".dwg"):
            if suite_filter and suite_filter != "ALL":
                su = detect_suite(input_path)
                if su != suite_filter:
                    return []
            return [input_path]
        return []
    if input_path.is_dir():
        paths = sorted(
            (p for p in input_path.rglob("*") if p.suffix.lower() in (".dxf", ".dwg")),
            key=lambda p: str(p),
        )
        if suite_filter and suite_filter != "ALL":
            paths = [p for p in paths if detect_suite(p) == suite_filter]
        return paths
    return []


def write_dxf_diagnostics_report(reports: list[dict], out_dir: Path) -> None:
    """
    Benchmark raporlarındaki dxf_diagnostics verilerinden DXF_DIAGNOSTICS_REPORT.md üretir.
    İçerik: en yaygın entity türleri, layer yapısı, sorun çıkaran türler, units retry, karmaşıklık.
    """
    from collections import Counter

    report_path = out_dir / "DXF_DIAGNOSTICS_REPORT.md"
    lines: list[str] = [
        "# DXF Diagnostics Raporu",
        "",
        f"Bu rapor {len(reports)} dosya üzerinden üretilmiştir.",
        "",
    ]

    # Sadece dxf_diagnostics dolu raporlar
    with_diag = [r for r in reports if r.get("dxf_diagnostics") and isinstance(r.get("dxf_diagnostics"), dict)]
    if not with_diag:
        lines.extend(["Hiçbir dosyada `dxf_diagnostics` verisi yok.", ""])
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return

    # --- 1. Entity türleri toplamları ---
    entity_totals: Counter = Counter()
    for r in with_diag:
        counts = (r.get("dxf_diagnostics") or {}).get("entity_counts") or {}
        for k, v in (counts if isinstance(counts, dict) else {}).items():
            entity_totals[k] += int(v) if isinstance(v, (int, float)) else 0

    lines.append("## 1. En yaygın entity türleri (toplam)")
    lines.append("")
    if entity_totals:
        for name, count in entity_totals.most_common():
            lines.append(f"- **{name}**: {count}")
    else:
        lines.append("Veri yok.")
    lines.append("")

    # --- 2. Layer yapısı (örnek: en sık görülen layer isimleri ve entity türleri) ---
    layer_names: Counter = Counter()
    layer_entity_types: dict[str, set[str]] = {}
    for r in with_diag:
        layers = (r.get("dxf_diagnostics") or {}).get("layers") or []
        if not isinstance(layers, list):
            continue
        for ly in layers:
            if not isinstance(ly, dict):
                continue
            name = ly.get("name") or ly.get("layer_name")
            if name:
                layer_names[name] += 1
                types = ly.get("entity_types") or []
                if isinstance(types, list):
                    key = name
                    if key not in layer_entity_types:
                        layer_entity_types[key] = set()
                    for t in types:
                        layer_entity_types[key].add(str(t))

    lines.append("## 2. En yaygın layer yapısı (layer isimleri)")
    lines.append("")
    if layer_names:
        for name, count in layer_names.most_common(20):
            types_str = ", ".join(sorted(layer_entity_types.get(name, [])))[:60]
            lines.append(f"- **{name}**: {count} dosyada | entity türleri: {types_str or '-'}")
    else:
        lines.append("Veri yok.")
    lines.append("")

    # --- 3. Sorun çıkaran entity türleri (spline, hatch, block) ---
    problem_files: dict[str, list[str]] = {"has_many_splines": [], "has_many_hatches": [], "has_many_blocks": []}
    for r in with_diag:
        diag = r.get("dxf_diagnostics") or {}
        flags = diag.get("diagnostics_flags") or []
        if not isinstance(flags, list):
            continue
        fname = Path(r.get("file") or "").name
        for flag in flags:
            if flag in problem_files:
                problem_files[flag].append(fname)

    lines.append("## 3. En çok sorun çıkaran entity türleri (spline, hatch, block)")
    lines.append("")
    for key, label in [
        ("has_many_splines", "Çok spline içeren dosyalar"),
        ("has_many_hatches", "Çok hatch içeren dosyalar"),
        ("has_many_blocks", "Çok block (INSERT) içeren dosyalar"),
    ]:
        files = problem_files.get(key, [])
        lines.append(f"### {label}")
        if files:
            for f in files[:30]:
                lines.append(f"- {f}")
            if len(files) > 30:
                lines.append(f"- ... ve {len(files) - 30} dosya daha")
        else:
            lines.append("Yok.")
        lines.append("")

    # --- 4. Units retry kullanılan dosyalar ---
    units_retry_files = [Path(r.get("file") or "").name for r in reports if r.get("units_retry_used")]
    lines.append("## 4. Units retry kullanılan dosyalar")
    lines.append("")
    if units_retry_files:
        for f in units_retry_files:
            lines.append(f"- {f}")
        lines.append("")
        lines.append(f"Toplam: {len(units_retry_files)} dosya.")
    else:
        lines.append("Units retry kullanılan dosya yok.")
    lines.append("")

    # --- 5. Geometri karmaşıklığı ---
    total_entities_list: list[int] = []
    total_layers_list: list[int] = []
    total_segments_list: list[int] = []
    spline_counts: list[int] = []
    hatch_counts: list[int] = []
    insert_counts: list[int] = []
    for r in with_diag:
        diag = r.get("dxf_diagnostics") or {}
        comp = diag.get("complexity") or {}
        if isinstance(comp, dict):
            total_entities_list.append(int(comp.get("total_entities") or 0))
            total_layers_list.append(int(comp.get("total_layers") or 0))
            total_segments_list.append(int(comp.get("total_segments_after_flatten") or 0))
            spline_counts.append(int(comp.get("spline_count") or 0))
            hatch_counts.append(int(comp.get("hatch_count") or 0))
            insert_counts.append(int(comp.get("insert_count") or 0))

    def _avg(lst: list) -> float:
        return sum(lst) / len(lst) if lst else 0.0

    lines.append("## 5. Geometri karmaşıklığı analizi")
    lines.append("")
    lines.append("| Metrik | Min | Max | Ortalama |")
    lines.append("|--------|-----|-----|----------|")
    if total_entities_list:
        lines.append(f"| total_entities | {min(total_entities_list)} | {max(total_entities_list)} | {_avg(total_entities_list):.1f} |")
    if total_layers_list:
        lines.append(f"| total_layers | {min(total_layers_list)} | {max(total_layers_list)} | {_avg(total_layers_list):.1f} |")
    if total_segments_list:
        lines.append(f"| total_segments_after_flatten | {min(total_segments_list)} | {max(total_segments_list)} | {_avg(total_segments_list):.1f} |")
    if spline_counts:
        lines.append(f"| spline_count | {min(spline_counts)} | {max(spline_counts)} | {_avg(spline_counts):.1f} |")
    if hatch_counts:
        lines.append(f"| hatch_count | {min(hatch_counts)} | {max(hatch_counts)} | {_avg(hatch_counts):.1f} |")
    if insert_counts:
        lines.append(f"| insert_count | {min(insert_counts)} | {max(insert_counts)} | {_avg(insert_counts):.1f} |")
    if not any([total_entities_list, total_layers_list]):
        lines.append("Veri yok.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def write_layer_intelligence_report(reports: list[dict], out_dir: Path) -> None:
    """
    layer_intelligence verilerinden LAYER_INTELLIGENCE_REPORT.md üretir.
    İçerik: en sık seçilen layer isimleri, layer selection başarı/fallback sayıları.
    """
    from collections import Counter

    report_path = out_dir / "LAYER_INTELLIGENCE_REPORT.md"
    lines: list[str] = [
        "# Layer Intelligence Raporu",
        "",
        f"Bu rapor {len(reports)} dosya üzerinden üretilmiştir.",
        "",
    ]

    # Layer intelligence ile seçilen vs fallback
    n_with_li = 0
    n_fallback = 0
    selected_layer_names: list[str] = []
    for r in reports:
        li = r.get("layer_intelligence") or {}
        sel = li.get("selected_layers") or []
        if sel:
            n_with_li += 1
            selected_layer_names.extend(sel)
        else:
            n_fallback += 1

    lines.append("## 1. En sık seçilen layer isimleri")
    lines.append("")
    if selected_layer_names:
        for name, count in Counter(selected_layer_names).most_common(20):
            lines.append(f"- **{name}**: {count} dosyada")
    else:
        lines.append("Veri yok.")
    lines.append("")

    lines.append("## 2. Layer selection başarı oranı")
    lines.append("")
    lines.append(f"- **Layer intelligence ile seçilen**: {n_with_li} dosya (skorlanan katmanlardan otomatik seçim)")
    lines.append(f"- **Fallback kullanılan**: {n_fallback} dosya (suggested_layers / total_length ile seçim)")
    total = len(reports)
    if total:
        pct = round(100.0 * n_with_li / total, 1)
        lines.append(f"- **Oran**: {n_with_li}/{total} ({pct}%) dosyada otomatik katman seçildi.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Not: Daha iyi seçim için graph connectivity veya contour detection eklenebilir; şu an entity türü, uzunluk ve layer isim heuristiği kullanılıyor.*")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def write_graph_report(reports: list[dict], out_dir: Path) -> None:
    """
    graph_metrics verilerinden GRAPH_REPORT.md üretir.
    En yüksek intersection/dangling/cycle sayıları, room örnekleri, örnek dosya metrik açıklaması.
    """
    report_path = out_dir / "GRAPH_REPORT.md"
    lines: list[str] = [
        "# Geometry Graph Raporu",
        "",
        f"Bu rapor {len(reports)} dosya üzerinden üretilmiştir.",
        "",
    ]

    with_metrics = [r for r in reports if r.get("graph_metrics") and isinstance(r.get("graph_metrics"), dict)]
    if not with_metrics:
        lines.append("Hiçbir dosyada `graph_metrics` verisi yok.")
        report_path.write_text("\n".join(lines), encoding="utf-8")
        return

    # En yüksek intersection_count
    by_intersection = sorted(
        [(Path(r.get("file") or "").name, (r.get("graph_metrics") or {}).get("intersection_count", 0)) for r in with_metrics],
        key=lambda x: (-x[1], x[0]),
    )[:10]
    lines.append("## 1. En yüksek kavşak sayısı (intersection_count)")
    lines.append("")
    for fname, count in by_intersection:
        lines.append(f"- **{fname}**: {count}")
    lines.append("")

    # En yüksek dangling_edges_count
    by_dangling = sorted(
        [(Path(r.get("file") or "").name, (r.get("graph_metrics") or {}).get("dangling_edges_count", 0)) for r in with_metrics],
        key=lambda x: (-x[1], x[0]),
    )[:10]
    lines.append("## 2. En yüksek sarkan kenar sayısı (dangling_edges_count)")
    lines.append("")
    for fname, count in by_dangling:
        lines.append(f"- **{fname}**: {count}")
    lines.append("")

    # En yüksek closed_cycles_count
    by_cycles = sorted(
        [(Path(r.get("file") or "").name, (r.get("graph_metrics") or {}).get("closed_cycles_count", 0)) for r in with_metrics],
        key=lambda x: (-x[1], x[0]),
    )[:10]
    lines.append("## 3. En yüksek döngü sayısı (closed_cycles_count)")
    lines.append("")
    for fname, count in by_cycles:
        lines.append(f"- **{fname}**: {count}")
    lines.append("")

    # Room candidates örnekleri (ilk dosyadan)
    lines.append("## 4. Oda konturu adayları (örnek)")
    lines.append("")
    sample_with_rooms = next((r for r in with_metrics if (r.get("room_candidates_count") or 0) > 0), None)
    if sample_with_rooms and (sample_with_rooms.get("room_candidates") or []):
        fname = Path(sample_with_rooms.get("file") or "").name
        lines.append(f"Dosya: **{fname}** — ilk birkaç oda adayı:")
        for i, room in enumerate((sample_with_rooms.get("room_candidates") or [])[:5]):
            lines.append(f"- Aday {i+1}: perimeter={room.get('perimeter')} m, vertex_count={room.get('vertex_count')}, bbox={room.get('bbox')}")
    else:
        lines.append("Bu run'da oda adayı bulunan dosya yok veya liste boş.")
    lines.append("")

    # Örnek dosya: graph metrikleri açıklamalı (ilk dosya)
    lines.append("## 5. Örnek dosya — graph metrikleri açıklaması")
    lines.append("")
    ex = with_metrics[0]
    fname = Path(ex.get("file") or "").name
    gm = ex.get("graph_metrics") or {}
    lines.append(f"Dosya: **{fname}**")
    lines.append("")
    lines.append("| Metrik | Değer | Açıklama |")
    lines.append("|--------|-------|----------|")
    lines.append(f"| node_count | {gm.get('node_count', '-')} | Graf düğüm sayısı (snap sonrası benzersiz uç noktalar) |")
    lines.append(f"| edge_count | {gm.get('edge_count', '-')} | Kenar sayısı |")
    lines.append(f"| connected_components_count | {gm.get('connected_components_count', '-')} | Bağlantılı bileşen sayısı |")
    lines.append(f"| degree_histogram | {gm.get('degree_histogram', {})} | 0/1/2/3+ uçlu düğüm dağılımı |")
    lines.append(f"| intersection_count | {gm.get('intersection_count', '-')} | Derecesi ≥3 olan kavşak sayısı |")
    lines.append(f"| dangling_edges_count | {gm.get('dangling_edges_count', '-')} | Ucu serbest (degree=1) kenar sayısı |")
    lines.append(f"| closed_cycles_count | {gm.get('closed_cycles_count', '-')} | Cyclomatic döngü sayısı (E−V+C) |")
    lines.append(f"| edge_length_stats | {gm.get('edge_length_stats', {})} | min/median/p95 kenar uzunluğu (m) |")
    lines.append(f"| dominant_angles | {gm.get('dominant_angles', {})} | 0°/90°/45°/135°/diğer açı dağılımı |")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DXF çizilebilirlik doğrulama: yükleme → önizleme → import → analiz → export.",
    )
    parser.add_argument("--input", "-i", required=True, help="DXF/DWG dosyası veya klasör yolu")
    parser.add_argument("--out", "-o", default="current", help="Rapor run adı; çıktı backend/reports/<out>/")
    parser.add_argument(
        "--suite",
        choices=["A", "B", "C", "REAL", "ALL"],
        default="ALL",
        help=(
            "Suite: A=A_expected_pass, B=B_realistic, C=C_stress, REAL=benchmarks/real_world, ALL=hepsi"
        ),
    )
    parser.add_argument("--mode", default="auto", choices=["auto"], help="Çalışma modu (şimdilik sadece auto)")
    parser.add_argument("--optimize", choices=["none", "on"], default="none",
                        help="Path optimize: none (varsayılan) veya on (pen-up travel azaltır)")
    parser.add_argument(
        "--path-mode",
        choices=["baseline", "component", "graph"],
        default="baseline",
        help=(
            "Path üretim modu: baseline (mevcut PathGenerator), "
            "component (component centroid'lerini optimize ederek sıralama) "
            "veya graph (duvar grafı tabanlı traversal)."
        ),
    )
    parser.add_argument(
        "--centerline",
        choices=["off", "on"],
        default="off",
        help="Double-line duvarlardan orta çizgi çıkar (on) veya mevcut duvar-only segmentleri kullan (off).",
    )
    parser.add_argument("--fail-on-warn", action="store_true", help="WARN sonucunu da hata say (çıkış kodu 1)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Hata: Girdi bulunamadı: {input_path}", file=sys.stderr)
        return 1

    paths = collect_dxf_paths(input_path, suite_filter=args.suite)
    if not paths:
        print("Hiç .dxf veya .dwg dosyası bulunamadı (veya suite filtresine uymuyor).", file=sys.stderr)
        return 1

    # Çıktı: backend/reports/<out>/summary.json, backend/reports/<out>/files/<file>.json
    _repo_root = _backend_root.parent
    out_dir = _repo_root / "backend" / "reports" / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    files_dir = out_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict] = []
    centerline_enabled = args.centerline == "on"
    for dxf_path in paths:
        report = run_one(
            dxf_path,
            args.mode,
            optimize_enabled=(args.optimize == "on"),
            centerline_enabled=centerline_enabled,
            path_mode=args.path_mode,
        )
        if report["result"] == "FAIL" and report.get("analyze_result") == "BLOCKED":
            try:
                raw = dxf_path.read_bytes()
                info_preview = inspect_dxf_layers_bytes(raw, units=None, scale=None, origin=(0.0, 0.0))
            except Exception:
                info_preview = {}
            report = run_retries(
                dxf_path,
                "",
                report,
                info_preview,
                args.mode,
                optimize_enabled=(args.optimize == "on"),
                centerline_enabled=centerline_enabled,
                path_mode=args.path_mode,
            )
        # Units auto-retry: mismatch + dosya birimi "m" ise units=mm ile tekrar dene, daha iyi sonucu seç
        if report.get("units_scale_mismatch") and report.get("dxf_units_detected") == "m":
            report_mm = run_one(
                dxf_path,
                args.mode,
                units_override="mm",
                optimize_enabled=(args.optimize == "on"),
                centerline_enabled=centerline_enabled,
                path_mode=args.path_mode,
            )
            report = _merge_units_retry_report(report, report_mm)
        # MVP scope sınıflandırması
        report["scope_class"] = _classify_scope(report)
        reports.append(report)
        safe_name = dxf_path.stem.replace(" ", "_")
        with open(files_dir / f"{safe_name}.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # final_result: FAIL_AFTER_RETRY -> FAIL; PASS_AFTER_RETRY -> PASS veya WARN (mevcut result korunur)
    def _final_result(r: dict) -> str:
        res = r["result"]
        if res == "FAIL_AFTER_RETRY":
            return "FAIL"
        if res == "PASS_AFTER_RETRY":
            return "PASS"  # retry sonrası zaten PASS/WARN idi, indirgeme için PASS say
        return res

    by_suite: dict[str, dict] = {}
    in_scope_total = 0
    in_scope_pass = 0
    in_scope_warn = 0
    in_scope_fail = 0
    in_scope_retention_walls: list[float] = []
    in_scope_path_overhead: list[float] = []
    out_scope_total = 0
    out_scope_by_class: dict[str, int] = {}

    for r in reports:
        su = r.get("suite") or "OTHER"
        if su not in by_suite:
            by_suite[su] = {"PASS": 0, "WARN": 0, "FAIL": 0, "retention_plan": [], "retention_drawn": []}
        fr = _final_result(r)
        by_suite[su][fr] += 1
        if r.get("shape_retention_plan") is not None:
            by_suite[su]["retention_plan"].append(r["shape_retention_plan"])
        if r.get("shape_retention_drawn") is not None:
            by_suite[su]["retention_drawn"].append(r["shape_retention_drawn"])

        scope = r.get("scope_class")
        if scope == SCOPE_SUPPORTED:
            in_scope_total += 1
            if fr == "PASS":
                in_scope_pass += 1
            elif fr == "WARN":
                in_scope_warn += 1
            elif fr == "FAIL":
                in_scope_fail += 1
            rvw = r.get("retention_vs_walls_candidate")
            if rvw is not None:
                try:
                    in_scope_retention_walls.append(float(rvw))
                except Exception:
                    pass
            poh = r.get("path_overhead")
            if poh is not None:
                try:
                    in_scope_path_overhead.append(float(poh))
                except Exception:
                    pass
        else:
            out_scope_total += 1
            key = scope or SCOPE_OTHER
            out_scope_by_class[key] = out_scope_by_class.get(key, 0) + 1

    budget_too_much_loss_count_C = sum(
        1 for r in reports
        if r.get("suite") == "C" and r.get("fail_reason_code") == "SEGMENT_BUDGET_TRUNCATED_TOO_MUCH"
    )
    fail_code_counts: dict[str, int] = {}
    for r in reports:
        code = r.get("fail_reason_code")
        if code:
            fail_code_counts[code] = fail_code_counts.get(code, 0) + 1
    fail_reason_codes_top = sorted(
        [{"code": k, "count": v} for k, v in fail_code_counts.items()],
        key=lambda x: (-x["count"], x["code"]),
    )[:TOP_FAIL_REASON_CODES]

    for su, data in by_suite.items():
        rp = data.get("retention_plan") or []
        rd = data.get("retention_drawn") or []
        rp_s = sorted(rp)
        rd_s = sorted(rd)
        n = len(rp_s)
        data["median_shape_retention_plan"] = round((rp_s[n // 2] if n % 2 else (rp_s[n // 2 - 1] + rp_s[n // 2]) / 2), 6) if n else None
        n = len(rd_s)
        data["median_shape_retention_drawn"] = round((rd_s[n // 2] if n % 2 else (rd_s[n // 2 - 1] + rd_s[n // 2]) / 2), 6) if n else None
        del data["retention_plan"]
        del data["retention_drawn"]

    in_scope_retention_walls_s = sorted(in_scope_retention_walls)
    in_scope_path_overhead_s = sorted(in_scope_path_overhead)

    def _median(lst: list[float]) -> float | None:
        if not lst:
            return None
        n = len(lst)
        if n % 2:
            return round(lst[n // 2], 6)
        return round((lst[n // 2 - 1] + lst[n // 2]) / 2.0, 6)

    summary = {
        "total": len(reports),
        "PASS": sum(1 for r in reports if _final_result(r) == "PASS"),
        "WARN": sum(1 for r in reports if _final_result(r) == "WARN"),
        "FAIL": sum(1 for r in reports if _final_result(r) == "FAIL"),
        "PASS_AFTER_RETRY": sum(1 for r in reports if r["result"] == "PASS_AFTER_RETRY"),
        "FAIL_AFTER_RETRY": sum(1 for r in reports if r["result"] == "FAIL_AFTER_RETRY"),
        "failure_reasons": {},
        "by_suite": by_suite,
        "budget_too_much_loss_count_C": budget_too_much_loss_count_C,
        "fail_reason_codes_top": fail_reason_codes_top,
        "in_scope_total": in_scope_total,
        "in_scope_PASS": in_scope_pass,
        "in_scope_WARN": in_scope_warn,
        "in_scope_FAIL": in_scope_fail,
        "out_scope_total": out_scope_total,
        "out_scope_by_class": out_scope_by_class,
        "in_scope_median_retention_vs_walls_candidate": _median(in_scope_retention_walls_s),
        "in_scope_median_path_overhead": _median(in_scope_path_overhead_s),
    }
    for r in reports:
        fr = r.get("failure_reason")
        if fr:
            summary["failure_reasons"][fr] = summary["failure_reasons"].get(fr, 0) + 1

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    write_dxf_diagnostics_report(reports, out_dir)
    write_layer_intelligence_report(reports, out_dir)
    write_graph_report(reports, out_dir)

    # Konsol tablosu
    print("\n--- DXF Drawability Report ---")
    print(f"{'Dosya':<36} {'Suite':<6} {'Sonuç':<18} {'Hareket':<8} {'Step':<8}")
    print("-" * 90)
    for r in reports:
        fname = Path(r["file"]).name
        if len(fname) > 34:
            fname = fname[:31] + "..."
        su = r.get("suite") or "-"
        res = r["result"]
        moves = r.get("move_count") or "-"
        step = r.get("final_step_size_used")
        step_s = f"{step:.3f}" if step is not None else "-"
        print(f"{fname:<36} {su!s:<6} {res:<18} {moves!s:<8} {step_s:<8}")
    print("-" * 90)
    print(f"Özet: PASS={summary['PASS']} WARN={summary['WARN']} FAIL={summary['FAIL']} "
          f"PASS_AFTER_RETRY={summary['PASS_AFTER_RETRY']} FAIL_AFTER_RETRY={summary['FAIL_AFTER_RETRY']}")
    # MVP scope sınıflandırması: kullanıcıya kapsam dışı planları vurgula
    for r in reports:
        scope = r.get("scope_class")
        if scope and scope != SCOPE_SUPPORTED:
            fname = Path(r.get("file") or "").name
            print(
                f"[uyarı] Bu DXF planı MVP kapsamı dışında: {fname} (scope_class={scope})"
            )
            recs = r.get("recommended_actions") or []
            if recs:
                print("        Önerilen aksiyonlar:")
                for rec in recs:
                    print(f"          - {rec}")
    if args.optimize == "on":
        with_opt = [r for r in reports if r.get("move_count_before_optimize") is not None]
        if with_opt:
            avg_red = sum(r.get("travel_reduction_pct") or 0 for r in with_opt) / len(with_opt)
            avg_move_before = sum(r.get("move_count_before_optimize") or 0 for r in with_opt) / len(with_opt)
            avg_move_after = sum(r.get("move_count_after_optimize") or 0 for r in with_opt) / len(with_opt)
            print(f"Optimize: {len(with_opt)} dosya | ortalama travel_reduction_pct={avg_red:.1f}% | "
                  f"move {avg_move_before:.0f} -> {avg_move_after:.0f}")
    print(f"Raporlar: {out_dir.absolute()}\n")

    if summary["FAIL"] > 0:
        return 1
    if args.fail_on_warn and (summary["WARN"] > 0 or summary["PASS_AFTER_RETRY"] > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
