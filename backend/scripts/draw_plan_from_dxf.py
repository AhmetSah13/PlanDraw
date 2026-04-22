from __future__ import annotations

"""
DXF floor-plan → robot çizim komutları demo script'i.

Kapsam:
- Tek bir DXF dosyasını okur.
- Layer intelligence ile duvar katman(lar)ını seçer.
- DXF importer ile:
  - INSERT explode
  - HATCH boundary extraction
  yaparak segment üretir.
- Normalization + (opsiyonel) wall centerline + wall filter uygular.
- Baseline path üretir.
- Robot komutlarını basit metin formatında yazar:

  PEN_UP
  MOVE x y
  PEN_DOWN
  DRAW x y
  ...
  PEN_UP

Not: Bu script, mevcut pipeline mantığını yeniden kullanır;
hiçbir limiti yumuşatmaz, sadece tek-dosya demo akışı sağlar.
"""

import argparse
import math
import sys
from pathlib import Path
from typing import List, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
_BACKEND_ROOT = _SCRIPT_DIR.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.importers.dxf_importer import (  # type: ignore[import]
    dxf_bytes_to_normalized_plan,
    inspect_dxf_layers_bytes,
    select_plan_layers,
)
from app.analysis.wall_centerline import (  # type: ignore[import]
    WallCenterlineConfig,
    apply_wall_centerline_to_plan,
)
from app.normalization.plan_normalizer import (  # type: ignore[import]
    NormalizeOptions,
    normalize_plan,
)
from app.importers.plan_importer import normalized_to_plan  # type: ignore[import]
from app.pathing.path_generator import PathGenerator  # type: ignore[import]
from app.utils.step_size_utils import preview_recommended_step_size  # type: ignore[import]
from app.normalization.normalized_plan import SegmentIn  # type: ignore[import]
from app.analysis.wall_filter import apply_wall_filter, WALL_FILTER_SNAP_TOL_M  # type: ignore[import]
from app.robot.mobile_robot_commands import (  # type: ignore[import]
    convert_path_to_mobile_robot_commands,
)
from app.robot.mobile_mission_planner import (  # type: ignore[import]
    plan_mobile_mission,
)


def _compute_step_size(total_length: float, bbox: list | None) -> float:
    """Toplam uzunluk + bbox'a göre, mevcut yardımcıyı kullanarak step_size seç."""
    TARGET_MOVES = 800
    raw = preview_recommended_step_size(float(total_length or 0.0), TARGET_MOVES, bbox)
    if raw is None or raw <= 0:
        raw = 0.1
    # verify_dxf_drawability ile uyumlu kıstırma
    STEP_MIN, STEP_MAX = 0.05, 0.50
    return max(STEP_MIN, min(STEP_MAX, float(raw)))


def _path_from_plan(plan, step_size: float) -> List[List[Tuple[float, float]]]:
    """Baseline path generator ile plan'dan stroke listesi (polylines) üret."""
    pg = PathGenerator(plan, step_size=step_size, order_walls=True)
    return pg.generate_path_segments()


def _measure_path_stats(
    paths: List[List[Tuple[float, float]]],
    start_xy: Tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float, int]:
    """
    Basit metrikler:
    - drawn_length_m: PEN_DOWN iken gidilen toplam mesafe
    - travel_length_m: PEN_UP iken gidilen toplam mesafe
    - move_count: MOVE + DRAW satırlarının toplamı
    """
    if not paths or not paths[0]:
        return 0.0, 0.0, 0

    drawn = 0.0
    travel = 0.0
    moves = 0

    # İlk stroke'a kadar travel
    cx, cy = float(start_xy[0]), float(start_xy[1])
    first = paths[0][0]
    travel += math.hypot(first[0] - cx, first[1] - cy)
    moves += 1  # MOVE
    cx, cy = first

    for poly in paths:
        if not poly:
            continue
        # Stroke başlangıcı (ilk nokta) için, önceki stroke'tan travel eklendi; burada sadece DRAW'lar sayılır.
        for i in range(1, len(poly)):
            x, y = poly[i]
            d = math.hypot(x - cx, y - cy)
            drawn += d
            moves += 1  # DRAW
            cx, cy = x, y
        # Bir sonraki stroke'un başlangıcına travel ölçümü döngü dışındaki parçada yapılır
        # (polyler arası travel'ı aşağıda ekliyoruz).

    # Polyline'lar arası travel (stroke bitişi → sonraki stroke başlangıcı)
    for idx in range(len(paths) - 1):
        last_pt = paths[idx][-1]
        next_pt = paths[idx + 1][0]
        d = math.hypot(next_pt[0] - last_pt[0], next_pt[1] - last_pt[1])
        travel += d
        moves += 1  # MOVE

    return drawn, travel, moves


def _write_robot_commands(
    paths: List[List[Tuple[float, float]]],
    out_path: Path,
) -> None:
    """
    Path (stroke listesi) → basit robot komut formatı.

    Format:
      PEN_UP
      MOVE x y
      PEN_DOWN
      DRAW x y
      ...
      PEN_UP
    """
    lines: list[str] = []
    if not paths:
        lines.append("PEN_UP")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return

    first = True
    for poly in paths:
        if not poly:
            continue
        x0, y0 = poly[0]
        lines.append("PEN_UP")
        lines.append(f"MOVE {x0:.6f} {y0:.6f}")
        lines.append("PEN_DOWN")
        for (x, y) in poly[1:]:
            lines.append(f"DRAW {x:.6f} {y:.6f}")
        first = False
    lines.append("PEN_UP")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _write_svg_preview(
    wall_segments: List[SegmentIn],
    centerline_segments: List[SegmentIn],
    paths: List[List[Tuple[float, float]]],
    out_path: Path,
    *,
    start_heading_deg: float | None = None,
) -> None:
    """
    SVG önizleme:
      - Duvar segmentleri (gri)
      - Centerline segmentleri (mavi)
      - Robot path (kırmızı)
    """
    if not wall_segments and not centerline_segments and not paths:
        out_path.write_text(
            "<svg xmlns='http://www.w3.org/2000/svg' width='1000' height='1000'/>",
            encoding="utf-8",
        )
        return

    xs: list[float] = []
    ys: list[float] = []

    def _acc_seg(s: SegmentIn) -> None:
        xs.append(s.x1)
        xs.append(s.x2)
        ys.append(s.y1)
        ys.append(s.y2)

    for s in wall_segments:
        _acc_seg(s)
    for s in centerline_segments:
        _acc_seg(s)
    for poly in paths:
        for (x, y) in poly:
            xs.append(x)
            ys.append(y)

    minx = min(xs)
    maxx = max(xs)
    miny = min(ys)
    maxy = max(ys)
    width = maxx - minx if maxx > minx else 1.0
    height = maxy - miny if maxy > miny else 1.0

    canvas = 1000.0
    pad = 40.0
    sx = (canvas - 2 * pad) / width
    sy = (canvas - 2 * pad) / height
    scale = min(sx, sy)

    def _tx(x: float, y: float) -> Tuple[float, float]:
        # Dünya → SVG: (0,0) sol-üst, y ekseni ters çevrilmiş
        tx = pad + (x - minx) * scale
        ty = canvas - pad - (y - miny) * scale
        return tx, ty

    svg_lines: list[str] = [
        "<svg xmlns='http://www.w3.org/2000/svg' width='1000' height='1000'>",
        "<g fill='none'>",
    ]

    # 1) Duvar segmentleri (gri)
    if wall_segments:
        d_parts: list[str] = []
        for s in wall_segments:
            x1, y1 = _tx(s.x1, s.y1)
            x2, y2 = _tx(s.x2, s.y2)
            d_parts.append(f"M {x1:.3f} {y1:.3f} L {x2:.3f} {y2:.3f}")
        svg_lines.append(
            f"<path d=\"{' '.join(d_parts)}\" stroke=\"#999999\" stroke-width=\"1\" />"
        )

    # 2) Centerline segmentleri (mavi)
    if centerline_segments:
        d_parts_cl: list[str] = []
        for s in centerline_segments:
            x1, y1 = _tx(s.x1, s.y1)
            x2, y2 = _tx(s.x2, s.y2)
            d_parts_cl.append(f"M {x1:.3f} {y1:.3f} L {x2:.3f} {y2:.3f}")
        svg_lines.append(
            f"<path d=\"{' '.join(d_parts_cl)}\" stroke=\"#0000FF\" stroke-width=\"1.5\" />"
        )

    # 3) Robot path (kırmızı)
    start_screen: Tuple[float, float] | None = None
    if paths:
        d_parts_path: list[str] = []
        for poly in paths:
            if not poly:
                continue
            x0, y0 = _tx(poly[0][0], poly[0][1])
            if start_screen is None:
                start_screen = (x0, y0)
            d_parts_path.append(f"M {x0:.3f} {y0:.3f}")
            for (x, y) in poly[1:]:
                xx, yy = _tx(x, y)
                d_parts_path.append(f"L {xx:.3f} {yy:.3f}")
        svg_lines.append(
            f"<path d=\"{' '.join(d_parts_path)}\" stroke=\"#FF0000\" stroke-width=\"2\" />"
        )

    # 4) Başlangıç noktası (yeşil daire) ve yön oku
    # Tek kaynak: start_heading_deg verilmişse mobil komut katmanından gelir; yoksa paths[0] geometrisinden.
    if paths and paths[0]:
        x0w, y0w = paths[0][0]
        x0s, y0s = _tx(x0w, y0w)
        svg_lines.append(
            f"<circle cx=\"{x0s:.3f}\" cy=\"{y0s:.3f}\" r=\"6\" fill=\"#00FF00\" stroke=\"none\" />"
        )
        # Yön oku: start_heading_deg varsa onu kullan (mobil katman kaynağı), yoksa paths[0][0]->paths[0][1]
        if start_heading_deg is not None:
            rad = math.radians(start_heading_deg)
            arrow_len = 0.5
            if len(paths[0]) >= 2:
                arrow_len = max(
                    arrow_len,
                    math.hypot(
                        paths[0][1][0] - paths[0][0][0],
                        paths[0][1][1] - paths[0][0][1],
                    ),
                )
            x1w = x0w + math.cos(rad) * arrow_len
            y1w = y0w + math.sin(rad) * arrow_len
            x1s, y1s = _tx(x1w, y1w)
        elif len(paths[0]) >= 2:
            x1w, y1w = paths[0][1]
            x1s, y1s = _tx(x1w, y1w)
        else:
            x1s, y1s = x0s, y0s

        if (x0s, y0s) != (x1s, y1s):
            svg_lines.append(
                f"<line x1=\"{x0s:.3f}\" y1=\"{y0s:.3f}\" x2=\"{x1s:.3f}\" y2=\"{y1s:.3f}\" "
                f"stroke=\"#00AA00\" stroke-width=\"2\" />"
            )
            dx = x1s - x0s
            dy = y1s - y0s
            length = math.hypot(dx, dy) or 1.0
            ux, uy = dx / length, dy / length
            tip_x, tip_y = x1s, y1s
            side_len = 10.0
            nx, ny = -uy, ux
            left_x = tip_x - ux * side_len + nx * side_len * 0.5
            left_y = tip_y - uy * side_len + ny * side_len * 0.5
            right_x = tip_x - ux * side_len - nx * side_len * 0.5
            right_y = tip_y - uy * side_len - ny * side_len * 0.5
            svg_lines.append(
                f"<polygon points=\"{tip_x:.3f},{tip_y:.3f} {left_x:.3f},{left_y:.3f} {right_x:.3f},{right_y:.3f}\" "
                f"fill=\"#00AA00\" />"
            )

    svg_lines.append("</g>")
    svg_lines.append("</svg>")
    out_path.write_text("\n".join(svg_lines), encoding="utf-8")


def run_pipeline(
    dxf_path: Path,
    out_commands: Path,
    *,
    centerline_enabled: bool = False,
    preview_svg_path: Path | None = None,
    mobile_robot_format: bool = False,
    optimize_mobile_mission: bool = False,
    mobile_planner_mode: str = "travel_first",
    mobile_travel_degradation_limit: float = 1.05,
) -> None:
    """Tek DXF dosyası için uçtan uca pipeline."""
    print(f"[bilgi] DXF yükleniyor: {dxf_path}")
    raw = dxf_path.read_bytes()

    # Önizleme: layer istatistikleri ve units
    preview = inspect_dxf_layers_bytes(raw, units=None, scale=None, origin=(0.0, 0.0))
    total_length = float(preview.get("total_length") or 0.0)
    bbox = preview.get("bbox")
    print(f"[bilgi] Önizleme total_length_m={total_length:.3f}, bbox={bbox}")

    # Layer intelligence ile katman seçimi
    # (daha zengin graph tabanlı seçim verify_dxf_drawability tarafında var; burada basit seçim kullanıyoruz)
    diag_like = {
        "layers": [
            {
                "name": name,
                "entity_count": int(st.get("entities", 0)),
                "total_length": float(st.get("total_length", 0.0) or 0.0),
                "entity_types": list(st.get("entity_types", []))
                if isinstance(st.get("entity_types"), list)
                else [],
            }
            for name, st in (preview.get("layers") or {}).items()
        ]
    }
    li = select_plan_layers(diag_like)
    selected_layers = li.get("selected_layers") or []
    if not selected_layers:
        # Fallback: preview heuristic
        from app.importers.dxf_importer import select_layers as _select_layers  # type: ignore[import]

        selected_layers = _select_layers(preview)
    print(f"[bilgi] Seçilen katmanlar: {selected_layers}")

    # Import: INSERT explode + HATCH boundary extraction + basic wall-only filtresi
    from app.importers.dxf_importer import dxf_bytes_to_normalized_plan as _imp  # type: ignore[import]

    normalized = _imp(
        raw,
        units=None,
        scale=None,
        origin=(0.0, 0.0),
        layer_whitelist=selected_layers,
        layer_blacklist=None,
    )
    print(f"[bilgi] Import sonrası segment sayısı: {len(normalized.segments)}")

    # Normalize (snap, merge, recenter)
    n_opts = NormalizeOptions(recenter=True, recenter_mode="center")
    normalized, _norm_warnings = normalize_plan(normalized, n_opts)
    print(f"[bilgi] Normalize sonrası segment sayısı: {len(normalized.segments)}")

    # SVG için katmanlar:
    # - wall_segments: normalize sonrası, centerline/filter öncesi duvar segmentleri
    # - centerline_segments: centerline sonucu ortaya çıkan yeni segmentler
    wall_segments_svg: List[SegmentIn] = list(normalized.segments)
    centerline_segments_svg: List[SegmentIn] = []

    # Opsiyonel: wall centerline (double-wall → tek çizgi)
    if centerline_enabled:
        cl_cfg = WallCenterlineConfig()
        normalized_before_cl = normalized
        normalized, cl_metrics = apply_wall_centerline_to_plan(normalized_before_cl, cfg=cl_cfg)
        print(
            "[bilgi] Centerline: pairs={pairs}, coverage={cov:.3f}, fallback={fb}".format(
                pairs=cl_metrics.get("centerline_pairs_detected")
                or cl_metrics.get("detected_double_wall_pairs_count"),
                cov=float(
                    cl_metrics.get("centerline_coverage_ratio")
                    or cl_metrics.get("double_wall_coverage_ratio")
                    or 0.0
                ),
                fb=cl_metrics.get("fallback_used"),
            )
        )
        # Centerline segmentlerini yaklaşık olarak, normalize öncesi duvarlardan
        # hash farkı ile ayır.
        def _seg_hash(s: SegmentIn) -> Tuple[int, int, int, int]:
            return (
                int(round(s.x1 * 1e6)),
                int(round(s.y1 * 1e6)),
                int(round(s.x2 * 1e6)),
                int(round(s.y2 * 1e6)),
            )

        orig_hashes = {_seg_hash(s) for s in wall_segments_svg}
        centerline_segments_svg = [
            s for s in normalized.segments if _seg_hash(s) not in orig_hashes
        ]

    # Wall filter (küçük komponent / çok kısa segment temizleme)
    filtered_plan, wf_metrics = apply_wall_filter(
        normalized,
        snap_tol=WALL_FILTER_SNAP_TOL_M,
    )
    drops = (wf_metrics or {}).get("drops") or {}
    print(
        "[bilgi] Wall filter: short={short}, small_comp={small}, angle_noise={ang}".format(
            short=int(drops.get("short_segment", 0)),
            small=int(drops.get("small_component", 0)),
            ang=int(drops.get("angle_noise", 0)),
        )
    )
    normalized = filtered_plan

    print(f"[bilgi] Filtre sonrası segment sayısı: {len(normalized.segments)}")

    # Step size ve path üretimi
    step_size = _compute_step_size(total_length, bbox)
    plan = normalized_to_plan(normalized)
    paths = _path_from_plan(plan, step_size=step_size)
    if not paths:
        print("[hata] Path üretilemedi; stroke listesi boş.")
        return

    # Mobil mission planner (opsiyonel; sadece mobile_robot_format ile anlamlı)
    planned_paths = paths
    if mobile_robot_format and optimize_mobile_mission:
        mission = plan_mobile_mission(
            paths,
            start_xy=(0.0, 0.0),
            start_heading_deg=0.0,
            optimize_order=True,
            optimize_direction=True,
            travel_weight=1.0,
            turn_weight=0.1,
            planner_mode=mobile_planner_mode,
            degradation_limit=mobile_travel_degradation_limit,
        )
        planned_paths = mission.get("planned_paths") or paths
        naive_travel = float(mission.get("naive_total_travel_m", 0.0))
        opt_travel = float(mission.get("total_travel_m", 0.0))
        naive_turn = float(mission.get("naive_estimated_turn_deg", 0.0))
        opt_turn = float(mission.get("estimated_turn_deg", 0.0))
        ratio = float(mission.get("travel_improvement_ratio", 1.0))
        fallback = bool(mission.get("fallback_used", False))
        mode = str(mission.get("planner_mode", "travel_first"))
        limit = float(mission.get("degradation_limit", 1.05))

        print(
            "[bilgi] Mobil mission planlama: planner_mode={mode}, original_path_count={orig}, "
            "planned_path_count={planned}, fallback_used={fb}, degradation_limit={lim:.2f}".format(
                mode=mode,
                orig=int(mission.get("original_path_count", 0)),
                planned=int(mission.get("planned_path_count", 0)),
                fb=fallback,
                lim=limit,
            )
        )
        print(
            "[bilgi] Mobil mission metrikleri: naive_total_travel_m={nt:.3f}, optimized_total_travel_m={ot:.3f}, "
            "naive_estimated_turn_deg={ntd:.1f}, optimized_estimated_turn_deg={otd:.1f}, "
            "travel_improvement_ratio={ratio:.3f}".format(
                nt=naive_travel,
                ot=opt_travel,
                ntd=naive_turn,
                otd=opt_turn,
                ratio=ratio,
            )
        )
        if fallback:
            print(
                "[uyarı] Mobil mission: travel kötüleşmesi degradation_limit aştı; naive plana fallback yapıldı."
            )

    # Metrikler
    drawn_len, travel_len, move_count = _measure_path_stats(paths, start_xy=(0.0, 0.0))
    print(
        "[bilgi] Çizim metrikleri: drawn_length_m={drawn:.3f}, travel_length_m={travel:.3f}, move_count={mc}".format(
            drawn=drawn_len,
            travel=travel_len,
            mc=move_count,
        )
    )

    # Preview için heading: mobil formatta komut katmanından, değilse None (paths geometrisi kullanılır)
    preview_heading_deg: float | None = None

    # Robot komutlarını yaz
    if mobile_robot_format:
        # Path (polyline listesi) → segment listesi (x1,y1,x2,y2)
        segs: list[tuple[float, float, float, float]] = []
        for poly in planned_paths:
            if len(poly) < 2:
                continue
            for i in range(1, len(poly)):
                x1, y1 = poly[i - 1]
                x2, y2 = poly[i]
                segs.append((x1, y1, x2, y2))

        # Mobil robot komutları (heading auto: ilk gerçek DRAW_TO vektöründen)
        mr = convert_path_to_mobile_robot_commands(
            segs,
            start_xy=(0.0, 0.0),
            start_heading_deg=None,
        )
        lines = mr["commands"]
        out_commands.write_text("\n".join(lines), encoding="utf-8")
        preview_heading_deg = float(mr.get("start_heading_deg", 0.0))

        # Flatten & sanitize metrikleri
        path_polyline_count = len(planned_paths)
        flattened_segment_count = len(segs)
        sanitized_segment_count = int(mr.get("sanitized_segment_count", 0))
        draw_cmd_count = int(mr.get("draw_command_count", 0))
        travel_cmd_count = int(mr.get("travel_command_count", 0))

        print(
            "[bilgi] Flatten/sanitize metrikleri: path_polyline_count={poly}, "
            "flattened_segment_count_before_sanitize={flat}, "
            "sanitized_segment_count={san}, "
            "draw_command_count={draw}, travel_command_count={travel}".format(
                poly=path_polyline_count,
                flat=flattened_segment_count,
                san=sanitized_segment_count,
                draw=draw_cmd_count,
                travel=travel_cmd_count,
            )
        )

        # Retention oranı (generic path vs mobil komut katmanı)
        path_drawn_length_m = float(drawn_len)
        mobile_drawn_length_m = float(mr.get("drawn_length_m", 0.0))
        if path_drawn_length_m > 0.0:
            mobile_drawn_retention_ratio = mobile_drawn_length_m / path_drawn_length_m
        else:
            mobile_drawn_retention_ratio = 1.0

        print(
            "[bilgi] Retention: path_drawn_length_m={pdl:.3f}, mobile_drawn_length_m={mdl:.3f}, "
            "mobile_drawn_retention_ratio={ratio:.3f}".format(
                pdl=path_drawn_length_m,
                mdl=mobile_drawn_length_m,
                ratio=mobile_drawn_retention_ratio,
            )
        )

        if mobile_drawn_retention_ratio < 0.95:
            print(
                "[uyarı] mobile_drawn_retention_ratio düşük (<0.95). "
                "path_metric=path_generator step-sampled stroke; "
                "mobile_metric=sanitized flattened segments üzerinden DRAW_TO toplamı."
            )

        print(
            "[bilgi] Mobil robot komutları: start_xy={start}, heading={hd:.1f}, drawn={dl:.3f}, "
            "travel={tl:.3f}, moves={mc}".format(
                start=mr.get("start_xy"),
                hd=float(mr.get("start_heading_deg", 0.0)),
                dl=float(mr.get("drawn_length_m", 0.0)),
                tl=float(mr.get("travel_length_m", 0.0)),
                mc=int(mr.get("move_count", 0)),
            )
        )
    else:
        _write_robot_commands(paths, out_commands)
        print(f"[bilgi] Robot komutları yazıldı: {out_commands}")

    # SVG önizleme istenmişse üret (mobil formatta heading tek kaynaktan: mr["start_heading_deg"])
    if preview_svg_path is not None:
        _write_svg_preview(
            wall_segments_svg,
            centerline_segments_svg,
            planned_paths if mobile_robot_format and optimize_mobile_mission else paths,
            preview_svg_path,
            start_heading_deg=preview_heading_deg,
        )
        print(f"[bilgi] SVG önizleme yazıldı: {preview_svg_path}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tek DXF floor-plan dosyasından robot çizim komutları üretir (duvar-only pipeline demo)."
    )
    parser.add_argument(
        "input",
        help="Girdi DXF dosya yolu",
    )
    parser.add_argument(
        "--out",
        default="robot_commands.txt",
        help="Çıktı komut dosyası (varsayılan: robot_commands.txt)",
    )
    parser.add_argument(
        "--centerline",
        choices=["off", "on"],
        default="off",
        help="Double-wall duvarlar için orta çizgi çıkarımı (varsayılan: off)",
    )
    parser.add_argument(
        "--mobile-robot-format",
        choices=["off", "on"],
        default="off",
        help="Mobil zemin-çizim robotu için yüksek seviye komut formatını kullan (SET_ORIGIN/MOVE_TO/DRAW_TO/END).",
    )
    parser.add_argument(
        "--optimize-mobile-mission",
        choices=["off", "on"],
        default="off",
        help="Mobil mission planning katmanını (greedy order/direction optimization) aç/kapat (yalnızca --mobile-robot-format on iken etkili).",
    )
    parser.add_argument(
        "--mobile-planner-mode",
        choices=["travel_first", "weighted"],
        default="travel_first",
        help="Planner modu: travel_first (default, güvenli) veya weighted (deneysel).",
    )
    parser.add_argument(
        "--mobile-travel-degradation-limit",
        type=float,
        default=1.05,
        help="Optimized travel > naive * limit ise naive plana fallback (varsayılan: 1.05).",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="SVG önizleme üret (preview.svg).",
    )
    args = parser.parse_args()

    dxf_path = Path(args.input)
    if not dxf_path.exists():
        print(f"[hata] Girdi dosyası bulunamadı: {dxf_path}", file=sys.stderr)
        return 1

    out_commands = Path(args.out)
    preview_svg = Path("preview.svg") if args.preview else None
    try:
        run_pipeline(
            dxf_path,
            out_commands,
            centerline_enabled=(args.centerline == "on"),
            preview_svg_path=preview_svg,
            mobile_robot_format=(args.mobile_robot_format == "on"),
            optimize_mobile_mission=(args.optimize_mobile_mission == "on"),
            mobile_planner_mode=args.mobile_planner_mode,
            mobile_travel_degradation_limit=float(args.mobile_travel_degradation_limit),
        )
    except Exception as ex:
        print(f"[hata] Pipeline çalışırken istisna oluştu: {ex!s}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

