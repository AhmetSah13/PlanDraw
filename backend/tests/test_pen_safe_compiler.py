"""Pen-safe stroke-aware compile ve doğrulama testleri (Patch 5)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.api.main import compile_plan
from app.api.schemas import CompilePlanRequest
from app.execution.commands import (
    MoveCommand,
    PenCommand,
    SpeedCommand,
    parse_commands,
    serialize_commands,
)
from app.execution.compiler import (
    compile_path_to_commands_from_segments,
    compile_segments_pen_safe,
)
from app.execution.pen_safe_validator import PenSafeValidationError, validate_pen_safe_commands


def _pen_states(commands) -> list[bool]:
    return [c.is_down for c in commands if isinstance(c, PenCommand)]


def _moves(commands) -> list[tuple[float, float]]:
    return [(c.x, c.y) for c in commands if isinstance(c, MoveCommand)]


def test_single_stroke_pen_safe_sequence() -> None:
    """Test 1 — Tek çizgi A → B."""
    segments = [[(1.0, 2.0), (4.0, 6.0)]]
    cmds = compile_segments_pen_safe(segments, speed=100.0, start_x=0.0, start_y=0.0)
    assert isinstance(cmds[0], SpeedCommand)
    assert isinstance(cmds[1], PenCommand) and cmds[1].is_down is False
    assert cmds[2] == MoveCommand(x=1.0, y=2.0)
    assert isinstance(cmds[3], PenCommand) and cmds[3].is_down is True
    assert cmds[4] == MoveCommand(x=4.0, y=6.0)
    assert isinstance(cmds[-1], PenCommand) and cmds[-1].is_down is False
    validate_pen_safe_commands(cmds)


def test_two_disconnected_strokes_pen_up_between() -> None:
    """Test 2 — İki kopuk çizgi: stroke arası travel PEN UP ile."""
    segments = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(5.0, 0.0), (6.0, 0.0)],
    ]
    cmds = compile_segments_pen_safe(segments, speed=120.0)
    text = serialize_commands(cmds)
    assert "PEN UP" in text
    pens = _pen_states(cmds)
    assert pens == [False, True, False, True, False]
    moves = _moves(cmds)
    assert moves == [(1.0, 0.0), (5.0, 0.0), (6.0, 0.0)]
    validate_pen_safe_commands(cmds)


def test_three_strokes_each_ends_pen_up() -> None:
    """Test 3 — Üç stroke: her biri PEN UP ile kapanır."""
    segments = [
        [(0.0, 0.0), (1.0, 0.0)],
        [(2.0, 1.0), (3.0, 1.0)],
        [(10.0, 5.0), (11.0, 5.0)],
    ]
    cmds = compile_segments_pen_safe(segments)
    pens = _pen_states(cmds)
    assert pens.count(False) == 4
    assert pens.count(True) == 3
    assert pens[-1] is False
    validate_pen_safe_commands(cmds)


def test_empty_and_single_point_segments_skipped_safely() -> None:
    """Test 4 — Boş / tek noktalı segment: riskli PEN DOWN üretilmez."""
    segments = [
        [],
        [(0.0, 0.0)],
        [(1.0, 1.0), (2.0, 2.0)],
    ]
    cmds = compile_segments_pen_safe(segments)
    assert len([c for c in cmds if isinstance(c, PenCommand) and c.is_down]) == 1
    assert isinstance(cmds[-1], PenCommand) and cmds[-1].is_down is False
    validate_pen_safe_commands(cmds)


def test_all_invalid_segments_only_pen_up() -> None:
    cmds = compile_path_to_commands_from_segments([[], [(0.0, 0.0)]])
    assert len(cmds) == 2
    assert isinstance(cmds[0], SpeedCommand)
    assert isinstance(cmds[1], PenCommand) and cmds[1].is_down is False


def test_validator_rejects_pen_down_travel_pattern() -> None:
    """Test 6 — Riskli komut listesi: kalem aşağıdayken travel / eksik PEN UP."""
    risky = [
        SpeedCommand(speed=100.0),
        PenCommand(is_down=True),
        MoveCommand(x=0.0, y=0.0),
        MoveCommand(x=10.0, y=0.0),
        PenCommand(is_down=False),
    ]
    with pytest.raises(PenSafeValidationError, match="PEN UP"):
        validate_pen_safe_commands(risky)

    ends_down = [
        SpeedCommand(speed=100.0),
        PenCommand(is_down=False),
        PenCommand(is_down=True),
        MoveCommand(x=1.0, y=0.0),
    ]
    with pytest.raises(PenSafeValidationError, match="PEN UP"):
        validate_pen_safe_commands(ends_down)

    empty_stroke = [
        SpeedCommand(speed=100.0),
        PenCommand(is_down=False),
        PenCommand(is_down=True),
        PenCommand(is_down=False),
    ]
    with pytest.raises(PenSafeValidationError, match="çizim MOVE"):
        validate_pen_safe_commands(empty_stroke)


def test_compile_plan_api_two_disconnected_lines_regression() -> None:
    """Test 5 — compile_plan API kopuk çizgilerde pen-safe üretir."""
    plan_text = """LINE 0 0 1 0
LINE 5 0 6 0
"""
    resp = compile_plan(
        CompilePlanRequest(
            plan_text=plan_text,
            step_size=1.0,
            speed=100.0,
            world_scale=1.0,
            world_offset=(0.0, 0.0),
        ),
    )
    assert resp.get("ok") is True
    raw = resp["commands_text_raw"]
    cmds, _ = parse_commands(raw, strict=False)
    validate_pen_safe_commands(cmds)
    assert raw.count("PEN UP") >= 2
    assert raw.count("PEN DOWN") >= 2
