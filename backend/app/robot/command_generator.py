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


def convert_path_to_robot_commands(
    path_segments: Iterable[Any],
) -> Dict[str, Any]:
    """
    Segment listesi (x1,y1,x2,y2) → basit robot komut listesi.

    Kurallar:
      1) Başta daima PEN_UP
      2) İlk segment başlangıcına MOVE
      3) Ardından PEN_DOWN
      4) Her segment için DRAW (hedef noktaya)
      5) Bağlantısız segmentler arasında PEN_UP + MOVE + PEN_DOWN

    Dönüş:
      {
        "commands": [ "PEN_UP", "MOVE x y", "PEN_DOWN", "DRAW x y", ... ],
        "move_count": int,           # MOVE + DRAW satırlarının sayısı
        "drawn_length_m": float,     # PEN_DOWN sırasında katedilen toplam mesafe
        "travel_length_m": float,    # PEN_UP sırasında katedilen toplam mesafe
      }
    """
    segments = list(path_segments)
    commands: List[str] = []

    # Boş giriş
    if not segments:
        commands.append("PEN_UP")
        return {
            "commands": commands,
            "move_count": 0,
            "drawn_length_m": 0.0,
            "travel_length_m": 0.0,
        }

    pen_down = False
    move_count = 0
    drawn_length = 0.0
    travel_length = 0.0

    # Robot başlangıç pozisyonu (0,0) varsayımı
    current_pos: Tuple[float, float] = (0.0, 0.0)

    # 1) Daima PEN_UP ile başla
    commands.append("PEN_UP")

    for idx, raw_seg in enumerate(segments):
        x1, y1, x2, y2 = _segment_to_coords(raw_seg)
        start = (x1, y1)
        end = (x2, y2)

        # Stroke başlangıcı: önceki konumdan bu segmentin başlangıcına travel.
        # Spec gereği: ilk segmentten önce daima MOVE komutu üretilir (mesafe 0 olsa bile).
        if idx == 0:
            dist = math.hypot(start[0] - current_pos[0], start[1] - current_pos[1])
            travel_length += dist
            commands.append(f"MOVE {start[0]:.6f} {start[1]:.6f}")
            move_count += 1
            current_pos = start
        else:
            # Eğer önceki segmentin sonu ile bu segmentin başı farklıysa:
            if not _points_equal(current_pos, start):
                # Kalem aşağıdaysa kaldır
                if pen_down:
                    commands.append("PEN_UP")
                    pen_down = False
                # Yeni başlangıca MOVE
                dist = math.hypot(start[0] - current_pos[0], start[1] - current_pos[1])
                travel_length += dist
                commands.append(f"MOVE {start[0]:.6f} {start[1]:.6f}")
                move_count += 1
                current_pos = start

        # PEN_DOWN değilse, çizime başlamadan önce indir
        if not pen_down:
            commands.append("PEN_DOWN")
            pen_down = True

        # Segmenti çiz (DRAW)
        dist_seg = math.hypot(end[0] - start[0], end[1] - start[1])
        drawn_length += dist_seg
        commands.append(f"DRAW {end[0]:.6f} {end[1]:.6f}")
        move_count += 1
        current_pos = end

    # Sonunda kalem aşağıdaysa kaldır
    if pen_down:
        commands.append("PEN_UP")
        pen_down = False

    return {
        "commands": commands,
        "move_count": move_count,
        "drawn_length_m": drawn_length,
        "travel_length_m": travel_length,
    }

