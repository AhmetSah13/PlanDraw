from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Dict, List, Tuple

from app.normalization.normalized_plan import SegmentIn, NormalizedPlan


def _seg_len(seg: SegmentIn) -> float:
    return math.hypot(seg.x2 - seg.x1, seg.y2 - seg.y1)


def _build_graph(
    segments: List[SegmentIn],
    snap_tol: float,
) -> Tuple[
    Dict[int, List[int]],
    List[Tuple[float, float]],
    List[Dict[str, object]],
]:
    """
    NormalizedPlan.segments listesinden basit bir kenar grafı kurar.
    Döner:
      - adj: node_id -> edge_id listesi
      - node_positions: node_id -> (x, y)
      - edges: edge kayıtları listesi {u, v, length, p1, p2}
    """
    coord_to_node: Dict[Tuple[int, int], int] = {}
    node_positions: List[Tuple[float, float]] = []

    def _snap_key(x: float, y: float) -> Tuple[int, int]:
        return (int(round(x / snap_tol)), int(round(y / snap_tol)))

    def _get_node(x: float, y: float) -> int:
        key = _snap_key(x, y)
        node_id = coord_to_node.get(key)
        if node_id is None:
            node_id = len(node_positions)
            coord_to_node[key] = node_id
            node_positions.append((x, y))
        return node_id

    edges: List[Dict[str, object]] = []
    adj: Dict[int, List[int]] = defaultdict(list)

    for seg in segments:
        u = _get_node(seg.x1, seg.y1)
        v = _get_node(seg.x2, seg.y2)
        if u == v:
            continue
        length = _seg_len(seg)
        if length <= 0:
            continue
        eid = len(edges)
        edges.append(
            {
                "u": u,
                "v": v,
                "length": length,
                "p1": (seg.x1, seg.y1),
                "p2": (seg.x2, seg.y2),
            }
        )
        adj[u].append(eid)
        adj[v].append(eid)

    return adj, node_positions, edges


def compute_component_centroids(
    segments: List[SegmentIn],
    snap_tol: float,
) -> List[Tuple[float, float]]:
    """
    Segment listesinden connected component centroid'lerini hesaplar.
    Döner: [(cx, cy), ...]
    """
    adj, node_positions, edges = _build_graph(segments, snap_tol)
    if not edges:
        return []

    # Node tabanlı adjacency (komşu node listesi)
    node_adj: Dict[int, List[int]] = defaultdict(list)
    for e in edges:
        u = int(e["u"])
        v = int(e["v"])
        node_adj[u].append(v)
        node_adj[v].append(u)

    visited = set()
    centroids: List[Tuple[float, float]] = []
    for node in node_adj.keys():
        if node in visited:
            continue
        que = deque([node])
        visited.add(node)
        comp_nodes: List[int] = []
        while que:
            u = que.popleft()
            comp_nodes.append(u)
            for v in node_adj.get(u, []):
                if v not in visited:
                    visited.add(v)
                    que.append(v)
        if not comp_nodes:
            continue
        sx = sy = 0.0
        for nid in comp_nodes:
            x, y = node_positions[nid]
            sx += x
            sy += y
        n = float(len(comp_nodes))
        centroids.append((sx / n, sy / n))
    return centroids


def build_components_with_candidates(
    segments: List[SegmentIn],
    snap_tol: float,
    k: int = 6,
) -> Dict[str, object]:
    """
    Connected component yapısını ve her component için uç nokta (entry/exit) adaylarını hesaplar.
    Döner:
      {
        "centroids": [(cx, cy), ...],
        "candidates": [ [(x, y), ...], ...],  # her component için en fazla k aday
      }
    """
    adj, node_positions, edges = _build_graph(segments, snap_tol)
    if not edges:
        return {"centroids": [], "candidates": []}

    # Node bazlı adjacency
    node_adj: Dict[int, List[int]] = defaultdict(list)
    for e in edges:
        u = int(e["u"])
        v = int(e["v"])
        node_adj[u].append(v)
        node_adj[v].append(u)

    # Connected components (node seviyesinde)
    visited = set()
    components: List[List[int]] = []
    for node in node_adj.keys():
        if node in visited:
            continue
        que = deque([node])
        visited.add(node)
        comp_nodes: List[int] = []
        while que:
            u = que.popleft()
            comp_nodes.append(u)
            for v in node_adj.get(u, []):
                if v not in visited:
                    visited.add(v)
                    que.append(v)
        if comp_nodes:
            components.append(comp_nodes)

    centroids: List[Tuple[float, float]] = []
    candidates: List[List[Tuple[float, float]]] = []

    for comp_nodes in components:
        # Component centroid
        sx = sy = 0.0
        for nid in comp_nodes:
            x, y = node_positions[nid]
            sx += x
            sy += y
        n = float(len(comp_nodes))
        cx, cy = (sx / n, sy / n) if n > 0 else (0.0, 0.0)
        centroids.append((cx, cy))

        # Derece hesabı
        degrees = {nid: len(node_adj.get(nid, [])) for nid in comp_nodes}
        deg1_nodes = [nid for nid in comp_nodes if degrees.get(nid, 0) == 1]

        cand_nodes: List[int]
        if deg1_nodes:
            # Eğer fazla varsa, centroid'e en uzak olanlardan ilk k tanesini seç
            deg1_nodes_sorted = sorted(
                deg1_nodes,
                key=lambda nid: (node_positions[nid][0] - cx) ** 2 + (node_positions[nid][1] - cy) ** 2,
                reverse=True,
            )
            cand_nodes = deg1_nodes_sorted[:k]
        else:
            # Degree==1 yoksa: centroid'e en uzak node'lardan ilk k tanesi
            comp_sorted = sorted(
                comp_nodes,
                key=lambda nid: (node_positions[nid][0] - cx) ** 2 + (node_positions[nid][1] - cy) ** 2,
                reverse=True,
            )
            cand_nodes = comp_sorted[:k]

        cand_points: List[Tuple[float, float]] = []
        for nid in cand_nodes:
            cand_points.append(node_positions[nid])
        candidates.append(cand_points)

    return {"centroids": centroids, "candidates": candidates}



def _connected_components(adj: Dict[int, List[int]]) -> List[List[int]]:
    """Node bazında connected component listesi."""
    visited = set()
    comps: List[List[int]] = []
    for node in adj.keys():
        if node in visited:
            continue
        que = deque([node])
        visited.add(node)
        comp_nodes: List[int] = []
        while que:
            u = que.popleft()
            comp_nodes.append(u)
            for eid in adj[u]:
                # Kenar üzerinden komşu node'lara bakmak için edge'ler gerekecek;
                # burada sadece node listesi için u'yu işaretliyoruz, gerçek traversal'da kenarlar kullanılıyor.
                pass
        comps.append(comp_nodes)
    return comps


def _dfs_traversal_for_component(
    start_node: int,
    adj: Dict[int, List[int]],
    node_positions: List[Tuple[float, float]],
    edges: List[Dict[str, object]],
    used_edge: List[bool],
) -> Tuple[List[Tuple[float, float]], float]:
    """
    Tek bir connected component üzerinde,
    tüm kenarları kapsayan sürekli bir stroke üretir.
    Kenarlar ileri + geri geçilebildiği için tekrar geometri olabilir.
    Döner: (nokta listesi, stroke_drawn_length)
    """
    path: List[Tuple[float, float]] = []
    drawn_len = 0.0

    def _add_segment(p_from: Tuple[float, float], p_to: Tuple[float, float]) -> None:
        nonlocal drawn_len
        if not path:
            path.append(p_from)
        else:
            if path[-1] != p_from:
                path.append(p_from)
        path.append(p_to)
        drawn_len += math.hypot(p_to[0] - p_from[0], p_to[1] - p_from[1])

    def _dfs(u: int) -> None:
        for eid in adj.get(u, []):
            if used_edge[eid]:
                continue
            used_edge[eid] = True
            e = edges[eid]
            v = e["v"] if e["u"] == u else e["u"]
            p1 = e["p1"]
            p2 = e["p2"]
            if u == e["u"]:
                _add_segment(p1, p2)
            else:
                _add_segment(p2, p1)
            _dfs(v)  # ileri giderken stroke devam ediyor
            # Geri dönüşte de aynı kenarı tekrar çizerek sürekli stroke sağlıyoruz
            if u == e["u"]:
                _add_segment(p2, p1)
            else:
                _add_segment(p1, p2)

    _dfs(start_node)
    return path, drawn_len


def generate_graph_traversal_path(
    plan: NormalizedPlan,
    snap_tol: float = 1e-4,
) -> Tuple[List[List[Tuple[float, float]]], Dict[str, object]]:
    """
    Duvar segmentlerinden graph tabanlı traversal path üretir.
    Çıktı:
      - path_segments: [ [ (x,y), ... ], ... ] (her liste bir component stroke'u)
      - metrics: {"components_count", "duplicated_edge_length_m", "traversal_mode_used"}
    """
    segments = list(plan.segments or [])
    if not segments:
        return [], {
            "components_count": 0,
            "duplicated_edge_length_m": 0.0,
            "traversal_mode_used": "none",
        }

    adj, node_positions, edges = _build_graph(segments, snap_tol)
    if not edges:
        return [], {
            "components_count": 0,
            "duplicated_edge_length_m": 0.0,
            "traversal_mode_used": "none",
        }

    used_edge = [False] * len(edges)
    path_segments: List[List[Tuple[float, float]]] = []
    total_drawn_len = 0.0

    # Çok basit: her node seti için DFS-backtrack tabanlı sürekli stroke
    visited_nodes = set()
    for node in adj.keys():
        if node in visited_nodes:
            continue
        # Bu connected component içinde en az bir kullanılmamış edge var mı?
        has_edge = any(not used_edge[eid] for eid in adj[node])
        if not has_edge:
            visited_nodes.add(node)
            continue
        stroke, drawn_len = _dfs_traversal_for_component(
            node,
            adj,
            node_positions,
            edges,
            used_edge,
        )
        if stroke:
            path_segments.append(stroke)
            total_drawn_len += drawn_len
        visited_nodes.add(node)

    unique_edge_total = sum(float(e["length"]) for e in edges)
    duplicated = max(0.0, total_drawn_len - unique_edge_total)

    metrics = {
        "components_count": len(path_segments),
        "duplicated_edge_length_m": round(duplicated, 6),
        "traversal_mode_used": "dfs_backtrack",
    }
    return path_segments, metrics

