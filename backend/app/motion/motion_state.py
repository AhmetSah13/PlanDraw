"""
Gelecekte diferansiyel sürüş tabanlı fiziksel yürütme için minimal durum modelleri.

Mevcut ``CommandExecutor`` (``app.execution.executor``) simülasyon odaklıdır ve
dünya çerçevesinde doğrudan doğruya hedefe ilerler (holonomic nokta-robot
yaklaşımı). Bu modül, ileride rotate-then-go ile uyumlu planlama için ayrı
tutulur; gerçek tekerlek kinematiği veya PID burada yoktur.

İleride ``execution_status`` benzeri alanlar eklenebilir; şimdilik sade tutulur.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pose2D:
    """Dünya çerçevesinde 2B konum ve başlık (derece)."""

    x: float
    y: float
    theta_deg: float


@dataclass
class RobotMotionState:
    """Fiziksel robotta taşınabilecek minimal durum (planlama / ileride kontrol)."""

    pose: Pose2D
    pen_down: bool
    last_speed_m_s: float | None = None
