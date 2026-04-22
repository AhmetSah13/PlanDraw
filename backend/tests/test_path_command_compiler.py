from __future__ import annotations

import pytest

from app.execution.commands import MoveCommand, PenCommand, SpeedCommand
from app.execution.path_compiler import (
    PlannedPathCompileOptions,
    compile_planned_path_to_commands,
)
from app.layout_ir.ir_types import SourceRef
from app.path_planning.plan_model import PlannedPath, PlannedStroke


def _src() -> SourceRef:
    return SourceRef(layer="0", entity_type="LINE", handle="h1")


def test_empty_planned_path():
    path = PlannedPath(strokes=())
    cmds, rep = compile_planned_path_to_commands(path)
    assert len(cmds) == 2
    assert isinstance(cmds[0], SpeedCommand)
    assert isinstance(cmds[1], PenCommand) and cmds[1].is_down is False
    assert rep.stroke_count == 0
    assert rep.travel_command_count == 0
    assert rep.draw_command_count == 0


def test_single_line_stroke():
    st = PlannedStroke(
        kind="line",
        points=((0.0, 0.0), (1.0, 0.0)),
        source=_src(),
        stroke_length_m=1.0,
        travel_from_previous_m=0.0,
        reversed=False,
        closed=False,
    )
    path = PlannedPath(strokes=(st,))
    cmds, rep = compile_planned_path_to_commands(
        path, options=PlannedPathCompileOptions(start_x_m=0.0, start_y_m=0.0)
    )
    assert rep.stroke_count == 1
    assert rep.draw_command_count == 1
    assert rep.travel_command_count == 0
    # SPEED, PEN UP, PEN DOWN, MOVE(1,0), PEN UP
    assert isinstance(cmds[0], SpeedCommand)
    assert isinstance(cmds[1], PenCommand) and not cmds[1].is_down
    assert isinstance(cmds[2], PenCommand) and cmds[2].is_down
    assert isinstance(cmds[3], MoveCommand) and cmds[3].x == 1.0 and cmds[3].y == 0.0
    assert isinstance(cmds[4], PenCommand) and not cmds[4].is_down


def test_two_strokes_travel_between():
    s0 = PlannedStroke(
        kind="line",
        points=((0.0, 0.0), (1.0, 0.0)),
        source=_src(),
        stroke_length_m=1.0,
        travel_from_previous_m=0.0,
        reversed=False,
        closed=False,
    )
    s1 = PlannedStroke(
        kind="line",
        points=((10.0, 0.0), (11.0, 0.0)),
        source=SourceRef(layer="0", entity_type="LINE", handle="h2"),
        stroke_length_m=1.0,
        travel_from_previous_m=9.0,
        reversed=False,
        closed=False,
    )
    path = PlannedPath(strokes=(s0, s1))
    cmds, rep = compile_planned_path_to_commands(
        path, options=PlannedPathCompileOptions(start_x_m=0.0, start_y_m=0.0)
    )
    assert rep.travel_command_count == 1
    assert rep.draw_command_count == 2
    # İkinci stroke öncesi travel: MOVE (10,0)
    move_travel = [c for c in cmds if isinstance(c, MoveCommand)]
    assert len(move_travel) == 3
    assert move_travel[1].x == 10.0 and move_travel[1].y == 0.0


def test_polyline_stroke():
    st = PlannedStroke(
        kind="polyline",
        points=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
        source=_src(),
        stroke_length_m=2.0,
        travel_from_previous_m=0.0,
        reversed=False,
        closed=False,
    )
    path = PlannedPath(strokes=(st,))
    cmds, rep = compile_planned_path_to_commands(
        path, options=PlannedPathCompileOptions(start_x_m=0.0, start_y_m=0.0)
    )
    assert rep.draw_command_count == 2
    moves = [c for c in cmds if isinstance(c, MoveCommand)]
    assert len(moves) == 2
    assert moves[0].x == 1.0 and moves[0].y == 0.0
    assert moves[1].x == 1.0 and moves[1].y == 1.0


def test_reversed_stroke_point_order():
    """Ters sıra noktalar korunur: önce (1,0) sonra (0,0) çizilir."""
    st = PlannedStroke(
        kind="line",
        points=((1.0, 0.0), (0.0, 0.0)),
        source=_src(),
        stroke_length_m=1.0,
        travel_from_previous_m=1.0,
        reversed=True,
        closed=False,
    )
    path = PlannedPath(strokes=(st,))
    cmds, rep = compile_planned_path_to_commands(
        path, options=PlannedPathCompileOptions(start_x_m=0.0, start_y_m=0.0)
    )
    assert rep.travel_command_count == 1
    moves = [c for c in cmds if isinstance(c, MoveCommand)]
    assert moves[0].x == 1.0 and moves[0].y == 0.0
    assert moves[1].x == 0.0 and moves[1].y == 0.0


def test_invalid_single_point_raises():
    st = PlannedStroke(
        kind="line",
        points=((0.0, 0.0),),
        source=_src(),
        stroke_length_m=0.0,
        travel_from_previous_m=0.0,
        reversed=False,
        closed=False,
    )
    path = PlannedPath(strokes=(st,))
    with pytest.raises(ValueError, match="geçersiz"):
        compile_planned_path_to_commands(path)
