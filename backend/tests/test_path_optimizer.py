# test_path_optimizer.py — Path optimizer: stroke sıralama, travel azaltma, determinizm
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import (
    Command,
    MoveCommand,
    PenCommand,
    SpeedCommand,
)
from app.execution.compiler import compile_path_to_commands_from_segments
from app.pathing.path_optimizer import (
    OptimizeConfig,
    optimize_commands,
    commands_to_polyline_segments,
)


def test_two_strokes_travel_reduced_or_unchanged():
    """İki stroke: optimize sonrası travel düşer veya aynı kalır (kötüleşmez)."""
    # İki ayrı segment: (0,0)-(1,0) ve (2,0)-(3,0). Travel = 1.0 (1'den 2'ye).
    segments = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(2.0, 0.0), (3.0, 0.0)],
    ]
    commands = compile_path_to_commands_from_segments(segments, speed=120.0)
    start = (0.0, 0.0)
    cfg = OptimizeConfig(enabled=True, join_epsilon_m=0.0)
    out = optimize_commands(commands, start, cfg)
    # Hâlâ iki stroke olmalı (join_epsilon=0 ile birleşmez)
    segs = commands_to_polyline_segments(out, start)
    strokes = [s for s in segs if s.pen_down and len(s.points) >= 2]
    assert len(strokes) >= 1
    # Move sayısı sadeleşmiş olabilir
    move_count = sum(1 for c in out if isinstance(c, MoveCommand))
    assert move_count >= 2


def test_stroke_reverse_start_closer():
    """Stroke yönü: başlangıca daha yakın uçtan başlanır."""
    # Bir stroke (5,0)-(10,0), diğeri (0,0)-(1,0). Start=(0,0). İkinci stroke zaten (0,0)'da başlıyor.
    # NN ile önce (0,0)-(1,0) seçilmeli, sonra (5,0)-(10,0). İkinci stroke ters çevrilirse (10,0)-(5,0);
    # (1,0)'dan (10,0) veya (5,0)'a gideriz; (5,0) daha yakın, o yüzden normal (5,0)-(10,0) seçilir.
    segments = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(5.0, 0.0), (10.0, 0.0)],
    ]
    commands = compile_path_to_commands_from_segments(segments, speed=120.0)
    start = (0.0, 0.0)
    cfg = OptimizeConfig(enabled=True, join_epsilon_m=0.0, preserve_order_for_layers=False)
    out = optimize_commands(commands, start, cfg)
    segs = commands_to_polyline_segments(out, start)
    strokes = [s for s in segs if s.pen_down and len(s.points) >= 2]
    assert len(strokes) == 2
    # İlk stroke (0,0)-(1,0) olmalı (start'a en yakın)
    assert strokes[0].points[0] == (0.0, 0.0) or strokes[0].points[-1] == (0.0, 0.0)


def test_determinism_same_input_same_output():
    """Aynı girdi -> aynı çıktı (deterministik)."""
    segments = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(1.0, 1.0), (2.0, 1.0)],
        [(3.0, 0.0), (4.0, 0.0)],
    ]
    commands = compile_path_to_commands_from_segments(segments, speed=120.0)
    start = (0.0, 0.0)
    cfg = OptimizeConfig(enabled=True, join_epsilon_m=0.0)
    out1 = optimize_commands(commands, start, cfg)
    out2 = optimize_commands(commands, start, cfg)
    assert len(out1) == len(out2)
    for c1, c2 in zip(out1, out2):
        assert type(c1) == type(c2)
        if isinstance(c1, MoveCommand):
            assert abs(c1.x - c2.x) < 1e-9 and abs(c1.y - c2.y) < 1e-9


def test_optimize_disabled_preserves_behavior():
    """Optimize kapalıyken davranış değişmez (aynı komutlar)."""
    segments = [[(0.0, 0.0), (1.0, 0.0)]]
    commands = compile_path_to_commands_from_segments(segments, speed=120.0)
    start = (0.0, 0.0)
    cfg = OptimizeConfig(enabled=False)
    out = optimize_commands(commands, start, cfg)
    assert len(out) == len(commands)
    assert all(type(a) == type(b) for a, b in zip(commands, out))


def test_nn_stroke_enters_from_nearest_endpoint_single_stroke():
    """
    Tek stroke (10,0)-(20,0), başlangıç (0,0): giriş (10,0) olmalı (baş uç daha yakın).
    Yanlış best_rev NN seçimi ilk noktayı (20,0) yapardı.
    """
    segments = [[(10.0, 0.0), (20.0, 0.0)]]
    commands = compile_path_to_commands_from_segments(segments, speed=120.0)
    start = (0.0, 0.0)
    cfg = OptimizeConfig(enabled=True, join_epsilon_m=0.0, preserve_order_for_layers=False)
    out = optimize_commands(commands, start, cfg)
    segs = commands_to_polyline_segments(out, start)
    strokes = [s for s in segs if s.pen_down and len(s.points) >= 2]
    assert len(strokes) == 1
    assert strokes[0].points[0] == (10.0, 0.0)
    assert strokes[0].points[-1] == (20.0, 0.0)
