# dxf_importer.py — ASCII DXF → NormalizedPlan (LINE, LWPOLYLINE, POLYLINE+VERTEX)
# Üçüncü parti bağımlılık yok; yalnızca ASCII DXF desteklenir.

from __future__ import annotations

import math
from typing import Any

from app.normalization.normalized_plan import NormalizedPlan, OriginIn, SegmentIn

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

    metadata: dict[str, Any] = {
        "source": "dxf",
        "insunits": insunits,
        "dxf_units_detected": detected_unit,
        "world_unit": WORLD_UNIT_BASE,
        "world_scale": total_scale,
        "unit_unknown": unit_unknown,
        "entity_counts": entity_counts,
        "parse_warnings": parsed.get("warnings", []),
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
    """
    parsed = parse_dxf_ascii(text)
    header = parsed["header"]
    entities = parsed["entities"]

    insunits = header.get("insunits")
    # detected_unit / unit_unknown burada sadece debug amaçlı; preview cevabında ayrıca dönecek.
    _, total_scale, detected_unit, unit_unknown = _compute_units_and_scale(
        units, scale, insunits
    )

    ox, oy = origin
    layer_stats: dict[str, dict[str, Any]] = {}
    total_segments = 0
    total_length = 0.0
    global_bbox = None  # [minx, miny, maxx, maxy]

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

    # bbox'ları list'e çevir (veya None bırak)
    for name, stats in layer_stats.items():
        if stats["bbox"] is not None:
            stats["bbox"] = [
                float(stats["bbox"][0]),
                float(stats["bbox"][1]),
                float(stats["bbox"][2]),
                float(stats["bbox"][3]),
            ]

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
    }
