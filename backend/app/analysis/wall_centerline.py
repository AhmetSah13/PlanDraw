from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.normalization.normalized_plan import NormalizedPlan, SegmentIn, OriginIn
from app.normalization.plan_normalizer import NormalizeOptions, normalize_plan


@dataclass(frozen=True)
class WallCenterlineConfig:
    """
    Duvar orta-çizgi çıkarımı için yapılandırma.

    Tüm mesafeler metre cinsindendir.
    """

    wall_gap_min_m: float = 0.05
    wall_gap_max_m: float = 0.40
    # Gürültülü mimari planlar için açı toleransını biraz geniş tut
    parallel_angle_tol_deg: float = 5.0
    # Eksen boyunca bindirme oranı (kısa segmente göre) alt sınırı
    overlap_min_ratio: float = 0.60
    snap_tol_m: float = 0.001
    min_stub_len_m: float = 0.02
    # Fallback kriterleri
    min_pairs_for_centerline: int = 2
    # Coverage oranı (centerline_total_length / input_total_length) alt sınırı
    # 0.3 altındaki durumlarda plan tamamı için hibrit uygulamaya geçmek yerine fallback yap.
    min_centerline_ratio_vs_input: float = 0.30


def _seg_len(seg: SegmentIn) -> float:
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def _unit_dir(seg: SegmentIn) -> Tuple[float, float]:
    """Segment yön vektörü (birim)."""
    L = _seg_len(seg)
    if L <= 0.0:
        return (0.0, 0.0)
    return ((seg.x2 - seg.x1) / L, (seg.y2 - seg.y1) / L)


def _angle_between_deg(seg1: SegmentIn, seg2: SegmentIn) -> float:
    """İki segment arasındaki açı farkı (0–90 derece aralığına indirgenmiş)."""
    ux, uy = _unit_dir(seg1)
    vx, vy = _unit_dir(seg2)
    dot = ux * vx + uy * vy
    dot = max(-1.0, min(1.0, dot))
    ang = math.degrees(math.acos(dot))
    if ang > 90.0:
        ang = 180.0 - ang
    return ang


def _project_onto_axis(
    seg: SegmentIn,
    axis: Tuple[float, float],
) -> Tuple[float, float]:
    """Segmente ait uçların verilen eksene (birim vektör) izdüşümü aralığı."""
    ux, uy = axis
    t1 = seg.x1 * ux + seg.y1 * uy
    t2 = seg.x2 * ux + seg.y2 * uy
    return (min(t1, t2), max(t1, t2))


def _line_distance(
    seg_ref: SegmentIn,
    seg_other: SegmentIn,
) -> float:
    """
    İkinci segmentin orta noktasının, birinci segmentin doğrusuna dik uzaklığı.
    Duvar boşluğu tahmini için yeterlidir.
    """
    mx = 0.5 * (seg_other.x1 + seg_other.x2)
    my = 0.5 * (seg_other.y1 + seg_other.y2)
    # ref doğrusu: P0 + t * d
    dx = seg_ref.x2 - seg_ref.x1
    dy = seg_ref.y2 - seg_ref.y1
    n = math.hypot(dx, dy)
    if n <= 0.0:
        return 0.0
    # Noktadan doğruya mesafe
    return abs(dy * mx - dx * my + seg_ref.x2 * seg_ref.y1 - seg_ref.x1 * seg_ref.y2) / n


def _overlap_and_ratio(
    seg1: SegmentIn,
    seg2: SegmentIn,
    axis: Tuple[float, float],
) -> Tuple[float, float]:
    """İki segmentin eksen boyunca kesişim uzunluğu ve kısa segmente oranı."""
    a1, b1 = _project_onto_axis(seg1, axis)
    a2, b2 = _project_onto_axis(seg2, axis)
    L1 = b1 - a1
    L2 = b2 - a2
    if L1 <= 0.0 or L2 <= 0.0:
        return 0.0, 0.0
    inter_a = max(a1, a2)
    inter_b = min(b1, b2)
    overlap = inter_b - inter_a
    if overlap <= 0.0:
        return 0.0, 0.0
    ratio = overlap / min(L1, L2)
    return overlap, ratio


def _centerline_segment_for_pair(
    seg1: SegmentIn,
    seg2: SegmentIn,
    axis: Tuple[float, float],
) -> SegmentIn | None:
    """
    İki paralel segment çifti için orta çizgi segmenti üret.
    Orta çizgi, iki doğrunun tam ortasından ve yalnızca bindikleri aralıkta geçirilir.
    """
    ux, uy = axis
    a1, b1 = _project_onto_axis(seg1, axis)
    a2, b2 = _project_onto_axis(seg2, axis)
    inter_a = max(a1, a2)
    inter_b = min(b1, b2)
    if inter_b <= inter_a:
        return None

    def point_on_seg(seg: SegmentIn, t: float, a: float, b: float) -> Tuple[float, float]:
        # seg doğrusu boyunca parametre t (projeksiyon) için nokta hesapla
        if b - a == 0.0:
            # Dejenere; uçlardan birini kullan
            return (seg.x1, seg.y1)
        # Uçların projeksiyonları
        t1 = seg.x1 * ux + seg.y1 * uy
        t2 = seg.x2 * ux + seg.y2 * uy
        if t2 - t1 == 0.0:
            return (seg.x1, seg.y1)
        s = (t - t1) / (t2 - t1)
        s = max(0.0, min(1.0, s))
        return (seg.x1 + (seg.x2 - seg.x1) * s, seg.y1 + (seg.y2 - seg.y1) * s)

    # Başlangıç ve bitiş için her iki duvardan nokta al, ortalamasını al
    p1_start = point_on_seg(seg1, inter_a, a1, b1)
    p2_start = point_on_seg(seg2, inter_a, a2, b2)
    cx1 = 0.5 * (p1_start[0] + p2_start[0])
    cy1 = 0.5 * (p1_start[1] + p2_start[1])

    p1_end = point_on_seg(seg1, inter_b, a1, b1)
    p2_end = point_on_seg(seg2, inter_b, a2, b2)
    cx2 = 0.5 * (p1_end[0] + p2_end[0])
    cy2 = 0.5 * (p1_end[1] + p2_end[1])

    return SegmentIn(x1=cx1, y1=cy1, x2=cx2, y2=cy2)


def extract_wall_centerlines(
    segments: List[SegmentIn],
    *,
    cfg: WallCenterlineConfig | None = None,
    unit_unknown: bool = False,
) -> Tuple[List[SegmentIn], Dict[str, Any]]:
    """
    Girdi segmentlerinden (duvar adayları) double-wall çiftlerini bulup
    tek bir orta çizgi segment kümesine dönüştürür.

    Dönen metrics alanları:
      - detected_double_wall_pairs_count
      - centerline_segments_count
      - dropped_as_non_wall_count
      - centerline_success_ratio
      - fallback_used (bool)
      - fallback_reason (str | None)
      - input_total_length_m
      - centerline_total_length_m
      - double_wall_coverage_ratio
      - hybrid_applied_centerline_length_m
      - hybrid_applied_ratio
      - hybrid_used
    """
    cfg = cfg or WallCenterlineConfig()
    metrics: Dict[str, Any] = {
        # Eski metrikler (geriye dönük uyum)
        "detected_double_wall_pairs_count": 0,
        "centerline_segments_count": 0,
        "dropped_as_non_wall_count": 0,
        "centerline_success_ratio": 0.0,
        "fallback_used": False,
        "fallback_reason": None,
        "input_total_length_m": 0.0,
        "centerline_total_length_m": 0.0,
        "double_wall_coverage_ratio": 0.0,
        "hybrid_applied_centerline_length_m": 0.0,
        "hybrid_applied_ratio": 0.0,
        "hybrid_used": False,
        # Yeni, daha okunaklı metrik alias'ları
        "centerline_pairs_detected": 0,
        "centerline_total_length": 0.0,
        "centerline_coverage_ratio": 0.0,
        # Basit kapı boşluğu tespiti (sadece metrik)
        "door_candidates_detected": 0,
    }

    if not segments:
        return [], metrics

    input_total_len = sum(_seg_len(s) for s in segments)
    metrics["input_total_length_m"] = float(input_total_len)

    # A) Basit grid tabanlı uzamsal indeks (segment bbox merkezine göre)
    # Hücre boyu: duvar aralığı ile aynı mertebede olsun.
    cell_size = max(cfg.wall_gap_max_m, cfg.wall_gap_min_m * 2.0)
    if cell_size <= 0.0:
        cell_size = 0.5

    grid: Dict[Tuple[int, int], List[int]] = {}
    seg_bboxes: List[Tuple[float, float, float, float]] = []
    for idx, s in enumerate(segments):
        minx = min(s.x1, s.x2)
        miny = min(s.y1, s.y2)
        maxx = max(s.x1, s.x2)
        maxy = max(s.y1, s.y2)
        seg_bboxes.append((minx, miny, maxx, maxy))
        cx = 0.5 * (minx + maxx)
        cy = 0.5 * (miny + maxy)
        gx = int(math.floor(cx / cell_size))
        gy = int(math.floor(cy / cell_size))
        grid.setdefault((gx, gy), []).append(idx)

    # B) Paralel adaylarını bul
    candidate_pairs: List[Dict[str, Any]] = []
    gaps: List[float] = []

    for idx, seg in enumerate(segments):
        minx, miny, maxx, maxy = seg_bboxes[idx]
        cx = 0.5 * (minx + maxx)
        cy = 0.5 * (miny + maxy)
        gx = int(math.floor(cx / cell_size))
        gy = int(math.floor(cy / cell_size))
        ux, uy = _unit_dir(seg)
        if ux == 0.0 and uy == 0.0:
            continue
        axis = (ux, uy)

        # Komşu hücreler
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (gx + dx, gy + dy)
                for j in grid.get(key, []):
                    if j <= idx:
                        continue
                    other = segments[j]
                    # Açı farkı
                    ang = _angle_between_deg(seg, other)
                    if ang > cfg.parallel_angle_tol_deg:
                        continue
                    # Eksen boyunca bindirme
                    overlap, overlap_ratio = _overlap_and_ratio(seg, other, axis)
                    if overlap <= 0.0 or overlap_ratio < cfg.overlap_min_ratio:
                        continue
                    # Duvar aralığı
                    gap = _line_distance(seg, other)
                    gaps.append(gap)
                    candidate_pairs.append(
                        {
                            "i": idx,
                            "j": j,
                            "gap": gap,
                            "overlap": overlap,
                            "min_len": min(_seg_len(seg), _seg_len(other)),
                        }
                    )

    if not candidate_pairs:
        # Hiç çift bulunamadı; doğrudan fallback (hibrit devreye giremez).
        metrics["fallback_used"] = True
        metrics["fallback_reason"] = "NO_DOUBLE_WALL_PAIRS"
        metrics["dropped_as_non_wall_count"] = 0
        metrics["hybrid_used"] = False
        return list(segments), metrics

    # Gap istatistiği: units bilinmiyorsa aralık penceresini mod/median etrafına daralt
    if unit_unknown and gaps:
        sorted_gaps = sorted(gaps)
        med = sorted_gaps[len(sorted_gaps) // 2]
        # Duvar boşluğunu medyan etrafında pencereyle daralt
        eff_min = max(cfg.wall_gap_min_m, 0.5 * med)
        eff_max = min(cfg.wall_gap_max_m, 1.5 * med)
        gap_min = eff_min
        gap_max = max(eff_min, eff_max)
    else:
        gap_min = cfg.wall_gap_min_m
        gap_max = cfg.wall_gap_max_m

    # Gap aralığına uymayan çiftleri at
    filtered_pairs: List[Dict[str, Any]] = []
    for p in candidate_pairs:
        if gap_min <= p["gap"] <= gap_max:
            filtered_pairs.append(p)
    candidate_pairs = filtered_pairs

    if not candidate_pairs:
        metrics["fallback_used"] = True
        metrics["fallback_reason"] = "NO_DOUBLE_WALL_PAIRS_IN_GAP_RANGE"
        metrics["dropped_as_non_wall_count"] = 0
        metrics["hybrid_used"] = False
        return list(segments), metrics

    # C) Skor hesabı ve greedy eşleştirme
    # Gap medyanına yakın, bindirmesi ve uzunluğu yüksek olan çiftler tercih edilir.
    gaps2 = [p["gap"] for p in candidate_pairs]
    gaps2_sorted = sorted(gaps2)
    gap_med = gaps2_sorted[len(gaps2_sorted) // 2]
    if gap_med <= 0.0:
        gap_med = gap_min if gap_min > 0.0 else 0.1

    for p in candidate_pairs:
        gap = p["gap"]
        overlap = p["overlap"]
        min_len = p["min_len"]
        gap_score = max(0.0, 1.0 - abs(gap - gap_med) / gap_med)
        p["score"] = overlap * (1.0 + gap_score) + 0.1 * min_len

    candidate_pairs.sort(key=lambda d: (-d["score"], d["gap"]))

    used: set[int] = set()
    chosen_pairs: List[Dict[str, Any]] = []
    for p in candidate_pairs:
        i = p["i"]
        j = p["j"]
        if i in used or j in used:
            continue
        used.add(i)
        used.add(j)
        chosen_pairs.append(p)

    metrics["detected_double_wall_pairs_count"] = len(chosen_pairs)
    metrics["centerline_pairs_detected"] = len(chosen_pairs)

    # D) Çiftlerden orta çizgi segmentleri üret
    centerline_segments: List[SegmentIn] = []
    for p in chosen_pairs:
        seg1 = segments[p["i"]]
        seg2 = segments[p["j"]]
        ux, uy = _unit_dir(seg1)
        if ux == 0.0 and uy == 0.0:
            continue
        axis = (ux, uy)
        cl = _centerline_segment_for_pair(seg1, seg2, axis)
        if cl is None:
            continue
        if _seg_len(cl) <= 0.0:
            continue
        centerline_segments.append(cl)

    metrics["centerline_segments_count"] = len(centerline_segments)

    if not centerline_segments:
        metrics["fallback_used"] = True
        metrics["fallback_reason"] = "CENTERLINE_GENERATION_FAILED"
        # Kullanılmayan segment sayısını kabaca raporla
        metrics["dropped_as_non_wall_count"] = len(segments)
        metrics["hybrid_used"] = False
        return list(segments), metrics

    # E) Snap + kollinear birleştirme + küçük budama için plan_normalizer kullan
    tmp_plan = NormalizedPlan(
        version="v1",
        units="m",
        scale=1.0,
        origin=OriginIn(x=0.0, y=0.0),
        segments=centerline_segments,
        metadata=None,
    )
    norm_opts = NormalizeOptions(
        merge_endpoints_tol=cfg.snap_tol_m,
        merge_collinear=True,
        collinear_angle_eps_deg=1.0,
        drop_zero_length=True,
        min_segment_len=cfg.min_stub_len_m,
        segment_budget=None,
        budget_strategy="keep_longest",
        recenter=False,
    )
    norm_plan, _warnings = normalize_plan(tmp_plan, norm_opts)
    centerline_segments_final = list(norm_plan.segments)
    centerline_total_len = sum(_seg_len(s) for s in centerline_segments_final)

    metrics["centerline_total_length_m"] = float(centerline_total_len)
    metrics["centerline_total_length"] = float(centerline_total_len)

    # Basit kapı boşluğu tespiti:
    # Aynı doğrultuda (yaklaşık kollineer) iki centerline segmenti arasında,
    # eksen boyunca 0.7–1.2 m arası boşluk varsa bunu kapı adayı say.
    DOOR_MIN = 0.7
    DOOR_MAX = 1.2
    door_candidates = 0

    def _axis_for_seg(s: SegmentIn) -> Tuple[float, float]:
        ux, uy = _unit_dir(s)
        return (ux, uy)

    def _proj_interval(s: SegmentIn, axis: Tuple[float, float]) -> Tuple[float, float]:
        return _project_onto_axis(s, axis)

    n_cl = len(centerline_segments_final)
    for i in range(n_cl):
        si = centerline_segments_final[i]
        ui, vi = _axis_for_seg(si)
        if ui == 0.0 and vi == 0.0:
            continue
        axis = (ui, vi)
        a1, b1 = _proj_interval(si, axis)
        for j in range(i + 1, n_cl):
            sj = centerline_segments_final[j]
            ang = _angle_between_deg(si, sj)
            if ang > cfg.parallel_angle_tol_deg:
                continue
            a2, b2 = _proj_interval(sj, axis)
            left = min(a1, b2)
            right = max(b1, a2)
            # Merkezlenmiş sıralama: [min(a1,b1), max(a1,b1)] vs [min(a2,b2), max(a2,b2)]
            # Boşluk uzunluğu: segmentler arası eksen mesafesi
            # (sade yaklaşım: en yakın uçlar arası fark)
            gap1 = abs(a2 - b1)
            gap2 = abs(a1 - b2)
            gap_len = min(gap1, gap2)
            if DOOR_MIN <= gap_len <= DOOR_MAX:
                door_candidates += 1

    metrics["door_candidates_detected"] = int(door_candidates)

    pairs_found = len(candidate_pairs)
    pairs_used = len(chosen_pairs)
    if pairs_found > 0:
        metrics["centerline_success_ratio"] = float(pairs_used) / float(pairs_found)
    else:
        metrics["centerline_success_ratio"] = 0.0

    # F) Hibrit uygulama: centerline üretilen çiftler için orta çizgi kullan,
    # diğer duvar segmentlerini aynen koru.
    coverage = 0.0
    if input_total_len > 0.0:
        coverage = float(centerline_total_len) / float(input_total_len)
    metrics["double_wall_coverage_ratio"] = coverage
    metrics["centerline_coverage_ratio"] = coverage
    metrics["hybrid_applied_centerline_length_m"] = float(centerline_total_len)
    metrics["hybrid_applied_ratio"] = coverage

    # Coverage çok düşükse (ör: sadece küçük bir kısım double-wall) hibrit çizimi
    # tüm plana yaymak yerine güvenli fallback uygula.
    if coverage < cfg.min_centerline_ratio_vs_input:
        metrics["fallback_used"] = True
        metrics["fallback_reason"] = "LOW_COVERAGE"
        metrics["hybrid_used"] = False
        metrics["dropped_as_non_wall_count"] = 0
        return list(segments), metrics

    # Fallback yalnızca hiç çift bulunamadığı, centerline üretiminin tamamen
    # başarısız olduğu veya coverage çok düşük olduğu durumlarda yapılır.
    metrics["fallback_used"] = False
    metrics["fallback_reason"] = None
    metrics["hybrid_used"] = True
    metrics["dropped_as_non_wall_count"] = max(0, len(segments) - 2 * pairs_used)

    # Hibrit segment listesi: normalize edilmiş centerline + eşleşmeyen orijinal segmentler
    unmatched_indices = [idx for idx in range(len(segments)) if idx not in used]
    hybrid_segments: List[SegmentIn] = []
    hybrid_segments.extend(centerline_segments_final)
    for idx in unmatched_indices:
        hybrid_segments.append(segments[idx])
    return hybrid_segments, metrics


def apply_wall_centerline_to_plan(
    plan: NormalizedPlan,
    *,
    cfg: WallCenterlineConfig | None = None,
) -> Tuple[NormalizedPlan, Dict[str, Any]]:
    """
    NormalizedPlan içindeki segmentlere wall centerline dönüşümü uygular.
    """
    unit_unknown = bool((plan.metadata or {}).get("unit_unknown"))
    segments = list(plan.segments)
    out_segments, metrics = extract_wall_centerlines(
        segments,
        cfg=cfg,
        unit_unknown=unit_unknown,
    )
    out_meta = dict(plan.metadata or {})
    out_meta["centerline_metrics"] = metrics
    out_plan = plan.model_copy(update={"segments": out_segments, "metadata": out_meta})
    return out_plan, metrics

