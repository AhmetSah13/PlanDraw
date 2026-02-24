from __future__ import annotations

import math
from typing import List, Tuple

from plan_module import Plan, Wall, load_plan_from_file


class PathGenerator:
    """Verilen bir plan için nokta tabanlı yol üretir."""

    def __init__(self, plan: Plan, step_size: float = 5.0) -> None:
        if step_size <= 0:
            raise ValueError("step_size sıfırdan büyük olmalıdır.")
        self.plan = plan
        self.step_size = float(step_size)

    def _generate_points_for_wall(self, wall: Wall) -> List[Tuple[float, float]]:
        """
        Tek bir duvar için başlangıçtan bitişe kadar nokta listesi üretir.

        Noktalar arası mesafe yaklaşık olarak step_size olacaktır.
        Son noktaya (duvarın bitişine) her zaman yer verilir.
        """
        dx = wall.x2 - wall.x1
        dy = wall.y2 - wall.y1

        uzunluk = math.hypot(dx, dy)
        if uzunluk == 0:
            # Sıfır uzunluklu duvar; sadece tek bir nokta döndür.
            return [(wall.x1, wall.y1)]

        # Kaç adımda geçileceğini hesapla (en az 1 adım).
        adim_sayisi = max(1, int(math.floor(uzunluk / self.step_size)))

        noktalar: List[Tuple[float, float]] = []

        # t, 0 ile 1 arasında parametre: t=0 -> başlangıç, t=1 -> bitiş
        for i in range(adim_sayisi):
            t = i * self.step_size / uzunluk
            x = wall.x1 + t * dx
            y = wall.y1 + t * dy
            noktalar.append((x, y))

        # Bitiş noktasını da ekle (tekrar varsa kontrol et)
        bitis = (wall.x2, wall.y2)
        if not noktalar or noktalar[-1] != bitis:
            noktalar.append(bitis)

        return noktalar

    def generate_path(self) -> List[Tuple[float, float]]:
        """
        Plandaki tüm duvarlar için nokta listesi üretir ve
        tek bir sıralı liste şeklinde birleştirir.
        """
        tum_noktalar: List[Tuple[float, float]] = []

        for wall in self.plan:
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

