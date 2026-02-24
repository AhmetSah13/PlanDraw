# motion_model.py — Drift/noise ile ideal -> gerçek hareket modeli
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class MotionConfig:
    enabled: bool = False
    drift_deg_per_sec: float = 1.0
    position_noise_std_per_sec: float = 2.0
    seed: Optional[int] = None


@dataclass
class MotionState:
    heading_drift_deg: float = 0.0
    rng: random.Random = field(default_factory=random.Random)


def apply_motion(
    ideal_dx: float,
    ideal_dy: float,
    dt: float,
    cfg: MotionConfig,
    state: MotionState,
) -> tuple[float, float]:
    """
    İdeal hareket vektörüne drift ve gürültü uygular.
    ideal_dx, ideal_dy = 0 ise (0, 0) döner.
    """
    if not cfg.enabled or dt <= 0.0:
        return (ideal_dx, ideal_dy)

    dist = math.hypot(ideal_dx, ideal_dy)
    if dist < 1e-12:
        return (0.0, 0.0)

    # Normalize ideal vektör
    ux = ideal_dx / dist
    uy = ideal_dy / dist

    # Drift: heading_drift_deg güncelle, vektörü döndür
    state.heading_drift_deg += cfg.drift_deg_per_sec * dt
    rad = math.radians(state.heading_drift_deg)
    cos_r = math.cos(rad)
    sin_r = math.sin(rad)
    drifted_ux = ux * cos_r - uy * sin_r
    drifted_uy = ux * sin_r + uy * cos_r
    drifted_dx = drifted_ux * dist
    drifted_dy = drifted_uy * dist

    # Noise: std = position_noise_std_per_sec * sqrt(dt)
    std = cfg.position_noise_std_per_sec * math.sqrt(dt)
    noise_dx = state.rng.gauss(0.0, std)
    noise_dy = state.rng.gauss(0.0, std)

    return (drifted_dx + noise_dx, drifted_dy + noise_dy)
