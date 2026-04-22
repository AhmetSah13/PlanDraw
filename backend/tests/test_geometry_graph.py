# test_geometry_graph.py — Geometry graph engine unit testleri (deterministik tol)
from __future__ import annotations

import pytest

pytest.importorskip("pydantic")
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.normalization.normalized_plan import SegmentIn
from app.analysis.geometry_graph import (
    build_graph,
    compute_graph_metrics,
    detect_room_outlines,
    detect_wall_candidates,
    DEFAULT_SNAP_TOL,
)


TOL = DEFAULT_SNAP_TOL


def _seg(x1: float, y1: float, x2: float, y2: float) -> SegmentIn:
    return SegmentIn(x1=x1, y1=y1, x2=x2, y2=y2)


def test_rectangle_one_cycle_one_component_no_dangling():
    """Basit dikdörtgen (4 segment) -> 1 cycle, 1 component, dangling=0."""
    # 10x5 dikdörtgen
    segments = [
        _seg(0, 0, 10, 0),
        _seg(10, 0, 10, 5),
        _seg(10, 5, 0, 5),
        _seg(0, 5, 0, 0),
    ]
    graph = build_graph(segments, tol=TOL)
    metrics = compute_graph_metrics(graph)
    assert metrics["node_count"] == 4
    assert metrics["edge_count"] == 4
    assert metrics["connected_components_count"] == 1
    assert metrics["closed_cycles_count"] == 1  # E - V + C = 4 - 4 + 1
    assert metrics["dangling_edges_count"] == 0
    assert metrics["intersection_count"] == 0
    # Oda adayı: 4 kenarlı döngü
    rooms = detect_room_outlines(graph, min_edges=4, min_perimeter_m=0.1)
    assert len(rooms) >= 1
    assert rooms[0]["vertex_count"] == 4
    assert rooms[0]["perimeter"] > 0


def test_t_junction_one_intersection_zero_cycles():
    """T kavşağı: 3 segment bir noktada birleşir -> intersection_count=1, cycle=0."""
    # (5,0) ortak uç: yatay (0,0)-(5,0), (5,0)-(10,0), dikey (5,0)-(5,10)
    segments = [
        _seg(0, 0, 5, 0),
        _seg(5, 0, 10, 0),
        _seg(5, 0, 5, 10),
    ]
    graph = build_graph(segments, tol=TOL)
    metrics = compute_graph_metrics(graph)
    assert metrics["node_count"] == 4  # (0,0), (5,0), (10,0), (5,10)
    assert metrics["edge_count"] == 3
    assert metrics["connected_components_count"] == 1
    assert metrics["intersection_count"] == 1  # (5,0) degree=3
    assert metrics["closed_cycles_count"] == 0  # E - V + C = 3 - 4 + 1 = 0
    assert metrics["dangling_edges_count"] == 3  # (0,0), (10,0), (5,10) degree=1 -> 3 sarkan kenar


def test_two_separate_rooms_two_components_two_cycles():
    """İki ayrı dikdörtgen (oda) -> components=2, cycles=2."""
    # Oda 1: (0,0)-(2,0)-(2,2)-(0,2)
    # Oda 2: (5,5)-(7,5)-(7,7)-(5,7)
    segments = [
        _seg(0, 0, 2, 0),
        _seg(2, 0, 2, 2),
        _seg(2, 2, 0, 2),
        _seg(0, 2, 0, 0),
        _seg(5, 5, 7, 5),
        _seg(7, 5, 7, 7),
        _seg(7, 7, 5, 7),
        _seg(5, 7, 5, 5),
    ]
    graph = build_graph(segments, tol=TOL)
    metrics = compute_graph_metrics(graph)
    assert metrics["node_count"] == 8
    assert metrics["edge_count"] == 8
    assert metrics["connected_components_count"] == 2
    assert metrics["closed_cycles_count"] == 2  # E - V + C = 8 - 8 + 2
    assert metrics["dangling_edges_count"] == 0
    rooms = detect_room_outlines(graph, min_edges=4, min_perimeter_m=0.1)
    assert len(rooms) == 2


def test_deterministic_snap():
    """Aynı segmentler farklı sırada verilse bile graf aynı (deterministik)."""
    segments1 = [_seg(0, 0, 1, 0), _seg(1, 0, 1, 1), _seg(1, 1, 0, 1), _seg(0, 1, 0, 0)]
    segments2 = [_seg(0, 1, 0, 0), _seg(1, 1, 0, 1), _seg(1, 0, 1, 1), _seg(0, 0, 1, 0)]
    g1 = build_graph(segments1, tol=TOL)
    g2 = build_graph(segments2, tol=TOL)
    m1 = compute_graph_metrics(g1)
    m2 = compute_graph_metrics(g2)
    assert m1["node_count"] == m2["node_count"]
    assert m1["edge_count"] == m2["edge_count"]
    assert m1["connected_components_count"] == m2["connected_components_count"]
    assert m1["closed_cycles_count"] == m2["closed_cycles_count"]


def test_zero_length_segment_ignored():
    """Çok kısa (tol altı) segment kenar üretmez."""
    segments = [_seg(0, 0, TOL / 2, 0), _seg(1, 0, 1, 1)]
    graph = build_graph(segments, tol=TOL)
    metrics = compute_graph_metrics(graph)
    assert metrics["edge_count"] == 1
    assert metrics["node_count"] == 2


def test_wall_candidates_axis_aligned():
    """Eksene hizalı segmentler duvar adayı kümesi verir."""
    segments = [
        _seg(0, 0, 5, 0),
        _seg(5, 0, 5, 3),
        _seg(5, 3, 0, 3),
        _seg(0, 3, 0, 0),
    ]
    graph = build_graph(segments, tol=TOL)
    walls = detect_wall_candidates(graph, min_length_m=0.1, top_k=5)
    assert len(walls) >= 1
    assert walls[0]["segment_count"] >= 1
    assert walls[0]["axis_alignment_score"] >= 0.9
