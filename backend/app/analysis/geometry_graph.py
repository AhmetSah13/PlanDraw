# geometry_graph.py — Segment tabanlı geometri grafı: düğüm/birim metrikleri, oda konturları, duvar adayları
"""
Plan segmentlerinden node-edge graf oluşturur; bağlantı bileşenleri, döngüler,
açı dağılımı ve duvar/oda adayları üretir. Epsilon/snap deterministiktir.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any

# Varsayılan snap toleransı (plan_normalizer merge_endpoints_tol ile uyumlu)
DEFAULT_SNAP_TOL = 1e-6
# Oda adayı: en az bu kadar kenar
MIN_ROOM_EDGES = 4
# Oda adayı: en az bu çevre (metre)
MIN_ROOM_PERIMETER_M = 0.1
# Eksene hizalı sayılacak açı toleransı (derece)
AXIS_ANGLE_TOL_DEG = 5.0
# Duvar kümesi: en az bu uzunluk toplamı (m)
MIN_WALL_CLUSTER_LENGTH_M = 0.5


def _snap(p: tuple[float, float], tol: float) -> tuple[float, float]:
    """Noktayı grid'e yapıştırır (deterministik)."""
    x, y = p
    return (round(x / tol) * tol, round(y / tol) * tol)


def _dist(p: tuple[float, float], q: tuple[float, float]) -> float:
    return math.hypot(q[0] - p[0], q[1] - p[1])


def _edge_key(a: tuple[float, float], b: tuple[float, float]) -> tuple[tuple[float, float], tuple[float, float]]:
    """Kenar için sıralı anahtar (yön fark etmez)."""
    return (a, b) if a <= b else (b, a)


def _angle_deg(dx: float, dy: float) -> float:
    """Vektör açısı [0, 360) derece (x eksenine göre)."""
    if abs(dx) < 1e-15 and abs(dy) < 1e-15:
        return 0.0
    return math.degrees(math.atan2(dy, dx)) % 360.0


def _angle_bucket(angle_deg: float) -> str:
    """Açıyı 0/90/45/135/diğer kovasına atar."""
    a = angle_deg % 180.0
    if a <= AXIS_ANGLE_TOL_DEG or a >= 180.0 - AXIS_ANGLE_TOL_DEG:
        return "0"
    if 90.0 - AXIS_ANGLE_TOL_DEG <= a <= 90.0 + AXIS_ANGLE_TOL_DEG:
        return "90"
    if 45.0 - AXIS_ANGLE_TOL_DEG <= a <= 45.0 + AXIS_ANGLE_TOL_DEG:
        return "45"
    if 135.0 - AXIS_ANGLE_TOL_DEG <= a <= 135.0 + AXIS_ANGLE_TOL_DEG:
        return "135"
    return "other"


def build_graph(
    segments: list[Any],
    tol: float = DEFAULT_SNAP_TOL,
) -> dict[str, Any]:
    """
    Segment listesinden node-edge graf üretir. Uç noktalar tol ile snap edilir.
    segments: SegmentIn benzeri (x1, y1, x2, y2) veya (x1,y1,x2,y2) tuple listesi.
    Döner: {"nodes": [(x,y), ...], "edges": [(n1, n2, length), ...], "node_to_id": {node: id}}
    """
    edges: list[tuple[tuple[float, float], tuple[float, float], float]] = []
    seen_edges: set[tuple[tuple[float, float], tuple[float, float]]] = set()

    for seg in segments:
        if hasattr(seg, "x1"):
            p1 = _snap((float(seg.x1), float(seg.y1)), tol)
            p2 = _snap((float(seg.x2), float(seg.y2)), tol)
        else:
            p1 = _snap((float(seg[0]), float(seg[1])), tol)
            p2 = _snap((float(seg[2]), float(seg[3])), tol)
        L = _dist(p1, p2)
        if L <= tol:
            continue
        key = _edge_key(p1, p2)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        edges.append((p1, p2, L))

    nodes = sorted(set(n for e in edges for n in (e[0], e[1])))
    node_to_id = {n: i for i, n in enumerate(nodes)}
    edges_with_id = [(node_to_id[e[0]], node_to_id[e[1]], e[2]) for e in edges]

    return {
        "nodes": nodes,
        "edges": edges_with_id,
        "node_to_id": node_to_id,
        "edge_list_raw": edges,
    }


def _build_adjacency(graph: dict[str, Any]) -> tuple[list[set[int]], list[float]]:
    """nodes + edges -> adjacency (her node için komşu set), edge_lengths (edge index -> length)."""
    nodes = graph["nodes"]
    edges = graph["edges"]
    n = len(nodes)
    adj: list[set[int]] = [set() for _ in range(n)]
    edge_lengths: list[float] = []
    for i, j, L in edges:
        adj[i].add(j)
        adj[j].add(i)
        edge_lengths.append(L)
    return adj, edge_lengths


def compute_graph_metrics(graph: dict[str, Any]) -> dict[str, Any]:
    """
    Graf metrikleri: node/edge sayısı, bileşenler, derece histogramı,
    kavşak sayısı, sarkan kenar sayısı, döngü sayısı ve çevreler, açı dağılımı, kenar uzunluk istatistikleri.
    """
    nodes = graph["nodes"]
    edges = graph["edges"]
    adj, edge_lengths = _build_adjacency(graph)
    edge_list_raw = graph.get("edge_list_raw") or []

    node_count = len(nodes)
    edge_count = len(edges)

    # Bağlantı bileşenleri (BFS)
    visited = [False] * node_count
    components: list[list[int]] = []
    for start in range(node_count):
        if visited[start]:
            continue
        comp: list[int] = []
        q: deque[int] = deque([start])
        visited[start] = True
        while q:
            u = q.popleft()
            comp.append(u)
            for v in adj[u]:
                if not visited[v]:
                    visited[v] = True
                    q.append(v)
        components.append(comp)

    # Derece histogramı
    degree_histogram = {"0": 0, "1": 0, "2": 0, "3+": 0}
    for u in range(node_count):
        d = len(adj[u])
        if d == 0:
            degree_histogram["0"] += 1
        elif d == 1:
            degree_histogram["1"] += 1
        elif d == 2:
            degree_histogram["2"] += 1
        else:
            degree_histogram["3+"] += 1

    intersection_count = degree_histogram["3+"]

    # Sarkan kenar sayısı
    dangling_edges_count = 0
    for u, v, _ in edges:
        if len(adj[u]) == 1 or len(adj[v]) == 1:
            dangling_edges_count += 1

    # Döngü: cyclomatic number = E - V + C
    cyclomatic = edge_count - node_count + len(components)
    closed_cycles_count = max(0, cyclomatic)

    # Basit döngü çevreleri (sınırlı sayıda)
    cycle_perimeters: list[float] = []
    seen_cycles: set[frozenset[tuple[tuple[float, float], tuple[float, float]]]] = set()
    node_to_coord = {i: nodes[i] for i in range(node_count)}

    for start in range(node_count):
        if len(adj[start]) < 2:
            continue
        stack: list[tuple[int, list[int], set[tuple[int, int]]]] = [(start, [start], set())]
        while stack and len(cycle_perimeters) < 100:
            u, path, used_edges = stack.pop()
            for v in adj[u]:
                if len(path) >= 2 and v == start:
                    cycle_edges = frozenset(
                        (path[i], path[i + 1]) if path[i] < path[i + 1] else (path[i + 1], path[i])
                        for i in range(len(path) - 1)
                    )
                    cycle_edges = cycle_edges | frozenset([(u, v) if u < v else (v, u)])
                    if cycle_edges not in seen_cycles and len(cycle_edges) <= 200:
                        seen_cycles.add(cycle_edges)
                        perim = sum(
                            _dist(nodes[path[i]], nodes[path[i + 1]]) for i in range(len(path) - 1)
                        ) + _dist(nodes[u], nodes[v])
                        cycle_perimeters.append(perim)
                    continue
                if v in path or len(path) >= 50:
                    continue
                edge_id = (u, v) if u < v else (v, u)
                if edge_id in used_edges:
                    continue
                stack.append((v, path + [v], used_edges | {edge_id}))

    # Açı dağılımı
    angle_buckets: dict[str, int] = {"0": 0, "90": 0, "45": 0, "135": 0, "other": 0}
    for (a, b, _) in edge_list_raw:
        dx, dy = b[0] - a[0], b[1] - a[1]
        bucket = _angle_bucket(_angle_deg(dx, dy))
        angle_buckets[bucket] = angle_buckets.get(bucket, 0) + 1

    # Kenar uzunluk istatistikleri
    if not edge_lengths:
        edge_length_stats = {"min": 0.0, "median": 0.0, "p95": 0.0}
    else:
        sorted_len = sorted(edge_lengths)
        edge_length_stats = {
            "min": sorted_len[0],
            "median": sorted_len[len(sorted_len) // 2],
            "p95": sorted_len[min(int(len(sorted_len) * 0.95), len(sorted_len) - 1)],
        }

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "connected_components_count": len(components),
        "connected_component_sizes": [len(c) for c in components],
        "degree_histogram": degree_histogram,
        "intersection_count": intersection_count,
        "dangling_edges_count": dangling_edges_count,
        "closed_cycles_count": closed_cycles_count,
        "cycle_perimeters": cycle_perimeters[:50],
        "dominant_angles": angle_buckets,
        "edge_length_stats": edge_length_stats,
        # MVP: duvar-benzerlik skoru (0–1). Basit floor-plan: az dangling, az intersection, az bileşen, en az 1 cycle.
        "wall_likeliness_score": _wall_likeliness_score(
            edge_count=edge_count,
            components_count=len(components),
            intersection_count=intersection_count,
            dangling_edges_count=dangling_edges_count,
            closed_cycles_count=closed_cycles_count,
        ),
    }


def _wall_likeliness_score(
    *,
    edge_count: int,
    components_count: int,
    intersection_count: int,
    dangling_edges_count: int,
    closed_cycles_count: int,
) -> float:
    if edge_count <= 0:
        return 0.0
    dangling_ratio = dangling_edges_count / float(edge_count)
    inter_ratio = intersection_count / float(max(1, edge_count))
    comp_penalty = min(1.0, max(0.0, (components_count - 1) / 10.0))
    cycle_bonus = 0.15 if closed_cycles_count > 0 else 0.0
    score = 1.0 - (0.6 * dangling_ratio + 0.3 * inter_ratio + 0.1 * comp_penalty) + cycle_bonus
    return max(0.0, min(1.0, round(score, 4)))


def detect_room_outlines(
    graph: dict[str, Any],
    min_edges: int = MIN_ROOM_EDGES,
    min_perimeter_m: float = MIN_ROOM_PERIMETER_M,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """
    Döngü tabanlı oda konturu adayları. En az min_edges kenar, min_perimeter_m çevre.
    """
    nodes = graph["nodes"]
    adj, _ = _build_adjacency(graph)
    candidates: list[dict[str, Any]] = []
    seen_cycles: set[frozenset[tuple[int, int]]] = set()

    for start in range(len(nodes)):
        if len(adj[start]) < 2:
            continue
        stack: list[tuple[int, list[int], set[tuple[int, int]]]] = [(start, [start], set())]
        while stack and len(candidates) < 200:
            u, path, used = stack.pop()
            for v in adj[u]:
                if len(path) >= 2 and v == start:
                    edge_set = frozenset(
                        (path[i], path[i + 1]) if path[i] < path[i + 1] else (path[i + 1], path[i])
                        for i in range(len(path) - 1)
                    )
                    edge_set = edge_set | frozenset([(u, v) if u < v else (v, u)])
                    if edge_set in seen_cycles or len(path) < min_edges:
                        continue
                    seen_cycles.add(edge_set)
                    pts = [nodes[i] for i in path]
                    perim = sum(
                        _dist(nodes[path[i]], nodes[path[i + 1]]) for i in range(len(path) - 1)
                    ) + _dist(nodes[u], nodes[v])
                    if perim < min_perimeter_m:
                        continue
                    xs = [p[0] for p in pts]
                    ys = [p[1] for p in pts]
                    candidates.append({
                        "perimeter": round(perim, 6),
                        "bbox": [min(xs), min(ys), max(xs), max(ys)],
                        "vertex_count": len(path),
                    })
                    continue
                if v in path or len(path) >= 100:
                    continue
                e = (u, v) if u < v else (v, u)
                if e in used:
                    continue
                stack.append((v, path + [v], used | {e}))

    candidates.sort(key=lambda x: (-x["perimeter"], -x["vertex_count"]))
    return candidates[:top_k]


def detect_wall_candidates(
    graph: dict[str, Any],
    min_length_m: float = MIN_WALL_CLUSTER_LENGTH_M,
    top_k: int = 20,
) -> list[dict[str, Any]]:
    """
    Eksene hizalı uzun segment kümelerini duvar adayı olarak kümele.
    """
    nodes = graph["nodes"]
    edges = graph["edges"]
    edge_list_raw = graph.get("edge_list_raw") or []
    adj, _ = _build_adjacency(graph)

    edge_axis_aligned = []
    for (a, b, L) in edge_list_raw:
        dx, dy = b[0] - a[0], b[1] - a[1]
        ang = _angle_deg(dx, dy) % 180.0
        aligned = (
            ang <= AXIS_ANGLE_TOL_DEG or ang >= 180.0 - AXIS_ANGLE_TOL_DEG
            or (90.0 - AXIS_ANGLE_TOL_DEG <= ang <= 90.0 + AXIS_ANGLE_TOL_DEG)
        )
        edge_axis_aligned.append(aligned)

    n = len(nodes)
    uf_parent = list(range(n))

    def find(x: int) -> int:
        if uf_parent[x] != x:
            uf_parent[x] = find(uf_parent[x])
        return uf_parent[x]

    def union(x: int, y: int) -> None:
        uf_parent[find(x)] = find(y)

    for idx, (u, v, _) in enumerate(edges):
        if edge_axis_aligned[idx]:
            union(u, v)

    comp_length: dict[int, float] = {}
    comp_edges: dict[int, list[int]] = {}
    comp_nodes: dict[int, set[int]] = {}
    for idx, (u, v, L) in enumerate(edges):
        if not edge_axis_aligned[idx]:
            continue
        c = find(u)
        comp_length[c] = comp_length.get(c, 0) + L
        comp_edges.setdefault(c, []).append(idx)
        comp_nodes.setdefault(c, set()).add(u)
        comp_nodes[c].add(v)

    clusters: list[dict[str, Any]] = []
    for c, length_sum in comp_length.items():
        if length_sum < min_length_m:
            continue
        edge_list = comp_edges.get(c, [])
        node_set = comp_nodes.get(c, set())
        aligned_len = sum(
            edge_list_raw[i][2] for i in edge_list if i < len(edge_axis_aligned) and edge_axis_aligned[i]
        )
        axis_alignment_score = aligned_len / length_sum if length_sum > 0 else 0.0
        degs = [len(adj[u]) for u in node_set]
        avg_deg = sum(degs) / len(degs) if degs else 0
        connectivity_score = min(1.0, avg_deg / 2.0)
        xs = [nodes[u][0] for u in node_set]
        ys = [nodes[u][1] for u in node_set]
        clusters.append({
            "length_sum": round(length_sum, 6),
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
            "segment_count": len(edge_list),
            "axis_alignment_score": round(axis_alignment_score, 4),
            "connectivity_score": round(connectivity_score, 4),
        })

    clusters.sort(key=lambda x: (-x["length_sum"], -x["segment_count"]))
    return clusters[:top_k]


def enrich_plan_with_graph_metrics(
    plan: Any,
    tol: float = DEFAULT_SNAP_TOL,
    top_k_rooms: int = 20,
    top_k_walls: int = 20,
) -> Any:
    """
    NormalizedPlan alır; metadata'ya graph_metrics, room_candidates, wall_candidates ekleyerek
    yeni plan döndürür. Pydantic model_copy kullanır.
    """
    segments = plan.segments if hasattr(plan, "segments") else []
    if not segments:
        meta = dict(plan.metadata or {})
        meta["graph_metrics"] = {}
        meta["room_candidates"] = []
        meta["wall_candidates"] = []
        return plan.model_copy(update={"metadata": meta})

    graph = build_graph(segments, tol=tol)
    metrics = compute_graph_metrics(graph)
    rooms = detect_room_outlines(graph, top_k=top_k_rooms)
    walls = detect_wall_candidates(graph, top_k=top_k_walls)

    meta = dict(plan.metadata or {})
    meta["graph_metrics"] = metrics
    meta["room_candidates"] = rooms
    meta["wall_candidates"] = walls
    return plan.model_copy(update={"metadata": meta})
