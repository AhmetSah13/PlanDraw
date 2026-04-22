#!/usr/bin/env python3
"""
DXF -> PrintableLayoutIR -> pre-alignment preview/report (Phase A+B).

Bu betik:
- DXF modelspace entity'lerini okur
- yalnızca LINE + bulge=0 LWPOLYLINE + düz POLYLINE destekler
- diğer her şeyi deterministik olarak reddeder (rejection listesi)
- PrintabilityReport üretir (PASS/WARN/FAIL)
- pre-alignment SVG preview + JSON summary yazar

Not: Alignment / path planning / execution bu aşamada yoktur.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.layout_ir.compiler import CompileOptions, compile_dxf_to_printable_layout
from app.layout_ir.validation import ValidationOptions, validate_printable_layout
from app.preview.preview_json import layout_to_json_summary
from app.preview.preview_svg import render_pre_alignment_svg


def main() -> int:
    p = argparse.ArgumentParser(description="DXF -> PrintableLayoutIR preview/report (Phase A+B)")
    p.add_argument("dxf_path", help="DXF dosya yolu")
    p.add_argument("--out-dir", default="reports/layout_ir", help="Çıktı klasörü")
    p.add_argument("--layer", action="append", help="Sadece bu layer(lar) (birden fazla verilebilir)")
    p.add_argument("--ignore-layer", action="append", help="Bu layer(lar) elensin")
    p.add_argument("--min-seg", type=float, default=0.005, help="Kısa segment eşiği (m)")
    p.add_argument(
        "--scale-to-world-m",
        type=float,
        default=None,
        help="DXF birimini metreye çevirme ölçeği. Verilmezse $INSUNITS ile otomatik tespit edilir.",
    )
    args = p.parse_args()

    dxf_path = Path(args.dxf_path)
    if not dxf_path.exists():
        print("Dosya yok:", str(dxf_path), file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    opts = CompileOptions(
        layer_whitelist=list(args.layer) if args.layer else None,
        layer_blacklist=list(args.ignore_layer) if args.ignore_layer else None,
        scale_to_world_m=float(args.scale_to_world_m) if args.scale_to_world_m is not None else None,
        origin_m=(0.0, 0.0),
    )

    layout, units_info = compile_dxf_to_printable_layout(str(dxf_path), options=opts, return_units_info=True)  # type: ignore[misc]
    report = validate_printable_layout(layout, options=ValidationOptions(min_segment_length_m=float(args.min_seg)))

    svg = render_pre_alignment_svg(layout)
    summary = layout_to_json_summary(layout, report, units_info=units_info)

    stem = dxf_path.stem
    svg_path = out_dir / f"{stem}.pre_alignment.svg"
    json_path = out_dir / f"{stem}.layout_ir.json"

    svg_path.write_text(svg, encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--- PrintableLayoutIR ---")
    print("DXF:", str(dxf_path))
    print("Units:", units_info.detected_units if units_info.detected_units is not None else "bilinmiyor")
    print("Applied scale_to_world_m:", f"{units_info.applied_scale_to_world_m:g}")
    print("Units source:", units_info.units_source)
    print("Supported:", report.supported_object_count)
    print("Rejected:", report.rejected_object_count)
    print("Drawn length (m):", f"{report.drawn_length_m:.3f}")
    print("Decision:", report.decision)
    if report.reasons:
        print("Reasons:", " | ".join(report.reasons))
    if report.recommendations:
        print("Recommendations:", " | ".join(report.recommendations))
    print("SVG:", str(svg_path))
    print("JSON:", str(json_path))

    return 0 if report.decision != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())

