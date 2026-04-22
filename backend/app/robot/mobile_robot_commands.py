from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Tuple

from app.normalization.normalized_plan import SegmentIn


def _segment_to_coords(seg: Any) -> Tuple[float, float, float, float]:
    """
    Segment koordinatlarını (x1,y1,x2,y2) olarak döndür.
    SegmentIn, dict veya (x1,y1,x2,y2) tuple/list kabul edilir.
    """
    if isinstance(seg, SegmentIn):
        return float(seg.x1), float(seg.y1), float(seg.x2), float(seg.y2)

    if isinstance(seg, dict):
        return (
            float(seg["x1"]),
            float(seg["y1"]),
            float(seg["x2"]),
            float(seg["y2"]),
        )

    if isinstance(seg, (list, tuple)) and len(seg) == 4:
        x1, y1, x2, y2 = seg
        return float(x1), float(y1), float(x2), float(y2)

    raise TypeError("Geçersiz segment tipi; SegmentIn, dict veya (x1,y1,x2,y2) bekleniyor.")


def _points_equal(
    a: Tuple[float, float],
    b: Tuple[float, float],
    tol: float = 1e-6,
) -> bool:
    """İki noktanın aynı olup olmadığını küçük bir toleransla kontrol et."""
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= tol


def _is_valid_number(x: float) -> bool:
    """NaN / inf içermeyen sonlu sayı kontrolü."""
    return math.isfinite(x)


def _sanitize_path_segments(
    path_segments: Iterable[Any],
    *,
    min_length: float = 1e-4,
) -> Tuple[list[Tuple[float, float, float, float]], int]:
    """
    Girdi segmentlerini mobil komut üretimi için temizler.

    - NaN/inf içeren koordinatları at.
    - Çok kısa (<= min_length) segmentleri at.
    - Sıfır uzunluklu veya duplicate (başlangıç/bitiş noktası aynı) segmentleri at.

    Döner:
      - temizlenmiş segment listesi
      - orijinal segment sayısı
    """
    cleaned: list[Tuple[float, float, float, float]] = []
    original_count = 0
    last_end: Tuple[float, float] | None = None

    for raw_seg in path_segments:
        original_count += 1
        x1, y1, x2, y2 = _segment_to_coords(raw_seg)
        if not (_is_valid_number(x1) and _is_valid_number(y1) and _is_valid_number(x2) and _is_valid_number(y2)):
            continue
        start = (x1, y1)
        end = (x2, y2)
        length = math.hypot(end[0] - start[0], end[1] - start[1])
        if length <= min_length:
            # Çok kısa veya sıfır uzunluklu segmentler atılır
            continue
        # Ardışık duplicate segmentleri kaba biçimde filtrele (aynı başlangıç ve bitiş)
        if last_end is not None and cleaned:
            last_seg = cleaned[-1]
            if _points_equal(last_seg[0:2], start) and _points_equal(last_seg[2:4], end):
                continue
        cleaned.append((x1, y1, x2, y2))
        last_end = end

    return cleaned, original_count


def _auto_heading_from_segments(
    segments: list[Tuple[float, float, float, float]],
) -> float:
    """
    İlk geçerli segmentten başlangıç heading'ini hesaplar.

    Konvansiyon:
      - 0° = +X yönü
      - Saat yönünün tersine pozitif (atan2(dy, dx))
      - Çıktı [-180°, 180°] aralığında normalize edilir.
    """
    for x1, y1, x2, y2 in segments:
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length <= 0.0:
            continue
        ang_rad = math.atan2(dy, dx)
        ang_deg = math.degrees(ang_rad)
        # [-180, 180] aralığına normalize et
        if ang_deg > 180.0:
            ang_deg -= 360.0
        if ang_deg <= -180.0:
            ang_deg += 360.0
        return ang_deg
    return 0.0


def get_preview_heading_deg(path_segments: Iterable[Any]) -> float:
    """
    Preview yön oku için kullanılacak heading (derece).
    Mobil komut katmanı ile aynı kaynaktan: ilk gerçek DRAW_TO vektörü.
    """
    mr = convert_path_to_mobile_robot_commands(
        path_segments, start_xy=(0.0, 0.0), start_heading_deg=None
    )
    return float(mr.get("start_heading_deg", 0.0))


def convert_path_to_mobile_robot_commands(
    path_segments: Iterable[Any],
    start_xy: Tuple[float, float] = (0.0, 0.0),
    start_heading_deg: float | None = None,
) -> Dict[str, Any]:
    """
    Segment listesi (x1,y1,x2,y2) → mobil zemin-çizim robotu için yüksek seviye komut listesi.

    Komut formatı:
      SET_ORIGIN x y
      SET_HEADING deg
      PEN_UP
      MOVE_TO x y        # pen up gezi
      PEN_DOWN
      DRAW_TO x y        # pen down çizim
      ...
      PEN_UP
      END

    Kurallar:
      - Daima SET_ORIGIN + SET_HEADING + PEN_UP ile başlar.
      - İlk stroke için: MOVE_TO x1 y1 → PEN_DOWN → ardışık DRAW_TO komutları.
      - Bağlantısız stroke'lar arasında: PEN_UP → MOVE_TO next_x1 next_y1 → PEN_DOWN.
      - Çıkış her zaman PEN_UP + END ile biter.

    Dönüş (sözlük):
      {
        "commands": [...],
        "move_count": int,              # toplam MOVE_TO + DRAW_TO sayısı
        "draw_command_count": int,      # DRAW_TO sayısı
        "travel_command_count": int,    # MOVE_TO sayısı
        "drawn_length_m": float,        # sadece DRAW_TO uzunluklarının toplamı
        "travel_length_m": float,       # sadece MOVE_TO uzunluklarının toplamı (pen_up)
        "start_xy": [x, y],
        "start_heading_deg": deg,
        "input_segment_count": int,
        "sanitized_segment_count": int,
      }
    """
    cleaned_segments, original_count = _sanitize_path_segments(path_segments)
    commands: List[str] = []

    # Başlangıç bilgileri
    sx, sy = float(start_xy[0]), float(start_xy[1])
    # Heading:
    # - Caller değer verdiyse (start_heading_deg is not None) override edilir ve sabit kalır.
    # - Otomatik modda (None) heading, komut akışındaki İLK GERÇEK DRAW_TO vektöründen
    #   hesaplanır; SET_HEADING satırı en sonda güncellenir.
    override_heading = start_heading_deg is not None
    if override_heading:
        heading = float(start_heading_deg)  # caller verdi
    else:
        heading = 0.0  # placeholder; ilk DRAW_TO’dan sonra düzeltilecek

    # Boş giriş veya tüm segmentler temizlenirken atıldıysa
    if not cleaned_segments:
        commands.append(f"SET_ORIGIN {sx:.6f} {sy:.6f}")
        commands.append(f"SET_HEADING {heading:.6f}")
        commands.append("PEN_UP")
        commands.append("END")
        return {
            "commands": commands,
            "move_count": 0,
            "drawn_length_m": 0.0,
            "travel_length_m": 0.0,
            "start_xy": [sx, sy],
            "start_heading_deg": heading,
            "draw_command_count": 0,
            "travel_command_count": 0,
            "input_segment_count": original_count,
            "sanitized_segment_count": 0,
        }

    pen_down = False
    move_count = 0
    draw_cmd_count = 0
    travel_cmd_count = 0
    drawn_length = 0.0
    travel_length = 0.0

    # Heading için ilk gerçek DRAW_TO vektörünü takip et (sadece auto modda kullanılır)
    first_draw_found = False
    first_draw_dx = 0.0
    first_draw_dy = 0.0

    current_pos: Tuple[float, float] = (sx, sy)

    # Başlangıç komutları (SET_HEADING placeholder; gerekirse sonda güncellenecek)
    commands.append(f"SET_ORIGIN {sx:.6f} {sy:.6f}")
    commands.append(f"SET_HEADING {heading:.6f}")
    commands.append("PEN_UP")

    for idx, (x1, y1, x2, y2) in enumerate(cleaned_segments):
        start = (x1, y1)
        end = (x2, y2)

        # İlk stroke veya yeni stroke başlangıcı: pen up + MOVE_TO
        if idx == 0:
            # İlk MOVE_TO (start_xy → ilk segment başlangıcı)
            dist = math.hypot(start[0] - current_pos[0], start[1] - current_pos[1])
            travel_length += dist
            commands.append(f"MOVE_TO {start[0]:.6f} {start[1]:.6f}")
            move_count += 1
            travel_cmd_count += 1
            current_pos = start
        else:
            # Eğer önceki segmentin sonu ile bu segmentin başı farklıysa:
            if not _points_equal(current_pos, start):
                if pen_down:
                    commands.append("PEN_UP")
                    pen_down = False
                dist = math.hypot(start[0] - current_pos[0], start[1] - current_pos[1])
                travel_length += dist
                commands.append(f"MOVE_TO {start[0]:.6f} {start[1]:.6f}")
                move_count += 1
                travel_cmd_count += 1
                current_pos = start

        # Pen aşağı değilse, çizime başlamadan önce indir
        if not pen_down:
            commands.append("PEN_DOWN")
            pen_down = True

        # Segmenti çiz (DRAW_TO)
        dist_seg = math.hypot(end[0] - start[0], end[1] - start[1])
        drawn_length += dist_seg
        commands.append(f"DRAW_TO {end[0]:.6f} {end[1]:.6f}")
        move_count += 1
        draw_cmd_count += 1

        # Heading auto modundaysa, ilk gerçek DRAW_TO vektöründen heading hesapla
        if not override_heading and not first_draw_found and dist_seg > 0.0:
            first_draw_dx = end[0] - start[0]
            first_draw_dy = end[1] - start[1]
            first_draw_found = True

        current_pos = end

    # Sonunda kalem aşağıdaysa kaldır
    if pen_down:
        commands.append("PEN_UP")
        pen_down = False

    commands.append("END")

    # Auto heading modundaysa, ilk gerçek DRAW_TO vektöründen heading'i hesapla
    if not override_heading and first_draw_found:
        ang_rad = math.atan2(first_draw_dy, first_draw_dx)
        ang_deg = math.degrees(ang_rad)
        if ang_deg > 180.0:
            ang_deg -= 360.0
        if ang_deg <= -180.0:
            ang_deg += 360.0
        heading = ang_deg
        # SET_HEADING satırını güncelle (index 1)
        commands[1] = f"SET_HEADING {heading:.6f}"

    return {
        "commands": commands,
        "move_count": move_count,
        "draw_command_count": draw_cmd_count,
        "travel_command_count": travel_cmd_count,
        "drawn_length_m": drawn_length,
        "travel_length_m": travel_length,
        "start_xy": [sx, sy],
        "start_heading_deg": heading,
        "input_segment_count": original_count,
        "sanitized_segment_count": len(cleaned_segments),
    }

