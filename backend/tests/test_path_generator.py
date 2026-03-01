# test_path_generator.py — PathGenerator ceil + eşit bölme; step aşmıyor
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.core.plan_module import Plan, Wall
from app.pathing.path_generator import PathGenerator


class TestPathGeneratorStepNotExceeded(unittest.TestCase):
    """PathGenerator: ardışık noktalar arası mesafe step_size'ı aşmaz."""

    def test_length_1_step_03_interval_at_most_step(self):
        # length=1.0, step=0.3 → n=ceil(1/0.3)=4 parça → 5 nokta, aralık 0.25 <= 0.3
        plan = Plan([Wall(0.0, 0.0, 1.0, 0.0)])
        pg = PathGenerator(plan, step_size=0.3)
        path = pg.generate_path()
        self.assertGreaterEqual(len(path), 2)
        for i in range(len(path) - 1):
            dx = path[i + 1][0] - path[i][0]
            dy = path[i + 1][1] - path[i][1]
            d = math.hypot(dx, dy)
            self.assertLessEqual(d, 0.3 + 1e-9, msg=f"Aralık {i}->{i+1} = {d} step 0.3'i aştı")
        self.assertAlmostEqual(path[0][0], 0.0)
        self.assertAlmostEqual(path[-1][0], 1.0)


if __name__ == "__main__":
    unittest.main()
