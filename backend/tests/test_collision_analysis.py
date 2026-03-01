from __future__ import annotations

import unittest
import sys
from pathlib import Path

# backend/tests: backend klasörünü path'e ekle
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import parse_commands  # type: ignore
from app.analysis.scenario_analysis import analyze_commands  # type: ignore


class TestCollisionAnalysis(unittest.TestCase):
    """Çakışma analizi: collision_count yalnızca 'proper' kesişimleri sayar."""

    def test_collision_warn_mode(self):
        # Basit dikdörtgen duvarlar: (0,0)-(200,0)-(200,200)-(0,200)
        walls = [
            [0.0, 0.0, 200.0, 0.0],
            [200.0, 0.0, 200.0, 200.0],
            [200.0, 200.0, 0.0, 200.0],
            [0.0, 200.0, 0.0, 0.0],
        ]
        # Yatay çizgi: sol duvardan sağ duvara
        text = """SPEED 100
PEN DOWN
MOVE -10 100
MOVE 210 100
PEN UP
"""
        commands, _ = parse_commands(text, strict=True)
        stats, diags = analyze_commands(
            commands,
            start=(0.0, 0.0),
            walls=walls,
            collision_mode="warn",
        )
        self.assertGreater(stats.collision_count, 0)
        msgs = [d.message for d in diags]
        self.assertTrue(any("kesişim" in m for m in msgs))
        self.assertTrue(any(d.severity == "WARN" for d in diags if "kesişim" in d.message))

    def test_collision_error_mode(self):
        walls = [
            [0.0, 0.0, 200.0, 0.0],
            [200.0, 0.0, 200.0, 200.0],
            [200.0, 200.0, 0.0, 200.0],
            [0.0, 200.0, 0.0, 0.0],
        ]
        text = """SPEED 100
PEN DOWN
MOVE -10 100
MOVE 210 100
PEN UP
"""
        commands, _ = parse_commands(text, strict=True)
        stats, diags = analyze_commands(
            commands,
            start=(0.0, 0.0),
            walls=walls,
            collision_mode="error",
        )
        self.assertGreater(stats.collision_count, 0)
        msgs = [d.message for d in diags]
        self.assertTrue(any("kesişim" in m for m in msgs))
        self.assertTrue(any(d.severity == "ERROR" for d in diags if "kesişim" in d.message))

    def test_wall_draw_overlap_not_counted_as_collision(self):
        """Çizim segmenti duvar ile aynı (üst üste) ise overlap; collision_count 0 kalır."""
        walls = [[0.0, 0.0, 100.0, 0.0]]
        text = """SPEED 100
PEN DOWN
MOVE 0 0
MOVE 100 0
PEN UP
"""
        commands, _ = parse_commands(text, strict=True)
        stats, diags = analyze_commands(
            commands,
            start=(0.0, 0.0),
            walls=walls,
            collision_mode="warn",
        )
        self.assertEqual(stats.collision_count, 0, "Overlap collision sayılmamalı")
        self.assertGreaterEqual(stats.wall_overlap_count, 1)
        msgs = [d.message for d in diags]
        self.assertFalse(any("beklenmeyen kesişim" in m for m in msgs))

    def test_proper_cross_increments_collision_count(self):
        """Çizim duvarı gerçekten keserse (proper) collision_count artar."""
        walls = [[0.0, 100.0, 200.0, 100.0]]
        text = """SPEED 100
PEN DOWN
MOVE 100 50
MOVE 100 150
PEN UP
"""
        commands, _ = parse_commands(text, strict=True)
        stats, diags = analyze_commands(
            commands,
            start=(0.0, 0.0),
            walls=walls,
            collision_mode="warn",
        )
        self.assertGreater(stats.collision_count, 0)
        self.assertEqual(stats.wall_proper_cross_count, stats.collision_count)
        self.assertTrue(any("beklenmeyen kesişim" in d.message for d in diags))


if __name__ == "__main__":
    unittest.main()

