# test_optimizer.py — Path optimizer birim testleri
from __future__ import annotations

import unittest
from commands import (
    parse_commands,
    serialize_commands,
    MoveCommand,
    PenCommand,
    SpeedCommand,
    WaitCommand,
    TurnCommand,
    ForwardCommand,
)
from path_optimizer import (
    OptimizeConfig,
    optimize_commands,
    commands_to_polyline_segments,
    segments_to_commands,
)


def _count_moves(commands):
    return sum(
        1
        for c in commands
        if isinstance(c, (MoveCommand,))
    )


class TestOptimizer(unittest.TestCase):
    def test_collinear_reduction(self):
        """Aynı doğrultuda ardışık MOVE'lar sadeleşmeli: MOVE 0 0, 5 0, 10 0, 15 0 -> MOVE 0 0, MOVE 15 0."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
MOVE 5 0
MOVE 10 0
MOVE 15 0
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=True, min_segment_length=0.0, collinear_angle_eps_deg=1.0, rdp_epsilon=0.0)
        out = optimize_commands(commands, start, cfg)
        move_cmds = [c for c in out if isinstance(c, MoveCommand)]
        self.assertEqual(len(move_cmds), 2, f"Beklenen 2 MOVE, gelen: {len(move_cmds)}")
        self.assertEqual((move_cmds[0].x, move_cmds[0].y), (0.0, 0.0))
        self.assertEqual((move_cmds[1].x, move_cmds[1].y), (15.0, 0.0))

    def test_pen_boundary_preserved(self):
        """PEN DOWN segmenti ve PEN UP segmenti ayrı kalmalı."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
MOVE 10 0
PEN UP
MOVE 20 0
MOVE 30 0
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=True, min_segment_length=0.0, collinear_angle_eps_deg=1.0, rdp_epsilon=0.0)
        out = optimize_commands(commands, start, cfg)
        pen_cmds = [c for c in out if isinstance(c, PenCommand)]
        self.assertGreaterEqual(len(pen_cmds), 2, "En az 2 PEN komutu (DOWN ve UP) olmalı")
        self.assertTrue(pen_cmds[0].is_down)
        self.assertFalse(pen_cmds[1].is_down)
        move_cmds = [c for c in out if isinstance(c, MoveCommand)]
        self.assertEqual(len(move_cmds), 4, "İki segment: 2+2 MOVE")

    def test_wait_preserved(self):
        """MOVE 0 0, WAIT 1.0, MOVE 10 0 — WAIT korunmalı."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
WAIT 1.0
MOVE 10 0
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=True, min_segment_length=0.0, collinear_angle_eps_deg=1.0, rdp_epsilon=0.0)
        out = optimize_commands(commands, start, cfg)
        wait_cmds = [c for c in out if isinstance(c, WaitCommand)]
        self.assertEqual(len(wait_cmds), 1, f"Bir WAIT olmalı, gelen: {len(wait_cmds)}")
        self.assertEqual(wait_cmds[0].seconds, 1.0)

    def test_turn_forward_normalize_and_optimize(self):
        """TURN 0, FORWARD 10, FORWARD 10 (collinear) -> MOVE 0 0, MOVE 20 0 (2 nokta)."""
        text = """SPEED 10
PEN DOWN
TURN 0
FORWARD 10
FORWARD 10
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=True, min_segment_length=0.0, collinear_angle_eps_deg=1.0, rdp_epsilon=0.0)
        out = optimize_commands(commands, start, cfg)
        move_cmds = [c for c in out if isinstance(c, MoveCommand)]
        self.assertEqual(len(move_cmds), 2, f"İki MOVE (başlangıç + bitiş) bekleniyor, gelen: {len(move_cmds)}")
        self.assertAlmostEqual(move_cmds[0].x, 0.0, places=9)
        self.assertAlmostEqual(move_cmds[0].y, 0.0, places=9)
        self.assertAlmostEqual(move_cmds[1].x, 20.0, places=9)
        self.assertAlmostEqual(move_cmds[1].y, 0.0, places=9)

    def test_optimize_disabled_returns_unchanged(self):
        """Optimize kapalıyken çıktı aynı olmalı (mutlak MOVE’a çevrilmez, sadece optimize uygulanmaz)."""
        text = """PEN DOWN
MOVE 0 0
MOVE 5 0
MOVE 10 0
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=False)
        out = optimize_commands(commands, start, cfg)
        self.assertEqual(len(out), len(commands))
        self.assertTrue(all(type(a) == type(b) for a, b in zip(out, commands)))


    def test_commands_to_polyline_segments(self):
        """Komutlar segmentlere doğru ayrılmalı."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
MOVE 10 0
PEN UP
MOVE 20 0
"""
        commands, _ = parse_commands(text, strict=True)
        segments = commands_to_polyline_segments(commands, (0.0, 0.0))
        self.assertEqual(len(segments), 2)
        self.assertTrue(segments[0].pen_down)
        self.assertEqual(len(segments[0].points), 2)
        self.assertFalse(segments[1].pen_down)
        self.assertEqual(len(segments[1].points), 1)
        self.assertEqual(segments[1].points[0], (20.0, 0.0))

    def test_segments_to_commands_roundtrip(self):
        """Segment -> komut -> serialize -> parse tekrar aynı yapıyı vermeli (2 MOVE)."""
        text = """SPEED 10
PEN DOWN
MOVE 0 0
MOVE 10 0
MOVE 20 0
"""
        commands, _ = parse_commands(text, strict=True)
        start = (0.0, 0.0)
        cfg = OptimizeConfig(enabled=True, min_segment_length=0.0, collinear_angle_eps_deg=1.0, rdp_epsilon=0.0)
        out = optimize_commands(commands, start, cfg)
        ser = serialize_commands(out)
        back, _ = parse_commands(ser, strict=False)
        move_back = [c for c in back if isinstance(c, MoveCommand)]
        self.assertGreaterEqual(len(move_back), 2)
        self.assertEqual((move_back[0].x, move_back[0].y), (0.0, 0.0))
        self.assertEqual((move_back[-1].x, move_back[-1].y), (20.0, 0.0))


if __name__ == "__main__":
    unittest.main()
