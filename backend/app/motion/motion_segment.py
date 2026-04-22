"""
Rotate-then-go segment: geometrik hedefler (komut haritalaması ile uyumlu).

``turn_delta_deg`` ve ``forward_distance_m`` çifti, segment başlangıcındaki
pozdan türetilen mutlak hedef başlık ve hedef noktayı tanımlar; kontrolör
bunları ``segment_controller`` içinde hesaplar.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RotateThenGoSegment:
    """
    Yerinde dönüş + düz çizgi ile yürütülecek tek segment.

    - ``turn_delta_deg``: Başlangıç başlığına göre eklenecek dönüş (derece).
    - ``forward_distance_m``: Dönüş tamamlandıktan sonra bu başlıkta gidilecek mesafe (m).
    """

    turn_delta_deg: float
    forward_distance_m: float
