from __future__ import annotations

import math
from typing import List, Tuple, Optional

EPS: float = 1e-9


def _orient(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
  """
  Yön testi: (b - a) x (c - a) (2B cross çarpımı).
  Pozitif: saat yönü tersi, negatif: saat yönü, ~0: kollinear.
  """
  return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _on_segment(ax: float, ay: float, bx: float, by: float, px: float, py: float) -> bool:
  """
  P noktası, AB doğrusu üzerinde ve A-B kutusu içinde mi?
  """
  if abs(_orient(ax, ay, bx, by, px, py)) > EPS:
    return False
  return (
    min(ax, bx) - EPS <= px <= max(ax, bx) + EPS
    and min(ay, by) - EPS <= py <= max(ay, by) + EPS
  )


def segment_intersection(
  a: Tuple[float, float],
  b: Tuple[float, float],
  c: Tuple[float, float],
  d: Tuple[float, float],
) -> Tuple[bool, Optional[Tuple[float, float]], str]:
  """
  İki doğru parçasının kesişimini hesaplar.

  Döner:
    (False, None, "")                -> kesişim yok
    (True, (x, y), "proper")         -> iç bölgede kesişim (X tipi)
    (True, (x, y), "touch")          -> sadece uç noktada temas
    (True, None,    "overlap")       -> kollinear, üst üste binen aralık
  """
  ax, ay = a
  bx, by = b
  cx, cy = c
  dx, dy = d

  o1 = _orient(ax, ay, bx, by, cx, cy)
  o2 = _orient(ax, ay, bx, by, dx, dy)
  o3 = _orient(cx, cy, dx, dy, ax, ay)
  o4 = _orient(cx, cy, dx, dy, bx, by)

  def _sign(v: float) -> int:
    if v > EPS:
      return 1
    if v < -EPS:
      return -1
    return 0

  s1, s2, s3, s4 = _sign(o1), _sign(o2), _sign(o3), _sign(o4)

  # Genel durum: karşı işaretli yönler -> proper kesişim
  if s1 * s2 < 0 and s3 * s4 < 0:
    # Doğruların kesim noktasını parametre t ile bul
    denom = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(denom) < EPS:
      # Nümerik tutarsızlık, ama zaten proper dedik: temas kabul etme
      return True, None, "overlap"
    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denom
    ix = ax + t * (bx - ax)
    iy = ay + t * (by - ay)
    return True, (ix, iy), "proper"

  # Kollinear durum
  if s1 == 0 and s2 == 0 and s3 == 0 and s4 == 0:
    # 1D aralık kesişimi: ortak uzunluk > EPS ise overlap, yoksa tek nokta (touch) veya ayrık (none)
    overlap_start_x = max(min(ax, bx), min(cx, dx))
    overlap_end_x = min(max(ax, bx), max(cx, dx))
    overlap_start_y = max(min(ay, by), min(cy, dy))
    overlap_end_y = min(max(ay, by), max(cy, dy))
    # Collinear için x veya y farkından biri segment boyunca uzunluk verir (diğeri ~0)
    overlap_len = max(overlap_end_x - overlap_start_x, overlap_end_y - overlap_start_y)

    if overlap_len < -EPS:
      return False, None, ""

    if overlap_len > EPS:
      return True, None, "overlap"

    # Tek noktada temas (overlap_len ~0): ortak nokta
    touch_pt = (overlap_start_x, overlap_start_y)
    return True, touch_pt, "touch"

  # Uç nokta teması (kollinear değil ama bir uç diğer segment üzerinde)
  for px, py in ((ax, ay), (bx, by), (cx, cy), (dx, dy)):
    if _on_segment(ax, ay, bx, by, px, py) and _on_segment(cx, cy, dx, dy, px, py):
      return True, (px, py), "touch"

  return False, None, ""


def polyline_segments(
  points: List[Tuple[float, float]]
) -> List[Tuple[Tuple[float, float], Tuple[float, float]]]:
  """
  Nokta listesinden ardışık segmentler üretir.
  """
  segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
  if len(points) < 2:
    return segs
  for i in range(len(points) - 1):
    a = points[i]
    b = points[i + 1]
    segs.append((a, b))
  return segs


def distance_point_to_segment(
  px: float,
  py: float,
  ax: float,
  ay: float,
  bx: float,
  by: float,
) -> float:
  """
  P noktasının AB segmentine olan en kısa mesafesi.
  """
  vx = bx - ax
  vy = by - ay
  wx = px - ax
  wy = py - ay
  seg_len2 = vx * vx + vy * vy
  if seg_len2 < EPS:
    return math.hypot(px - ax, py - ay)
  t = (wx * vx + wy * vy) / seg_len2
  if t <= 0.0:
    cx, cy = ax, ay
  elif t >= 1.0:
    cx, cy = bx, by
  else:
    cx, cy = ax + t * vx, ay + t * vy
  return math.hypot(px - cx, py - cy)

