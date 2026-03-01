# test_export.py — Robot export format doğrulama
from __future__ import annotations

import unittest
import sys
from pathlib import Path

# backend/tests
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import parse_commands
from app.analysis.scenario_analysis import export_commands_to_string


class TestExport(unittest.TestCase):
    def test_robot_v1_square_duration(self):
        """Kare script: 4 MOVE, her biri duration ≈ 0.1 (10/100)."""
        text = """SPEED 100
PEN DOWN
REPEAT 4
  FORWARD 10
  TURN 90
END
PEN UP
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        content, blocked, _stats, _diags = export_commands_to_string(
            commands, start, format="robot_v1"
        )
        self.assertFalse(blocked)
        move_lines = [l for l in content.splitlines() if l.strip().startswith("MOVE ")]
        self.assertEqual(len(move_lines), 4, f"4 MOVE bekleniyor, gelen: {len(move_lines)}")
        for line in move_lines:
            parts = line.split()
            self.assertEqual(len(parts), 4, f"MOVE x y t formatı: {line}")
            t = float(parts[3])
            self.assertAlmostEqual(t, 0.1, places=3, msg=f"duration ≈ 0.1: {line}")

    def test_robot_v1_wait(self):
        """WAIT 0.5 -> robot_v1'de WAIT 0.5."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
WAIT 0.5
MOVE 10 0
"""
        commands, _ = parse_commands(text, strict=True)
        content, _blocked, _, _ = export_commands_to_string(
            commands, (0.0, 0.0), format="robot_v1"
        )
        self.assertIn("WAIT 0.5", content)

    def test_gcode_lite_wait(self):
        """WAIT 0.5 -> gcode_lite'da G4 P500."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
WAIT 0.5
MOVE 10 0
"""
        commands, _ = parse_commands(text, strict=True)
        content, _blocked, _, _ = export_commands_to_string(
            commands, (0.0, 0.0), format="gcode_lite"
        )
        self.assertIn("G4 P500", content)


if __name__ == "__main__":
    unittest.main()
