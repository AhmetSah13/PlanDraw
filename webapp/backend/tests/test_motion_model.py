# test_motion_model.py — Motion model birim testleri
from __future__ import annotations

import unittest
import sys
from pathlib import Path

# app modülünü bul (backend/app)
_backend = Path(__file__).resolve().parent.parent
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from app.motion_model import MotionConfig, MotionState, apply_motion


class TestMotionModel(unittest.TestCase):
    def test_disabled_returns_ideal(self):
        """enabled=False ise real_dx, real_dy == ideal_dx, ideal_dy."""
        cfg = MotionConfig(enabled=False)
        state = MotionState()
        real_dx, real_dy = apply_motion(10.0, 0.0, 0.016, cfg, state)
        self.assertAlmostEqual(real_dx, 10.0, places=9)
        self.assertAlmostEqual(real_dy, 0.0, places=9)

    def test_dt_zero_returns_zero(self):
        """ideal hareket 0 değilse bile dt=0 için apply_motion (drift/noise dt ile çarpıldığı için) — aslında dt<=0 branch'te ideal_dx, ideal_dy dönüyor."""
        cfg = MotionConfig(enabled=True, drift_deg_per_sec=1.0, position_noise_std_per_sec=2.0)
        state = MotionState()
        real_dx, real_dy = apply_motion(5.0, 5.0, 0.0, cfg, state)
        self.assertAlmostEqual(real_dx, 5.0, places=9)
        self.assertAlmostEqual(real_dy, 5.0, places=9)

    def test_ideal_zero_returns_zero(self):
        """ideal_dx, ideal_dy = 0 ise (0, 0) döner."""
        cfg = MotionConfig(enabled=True, position_noise_std_per_sec=10.0)
        state = MotionState()
        real_dx, real_dy = apply_motion(0.0, 0.0, 0.1, cfg, state)
        self.assertAlmostEqual(real_dx, 0.0, places=9)
        self.assertAlmostEqual(real_dy, 0.0, places=9)

    def test_seed_deterministic(self):
        """seed=42 ile aynı ideal_dx, ideal_dy, dt için apply_motion iki kez aynı sonucu üretmeli."""
        cfg = MotionConfig(enabled=True, drift_deg_per_sec=1.0, position_noise_std_per_sec=2.0, seed=42)
        state1 = MotionState(rng=__import__("random").Random(42))
        state2 = MotionState(rng=__import__("random").Random(42))
        r1 = apply_motion(1.0, 0.0, 0.016, cfg, state1)
        r2 = apply_motion(1.0, 0.0, 0.016, cfg, state2)
        self.assertAlmostEqual(r1[0], r2[0], places=9)
        self.assertAlmostEqual(r1[1], r2[1], places=9)


if __name__ == "__main__":
    unittest.main()
