# verify_dxf_drawability.py — DXF yükleme → önizleme → import → analiz → çizim/export doğrulama
# API ile aynı pipeline fonksiyonlarını kullanır; sadece enstrümantasyon ve raporlama ekler.

from __future__ import annotations

import argparse
import json
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
    from app.importers.dxf_importer import inspect_dxf_layers, dxf_to_normalized_plan
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
    from app.execution.compiler import compile_path_to_commands
    from app.analysis.scenario_analysis import (
        analyze_commands,
        export_commands_to_string,
        ScenarioLimits,
    )
    from app.execution.commands import parse_commands, serialize_commands
except ImportError as e:
    print(f"Hata: app modülleri yüklenemedi (pydantic/fastapi gerekebilir): {e}", file=sys.stderr)
    sys.exit(1)

# Sabitler (API ile uyumlu)
TARGET_MOVES = 800
STEP_MIN, STEP_MAX = 0.05, 0.50
SPEED_DEFAULT = 120.0
WALL_KEYWORDS = ("wall", "walls", "duvar", "a-wall", "m-wall")


def _clamp_step(raw: float | None) -> float:
    """Önerilen step'i [0.05, 0.50] aralığına kıstırır."""
    if raw is None or raw <= 0:
        return STEP_MAX
    return max(STEP_MIN, min(STEP_MAX, float(raw)))


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
        "error": None,
    }

    try:
        content = dxf_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        report["error"] = str(e)
        report["failure_reason"] = "Dosya okunamadı"
        report["recommended_actions"].append("Dosya yolunu ve encoding'i kontrol edin.")
        return report

    # --- Preview ---
    preview_result, rt_preview = run_stage(
        "preview",
        inspect_dxf_layers,
        content,
        units=None,
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

    raw_step = preview_recommended_step_size(
        float(info.get("total_length") or 0),
        TARGET_MOVES,
        info.get("bbox"),
    )
    report["recommended_step_size_raw"] = raw_step
    step = _clamp_step(step_override if step_override is not None else raw_step)
    report["final_step_size_used"] = step

    layers = layers_override if layers_override is not None else select_layers(info)
    report["selected_layers"] = layers

    if not layers:
        report["failure_reason"] = "Hiç katman seçilemedi"
        report["recommended_actions"].append("DXF'te LINE/LWPOLYLINE/POLYLINE katmanları ekleyin.")
        return report

    # --- Import (normalize + recenter) ---
    import_result, rt_import = run_stage(
        "import",
        _import_dxf,
        content,
        layers=layers,
        step_size=step,
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

    # --- Path ---
    plan = normalized_to_plan(normalized)
    path_result, rt_path = run_stage(
        "path",
        _generate_path,
        plan,
        step_size=step,
    )
    report["runtime_ms"]["path"] = round(rt_path, 2)

    if not path_result or (isinstance(path_result, tuple) and path_result[0] is None):
        report["failure_reason"] = "Yol üretilemedi"
        report["recommended_actions"].append("step_size değerini artırmayı deneyin (Fast mode).")
        return report

    raw_path = path_result

    # --- Pen-up travel (sıralı duvarlar üzerinden) ---
    walls_list = list(plan.walls)
    if walls_list:
        start_pt = _bbox_center(walls_list) or (walls_list[0].x1, walls_list[0].y1)
        ordered = order_segments_nearest_neighbor(walls_list, start_point=start_pt)
        report["pen_up_travel_distance"] = round(compute_travel_distance(ordered, start_pt), 6)
    else:
        report["pen_up_travel_distance"] = 0.0

    # --- Commands + Analyze ---
    commands = compile_path_to_commands(raw_path, speed=SPEED_DEFAULT)
    start = (raw_path[0][0], raw_path[0][1]) if raw_path else (0.0, 0.0)

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

    return report


def _import_dxf(
    content: str,
    *,
    layers: list[str],
    step_size: float,
) -> tuple:
    """DXF içeriğini import eder, normalize + recenter uygular. (normalized, warnings) döner."""
    normalized = dxf_to_normalized_plan(
        content,
        units=None,
        scale=None,
        origin=(0.0, 0.0),
        layer_whitelist=layers,
        layer_blacklist=None,
    )
    opts = NormalizeOptions(recenter=True, recenter_mode="center")
    normalized, warnings = normalize_plan(normalized, opts)
    return (normalized, warnings)


def _generate_path(plan, step_size: float):
    """Plan için sıralı yol noktaları üretir."""
    pg = PathGenerator(plan, step_size=step_size, order_walls=True)
    return pg.generate_path()


def run_retries(dxf_path: Path, content: str, report: dict, info_preview: dict, mode: str) -> dict:
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
        report = run_one(dxf_path, mode, step_override=overrides.get("step_override"), layers_override=overrides.get("layers_override"))
        report["retry_attempts"] = report.get("retry_attempts", [])
        report["retry_attempts"].append({"strategy": strategy_name, "result": report["result"]})

        if report["result"] == "PASS" or report["result"] == "WARN":
            report["result"] = "PASS_AFTER_RETRY"
            report["strategy_succeeded"] = strategy_name
            return report

    report["result"] = "FAIL_AFTER_RETRY"
    report["strategy_succeeded"] = None
    return report


def collect_dxf_paths(input_path: Path) -> list[Path]:
    """Tek dosya veya klasör (özyinelemeli) içindeki .dxf dosyalarını toplar."""
    if input_path.is_file():
        if input_path.suffix.lower() == ".dxf":
            return [input_path]
        return []
    if input_path.is_dir():
        return sorted(input_path.rglob("*.dxf"), key=lambda p: str(p))
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DXF çizilebilirlik doğrulama: yükleme → önizleme → import → analiz → export.",
    )
    parser.add_argument("--input", "-i", required=True, help="DXF dosyası veya klasör yolu")
    parser.add_argument("--out", "-o", default="backend/reports", help="Raporların yazılacağı klasör")
    parser.add_argument("--mode", default="auto", choices=["auto"], help="Çalışma modu (şimdilik sadece auto)")
    parser.add_argument("--fail-on-warn", action="store_true", help="WARN sonucunu da hata say (çıkış kodu 1)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Hata: Girdi bulunamadı: {input_path}", file=sys.stderr)
        return 1

    paths = collect_dxf_paths(input_path)
    if not paths:
        print("Hiç .dxf dosyası bulunamadı.", file=sys.stderr)
        return 1

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    reports: list[dict] = []
    for dxf_path in paths:
        report = run_one(dxf_path, args.mode)
        if report["result"] == "FAIL" and report.get("analyze_result") == "BLOCKED":
            # Otomatik retry (UI ile aynı stratejiler)
            try:
                content = dxf_path.read_text(encoding="utf-8", errors="replace")
                info_preview = inspect_dxf_layers(content, units=None, scale=None, origin=(0.0, 0.0))
            except Exception:
                content = ""
                info_preview = {}
            report = run_retries(dxf_path, content, report, info_preview, args.mode)

        reports.append(report)

        # Dosya bazlı JSON
        safe_name = dxf_path.stem.replace(" ", "_")
        out_file = out_dir / f"{safe_name}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    # Özet
    summary = {
        "total": len(reports),
        "PASS": sum(1 for r in reports if r["result"] == "PASS"),
        "WARN": sum(1 for r in reports if r["result"] == "WARN"),
        "FAIL": sum(1 for r in reports if r["result"] == "FAIL"),
        "PASS_AFTER_RETRY": sum(1 for r in reports if r["result"] == "PASS_AFTER_RETRY"),
        "FAIL_AFTER_RETRY": sum(1 for r in reports if r["result"] == "FAIL_AFTER_RETRY"),
        "failure_reasons": {},
    }
    for r in reports:
        if r.get("failure_reason"):
            summary["failure_reasons"][r["failure_reason"]] = summary["failure_reasons"].get(r["failure_reason"], 0) + 1

    with open(out_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Konsol tablosu
    print("\n--- DXF Drawability Report ---")
    print(f"{'Dosya':<40} {'Sonuç':<18} {'Hareket':<8} {'Çakışma':<8} {'Step':<8}")
    print("-" * 90)
    for r in reports:
        fname = Path(r["file"]).name
        if len(fname) > 38:
            fname = fname[:35] + "..."
        res = r["result"]
        moves = r.get("move_count") or "-"
        coll = r.get("collision_count") is not None and r["collision_count"] or "-"
        step = r.get("final_step_size_used")
        step_s = f"{step:.3f}" if step is not None else "-"
        print(f"{fname:<40} {res:<18} {moves!s:<8} {coll!s:<8} {step_s:<8}")
    print("-" * 90)
    print(f"Özet: PASS={summary['PASS']} WARN={summary['WARN']} FAIL={summary['FAIL']} "
          f"PASS_AFTER_RETRY={summary['PASS_AFTER_RETRY']} FAIL_AFTER_RETRY={summary['FAIL_AFTER_RETRY']}")
    print(f"Raporlar: {out_dir.absolute()}\n")

    if summary["FAIL"] + summary["FAIL_AFTER_RETRY"] > 0:
        return 1
    if args.fail_on_warn and (summary["WARN"] > 0 or summary["PASS_AFTER_RETRY"] > 0):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
