#!/usr/bin/env python3
"""
DXF -> PrintableLayoutIR -> hizalama -> post-alignment SVG + rapor JSON.

Veri akışı:
  PrintableLayoutIR (derleyici)
  -> aligner (rijit 2D)
  -> AlignedLayoutIR + AlignmentReport
  -> post_alignment.svg + alignment.json

Path planning / execution / UI yoktur.
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
from app.alignment.alignment_model import ControlPoint, alignment_report_to_jsonable
from app.layout_ir.compiler import CompileOptions, compile_dxf_to_printable_layout
from app.preview.preview_svg import render_post_alignment_svg, render_pre_alignment_svg


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


def main() -> int:
    ap = argparse.ArgumentParser(description="PrintableLayoutIR hizalama + post-alignment önizleme")
    ap.add_argument("dxf_path", help="DXF dosya yolu (PrintableLayoutIR üretmek için)")
    ap.add_argument("control_points_json", help="Kontrol noktaları JSON (cad_x/y, site_x/y)")
    ap.add_argument("--out-dir", default="reports/alignment", help="Çıktı klasörü")
    ap.add_argument(
        "--tolerance-m",
        type=float,
        default=None,
        help="Residual üst sınırı (m). JSON veya bu argüman; ikisi yoksa 0.05",
    )
    ap.add_argument("--layer", action="append", help="Sadece bu layer(lar)")
    ap.add_argument("--ignore-layer", action="append", help="Bu layer(lar) elensin")
    ap.add_argument(
        "--scale-to-world-m",
        type=float,
        default=None,
        help="Derleyici ölçeği (m). Verilmezse DXF $INSUNITS otomatik",
    )
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

    pre_svg = render_pre_alignment_svg(layout)
    post_svg = render_post_alignment_svg(aligned)

    stem = dxf_path.stem
    pre_path = out_dir / f"{stem}.pre_alignment.svg"
    post_path = out_dir / f"{stem}.post_alignment.svg"
    json_path = out_dir / f"{stem}.alignment.json"

    pre_path.write_text(pre_svg, encoding="utf-8")
    post_path.write_text(post_svg, encoding="utf-8")

    summary: dict = {
        "dxf": str(dxf_path),
        "control_points": str(cp_path),
        "units": {
            "detected_units": units_info.detected_units,
            "original_units_code": units_info.insunits_code,
            "applied_scale_to_world_m": units_info.applied_scale_to_world_m,
            "units_source": units_info.units_source,
        },
        "alignment": alignment_report_to_jsonable(report),
    }
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- Hizalama ---")
    print("Transform:", report.transform_type)
    print("Blocked:", report.blocked)
    print("Residual max (m):", report.residual_max_m)
    print("Tolerance (m):", report.tolerance_m)
    print("Pre SVG:", pre_path)
    print("Post SVG:", post_path)
    print("JSON:", json_path)

    return 0 if not report.blocked else 1


if __name__ == "__main__":
    raise SystemExit(main())
