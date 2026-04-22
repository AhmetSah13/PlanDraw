# dxf_importer.py — ASCII DXF → NormalizedPlan (LINE, LWPOLYLINE, POLYLINE+VERTEX)
# Üçüncü parti bağımlılık yok; yalnızca ASCII DXF desteklenir.

from __future__ import annotations

import math
import os
import tempfile
from typing import Any

from app.normalization.normalized_plan import NormalizedPlan, OriginIn, SegmentIn

from app.importers.dxf_ezdxf_adapter import DiscretizeConfig, discretize_entity_to_segments
from app.importers.dxf_preprocess import ExplodeConfig, explode_inserts

try:
    import ezdxf
    from ezdxf import recover
except Exception:  # pragma: no cover
    ezdxf = None  # type: ignore
    recover = None  # type: ignore

# Group code 999 (yorum) için look-ahead resync üst sınırı
RESYNC_LOOKAHEAD_LINES = 50

# $INSUNITS (group 70): 0=Unitless, 1=Inches, 2=Feet, 4=mm, 5=cm, 6=m
# Buradaki isimler DXF iç birimini temsil eder; dünya birimi ise her zaman metre kabul edilir.
INSUNITS_TO_NAME: dict[int, str] = {
    0: "unitless",
    1: "inch",
    2: "foot",
    4: "mm",
    5: "cm",
    6: "m",
}

# DXF iç biriminden metreye çarpan.
DXF_UNIT_TO_METERS: dict[str, float] = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "inch": 0.0254,
    "foot": 0.3048,
}

WORLD_UNIT_BASE = "m"


def _compute_units_and_scale(
    units: str | None,
    scale: float | None,
    insunits: int | None,
) -> tuple[str, float, str, bool]:
    """
    dxf_to_normalized_plan ve inspect_dxf_layers için ortak units/scale hesabı.

    Amaç:
    - DXF iç birimini saptamak (mm/cm/m/inch/foot veya unitless).
    - Dünya birimini her zaman metre (WORLD_UNIT_BASE) kabul etmek.
    - Toplam ölçeği (DXF koordinatı → metre) hesaplamak.

    Dönen değerler:
    - out_units: NormalizedPlan.units alanına yazılacak değer (mm/cm/m).
    - total_scale: DXF ham koordinatlarına uygulanacak çarpan (metre cinsinden).
    - detected_unit: DXF iç birimi ismi ("mm", "cm", "m", "inch", "foot" veya "unitless").
    - unit_unknown: True ise $INSUNITS bilgisi yoktu veya 0 idi (varsayım yapıldı).
    """
    unit_unknown = False

    # 1) DXF header'dan gelen iç birim (insunits)
    detected_unit = "unitless"
    if insunits is not None and insunits in INSUNITS_TO_NAME:
        detected_unit = INSUNITS_TO_NAME[insunits]

    # 2) Kullanıcı override'ı (options.units_override) varsa onu baz al.
    if units is not None:
        if units not in ("mm", "cm", "m"):
            raise ValueError(f"Geçersiz units: '{units}' (mm, cm, m olmalı)")
        # Override verildiyse DXF koordinatlarını bu birimde kabul et ve
        # metreye çevirirken sadece bunu kullan (INSUNITS'i yok say).
        source_unit = units
        dxf_unit_for_scale = units
    else:
        # Header'daki insunits'e göre tahmin et; yoksa mm varsayıp uyarı işaretle.
        if detected_unit in ("mm", "cm", "m"):
            source_unit = detected_unit
            dxf_unit_for_scale = detected_unit
        elif detected_unit in ("inch", "foot"):
            # inch/foot: metreye çevirirken gerçek birimi kullan, fakat
            # NormalizedPlan.units için mm raporla.
            source_unit = "mm"
            dxf_unit_for_scale = detected_unit
        else:
            source_unit = "mm"
            dxf_unit_for_scale = "mm"
            unit_unknown = True

    # 3) DXF iç birimi → metre ölçeği.
    base_to_m = DXF_UNIT_TO_METERS.get(dxf_unit_for_scale, 0.001)

    user_scale = float(scale) if scale is not None else 1.0
    total_scale = base_to_m * user_scale

    out_units = source_unit
    return out_units, total_scale, detected_unit, unit_unknown


def _strip_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines()]


def _is_binary_dxf(text: str) -> bool:
    """Binary DXF ilk satırda 'AutoCAD Binary DXF' veya null byte içerir."""
    first_line = text.split("\n")[0].strip() if text else ""
    if "AutoCAD Binary DXF" in first_line or "Binary" in first_line.upper():
        return True
    if "\x00" in text[:1024]:
        return True
    return False


def _load_ezdxf_doc_from_bytes(raw: bytes) -> tuple[Any, list[str]]:
    """
    raw bytes -> ezdxf Document yükler.
    Not: ezdxf stream API'si metin odaklı olduğundan, burada temp dosya kullanıyoruz.
    """
    if ezdxf is None or recover is None:
        raise ValueError("ezdxf yüklü değil; tam DXF desteği kullanılamıyor")
    warnings: list[str] = []
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".dxf") as f:
            tmp_path = f.name
            f.write(raw)
            f.flush()
        doc, auditor = recover.readfile(tmp_path)  # type: ignore[call-arg]
        # Auditor hatalarını string olarak ekle (detayları Insight'ta ayrıca gösterebiliriz)
        if getattr(auditor, "has_errors", False) or getattr(auditor, "has_fixes", False):
            warnings.append("DXF recover/audit uygulandı; dosya yapısı sorunlu olabilir.")
        return doc, warnings
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass


def _adaptive_tol_m_from_bbox(bbox_m: list[float] | None) -> float:
    # Varsayılan: max(2mm, bbox_scale*0.0005) — küçük planlarda daha sık
    if not bbox_m or len(bbox_m) != 4:
        return 0.002
    minx, miny, maxx, maxy = bbox_m
    scale = max(maxx - minx, maxy - miny)
    return max(0.002, float(scale) * 0.0005)


def _ezdxf_doc_to_segments(
    doc: Any,
    *,
    scale_to_world_m: float,
    origin_m: tuple[float, float],
    layer_whitelist: list[str] | None,
    layer_blacklist: list[str] | None,
    tolerance_m: float,
    target_max_segments: int,
    max_insert_depth: int,
    explode_blocks: bool,
) -> tuple[list[SegmentIn], dict[str, Any]]:
    """
    ezdxf doc modelspace -> SegmentIn[] (metre).
    Döner: (segments, stats) — stats insight/warnings için.
    """
    stats: dict[str, Any] = {
        "discretized_counts": {"ARC": 0, "CIRCLE": 0, "SPLINE": 0},
        "insert_exploded_count": 0,
        # HATCH boundary extraction için istatistik
        "hatch_boundaries_extracted": 0,
        "warnings": [],
        "entity_counts_total": {},
        "layer_entity_counts": {},
        "layers": {},
        # MVP wall-only: elenen entity'leri raporla (pipeline'ı şişirmesin)
        "dropped_entities_by_reason": {},  # reason -> count
        "dropped_entities_by_type": {},  # etype -> count
        "filtered_out_by_layer": 0,
        "bbox": None,
        "total_length": 0.0,
        "total_segments": 0,
    }
    msp = doc.modelspace()
    entities = list(msp)  # type: ignore[arg-type]

    # total entity counts (ezdxf)
    for e in entities:
        t = e.dxftype()
        stats["entity_counts_total"][t] = stats["entity_counts_total"].get(t, 0) + 1
        layer = getattr(getattr(e, "dxf", None), "layer", "0") or "0"
        lec = stats["layer_entity_counts"].setdefault(layer, {})
        lec[t] = lec.get(t, 0) + 1

    # explode INSERT
    ents2, explode_w = explode_inserts(
        entities,
        cfg=ExplodeConfig(
            max_recursion_depth=int(max_insert_depth),
            explode_inserts=bool(explode_blocks),
        ),
    )
    stats["warnings"].extend(explode_w)
    stats["insert_exploded_count"] += sum(1 for w in explode_w if w.get("code") == "INSERT_EXPLODED")

    cfg = DiscretizeConfig(tolerance_m=float(tolerance_m), max_segments=int(target_max_segments))

    segments: list[SegmentIn] = []

    def _update_bbox(bbox, x, y):
        if bbox is None:
            return [x, y, x, y]
        minx, miny, maxx, maxy = bbox
        return [min(minx, x), min(miny, y), max(maxx, x), max(maxy, y)]

    for e in ents2:
        layer = getattr(getattr(e, "dxf", None), "layer", "0") or "0"
        if layer_whitelist is not None and layer not in layer_whitelist:
            stats["filtered_out_by_layer"] = int(stats.get("filtered_out_by_layer", 0)) + 1
            continue
        if layer_blacklist is not None and layer in layer_blacklist:
            stats["filtered_out_by_layer"] = int(stats.get("filtered_out_by_layer", 0)) + 1
            continue
        t = e.dxftype()

        # Wall-only: annotation/noise/bloğu çizme (ama say)
        if t in NON_WALL_ENTITY_TYPES:
            stats["dropped_entities_by_reason"]["non_wall_annotation"] = (
                stats["dropped_entities_by_reason"].get("non_wall_annotation", 0) + 1
            )
            stats["dropped_entities_by_type"][t] = stats["dropped_entities_by_type"].get(t, 0) + 1
            continue
        if t in BLOCK_ENTITY_TYPES:
            # explode_blocks=False veya recursion limit ile kalan INSERT'ler
            stats["dropped_entities_by_reason"]["block_insert"] = (
                stats["dropped_entities_by_reason"].get("block_insert", 0) + 1
            )
            stats["dropped_entities_by_type"][t] = stats["dropped_entities_by_type"].get(t, 0) + 1
            continue
        if t not in WALL_DRAWABLE_ENTITY_TYPES:
            stats["dropped_entities_by_reason"]["non_wall_other"] = (
                stats["dropped_entities_by_reason"].get("non_wall_other", 0) + 1
            )
            stats["dropped_entities_by_type"][t] = stats["dropped_entities_by_type"].get(t, 0) + 1
            continue

        segs, w, discretized = discretize_entity_to_segments(
            e,
            cfg=cfg,
            scale_to_world_m=scale_to_world_m,
            origin_m=origin_m,
        )
        segments.extend(segs)
        stats["warnings"].extend(w)
        if discretized and t in stats["discretized_counts"]:
            stats["discretized_counts"][t] += 1
        if not segs and t in WALL_DRAWABLE_ENTITY_TYPES:
            stats["dropped_entities_by_reason"]["discretize_failed_or_empty"] = (
                stats["dropped_entities_by_reason"].get("discretize_failed_or_empty", 0) + 1
            )
            stats["dropped_entities_by_type"][t] = stats["dropped_entities_by_type"].get(t, 0) + 1
        if segs:
            if t == "HATCH":
                # En az bir boundary segmenti üreten HATCH sayısını takip et
                stats["hatch_boundaries_extracted"] = int(stats.get("hatch_boundaries_extracted", 0) or 0) + 1
            layer_stats = stats["layers"].setdefault(
                layer,
                {"entities": 0, "segments": 0, "total_length": 0.0, "bbox": None},
            )
            layer_stats["entities"] += 1
            for s in segs:
                L = math.hypot(s.x2 - s.x1, s.y2 - s.y1)
                layer_stats["segments"] += 1
                layer_stats["total_length"] += L
                layer_stats["bbox"] = _update_bbox(layer_stats["bbox"], s.x1, s.y1)
                layer_stats["bbox"] = _update_bbox(layer_stats["bbox"], s.x2, s.y2)
                stats["total_segments"] += 1
                stats["total_length"] += L
                stats["bbox"] = _update_bbox(stats["bbox"], s.x1, s.y1)
                stats["bbox"] = _update_bbox(stats["bbox"], s.x2, s.y2)
        if len(segments) > target_max_segments:
            break

    return segments, stats


# Benchmark spec: preprocess sonrası, layer filtresi ve segment_budget öncesi tüm segmentler.
PREPROESS_SEGMENT_CAP = 999999


def get_dxf_all_segments_before_filter(
    raw: bytes,
    *,
    units: str | None = None,
    scale: float | None = None,
    origin: tuple[float, float] = (0.0, 0.0),
    chord_tolerance_m: float | None = None,
    target_max_segments: int = PREPROESS_SEGMENT_CAP,
    max_insert_depth: int = 8,
    explode_blocks: bool = True,
    layer_whitelist: list[str] | None = None,
) -> tuple[list[SegmentIn], dict[str, Any]]:
    """
    Preprocess (INSERT explode + discretize) sonrası, layer filtresi ve budget öncesi
    tüm segmentleri döndürür. original_total_segments / original_total_length_m
    bu listeden hesaplanır.
    """
    if ezdxf is None or recover is None:
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return [], {}
        plan = dxf_to_normalized_plan(
            text,
            units=units,
            scale=scale,
            origin=origin,
            layer_whitelist=layer_whitelist,
            layer_blacklist=None,
        )
        # ASCII parser şu an sadece LINE/LWPOLYLINE/POLYLINE desteklediği için
        # wall-only + drawable ayrımı stats bazında yapılamıyor; basit toplam uzunluk döndürülür.
        segs = list(plan.segments)
        stats: dict[str, Any] = {
            "total_segments": len(segs),
            "total_length": sum(
                math.hypot(s.x2 - s.x1, s.y2 - s.y1) for s in segs
            ),
        }
        return segs, stats

    doc, _ = _load_ezdxf_doc_from_bytes(raw)
    insunits = None
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = None
    _, total_scale, _, _ = _compute_units_and_scale(units, scale, insunits)
    ox, oy = origin
    bbox_m: list[float] | None = None
    try:
        ext = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        if ext and ext[0] and ext[1]:
            minp, maxp = ext
            bbox_m = [
                float(minp[0]) * total_scale + ox,
                float(minp[1]) * total_scale + oy,
                float(maxp[0]) * total_scale + ox,
                float(maxp[1]) * total_scale + oy,
            ]
    except Exception:
        bbox_m = None
    tol = float(chord_tolerance_m) if chord_tolerance_m is not None else _adaptive_tol_m_from_bbox(bbox_m)
    segments, stats = _ezdxf_doc_to_segments(
        doc,
        scale_to_world_m=total_scale,
        origin_m=(ox, oy),
        layer_whitelist=layer_whitelist,
        layer_blacklist=None,
        tolerance_m=tol,
        target_max_segments=int(target_max_segments),
        max_insert_depth=int(max_insert_depth),
        explode_blocks=bool(explode_blocks),
    )
    return segments, stats


# DXF Diagnostics: entity türleri ve eşikler
DIAGNOSTICS_ENTITY_TYPES = (
    "LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "SPLINE",
    "INSERT", "HATCH", "TEXT", "DIMENSION",
)
DIAG_HAS_MANY_SPLINES = 10
DIAG_HAS_MANY_HATCHES = 5
DIAG_HAS_MANY_BLOCKS = 20
DIAG_TOO_MANY_LAYERS = 50
DIAG_TOO_MANY_ENTITIES = 10000
DIAG_BBOX_WORLD_MISMATCH_M = 10000.0


def analyze_dxf_structure(raw_dxf_bytes: bytes) -> dict[str, Any]:
    """
    DXF dosyasının yapı analizi: entity dağılımı, layer analizi, karmaşıklık, bbox, birim, problem sinyalleri.
    Mevcut pipeline'ı değiştirmez; sadece analiz/raporlama katmanı.
    """
    result: dict[str, Any] = {
        "entity_counts": {},
        "layers": [],
        "complexity": {},
        "bbox": {},
        "units": {},
        "diagnostics_flags": [],
        # INSERT / HATCH diagnostikleri
        "insert_count": 0,
        "exploded_insert_entities": 0,
        "hatch_count": 0,
        "hatch_boundaries_extracted": 0,
    }
    for et in DIAGNOSTICS_ENTITY_TYPES:
        result["entity_counts"][et] = 0

    if ezdxf is None or recover is None:
        try:
            text = raw_dxf_bytes.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            result["diagnostics_flags"].append("binary_dxf_no_ezdxf")
            return result
        info = inspect_dxf_layers(text, units=None, scale=None, origin=(0.0, 0.0))
        ec = info.get("entity_counts_total") or info.get("layers", {})
        if isinstance(ec, dict):
            for k, v in ec.items():
                if k in result["entity_counts"]:
                    result["entity_counts"][k] = int(v)
        layers_info = info.get("layers") or {}
        for name, st in layers_info.items():
            if isinstance(st, dict):
                result["layers"].append({
                    "name": name,
                    "entity_count": int(st.get("entities", 0)),
                    "total_length": float(st.get("total_length_m", st.get("total_length", 0)) or 0),
                    "entity_types": list(st.get("entity_types", [])) if isinstance(st.get("entity_types"), list) else [],
                })
        insert_cnt = result["entity_counts"].get("INSERT", 0)
        hatch_cnt = result["entity_counts"].get("HATCH", 0)
        result["insert_count"] = int(insert_cnt)
        result["hatch_count"] = int(hatch_cnt)
        # ASCII yolunda boundary extraction bilgimiz yok; 0 bırak.
        result["complexity"] = {
            "total_entities": sum(result["entity_counts"].values()),
            "total_layers": len(result["layers"]),
            "total_segments_after_flatten": 0,
            "spline_count": result["entity_counts"].get("SPLINE", 0),
            "hatch_count": hatch_cnt,
            "insert_count": insert_cnt,
            "exploded_insert_entities": 0,
            "hatch_boundaries_extracted": 0,
        }
        bbox = info.get("bbox")
        if bbox and len(bbox) >= 4:
            result["bbox"] = {
                "bbox_size_world": [bbox[2] - bbox[0], bbox[3] - bbox[1]],
                "bbox_size_raw": None,
            }
        result["units"] = {"units_detected": info.get("dxf_units_detected")}
        return result

    doc, _ = _load_ezdxf_doc_from_bytes(raw_dxf_bytes)
    insunits = None
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = None
    _, total_scale, detected_unit, _ = _compute_units_and_scale(None, None, insunits)
    ox, oy = 0.0, 0.0
    bbox_m: list[float] | None = None
    bbox_raw: list[float] | None = None
    try:
        ext = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        if ext and ext[0] and ext[1]:
            minp, maxp = ext
            bbox_raw = [
                float(maxp[0]) - float(minp[0]),
                float(maxp[1]) - float(minp[1]),
            ]
            bbox_m = [
                float(minp[0]) * total_scale + ox,
                float(minp[1]) * total_scale + oy,
                float(maxp[0]) * total_scale + ox,
                float(maxp[1]) * total_scale + oy,
            ]
    except Exception:
        pass
    tol = _adaptive_tol_m_from_bbox(bbox_m) if bbox_m else 0.005
    segments, stats = _ezdxf_doc_to_segments(
        doc,
        scale_to_world_m=total_scale,
        origin_m=(ox, oy),
        layer_whitelist=None,
        layer_blacklist=None,
        tolerance_m=tol,
        target_max_segments=PREPROESS_SEGMENT_CAP,
        max_insert_depth=8,
        explode_blocks=True,
    )
    entity_counts_total = stats.get("entity_counts_total") or {}
    for k in result["entity_counts"]:
        result["entity_counts"][k] = int(entity_counts_total.get(k, 0))
    layer_entity_counts = stats.get("layer_entity_counts") or {}
    layer_stats = stats.get("layers") or {}
    for name, st in layer_stats.items():
        types_in_layer = layer_entity_counts.get(name) or {}
        entity_types = [t for t, c in types_in_layer.items() if c > 0]
        result["layers"].append({
            "name": name,
            "entity_count": int(st.get("entities", 0)),
            "total_length": float(st.get("total_length", 0) or 0),
            "entity_types": sorted(entity_types) if entity_types else [],
        })
    total_entities = sum(result["entity_counts"].values())
    insert_cnt = result["entity_counts"].get("INSERT", 0)
    hatch_cnt = result["entity_counts"].get("HATCH", 0)
    exploded_insert_entities = int(stats.get("insert_exploded_count", 0) or 0)
    hatch_boundaries_extracted = int(stats.get("hatch_boundaries_extracted", 0) or 0)
    result["insert_count"] = int(insert_cnt)
    result["exploded_insert_entities"] = exploded_insert_entities
    result["hatch_count"] = int(hatch_cnt)
    result["hatch_boundaries_extracted"] = hatch_boundaries_extracted
    result["complexity"] = {
        "total_entities": total_entities,
        "total_layers": len(result["layers"]),
        "total_segments_after_flatten": len(segments),
        "spline_count": result["entity_counts"].get("SPLINE", 0),
        "hatch_count": hatch_cnt,
        "insert_count": insert_cnt,
        "exploded_insert_entities": exploded_insert_entities,
        "hatch_boundaries_extracted": hatch_boundaries_extracted,
    }
    gbbox = stats.get("bbox")
    if gbbox and len(gbbox) >= 4:
        result["bbox"] = {
            "bbox_size_world": [
                round(float(gbbox[2]) - float(gbbox[0]), 6),
                round(float(gbbox[3]) - float(gbbox[1]), 6),
            ],
            "bbox_size_raw": bbox_raw,
        }
    else:
        result["bbox"] = {"bbox_size_world": None, "bbox_size_raw": bbox_raw}
    result["units"] = {"units_detected": detected_unit}

    flags: list[str] = []
    if result["entity_counts"].get("SPLINE", 0) >= DIAG_HAS_MANY_SPLINES:
        flags.append("has_many_splines")
    if result["entity_counts"].get("HATCH", 0) >= DIAG_HAS_MANY_HATCHES:
        flags.append("has_many_hatches")
    if result["entity_counts"].get("INSERT", 0) >= DIAG_HAS_MANY_BLOCKS:
        flags.append("has_many_blocks")
    if len(result["layers"]) >= DIAG_TOO_MANY_LAYERS:
        flags.append("too_many_layers")
    if total_entities >= DIAG_TOO_MANY_ENTITIES:
        flags.append("too_many_entities")
    bbox_world = result["bbox"].get("bbox_size_world")
    if bbox_world and detected_unit == "m":
        max_side = max(float(bbox_world[0]), float(bbox_world[1]))
        if max_side > DIAG_BBOX_WORLD_MISMATCH_M:
            flags.append("possible_units_mismatch")
    result["diagnostics_flags"] = flags
    return result


# Layer intelligence: plan/duvar katmanı otomatik seçimi için skorlama
LAYER_ENTITY_SCORE = {
    "LINE": 3,
    "LWPOLYLINE": 3,
    "ARC": 2,
    "POLYLINE": 1,
    "TEXT": -3,
    "DIMENSION": -3,
    "MTEXT": -3,
    "HATCH": -2,
    "INSERT": -2,
    "CIRCLE": 0,  # nötr (bazen plan, bazen detay)
    "SPLINE": 0,
}
LAYER_NAME_KEYWORDS = ("wall", "walls", "duvar", "outline", "plan", "floor")
LAYER_NAME_BONUS = 5
LAYER_MIN_ENTITIES = 3
LAYER_PENALTY_FEW_ENTITIES = 3
LAYER_SCORE_TIE_THRESHOLD = 1.0  # top1 ile top2 farkı bu kadar veya altındaysa 2 katman seçilebilir
LAYER_CANDIDATES_TOP_N = 3
LAYER_SELECT_DEFAULT_COUNT = 1


def select_plan_layers(dxf_diagnostics: dict[str, Any]) -> dict[str, Any]:
    """
    DXF diagnostics çıktısından çizim için uygun katmanları skorlayıp seçer.
    Döner: { "candidate_layers": [], "selected_layers": [], "scores": { "LayerName": score } }
    """
    result: dict[str, Any] = {
        "candidate_layers": [],
        "selected_layers": [],
        "scores": {},
    }
    layers = dxf_diagnostics.get("layers") or []
    if not isinstance(layers, list) or not layers:
        return result

    scored: list[tuple[str, float]] = []
    for ly in layers:
        if not isinstance(ly, dict):
            continue
        name = ly.get("name") or ly.get("layer_name")
        if not name or not isinstance(name, str):
            continue
        entity_count = int(ly.get("entity_count", 0))
        total_length = float(ly.get("total_length", 0) or 0)
        entity_types = ly.get("entity_types") or []
        if not isinstance(entity_types, list):
            entity_types = []

        score = 0.0
        # Entity türü skoru
        for et in entity_types:
            score += LAYER_ENTITY_SCORE.get(str(et).upper(), 0)
        # Uzunluk: log(total_length + 1)
        score += math.log(total_length + 1.0)
        # Çok az entity → plan değildir
        if entity_count < LAYER_MIN_ENTITIES:
            score -= LAYER_PENALTY_FEW_ENTITIES
        # İsim heuristiği
        name_lower = name.lower()
        if any(kw in name_lower for kw in LAYER_NAME_KEYWORDS):
            score += LAYER_NAME_BONUS

        result["scores"][name] = round(score, 4)
        scored.append((name, score))

    scored.sort(key=lambda x: (-x[1], x[0]))
    result["candidate_layers"] = [name for name, _ in scored[:LAYER_CANDIDATES_TOP_N]]
    if not scored:
        return result
    top1_name, top1_score = scored[0]
    result["selected_layers"] = [top1_name]
    if len(scored) >= 2:
        top2_name, top2_score = scored[1]
        if top1_score - top2_score < LAYER_SCORE_TIE_THRESHOLD and top2_score > 0:
            result["selected_layers"] = [top1_name, top2_name]
    return result


def inspect_dxf_layers_bytes(
    raw: bytes,
    *,
    units: str | None = None,
    scale: float | None = None,
    origin: tuple[float, float] = (0.0, 0.0),
    chord_tolerance_m: float | None = None,
    target_max_segments: int = 15000,
    max_insert_depth: int = 8,
    explode_blocks: bool = True,
) -> dict[str, Any]:
    """
    Bytes DXF (ASCII/Binary) için preview/inspect.
    ezdxf varsa eğriler+bloklar dahil segment istatistikleri döner.
    """
    if ezdxf is None or recover is None:
        text = raw.decode("utf-8", errors="strict")
        return inspect_dxf_layers(text, units=units, scale=scale, origin=origin)

    doc, doc_warnings = _load_ezdxf_doc_from_bytes(raw)
    insunits = None
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = None
    _, total_scale, detected_unit, unit_unknown = _compute_units_and_scale(units, scale, insunits)
    ox, oy = origin

    # bbox tahmini (header extents varsa)
    bbox_m: list[float] | None = None
    try:
        ext = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        if ext and ext[0] and ext[1]:
            minp, maxp = ext
            bbox_m = [
                float(minp[0]) * total_scale + ox,
                float(minp[1]) * total_scale + oy,
                float(maxp[0]) * total_scale + ox,
                float(maxp[1]) * total_scale + oy,
            ]
    except Exception:
        bbox_m = None

    tol = float(chord_tolerance_m) if chord_tolerance_m is not None else _adaptive_tol_m_from_bbox(bbox_m)
    _, stats = _ezdxf_doc_to_segments(
        doc,
        scale_to_world_m=total_scale,
        origin_m=(ox, oy),
        layer_whitelist=None,
        layer_blacklist=None,
        tolerance_m=tol,
        target_max_segments=int(target_max_segments),
        max_insert_depth=int(max_insert_depth),
        explode_blocks=bool(explode_blocks),
    )

    layer_stats = stats.get("layers") or {}
    # bbox'ları float list'e normalize et
    for name, st in layer_stats.items():
        if st.get("bbox") is not None:
            st["bbox"] = [float(x) for x in st["bbox"]]
        st["total_length_m"] = float(st.get("total_length", 0.0))
    global_bbox = stats.get("bbox")
    global_bbox_list = [float(x) for x in global_bbox] if global_bbox is not None else None

    # suggested_layers: keyword -> yoksa length top3
    KEYWORDS = ["wall", "walls", "duvar", "a-wall", "m-wall"]
    def _has_keyword(n: str) -> bool:
        lower = n.lower()
        return any(kw in lower for kw in KEYWORDS)

    layers_with_stats = [
        (name, st)
        for name, st in layer_stats.items()
        if st.get("segments", 0) > 0 and st.get("total_length", 0.0) > 0.0
    ]
    keyword_layers = [(n, s) for n, s in layers_with_stats if _has_keyword(n)]
    if keyword_layers:
        keyword_layers.sort(key=lambda item: (-float(item[1].get("total_length", 0.0)), item[0]))
        suggested_layers = [n for n, _ in keyword_layers]
    else:
        layers_with_stats.sort(key=lambda item: (-float(item[1].get("total_length", 0.0)), item[0]))
        suggested_layers = [n for n, _ in layers_with_stats[:3]]

    # Insight raporu için mevcut yardımcıları kullan
    entity_counts_total = stats.get("entity_counts_total", {})
    entity_counts_supported = {
        k: v for k, v in entity_counts_total.items()
        if k in SUPPORTED_ENTITY_TYPES or k in ("ARC", "CIRCLE", "SPLINE", "INSERT")
    }
    entity_counts_unsupported = {
        k: v for k, v in entity_counts_total.items()
        if k not in entity_counts_supported and k not in ("VERTEX", "SEQEND")
    }

    parse_warnings: list[Any] = list(doc_warnings)
    warning_codes: list[str] = []
    if unit_unknown:
        warning_codes.append("UNIT_UNKNOWN")
    if (stats.get("discretized_counts", {}).get("SPLINE", 0) or 0) > 0:
        warning_codes.append("SPLINE_DISCRETIZED")
    if (stats.get("discretized_counts", {}).get("ARC", 0) or 0) > 0 or (stats.get("discretized_counts", {}).get("CIRCLE", 0) or 0) > 0:
        warning_codes.append("ARC_DISCRETIZED")
    if (stats.get("insert_exploded_count", 0) or 0) > 0:
        warning_codes.append("INSERT_EXPLODED")
    parse_warnings.extend(stats.get("warnings") or [])

    # layer scoring + reasons: mevcut fonksiyon
    layers_by_length = sorted(
        layers_with_stats,
        key=lambda item: (-float(item[1].get("total_length", 0.0)), item[0]),
    )
    layer_scores, suggested_layers_reasons = _build_layer_scores_and_reasons(
        layer_stats,
        stats.get("layer_entity_counts", {}) or {},
        keyword_layers,
        layers_by_length,
    )

    supported_total = sum(int(x) for x in entity_counts_supported.values())
    unsupported_total = sum(int(x) for x in entity_counts_unsupported.values())
    if unsupported_total > 0:
        recommended_action = (
            f"Eğriler/bloklar dahil {supported_total} entity segmente çevrildi. "
            f"{unsupported_total} entity çizim dışı olabilir. Önerilen katmanları seçin."
        )
    else:
        recommended_action = "Plan hazır. Önerilen katmanları seçip komutları oluşturun."

    return {
        "layers": layer_stats,
        "total_segments": int(stats.get("total_segments", 0)),
        "total_length": float(stats.get("total_length", 0.0)),
        "bbox": global_bbox_list,
        "suggested_layers": suggested_layers,
        "dxf_units_detected": detected_unit,
        "world_unit": WORLD_UNIT_BASE,
        "world_scale": total_scale,
        "unit_unknown": unit_unknown,
        "entity_counts_total": entity_counts_total,
        "entity_counts_supported": entity_counts_supported,
        "entity_counts_unsupported": entity_counts_unsupported,
        "unsupported_samples": [],
        "layer_entity_counts": stats.get("layer_entity_counts", {}),
        "layer_scores": layer_scores,
        "suggested_layers_reasons": suggested_layers_reasons,
        "parse_warnings": parse_warnings,
        "warning_codes": warning_codes,
        "recommended_action": recommended_action,
    }


def _parse_group_pairs_streaming(
    lines: list[str],
) -> tuple[list[tuple[int, str]], list[str]]:
    """
    Satır listesi üzerinde akışlı group-code çiftleri okur.
    - Boş / sadece boşluk satırları atlanır.
    - code satırı tamsayı değilse: en fazla RESYNC_LOOKAHEAD_LINES satır ileriye bakıp
      tamsayı group code aranır; bulunursa uyarı eklenip oradan devam edilir.
    - 999 (yorum): çift tüketilir, listeye eklenmez.
    Döner: (pairs, warnings).
    """
    pairs: list[tuple[int, str]] = []
    warnings: list[str] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        code_line = raw.strip()
        i += 1
        if not code_line:
            continue
        try:
            code = int(code_line)
        except ValueError:
            # Resync: ileriye doğru tamsayı group code ara
            found: int | None = None
            j = i
            scanned = 0
            while j < len(lines) and scanned < RESYNC_LOOKAHEAD_LINES:
                l = lines[j].strip()
                if l:
                    scanned += 1
                    try:
                        int(l)
                        found = j
                        break
                    except ValueError:
                        pass
                j += 1
            if found is not None:
                warnings.append(f"DXF parse resynced at line {found + 1}")
                i = found
                continue
            start = max(0, i - 1 - 2)
            end = min(len(lines), i - 1 + 4)
            context_lines = [f"  {start + k + 1}: {lines[start + k]!r}" for k in range(end - start)]
            raise ValueError(
                f"Geçersiz DXF group code (tamsayı bekleniyor): '{code_line}'. Yakın satırlar:\n" + "\n".join(context_lines)
            )
        # Sonraki boş olmayan satır = value
        j = i
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines):
            break
        value_line = lines[j].strip()
        i = j + 1
        if code == 999:
            continue
        pairs.append((code, value_line))
    return pairs, warnings


def _find_sections(pairs: list[tuple[int, str]]) -> dict[str, list[tuple[int, str]]]:
    """SECTION (0) / 2 name ile bölümleri bul; ENDSEC'e kadar topla."""
    sections: dict[str, list[tuple[int, str]]] = {}
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code == 0 and value == "SECTION":
            i += 1
            if i >= len(pairs):
                raise ValueError("DXF: SECTION sonrası section adı (2) eksik")
            code2, name = pairs[i]
            if code2 != 2:
                raise ValueError("DXF: SECTION sonrası group code 2 (section adı) bekleniyor")
            name = name.strip().upper()
            i += 1
            section_pairs: list[tuple[int, str]] = []
            while i < len(pairs):
                c, v = pairs[i]
                if c == 0 and v == "ENDSEC":
                    i += 1
                    break
                section_pairs.append((c, v))
                i += 1
            sections[name] = section_pairs
            continue
        i += 1
    return sections


def _get_header_insunits(header_pairs: list[tuple[int, str]]) -> int | None:
    """HEADER bölümünde $INSUNITS değerini döndür (group 9 '$INSUNITS' sonrası 70)."""
    for j, (code, value) in enumerate(header_pairs):
        if code == 9 and value.strip() == "$INSUNITS":
            if j + 1 < len(header_pairs) and header_pairs[j + 1][0] == 70:
                try:
                    return int(header_pairs[j + 1][1].strip())
                except ValueError:
                    pass
            break
    return None


def _split_entities(pairs: list[tuple[int, str]]) -> list[tuple[str, list[tuple[int, str]]]]:
    """ENTITIES bölümünde her 0 <type> ile başlayan entity'yi (type, pairs) olarak ayır."""
    entities: list[tuple[str, list[tuple[int, str]]]] = []
    i = 0
    while i < len(pairs):
        code, value = pairs[i]
        if code != 0:
            i += 1
            continue
        etype = value.strip().upper()
        i += 1
        entity_pairs: list[tuple[int, str]] = []
        while i < len(pairs) and pairs[i][0] != 0:
            entity_pairs.append(pairs[i])
            i += 1
        entities.append((etype, entity_pairs))
    return entities


def _entity_get_first(entity_pairs: list[tuple[int, str]], *codes: int) -> list[float]:
    """İlk eşleşen code sırasıyla değerleri float olarak döndür (sıra: 10,20,11,21 gibi)."""
    by_code: dict[int, list[str]] = {}
    for c, v in entity_pairs:
        if c not in by_code:
            by_code[c] = []
        by_code[c].append(v.strip())
    out: list[float] = []
    for c in codes:
        if c in by_code and by_code[c]:
            try:
                out.append(float(by_code[c][0]))
            except ValueError:
                out.append(0.0)
        else:
            return out
    return out


def _entity_get_all_xy_ordered(entity_pairs: list[tuple[int, str]]) -> list[tuple[float, float]]:
    """10 ve 20 değerlerini sırayla (x1,y1, x2,y2, ...) topla."""
    xs: list[float] = []
    ys: list[float] = []
    for c, v in entity_pairs:
        if c == 10:
            try:
                xs.append(float(v.strip()))
            except ValueError:
                pass
        elif c == 20:
            try:
                ys.append(float(v.strip()))
            except ValueError:
                pass
    n = min(len(xs), len(ys))
    return [(xs[i], ys[i]) for i in range(n)]


def _entity_get_flag70(entity_pairs: list[tuple[int, str]]) -> int:
    """70 (polyline flags) ilk değerini döndür; yoksa 0."""
    for c, v in entity_pairs:
        if c == 70:
            try:
                return int(v.strip())
            except ValueError:
                return 0
    return 0


def _entity_get_layer(entity_pairs: list[tuple[int, str]]) -> str:
    """8 = layer adı."""
    for c, v in entity_pairs:
        if c == 8:
            return v.strip()
    return "0"


def _entity_get_handle(entity_pairs: list[tuple[int, str]]) -> str | None:
    """5 = entity handle (opsiyonel)."""
    for c, v in entity_pairs:
        if c == 5:
            return v.strip()
    return None


# Desteklenen entity tipleri (segment üretir)
SUPPORTED_ENTITY_TYPES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE"})

# MVP: Wall-only pipeline
# Amaç: Basit floor-plan duvar çizgilerini güvenilir şekilde çizmek; annotation/noise entity'lerini elemek.
# Not: HATCH boundary'leri ezdxf ile segmente çevrilebildiği için wall drawable setine dahil.
WALL_DRAWABLE_ENTITY_TYPES = frozenset({"LINE", "LWPOLYLINE", "POLYLINE", "ARC", "SPLINE", "HATCH"})
NON_WALL_ENTITY_TYPES = frozenset({"TEXT", "MTEXT", "DIMENSION"})
BLOCK_ENTITY_TYPES = frozenset({"INSERT"})

# Bilinen desteklenmeyen tipler (insight raporunda ayrı sayılır)
UNSUPPORTED_ENTITY_TYPES = frozenset({
    "ARC", "CIRCLE", "SPLINE", "HATCH", "INSERT", "XREF",
    "DIMENSION", "TEXT", "MTEXT", "ELLIPSE", "POINT", "SOLID",
    "TRACE", "SHAPE", "IMAGE", "LEADER", "MLEADER",
})

# Uyarı kodu → kullanıcı aksiyonu önerisi
WARNING_CODE_USER_ACTIONS: dict[str, str] = {
    "UNSUPPORTED_INSERT": "Bloklar (INSERT) henüz desteklenmiyor. CAD'de 'Explode' ile patlatıp tekrar kaydedin.",
    "UNSUPPORTED_ARC": "Yaylar (ARC) atlandı. CAD'de 'Flatten' veya polyline'a dönüştürün.",
    "UNSUPPORTED_SPLINE": "Eğriler (SPLINE) atlandı. CAD'de polyline'a dönüştürün.",
    "UNSUPPORTED_CIRCLE": "Daireler (CIRCLE) atlandı. CAD'de polyline'a dönüştürün.",
    "HAS_HATCH": "Taramalar (HATCH) çizilmez. Sadece boundary polyline kullanılabilir.",
    "HAS_TEXT_DIM": "Ölçü ve metin entity'leri çizilmez. Duvar katmanını seçin.",
    "LAYER_COMPLEXITY_HIGH": "Katmanda çok fazla entity tipi var. Sadece duvar katmanını seçin.",
    "UNIT_UNKNOWN": "DXF birimi belirsiz; mm varsayıldı. Doğru birim için CAD'de $INSUNITS ayarlayın.",
}


def parse_dxf_ascii(text: str) -> dict[str, Any]:
    """
    ASCII DXF metnini parse eder. Akışlı group-code çiftleri; boş satırlar ve 999 yorumları tolere edilir.
    Dönüş: {"header": {...}, "entities": [...], "warnings": [...]}
    Binary veya ENTITIES yoksa ValueError.
    """
    if not text or not text.strip():
        raise ValueError("DXF metni boş")
    if _is_binary_dxf(text):
        raise ValueError("Binary DXF desteklenmiyor; yalnızca ASCII DXF kullanın")

    lines = text.splitlines()
    pairs, parse_warnings = _parse_group_pairs_streaming(lines)

    sections = _find_sections(pairs)
    if "ENTITIES" not in sections:
        raise ValueError("DXF dosyasında ENTITIES bölümü bulunamadı")

    header = {"insunits": None}
    if "HEADER" in sections:
        header["insunits"] = _get_header_insunits(sections["HEADER"])

    entity_list: list[dict[str, Any]] = []
    for etype, entity_pairs in _split_entities(sections["ENTITIES"]):
        entity_list.append({"type": etype, "pairs": entity_pairs})

    return {"header": header, "entities": entity_list, "warnings": parse_warnings}


def _line_to_segment(
    entity_pairs: list[tuple[int, str]],
    origin: tuple[float, float],
    scale: float,
    layer_whitelist: list[str] | None,
    layer_blacklist: list[str] | None,
) -> SegmentIn | None:
    vals = _entity_get_first(entity_pairs, 10, 20, 11, 21)
    if len(vals) < 4:
        return None
    if layer_whitelist is not None and _entity_get_layer(entity_pairs) not in layer_whitelist:
        return None
    if layer_blacklist is not None and _entity_get_layer(entity_pairs) in layer_blacklist:
        return None
    x1 = vals[0] * scale + origin[0]
    y1 = vals[1] * scale + origin[1]
    x2 = vals[2] * scale + origin[0]
    y2 = vals[3] * scale + origin[1]
    return SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2)


def _lwpolyline_to_segments(
    entity_pairs: list[tuple[int, str]],
    origin: tuple[float, float],
    scale: float,
    layer_whitelist: list[str] | None,
    layer_blacklist: list[str] | None,
) -> list[SegmentIn]:
    if layer_whitelist is not None and _entity_get_layer(entity_pairs) not in layer_whitelist:
        return []
    if layer_blacklist is not None and _entity_get_layer(entity_pairs) in layer_blacklist:
        return []
    pts = _entity_get_all_xy_ordered(entity_pairs)
    if len(pts) < 2:
        return []
    closed = (_entity_get_flag70(entity_pairs) & 1) != 0
    segs: list[SegmentIn] = []
    for i in range(len(pts) - 1):
        x1, y1 = pts[i][0] * scale + origin[0], pts[i][1] * scale + origin[1]
        x2, y2 = pts[i + 1][0] * scale + origin[0], pts[i + 1][1] * scale + origin[1]
        segs.append(SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2))
    if closed and len(pts) >= 2:
        x1, y1 = pts[-1][0] * scale + origin[0], pts[-1][1] * scale + origin[1]
        x2, y2 = pts[0][0] * scale + origin[0], pts[0][1] * scale + origin[1]
        segs.append(SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2))
    return segs


def _polyline_vertices_to_segments(
    vertex_entities: list[list[tuple[int, str]]],
    flags: int,
    origin: tuple[float, float],
    scale: float,
    layer_whitelist: list[str] | None,
    layer_blacklist: list[str] | None,
    polyline_layer: str,
) -> list[SegmentIn]:
    """POLYLINE entity'nin layer'ı polyline_layer ile verilir; filtre bu layer'a göre uygulanır."""
    if layer_whitelist is not None and polyline_layer not in layer_whitelist:
        return []
    if layer_blacklist is not None and polyline_layer in layer_blacklist:
        return []
    pts: list[tuple[float, float]] = []
    for vp in vertex_entities:
        xy = _entity_get_all_xy_ordered(vp)
        if xy:
            pts.append(xy[0])
    if len(pts) < 2:
        return []
    closed = (flags & 1) != 0
    segs: list[SegmentIn] = []
    for i in range(len(pts) - 1):
        x1, y1 = pts[i][0] * scale + origin[0], pts[i][1] * scale + origin[1]
        x2, y2 = pts[i + 1][0] * scale + origin[0], pts[i + 1][1] * scale + origin[1]
        segs.append(SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2))
    if closed and len(pts) >= 2:
        x1, y1 = pts[-1][0] * scale + origin[0], pts[-1][1] * scale + origin[1]
        x2, y2 = pts[0][0] * scale + origin[0], pts[0][1] * scale + origin[1]
        segs.append(SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2))
    return segs


def dxf_to_normalized_plan(
    text: str,
    *,
    units: str | None = None,
    scale: float | None = None,
    origin: tuple[float, float] = (0.0, 0.0),
    layer_whitelist: list[str] | None = None,
    layer_blacklist: list[str] | None = None,
) -> NormalizedPlan:
    """
    ASCII DXF metnini NormalizedPlan v1'e dönüştürür.
    Desteklenen entity'ler: LINE, LWPOLYLINE, POLYLINE (VERTEX ile).
    Arc/circle/spline yok sayılır. Hiç desteklenen entity yoksa ValueError.
    """
    parsed = parse_dxf_ascii(text)
    header = parsed["header"]
    entities = parsed["entities"]

    # Birim ve ölçek (inspect_dxf_layers ile aynı mantık)
    insunits = header.get("insunits")
    out_units, total_scale, detected_unit, unit_unknown = _compute_units_and_scale(
        units, scale, insunits
    )

    ox, oy = origin
    segments: list[SegmentIn] = []
    entity_counts: dict[str, int] = {}

    # POLYLINE + VERTEX zincirlerini tek seferde işle
    i = 0
    while i < len(entities):
        etype = entities[i]["type"]
        pairs = entities[i]["pairs"]
        if etype == "POLYLINE":
            flags = _entity_get_flag70(pairs)
            verts: list[list[tuple[int, str]]] = []
            i += 1
            while i < len(entities) and entities[i]["type"] == "VERTEX":
                verts.append(entities[i]["pairs"])
                i += 1
            if i < len(entities) and entities[i]["type"] == "SEQEND":
                i += 1
            polyline_layer = _entity_get_layer(pairs)
            segs = _polyline_vertices_to_segments(
                verts, flags, (ox, oy), total_scale, layer_whitelist, layer_blacklist, polyline_layer
            )
            segments.extend(segs)
            entity_counts["POLYLINE"] = entity_counts.get("POLYLINE", 0) + 1
            continue

        if etype == "LINE":
            seg = _line_to_segment(pairs, (ox, oy), total_scale, layer_whitelist, layer_blacklist)
            if seg is not None:
                segments.append(seg)
            entity_counts["LINE"] = entity_counts.get("LINE", 0) + 1
        elif etype == "LWPOLYLINE":
            segs = _lwpolyline_to_segments(
                pairs, (ox, oy), total_scale, layer_whitelist, layer_blacklist
            )
            segments.extend(segs)
            entity_counts["LWPOLYLINE"] = entity_counts.get("LWPOLYLINE", 0) + 1
        # VERTEX, SEQEND, ARC, CIRCLE, SPLINE vb. tek başına atlanır (POLYLINE dışında)
        i += 1
    # SEQEND tek başına kalmışsa zaten atlandı

    if not segments:
        raise ValueError(
            "DXF dosyasında desteklenen entity (LINE, LWPOLYLINE, POLYLINE) bulunamadı veya filtre sonrası segment kalmadı"
        )

    # Extraction summary (importer çıkışı, normalize öncesi)
    def _seg_len(s: SegmentIn) -> float:
        return math.hypot(s.x2 - s.x1, s.y2 - s.y1)

    def _has_nan(s: SegmentIn) -> bool:
        return (
            math.isnan(s.x1) or math.isnan(s.y1) or math.isnan(s.x2) or math.isnan(s.y2)
            or not math.isfinite(s.x1) or not math.isfinite(s.y1)
            or not math.isfinite(s.x2) or not math.isfinite(s.y2)
        )

    lengths = [_seg_len(s) for s in segments]
    dropped_zero_length_count = sum(1 for L in lengths if L <= 1e-12)
    dropped_nan_count = sum(1 for s in segments if _has_nan(s))
    valid_segments = [s for s in segments if not _has_nan(s)]
    valid_lengths = [_seg_len(s) for s in valid_segments if not _has_nan(s)]

    # Duplicate estimate: hash-based (x1,y1,x2,y2 rounded)
    def _seg_hash(s: SegmentIn) -> str:
        return f"{round(s.x1, 6)},{round(s.y1, 6)},{round(s.x2, 6)},{round(s.y2, 6)}"

    seen_hashes: set[str] = set()
    dup_estimate = 0
    for s in valid_segments:
        h = _seg_hash(s)
        if h in seen_hashes:
            dup_estimate += 1
        seen_hashes.add(h)

    extraction_summary: dict[str, Any] = {
        "extracted_segment_count": len(segments),
        "dropped_zero_length_count": dropped_zero_length_count,
        "dropped_nan_count": dropped_nan_count,
        "segment_budget_applied": False,
        "kept_count": len(segments),
        "dropped_count": 0,
        "min_segment_length": min(valid_lengths) if valid_lengths else 0.0,
        "max_segment_length": max(valid_lengths) if valid_lengths else 0.0,
        "duplicate_estimate_count": dup_estimate,
    }

    metadata: dict[str, Any] = {
        "source": "dxf",
        "insunits": insunits,
        "dxf_units_detected": detected_unit,
        "world_unit": WORLD_UNIT_BASE,
        "world_scale": total_scale,
        "unit_unknown": unit_unknown,
        "entity_counts": entity_counts,
        "parse_warnings": parsed.get("warnings", []),
        "extraction_summary": extraction_summary,
    }
    if unit_unknown:
        metadata.setdefault("parse_warnings", []).append(
            "DXF $INSUNITS bulunamadı veya 0; mm varsayıldı ve metreye çevrildi."
        )
    return NormalizedPlan(
        version="v1",
        units=out_units,
        scale=1.0,
        origin=OriginIn(x=ox, y=oy),
        segments=segments,
        metadata=metadata,
    )


def dxf_bytes_to_normalized_plan(
    raw: bytes,
    *,
    units: str | None = None,
    scale: float | None = None,
    origin: tuple[float, float] = (0.0, 0.0),
    layer_whitelist: list[str] | None = None,
    layer_blacklist: list[str] | None = None,
    chord_tolerance_m: float | None = None,
    target_max_segments: int = 15000,
    max_insert_depth: int = 8,
    explode_blocks: bool = True,
) -> NormalizedPlan:
    """
    Bytes DXF (ASCII veya Binary) -> NormalizedPlan.
    ezdxf mevcutsa SPLINE/ARC/CIRCLE/INSERT dahil segmente çevirmeyi dener.
    ezdxf yoksa UTF-8 decode ile mevcut ASCII parser'a düşer.
    """
    if ezdxf is None or recover is None:
        # fallback: UTF-8 text bekler
        try:
            text = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            raise ValueError("DXF okunamadı (binary olabilir) ve ezdxf yüklü değil.")
        return dxf_to_normalized_plan(
            text,
            units=units,
            scale=scale,
            origin=origin,
            layer_whitelist=layer_whitelist,
            layer_blacklist=layer_blacklist,
        )

    doc, doc_warnings = _load_ezdxf_doc_from_bytes(raw)
    insunits = None
    try:
        insunits = int(doc.header.get("$INSUNITS", 0))
    except Exception:
        insunits = None

    out_units, total_scale, detected_unit, unit_unknown = _compute_units_and_scale(
        units, scale, insunits
    )

    ox, oy = origin
    # Önce kaba bbox: layer filtreli olmasın (tolerance hesabı için)
    bbox_m: list[float] | None = None
    try:
        ext = doc.header.get("$EXTMIN"), doc.header.get("$EXTMAX")
        if ext and ext[0] and ext[1]:
            minp, maxp = ext
            bbox_m = [
                float(minp[0]) * total_scale + ox,
                float(minp[1]) * total_scale + oy,
                float(maxp[0]) * total_scale + ox,
                float(maxp[1]) * total_scale + oy,
            ]
    except Exception:
        bbox_m = None

    tol = float(chord_tolerance_m) if chord_tolerance_m is not None else _adaptive_tol_m_from_bbox(bbox_m)

    segments, stats = _ezdxf_doc_to_segments(
        doc,
        scale_to_world_m=total_scale,
        origin_m=(ox, oy),
        layer_whitelist=layer_whitelist,
        layer_blacklist=layer_blacklist,
        tolerance_m=tol,
        target_max_segments=int(target_max_segments),
        max_insert_depth=int(max_insert_depth),
        explode_blocks=bool(explode_blocks),
    )

    if not segments:
        raise ValueError("DXF'ten segment üretilemedi (explode/discretize sonrası 0).")

    warning_codes: list[str] = []
    parse_warnings: list[Any] = list(doc_warnings)
    if unit_unknown:
        warning_codes.append("UNIT_UNKNOWN")
        parse_warnings.append("DXF $INSUNITS bulunamadı veya 0; mm varsayıldı ve metreye çevrildi.")
    if stats["discretized_counts"].get("SPLINE", 0) > 0:
        warning_codes.append("SPLINE_DISCRETIZED")
    if stats["discretized_counts"].get("ARC", 0) > 0 or stats["discretized_counts"].get("CIRCLE", 0) > 0:
        warning_codes.append("ARC_DISCRETIZED")
    if stats.get("insert_exploded_count", 0) > 0:
        warning_codes.append("INSERT_EXPLODED")

    parse_warnings.extend(stats.get("warnings") or [])
    parse_warnings.append(
        {
            "code": "DISCRETIZE_TOL_USED",
            "message": f"Flatten tolerance: {tol:.6f} m",
            "user_action": "Detay/Normal/Hızlı mod ile toleransı değiştirebilirsiniz.",
        }
    )
    if len(segments) >= int(target_max_segments):
        warning_codes.append("SEGMENT_BUDGET_APPLIED")
        parse_warnings.append(
            {
                "code": "SEGMENT_BUDGET_APPLIED",
                "message": (
                    f"Segment bütçesi uygulandı: {len(segments)} segment "
                    f"(limit={int(target_max_segments)}). Ek geometri kesilmiş olabilir."
                ),
                "user_action": "target_max_segments artırın veya katman filtresini daraltın.",
            }
        )

    metadata: dict[str, Any] = {
        "source": "dxf",
        "insunits": insunits,
        "dxf_units_detected": detected_unit,
        "world_unit": WORLD_UNIT_BASE,
        "world_scale": total_scale,
        "unit_unknown": unit_unknown,
        "entity_counts": stats.get("entity_counts_total", {}),
        "parse_warnings": parse_warnings,
        "warning_codes": warning_codes,
        "discretized_counts": stats.get("discretized_counts", {}),
    }
    # MVP: wall-only extraction özeti (neden ne elendi)
    extraction_summary: dict[str, Any] = {
        "wall_only": True,
        "extracted_segment_count": len(segments),
        "filtered_out_by_layer": int(stats.get("filtered_out_by_layer", 0) or 0),
        "dropped_entities_by_reason": stats.get("dropped_entities_by_reason", {}) or {},
        "dropped_entities_by_type": stats.get("dropped_entities_by_type", {}) or {},
        "segment_budget_applied": bool(len(segments) >= int(target_max_segments)),
    }
    metadata["extraction_summary"] = extraction_summary
    return NormalizedPlan(
        version="v1",
        units=out_units,
        scale=1.0,
        origin=OriginIn(x=ox, y=oy),
        segments=segments,
        metadata=metadata,
    )


def _count_all_entities_and_unsupported_samples(
    entities: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, dict[str, int]], list[dict[str, Any]]]:
    """
    Tüm entity tiplerini sayar, katman bazlı entity sayıları ve desteklenmeyen örnekler döner.
    POLYLINE/VERTEX/SEQEND tek entity olarak sayılır (POLYLINE = 1).
    """
    entity_counts_total: dict[str, int] = {}
    layer_entity_counts: dict[str, dict[str, int]] = {}
    unsupported_samples: list[dict[str, Any]] = []
    max_samples = 10

    i = 0
    while i < len(entities):
        etype = entities[i]["type"]
        pairs = entities[i]["pairs"]
        layer_name = _entity_get_layer(pairs) or "0"
        handle = _entity_get_handle(pairs)

        # Entity say
        entity_counts_total[etype] = entity_counts_total.get(etype, 0) + 1
        if layer_name not in layer_entity_counts:
            layer_entity_counts[layer_name] = {}
        layer_entity_counts[layer_name][etype] = layer_entity_counts[layer_name].get(etype, 0) + 1

        # Desteklenmeyen örnek topla (VERTEX, SEQEND hariç — bunlar POLYLINE ile birlikte)
        if etype not in SUPPORTED_ENTITY_TYPES and etype not in ("VERTEX", "SEQEND"):
            if len(unsupported_samples) < max_samples:
                note = "Atlandı"
                if etype == "INSERT":
                    note = "Blok referansı; patlatılmadı"
                elif etype in ("ARC", "CIRCLE", "SPLINE"):
                    note = "Eğri; discretize edilmedi"
                elif etype in ("HATCH", "TEXT", "MTEXT", "DIMENSION"):
                    note = "Çizim dışı entity"
                unsupported_samples.append({
                    "type": etype,
                    "layer": layer_name,
                    "handle": handle,
                    "note": note,
                })

        if etype == "POLYLINE":
            i += 1
            while i < len(entities) and entities[i]["type"] == "VERTEX":
                i += 1
            if i < len(entities) and entities[i]["type"] == "SEQEND":
                i += 1
            continue
        i += 1

    return entity_counts_total, layer_entity_counts, unsupported_samples


def _build_layer_scores_and_reasons(
    layer_stats: dict[str, dict[str, Any]],
    layer_entity_counts: dict[str, dict[str, int]],
    keyword_layers: list[tuple[str, dict]],
    layers_by_length: list[tuple[str, dict]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    layer_scores ve suggested_layers_reasons üretir.
    """
    KEYWORDS = ["wall", "walls", "duvar", "a-wall", "m-wall"]

    def _has_keyword(name: str) -> bool:
        return any(kw in name.lower() for kw in KEYWORDS)

    layer_scores: list[dict[str, Any]] = []
    for name, stats in layer_stats.items():
        if stats.get("segments", 0) == 0 or stats.get("total_length", 0) <= 0:
            continue
        reasons: list[str] = []
        score = 0.0
        entity_mix = layer_entity_counts.get(name, {})
        entity_mix_summary = ", ".join(f"{t}:{c}" for t, c in sorted(entity_mix.items())[:5])
        if len(entity_mix) > 5:
            entity_mix_summary += ", ..."

        # İsim eşleşmesi
        if _has_keyword(name):
            score += 2.0
            reasons.append("İsim eşleşmesi (wall/duvar)")
        # Uzunluk (en uzun katmanlar)
        length = stats.get("total_length", 0)
        if length > 0:
            score += min(1.5, length / 100.0)  # Uzunluk bonusu
            reasons.append(f"Toplam uzunluk: {length:.1f}m")
        # TEXT/DIM oranı düşük
        text_dim = entity_mix.get("TEXT", 0) + entity_mix.get("MTEXT", 0) + entity_mix.get("DIMENSION", 0)
        total_ent = sum(entity_mix.values())
        if total_ent > 0 and text_dim / total_ent > 0.3:
            score -= 1.0
            reasons.append("Yüksek metin/ölçü oranı")
        elif total_ent > 0 and text_dim == 0:
            reasons.append("Metin/ölçü yok")
        # Bbox kapsama (basit: segment var)
        if stats.get("bbox"):
            reasons.append("Bbox kapsıyor")

        layer_scores.append({
            "layer": name,
            "score": round(score, 2),
            "reasons": reasons,
            "length_m": round(length, 4),
            "entity_mix_summary": entity_mix_summary,
        })

    layer_scores.sort(key=lambda x: (-x["score"], -x["length_m"], x["layer"]))

    # suggested_layers_reasons
    suggested_layers_reasons: list[dict[str, Any]] = []
    if keyword_layers:
        for name, _ in keyword_layers[:5]:
            reasons_str = "İsim eşleşmesi (wall/duvar)"
            suggested_layers_reasons.append({"layer": name, "reason": reasons_str})
    else:
        for name, stats in layers_by_length[:5]:
            reasons_str = "En yüksek toplam uzunluk"
            suggested_layers_reasons.append({"layer": name, "reason": reasons_str})

    return layer_scores, suggested_layers_reasons


def inspect_dxf_layers(
    text: str,
    *,
    units: str | None = None,
    scale: float | None = None,
    origin: tuple[float, float] = (0.0, 0.0),
) -> dict[str, Any]:
    """
    DXF katmanlarını ve segment istatistiklerini döndürür.
    dxf_to_normalized_plan ile aynı units/scale/origin mantığını kullanır.
    DXF Insight Report: entity_counts_total, unsupported_samples, layer_scores, suggested_layers_reasons.
    """
    parsed = parse_dxf_ascii(text)
    header = parsed["header"]
    entities = parsed["entities"]

    insunits = header.get("insunits")
    _, total_scale, detected_unit, unit_unknown = _compute_units_and_scale(
        units, scale, insunits
    )

    # 1) Tüm entity sayıları ve desteklenmeyen örnekler
    entity_counts_total, layer_entity_counts, unsupported_samples = (
        _count_all_entities_and_unsupported_samples(entities)
    )
    entity_counts_supported = {
        k: v for k, v in entity_counts_total.items()
        if k in SUPPORTED_ENTITY_TYPES
    }
    entity_counts_unsupported = {
        k: v for k, v in entity_counts_total.items()
        if k not in SUPPORTED_ENTITY_TYPES and k not in ("VERTEX", "SEQEND")
    }

    # 2) Reason-coded parse_warnings
    parse_warnings: list[dict[str, Any] | str] = list(parsed.get("warnings", []))
    warning_codes: list[str] = []
    if unit_unknown:
        parse_warnings.append("DXF $INSUNITS bulunamadı veya 0; mm varsayıldı ve metreye çevrildi.")
        warning_codes.append("UNIT_UNKNOWN")
    if entity_counts_total.get("INSERT", 0) > 0:
        warning_codes.append("UNSUPPORTED_INSERT")
    if entity_counts_total.get("ARC", 0) > 0:
        warning_codes.append("UNSUPPORTED_ARC")
    if entity_counts_total.get("SPLINE", 0) > 0:
        warning_codes.append("UNSUPPORTED_SPLINE")
    if entity_counts_total.get("CIRCLE", 0) > 0:
        warning_codes.append("UNSUPPORTED_CIRCLE")
    if entity_counts_total.get("HATCH", 0) > 0:
        warning_codes.append("HAS_HATCH")
    text_dim_count = (
        entity_counts_total.get("TEXT", 0) + entity_counts_total.get("MTEXT", 0) +
        entity_counts_total.get("DIMENSION", 0)
    )
    if text_dim_count > 0:
        warning_codes.append("HAS_TEXT_DIM")

    # Structured warnings (backward compatible: string + structured)
    for code in warning_codes:
        parse_warnings.append({
            "code": code,
            "message": WARNING_CODE_USER_ACTIONS.get(code, "Bilinmeyen uyarı"),
            "user_action": WARNING_CODE_USER_ACTIONS.get(code, "Detayları inceleyin."),
        })

    # 3) Layer stats (desteklenen entity'lerden segment)
    ox, oy = origin
    layer_stats: dict[str, dict[str, Any]] = {}
    total_segments = 0
    total_length = 0.0
    global_bbox = None

    def _update_bbox(bbox, x, y):
        if bbox is None:
            return [x, y, x, y]
        minx, miny, maxx, maxy = bbox
        return [
            min(minx, x),
            min(miny, y),
            max(maxx, x),
            max(maxy, y),
        ]

    i = 0
    while i < len(entities):
        etype = entities[i]["type"]
        pairs = entities[i]["pairs"]

        if etype == "POLYLINE":
            flags = _entity_get_flag70(pairs)
            verts: list[list[tuple[int, str]]] = []
            i += 1
            while i < len(entities) and entities[i]["type"] == "VERTEX":
                verts.append(entities[i]["pairs"])
                i += 1
            if i < len(entities) and entities[i]["type"] == "SEQEND":
                i += 1
            layer_name = _entity_get_layer(pairs) or "0"
            segs = _polyline_vertices_to_segments(
                verts,
                flags,
                (ox, oy),
                total_scale,
                layer_whitelist=None,
                layer_blacklist=None,
                polyline_layer=layer_name,
            )
            if segs:
                stats = layer_stats.setdefault(
                    layer_name,
                    {"entities": 0, "segments": 0, "total_length": 0.0, "bbox": None},
                )
                stats["entities"] += 1
                for seg in segs:
                    length = math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)
                    stats["segments"] += 1
                    stats["total_length"] += length
                    stats["bbox"] = _update_bbox(stats["bbox"], seg.x1, seg.y1)
                    stats["bbox"] = _update_bbox(stats["bbox"], seg.x2, seg.y2)
                    total_segments += 1
                    total_length += length
                    global_bbox = _update_bbox(global_bbox, seg.x1, seg.y1)
                    global_bbox = _update_bbox(global_bbox, seg.x2, seg.y2)
            continue

        if etype == "LINE":
            layer_name = _entity_get_layer(pairs) or "0"
            seg = _line_to_segment(
                pairs,
                (ox, oy),
                total_scale,
                layer_whitelist=None,
                layer_blacklist=None,
            )
            segs = [seg] if seg is not None else []
        elif etype == "LWPOLYLINE":
            layer_name = _entity_get_layer(pairs) or "0"
            segs = _lwpolyline_to_segments(
                pairs,
                (ox, oy),
                total_scale,
                layer_whitelist=None,
                layer_blacklist=None,
            )
        else:
            i += 1
            continue

        if segs:
            stats = layer_stats.setdefault(
                layer_name,
                {"entities": 0, "segments": 0, "total_length": 0.0, "bbox": None},
            )
            stats["entities"] += 1
            for seg in segs:
                length = math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)
                stats["segments"] += 1
                stats["total_length"] += length
                stats["bbox"] = _update_bbox(stats["bbox"], seg.x1, seg.y1)
                stats["bbox"] = _update_bbox(stats["bbox"], seg.x2, seg.y2)
                total_segments += 1
                total_length += length
                global_bbox = _update_bbox(global_bbox, seg.x1, seg.y1)
                global_bbox = _update_bbox(global_bbox, seg.x2, seg.y2)

        i += 1

    if total_segments == 0:
        raise ValueError(
            "DXF dosyasında desteklenen entity (LINE, LWPOLYLINE, POLYLINE) bulunamadı veya filtre sonrası segment kalmadı"
        )

    # bbox'ları list'e çevir
    for name, stats in layer_stats.items():
        if stats["bbox"] is not None:
            stats["bbox"] = [
                float(stats["bbox"][0]),
                float(stats["bbox"][1]),
                float(stats["bbox"][2]),
                float(stats["bbox"][3]),
            ]
        # layer_total_length_m (metre)
        stats["total_length_m"] = float(stats.get("total_length", 0.0))

    global_bbox_list = None
    if global_bbox is not None:
        global_bbox_list = [
            float(global_bbox[0]),
            float(global_bbox[1]),
            float(global_bbox[2]),
            float(global_bbox[3]),
        ]

    # suggested_layers heuristiği
    KEYWORDS = ["wall", "walls", "duvar", "a-wall", "m-wall"]

    def _has_keyword(name: str) -> bool:
        lower = name.lower()
        return any(kw in lower for kw in KEYWORDS)

    layers_with_stats = [
        (name, stats)
        for name, stats in layer_stats.items()
        if stats["segments"] > 0 and stats["total_length"] > 0.0
    ]

    keyword_layers = [
        (name, stats)
        for name, stats in layers_with_stats
        if _has_keyword(name)
    ]
    if keyword_layers:
        keyword_layers.sort(key=lambda item: (-item[1]["total_length"], item[0]))
        suggested_layers = [name for name, _ in keyword_layers]
    else:
        layers_with_stats.sort(key=lambda item: (-item[1]["total_length"], item[0]))
        suggested_layers = [name for name, _ in layers_with_stats[:3]]

    # Layer scoring ve suggested_layers_reasons
    layers_by_length = sorted(
        layers_with_stats,
        key=lambda item: (-item[1]["total_length"], item[0]),
    )
    layer_scores, suggested_layers_reasons = _build_layer_scores_and_reasons(
        layer_stats, layer_entity_counts, keyword_layers, layers_by_length
    )

    # LAYER_COMPLEXITY_HIGH: çok fazla entity tipi olan katmanlar
    for ls in layer_scores:
        mix = layer_entity_counts.get(ls["layer"], {})
        if len(mix) > 5 and "LAYER_COMPLEXITY_HIGH" not in warning_codes:
            warning_codes.append("LAYER_COMPLEXITY_HIGH")
            parse_warnings.append({
                "code": "LAYER_COMPLEXITY_HIGH",
                "message": "Bazı katmanlarda çok fazla entity tipi var.",
                "user_action": WARNING_CODE_USER_ACTIONS.get("LAYER_COMPLEXITY_HIGH", "Sadece duvar katmanını seçin."),
            })
            break

    # recommended_action: kısa öneri cümlesi
    supported_total = sum(entity_counts_supported.values())
    unsupported_total = sum(entity_counts_unsupported.values())
    if unsupported_total > 0 and supported_total > 0:
        recommended_action = (
            f"{supported_total} desteklenen entity çizilebilir. "
            f"{unsupported_total} desteklenmeyen entity atlandı. "
            "Önerilen katmanları seçip devam edin."
        )
    elif unsupported_total > 0 and supported_total == 0:
        recommended_action = (
            "Desteklenen entity yok. Sadece LINE, LWPOLYLINE, POLYLINE desteklenir. "
            "CAD'de eğrileri polyline'a dönüştürüp tekrar deneyin."
        )
    else:
        recommended_action = "Plan hazır. Önerilen katmanları seçip komutları oluşturun."

    return {
        "layers": layer_stats,
        "total_segments": total_segments,
        "total_length": float(total_length),
        "bbox": global_bbox_list,
        "suggested_layers": suggested_layers,
        "dxf_units_detected": detected_unit,
        "world_unit": WORLD_UNIT_BASE,
        "world_scale": total_scale,
        "unit_unknown": unit_unknown,
        # DXF Insight Report
        "entity_counts_total": entity_counts_total,
        "entity_counts_supported": entity_counts_supported,
        "entity_counts_unsupported": entity_counts_unsupported,
        "unsupported_samples": unsupported_samples,
        "layer_entity_counts": layer_entity_counts,
        "layer_scores": layer_scores,
        "suggested_layers_reasons": suggested_layers_reasons,
        "parse_warnings": parse_warnings,
        "warning_codes": warning_codes,
        "recommended_action": recommended_action,
    }
