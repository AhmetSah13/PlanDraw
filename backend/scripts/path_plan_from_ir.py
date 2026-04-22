#!/usr/bin/env python3
"""
DXF -> PrintableLayoutIR -> hizalama -> path plan (JSON artifact).

Execution / komut üretimi yoktur.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.alignment.aligner import align_printable_layout_rigid_2d
from app.alignment.alignment_model import ControlPoint
from app.layout_ir.compiler import CompileOptions, compile_dxf_to_printable_layout
from app.path_planning.plan_model import PlannedStroke
from app.path_planning.planner import PathPlanningOptions, plan_path_from_aligned_layout


def _load_control_points(path: Path) -> tuple[list[ControlPoint], float | None]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    tol = raw.get("tolerance_m")
    pts = raw.get("points")
    if not isinstance(pts, list):
        raise ValueError("JSON içinde 'points' listesi gerekli")
    out: list[ControlPoint] = []
    for p in pts:
        if not isinstance(p, dict):
            raise ValueError("Her nokta bir nesne olmalı")
        out.append(
            ControlPoint(
                cad_x=float(p["cad_x"]),
                cad_y=float(p["cad_y"]),
                site_x=float(p["site_x"]),
                site_y=float(p["site_y"]),
                label=p.get("label"),
                weight=float(p["weight"]) if p.get("weight") is not None else None,
            )
        )
    tol_f = float(tol) if tol is not None else None
    return out, tol_f


def _stroke_to_json(s: PlannedStroke) -> dict:
    return {
        "kind": s.kind,
        "closed": s.closed,
        "reversed": s.reversed,
        "stroke_length_m": s.stroke_length_m,
        "travel_from_previous_m": s.travel_from_previous_m,
        "points": [list(p) for p in s.points],
        "source": {
            "layer": s.source.layer,
            "entity_type": s.source.entity_type,
            "handle": s.source.handle,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Hizalanmış layout için path plan JSON")
    ap.add_argument("dxf_path", help="DXF dosya yolu")
    ap.add_argument("control_points_json", help="Hizalama kontrol noktaları JSON")
    ap.add_argument("--out-dir", default="reports/path_plan", help="Çıktı klasörü")
    ap.add_argument(
        "--tolerance-m",
        type=float,
        default=None,
        help="Hizalama residual toleransı (m). JSON veya bu argüman; ikisi yoksa 0.05",
    )
    ap.add_argument("--layer", action="append", help="Derleyici: sadece bu layer(lar)")
    ap.add_argument("--ignore-layer", action="append", help="Derleyici: bu layer(lar) elensin")
    ap.add_argument(
        "--scale-to-world-m",
        type=float,
        default=None,
        help="Derleyici ölçeği (m). Verilmezse DXF $INSUNITS otomatik",
    )
    ap.add_argument("--min-segment-m", type=float, default=0.005, help="Path: kısa kenar eşiği (m)")
    ap.add_argument("--start-x", type=float, default=0.0, help="Plan başlangıç X (m)")
    ap.add_argument("--start-y", type=float, default=0.0, help="Plan başlangıç Y (m)")
    args = ap.parse_args()

    dxf_path = Path(args.dxf_path)
    cp_path = Path(args.control_points_json)
    if not dxf_path.exists():
        print("DXF yok:", dxf_path, file=sys.stderr)
        return 2
    if not cp_path.exists():
        print("Kontrol noktası JSON yok:", cp_path, file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        cps, tol_from_file = _load_control_points(cp_path)
    except Exception as ex:
        print("Kontrol noktası JSON okunamadı:", ex, file=sys.stderr)
        return 2

    tol = args.tolerance_m
    if tol is None and tol_from_file is not None:
        tol = tol_from_file
    if tol is None:
        tol = 0.05

    opts = CompileOptions(
        layer_whitelist=list(args.layer) if args.layer else None,
        layer_blacklist=list(args.ignore_layer) if args.ignore_layer else None,
        scale_to_world_m=float(args.scale_to_world_m) if args.scale_to_world_m is not None else None,
        origin_m=(0.0, 0.0),
    )

    layout, units_info = compile_dxf_to_printable_layout(
        str(dxf_path), options=opts, return_units_info=True  # type: ignore[misc]
    )
    aligned, report = align_printable_layout_rigid_2d(layout, cps, tolerance_m=float(tol))
    if report.blocked:
        print("Uyarı: hizalama blocked=True; plan yine de üretilir.", file=sys.stderr)

    p_opts = PathPlanningOptions(
        min_segment_length_m=float(args.min_segment_m),
        start_x_m=float(args.start_x),
        start_y_m=float(args.start_y),
    )
    path, p_report = plan_path_from_aligned_layout(aligned, options=p_opts)

    m = p_report.metrics
    artifact = {
        "dxf": str(dxf_path),
        "units": {
            "detected_units": units_info.detected_units,
            "original_units_code": units_info.insunits_code,
            "applied_scale_to_world_m": units_info.applied_scale_to_world_m,
            "units_source": units_info.units_source,
        },
        "alignment_blocked": report.blocked,
        "metrics": {
            "stroke_count": m.stroke_count,
            "drawing_length_m": m.drawing_length_m,
            "travel_length_m": m.travel_length_m,
            "pen_lifts": m.pen_lifts,
            "skipped_short_segment_count": m.skipped_short_segment_count,
            "total_points": m.total_points,
            "strategy": m.strategy,
            "notes": list(m.notes),
        },
        "strokes": [_stroke_to_json(s) for s in path.strokes],
    }

    stem = dxf_path.stem
    json_path = out_dir / f"{stem}.path_plan.json"
    json_path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- Path plan ---")
    print("Strokes:", m.stroke_count)
    print("Drawing (m):", f"{m.drawing_length_m:.6f}")
    print("Travel (m):", f"{m.travel_length_m:.6f}")
    print("Pen lifts:", m.pen_lifts)
    print("Skipped short segments:", m.skipped_short_segment_count)
    print("JSON:", json_path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
