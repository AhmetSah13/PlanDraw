from __future__ import annotations

import math
from typing import List, Optional, Tuple

from app.core.plan_module import Plan, Wall, load_plan_from_file


def _squared_dist(px: float, py: float, qx: float, qy: float) -> float:
    """İki nokta arası mesafenin karesi (karşılaştırma için, sqrt gereksiz)."""
    dx = qx - px
    dy = qy - py
    return dx * dx + dy * dy


def _bbox_center(walls: List[Wall]) -> Optional[Tuple[float, float]]:
    """Duvarların kapsadığı bbox merkezini döner; boş liste ise None."""
    if not walls:
        return None
    xs: List[float] = []
    ys: List[float] = []
    for w in walls:
        xs.extend((w.x1, w.x2))
        ys.extend((w.y1, w.y2))
    return ((min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0)


def order_segments_nearest_neighbor(
    walls: List[Wall],
    start_point: Optional[Tuple[float, float]] = None,
) -> List[Wall]:
    """
    En yakın komşu + uç çevirme ile duvar sıralaması.
    Pen-up (seyahat) mesafesini azaltır; deterministiktir.
    Orijinal planı değiştirmez; gerekirse çevrilmiş kopya Wall döner.
    """
    if not walls:
        return []
    n = len(walls)
    start = start_point if start_point is not None else _bbox_center(walls)
    if start is None:
        start = (walls[0].x1, walls[0].y1)

    # (segment_index,) ile indeksleri sakla; orijinal sıra tie-break için
    remaining = set(range(n))
    ordered: List[Wall] = []
    cx, cy = start[0], start[1]

    while remaining:
        best_idx: Optional[int] = None
        best_dist_sq: float = float("inf")
        use_flip = False
        # Tie-break: (dist_sq, segment_idx, entry_x, entry_y)
        best_key: Tuple[float, int, float, float] = (float("inf"), 0, 0.0, 0.0)

        for idx in remaining:
            w = walls[idx]
            d_a = _squared_dist(cx, cy, w.x1, w.y1)
            d_b = _squared_dist(cx, cy, w.x2, w.y2)
            if d_a <= d_b:
                dist_sq = d_a
                flip = False
                entry = (w.x1, w.y1)
            else:
                dist_sq = d_b
                flip = True
                entry = (w.x2, w.y2)
            key = (dist_sq, idx, entry[0], entry[1])
            if key < best_key:
                best_key = key
                best_idx = idx
                best_dist_sq = dist_sq
                use_flip = flip

        if best_idx is None:
            break
        remaining.discard(best_idx)
        w = walls[best_idx]
        if use_flip:
            ordered.append(Wall(x1=w.x2, y1=w.y2, x2=w.x1, y2=w.y1))
            cx, cy = w.x1, w.y1
        else:
            ordered.append(Wall(x1=w.x1, y1=w.y1, x2=w.x2, y2=w.y2))
            cx, cy = w.x2, w.y2

    return ordered


def compute_travel_distance(
    ordered_walls: List[Wall],
    start_point: Tuple[float, float],
) -> float:
    """
    Sıralı duvar listesi için toplam seyahat (pen-up) mesafesi.
    Her duvar (x1,y1)->(x2,y2) olarak geçilir; önce start_point'ten ilk duvar başına,
    sonra her duvar sonundan bir sonraki duvar başına mesafe toplanır.
    """
    total = 0.0
    px, py = start_point[0], start_point[1]
    for w in ordered_walls:
        total += math.hypot(w.x1 - px, w.y1 - py)
        px, py = w.x2, w.y2
    return total


class PathGenerator:
    """
    Verilen bir plan için nokta tabanlı yol üretir.
    order_walls=True (varsayılan) ile duvarlar en-yakın-komşu sıralanır;
    böylece pen-up seyahat mesafesi ve çakışma riski azalır.
    """

    def __init__(
        self,
        plan: Plan,
        step_size: float = 5.0,
        order_walls: bool = True,
    ) -> None:
        if step_size <= 0:
            raise ValueError("step_size sıfırdan büyük olmalıdır.")
        self.plan = plan
        self.step_size = float(step_size)
        self.order_walls = bool(order_walls)


    def _generate_points_for_wall(self, wall: Wall) -> List[Tuple[float, float]]:
        """
        Tek bir duvar için başlangıçtan bitişe eşit aralıklı nokta listesi üretir.
        n = ceil(length/step) parçaya bölünür; iki nokta arası mesafe step'i aşmaz.
        """
        dx = wall.x2 - wall.x1
        dy = wall.y2 - wall.y1
        length = math.hypot(dx, dy)

        if length <= 0:
            return [(wall.x1, wall.y1)]

        step = max(1e-6, float(self.step_size))
        n = max(1, int(math.ceil(length / step)))

        points: List[Tuple[float, float]] = []
        for i in range(n + 1):
            t = i / n
            points.append((wall.x1 + dx * t, wall.y1 + dy * t))
        return points

    def generate_path(self) -> List[Tuple[float, float]]:
        """
        Plandaki tüm duvarlar için nokta listesi üretir ve
        tek bir sıralı liste şeklinde birleştirir.
        order_walls=True ise önce en-yakın-komşu sıralama uygulanır (orijinal plan değişmez).
        """
        walls_to_use: List[Wall]
        if self.order_walls:
            wall_list = list(self.plan)
            if wall_list:
                start = _bbox_center(wall_list)
                walls_to_use = order_segments_nearest_neighbor(wall_list, start_point=start)
            else:
                walls_to_use = []
        else:
            walls_to_use = list(self.plan)

        tum_noktalar: List[Tuple[float, float]] = []
        for wall in walls_to_use:
            duvar_noktalari = self._generate_points_for_wall(wall)
            tum_noktalar.extend(duvar_noktalari)

        return tum_noktalar


if __name__ == "__main__":
    # Küçük bir örnek kullanım:
    # Aynı klasördeki 'plan.txt' dosyasını okur, yol üretir ve toplam nokta sayısını yazdırır.
    plan = load_plan_from_file("plan.txt")
    path_generator = PathGenerator(plan, step_size=5.0)
    path = path_generator.generate_path()

    print(f"Toplam nokta sayısı: {len(path)}")
    print("İlk 10 nokta:")
    for noktalar_index, (x, y) in enumerate(path[:10], start=1):
        print(f"  {noktalar_index:02d}. ({x:.2f}, {y:.2f})")

