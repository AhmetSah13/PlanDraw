from __future__ import annotations

import math

from app.analysis.wall_centerline import (
    WallCenterlineConfig,
    extract_wall_centerlines,
)
from app.normalization.normalized_plan import SegmentIn


def _len(seg: SegmentIn) -> float:
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def test_rectangle_double_wall_to_single_centerline_rectangle() -> None:
    """
    Dış ve iç dikdörtgen (double-wall) verildiğinde,
    orta çizgide tek bir dikdörtgen seti elde edilmeli.
    """
    # Dış dikdörtgen (0,0) - (4,3)
    outer = [
        SegmentIn(x1=0.0, y1=0.0, x2=4.0, y2=0.0),
        SegmentIn(x1=4.0, y1=0.0, x2=4.0, y2=3.0),
        SegmentIn(x1=4.0, y1=3.0, x2=0.0, y2=3.0),
        SegmentIn(x1=0.0, y1=3.0, x2=0.0, y2=0.0),
    ]
    # İç dikdörtgen (0.2,0.2) - (3.8,2.8)
    inner = [
        SegmentIn(x1=0.2, y1=0.2, x2=3.8, y2=0.2),
        SegmentIn(x1=3.8, y1=0.2, x2=3.8, y2=2.8),
        SegmentIn(x1=3.8, y1=2.8, x2=0.2, y2=2.8),
        SegmentIn(x1=0.2, y1=2.8, x2=0.2, y2=0.2),
    ]
    segs = outer + inner
    cfg = WallCenterlineConfig(
        wall_gap_min_m=0.15,
        wall_gap_max_m=0.30,
        parallel_angle_tol_deg=3.0,
        overlap_min_ratio=0.8,
        snap_tol_m=0.001,
        min_stub_len_m=0.02,
        min_pairs_for_centerline=2,
        min_centerline_ratio_vs_input=0.4,
    )
    center, metrics = extract_wall_centerlines(segs, cfg=cfg, unit_unknown=False)

    assert not metrics["fallback_used"]
    # Dört kenar için en az dört orta çizgi segmenti beklenir (normalize sonrası birleşebilir)
    assert metrics["detected_double_wall_pairs_count"] >= 4
    assert metrics["centerline_segments_count"] >= 4
    # Orta dikdörtgen yaklaşık (0.1,0.1)-(3.9,2.9) etrafında olmalı
    xs = [s.x1 for s in center] + [s.x2 for s in center]
    ys = [s.y1 for s in center] + [s.y2 for s in center]
    assert min(xs) > 0.05 and max(xs) < 3.95
    assert min(ys) > 0.05 and max(ys) < 2.95


def test_single_line_walls_unchanged_with_fallback() -> None:
    """
    Zaten tek çizgi duvarlar varsa ve double-wall eşiği sağlanmıyorsa,
    fallback devreye girip segmentleri aynen korumalı.
    """
    segs = [
        SegmentIn(x1=0.0, y1=0.0, x2=4.0, y2=0.0),
        SegmentIn(x1=0.0, y1=2.0, x2=4.0, y2=2.0),
    ]
    cfg = WallCenterlineConfig(
        wall_gap_min_m=0.5,
        wall_gap_max_m=1.0,
        parallel_angle_tol_deg=3.0,
        overlap_min_ratio=0.9,
        snap_tol_m=0.001,
        min_stub_len_m=0.02,
        min_pairs_for_centerline=2,
        min_centerline_ratio_vs_input=0.8,
    )
    center, metrics = extract_wall_centerlines(segs, cfg=cfg, unit_unknown=False)

    assert metrics["fallback_used"]
    assert metrics["fallback_reason"] in ("NO_DOUBLE_WALL_PAIRS", "NO_DOUBLE_WALL_PAIRS_IN_GAP_RANGE")
    # Girdi ile çıktı segment uzunluk ve sayısı aynı kalmalı (hibrit devrede değil)
    assert len(center) == len(segs)
    assert math.isclose(sum(_len(s) for s in center), sum(_len(s) for s in segs), rel_tol=1e-6)


def test_near_parallel_noise_not_merged() -> None:
    """
    Neredeyse paralel ama uzak/gürültü niteliğindeki çizgiler eşleştirilmemeli.
    """
    segs = [
        SegmentIn(x1=0.0, y1=0.0, x2=5.0, y2=0.05),
        SegmentIn(x1=0.0, y1=1.0, x2=5.0, y2=1.1),
        # Gürültü: kısa, eğimli çizgiler
        SegmentIn(x1=1.0, y1=2.0, x2=1.2, y2=2.3),
        SegmentIn(x1=3.0, y1=2.0, x2=3.1, y2=2.4),
    ]
    cfg = WallCenterlineConfig(
        wall_gap_min_m=0.2,
        wall_gap_max_m=0.3,
        parallel_angle_tol_deg=1.0,
        overlap_min_ratio=0.9,
        snap_tol_m=0.001,
        min_stub_len_m=0.02,
        min_pairs_for_centerline=1,
        min_centerline_ratio_vs_input=0.8,
    )
    center, metrics = extract_wall_centerlines(segs, cfg=cfg, unit_unknown=False)

    # Boşluk çok büyük veya açı toleransı sıkı olduğundan çift bulunmamalı
    assert metrics["fallback_used"]
    assert metrics["detected_double_wall_pairs_count"] == 0
    assert len(center) == len(segs)


def test_hybrid_partial_centerline_keeps_unpaired_segments() -> None:
    """
    Bir adet double-wall çift + bir adet tek duvar olduğunda,
    hibrit mod devreye girmeli; çift için centerline üretilirken
    tek duvar segmenti aynen korunmalı (tam fallback yok).
    """
    # Double-wall yatay duvar (0..4, gap=0.2)
    d1 = SegmentIn(x1=0.0, y1=0.0, x2=4.0, y2=0.0)
    d2 = SegmentIn(x1=0.0, y1=0.2, x2=4.0, y2=0.2)
    # Tek düşey duvar (single-line)
    single = SegmentIn(x1=5.0, y1=0.0, x2=5.0, y2=3.0)
    segs = [d1, d2, single]

    cfg = WallCenterlineConfig(
        wall_gap_min_m=0.15,
        wall_gap_max_m=0.30,
        parallel_angle_tol_deg=3.0,
        overlap_min_ratio=0.8,
        snap_tol_m=0.001,
        min_stub_len_m=0.02,
        min_pairs_for_centerline=1,
        min_centerline_ratio_vs_input=0.9,
    )
    hybrid_segs, metrics = extract_wall_centerlines(segs, cfg=cfg, unit_unknown=False)

    assert not metrics["fallback_used"]
    assert metrics["hybrid_used"]
    assert metrics["detected_double_wall_pairs_count"] == 1
    # Hibrit çıktıda en az 2 segment olmalı (bir centerline + tek duvar)
    assert len(hybrid_segs) >= 2
    # Toplam uzunluk, girdi uzunluğunun anlamlı bir kısmını korumalı
    assert metrics["hybrid_applied_centerline_length_m"] > 0.0


def test_t_junction_double_wall_pairs_detected() -> None:
    """
    Basit bir T kavşağı (double-wall kollar) için en az birkaç çiftin bulunması beklenir.
    Ayrıntılı topoloji kontrolü yerine çift sayısı ve fallback olmamasını kontrol ederiz.
    """
    # T harfi: dikey gövde + yatay tepe, her biri double-wall
    segs: list[SegmentIn] = []
    gap = 0.2
    # Dikey gövde: x=0 ve x=gap, y=0..4
    segs.append(SegmentIn(x1=0.0, y1=0.0, x2=0.0, y2=4.0))
    segs.append(SegmentIn(x1=gap, y1=0.0, x2=gap, y2=4.0))
    # Yatay tepe: y=4 ve y=4+gap, x=-2..2
    segs.append(SegmentIn(x1=-2.0, y1=4.0, x2=2.0, y2=4.0))
    segs.append(SegmentIn(x1=-2.0, y1=4.0 + gap, x2=2.0, y2=4.0 + gap))

    cfg = WallCenterlineConfig(
        wall_gap_min_m=0.15,
        wall_gap_max_m=0.30,
        parallel_angle_tol_deg=3.0,
        overlap_min_ratio=0.7,
        snap_tol_m=0.001,
        min_stub_len_m=0.02,
        min_pairs_for_centerline=2,
        min_centerline_ratio_vs_input=0.4,
    )
    center, metrics = extract_wall_centerlines(segs, cfg=cfg, unit_unknown=False)

    assert not metrics["fallback_used"]
    assert metrics["detected_double_wall_pairs_count"] >= 2
    assert metrics["centerline_segments_count"] >= 2
    # Toplam orta çizgi uzunluğu, giriş uzunluğunun anlamlı bir kısmı olmalı
    assert metrics["centerline_total_length_m"] > 0.4 * metrics["input_total_length_m"]

