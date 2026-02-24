from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class Wall:
    """Bir duvarı temsil eden sınıf."""

    x1: float
    y1: float
    x2: float
    y2: float

    def __str__(self) -> str:
        return f"Duvar: ({self.x1}, {self.y1}) -> ({self.x2}, {self.y2})"


class Plan:
    """Plan içindeki tüm duvarları tutan sınıf."""

    def __init__(self, walls: List[Wall] | None = None) -> None:
        self.walls: List[Wall] = walls or []

    def add_wall(self, wall: Wall) -> None:
        """Plana yeni bir duvar ekler."""
        self.walls.append(wall)

    def __iter__(self):
        return iter(self.walls)

    def __str__(self) -> str:
        satirlar = ["Plan içeriği:"]
        if not self.walls:
            satirlar.append("  (Hiç duvar yok)")
        else:
            for i, wall in enumerate(self.walls, start=1):
                satirlar.append(f"  {i:02d}. {wall}")
        return "\n".join(satirlar)


def _parse_wall_line(line: str) -> Wall:
    """
    Tek bir satırı (ör: 'LINE x1 y1 x2 y2') çözümler ve Wall nesnesi döndürür.

    Hatalı formatta ise ValueError fırlatır.
    """
    parcalar = line.strip().split()

    if len(parcalar) != 5:
        raise ValueError(f"Geçersiz satır formatı: '{line.strip()}' (5 parça bekleniyordu)")

    if parcalar[0].upper() != "LINE":
        raise ValueError(f"Geçersiz satır tipi: '{parcalar[0]}' (LINE bekleniyordu)")

    try:
        x1, y1, x2, y2 = map(float, parcalar[1:])
    except ValueError as exc:
        raise ValueError(f"Koordinatlar sayı olmalı: '{line.strip()}'") from exc

    return Wall(x1=x1, y1=y1, x2=x2, y2=y2)


def load_plan_from_string(text: str) -> Plan:
    """
    Verilen metinden plan yükler (dosya yerine string).

    Her satır 'LINE x1 y1 x2 y2' formatında olmalıdır.
    Boş satırlar ve '#' ile başlayan yorum satırları yok sayılır.
    """
    walls: List[Wall] = []
    for satir_no, satir in enumerate(text.splitlines(), start=1):
        ham = satir.strip()
        if not ham:
            continue
        if ham.startswith("#"):
            continue
        try:
            wall = _parse_wall_line(ham)
        except ValueError as exc:
            raise ValueError(f"line {satir_no}: {exc}") from exc
        walls.append(wall)
    return Plan(walls)


def load_plan_from_file(path: str = "plan.txt") -> Plan:
    """
    Verilen dosya yolundan plan yükler.

    Her satır 'LINE x1 y1 x2 y2' formatında olmalıdır.
    Boş satırlar ve yalnızca '#' ile başlayan yorum satırları yok sayılır.
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    walls = []
    for satir_no, satir in enumerate(text.splitlines(), start=1):
        ham = satir.strip()
        if not ham or ham.startswith("#"):
            continue
        try:
            walls.append(_parse_wall_line(ham))
        except ValueError as exc:
            raise ValueError(f"{path}:{satir_no}: {exc}") from exc
    return Plan(walls)


if __name__ == "__main__":
    # Basit kullanım örneği:
    # Aynı klasördeki 'plan.txt' dosyasını okur ve sonucu yazdırır.
    plan = load_plan_from_file("plan.txt")
    print(plan)

