from __future__ import annotations

import math

from app.alignment.aligner import align_printable_layout_rigid_2d
from app.alignment.alignment_model import ControlPoint
from app.layout_ir.ir_types import LineObject, PrintableLayout, SourceRef


def _line(x1: float, y1: float, x2: float, y2: float) -> LineObject:
    return LineObject(
        x1,
        y1,
        x2,
        y2,
        SourceRef(layer="0", entity_type="LINE", handle=None),
    )


def test_rigid_identity_two_points():
    layout = PrintableLayout(objects=(_line(0.0, 0.0, 1.0, 0.0),))
    cps = [
        ControlPoint(0.0, 0.0, 0.0, 0.0),
        ControlPoint(1.0, 0.0, 1.0, 0.0),
    ]
    aligned, rep = align_printable_layout_rigid_2d(layout, cps, tolerance_m=0.01)
    assert not rep.blocked
    assert rep.residual_max_m < 1e-9
    o = aligned.objects[0]
    assert isinstance(o, LineObject)
    assert abs(o.x1 - 0.0) < 1e-9 and abs(o.y1 - 0.0) < 1e-9


def test_rigid_translation_rotation():
    # 90 derece CAD -> site: (x,y) -> (-y, x)  [site = R * cad], R = [[0,-1],[1,0]]
    layout = PrintableLayout(objects=(_line(0.0, 0.0, 1.0, 0.0),))
    cps = [
        ControlPoint(0.0, 0.0, 0.0, 0.0),
        ControlPoint(1.0, 0.0, 0.0, 1.0),
    ]
    aligned, rep = align_printable_layout_rigid_2d(layout, cps, tolerance_m=0.01)
    assert not rep.blocked
    o = aligned.objects[0]
    assert isinstance(o, LineObject)
    assert abs(o.x1 - 0.0) < 1e-6 and abs(o.y1 - 0.0) < 1e-6
    assert abs(o.x2 - 0.0) < 1e-6 and abs(o.y2 - 1.0) < 1e-6
    assert abs(rep.transform.theta_rad - math.pi / 2) < 1e-6


def test_blocked_too_few_points():
    layout = PrintableLayout(objects=(_line(0.0, 0.0, 1.0, 0.0),))
    cps = [ControlPoint(0.0, 0.0, 0.0, 0.0)]
    aligned, rep = align_printable_layout_rigid_2d(layout, cps, tolerance_m=0.01)
    assert rep.blocked
    assert aligned.objects[0].x1 == 0.0
