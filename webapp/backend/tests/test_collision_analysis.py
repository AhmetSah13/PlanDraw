from __future__ import annotations

import unittest
import sys
from pathlib import Path

# Proje kökü (NewBot): webapp/backend/tests -> parents[3]
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
  sys.path.insert(0, str(_root))

from commands import parse_commands  # type: ignore
from scenario_analysis import analyze_commands  # type: ignore


class TestCollisionAnalysis(unittest.TestCase):
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


if __name__ == "__main__":
  unittest.main()

