from __future__ import annotations

from app.alignment.alignment_model import AlignedLayout
from app.layout_ir.ir_types import LineObject, PolylineObject, PrintableLayout, SourceRef
from app.path_planning.planner import PathPlanningOptions, plan_path_from_aligned_layout


def _src() -> SourceRef:
    return SourceRef(layer="0", entity_type="LINE", handle=None)


def test_empty_aligned_layout():
    al = AlignedLayout(objects=())
    path, rep = plan_path_from_aligned_layout(al, options=PathPlanningOptions(min_segment_length_m=0.01))
    assert len(path.strokes) == 0
    assert rep.metrics.stroke_count == 0
    assert rep.metrics.pen_lifts == 0


def test_two_lines_greedy_order():
    """(0,0)-(1,0) sonra (10,0)-(11,0): başlangıç (0,0) yakınından başlamalı."""
    objs = (
        LineObject(10.0, 0.0, 11.0, 0.0, _src()),
        LineObject(0.0, 0.0, 1.0, 0.0, _src()),
    )
    al = AlignedLayout(objects=objs)
    path, rep = plan_path_from_aligned_layout(
        al,
        options=PathPlanningOptions(min_segment_length_m=0.001, start_x_m=0.0, start_y_m=0.0),
    )
    assert rep.metrics.stroke_count == 2
    assert path.strokes[0].points[0][0] == 0.0


def test_short_line_skipped():
    al = AlignedLayout(objects=(LineObject(0.0, 0.0, 0.0001, 0.0, _src()),))
    path, rep = plan_path_from_aligned_layout(
        al, options=PathPlanningOptions(min_segment_length_m=0.005)
    )
    assert rep.metrics.stroke_count == 0
    assert rep.metrics.skipped_short_segment_count >= 1


def test_open_polyline_split():
    pts = ((0.0, 0.0), (0.001, 0.0), (2.0, 0.0))
    al = AlignedLayout(
        objects=(PolylineObject(pts, closed=False, source=_src(), tag="geometry"),)
    )
    path, rep = plan_path_from_aligned_layout(
        al, options=PathPlanningOptions(min_segment_length_m=0.005)
    )
    assert rep.metrics.stroke_count >= 1
