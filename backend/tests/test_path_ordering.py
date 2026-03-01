# test_path_ordering.py — En-yakın-komşu sıralama ve seyahat mesafesi
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.core.plan_module import Plan, Wall
from app.pathing.path_generator import (
    PathGenerator,
    order_segments_nearest_neighbor,
    compute_travel_distance,
    _bbox_center,
)


def _wall_key(w: Wall) -> tuple:
    """Sıra karşılaştırması için deterministik anahtar."""
    return (w.x1, w.y1, w.x2, w.y2)


class TestPathOrderingReducesTravel(unittest.TestCase):
    """Sıralama seyahat mesafesini belirgin şekilde azaltmalı."""

    def test_two_clusters_ordering_reduces_travel(self):
        # İki küme: (0,0) civarı 4 segment, (100,100) civarı 4 segment.
        # Kötü sıra: kümeler arası geçişler çok (c1_0, c2_0, c1_1, c2_1, ...)
        cluster1 = [
            Wall(0.0, 0.0, 1.0, 0.0),
            Wall(1.0, 0.0, 1.0, 1.0),
            Wall(1.0, 1.0, 0.0, 1.0),
            Wall(0.0, 1.0, 0.0, 0.0),
        ]
        cluster2 = [
            Wall(100.0, 100.0, 101.0, 100.0),
            Wall(101.0, 100.0, 101.0, 101.0),
            Wall(101.0, 101.0, 100.0, 101.0),
            Wall(100.0, 101.0, 100.0, 100.0),
        ]
        naive_order = [
            cluster1[0], cluster2[0], cluster1[1], cluster2[1],
            cluster1[2], cluster2[2], cluster1[3], cluster2[3],
        ]
        start = _bbox_center(naive_order)
        self.assertIsNotNone(start)

        travel_naive = compute_travel_distance(naive_order, start)
        ordered = order_segments_nearest_neighbor(naive_order, start_point=start)
        travel_ordered = compute_travel_distance(ordered, start)

        self.assertLess(travel_ordered, travel_naive, "Sıralı seyahat naiften küçük olmalı")
        self.assertLessEqual(
            travel_ordered,
            travel_naive * 0.6,
            "Sıralama seyahatı en az %40 azaltmalı",
        )

    def test_ordering_deterministic(self):
        walls = [
            Wall(0.0, 0.0, 1.0, 0.0),
            Wall(1.0, 0.0, 1.0, 1.0),
            Wall(10.0, 10.0, 11.0, 10.0),
            Wall(2.0, 2.0, 3.0, 2.0),
        ]
        start = (5.0, 5.0)
        a = order_segments_nearest_neighbor(walls, start_point=start)
        b = order_segments_nearest_neighbor(walls, start_point=start)
        self.assertEqual([_wall_key(w) for w in a], [_wall_key(w) for w in b])


class TestPathGeneratorOrderWallsIntegration(unittest.TestCase):
    """PathGenerator order_walls entegrasyonu; mevcut davranış bozulmamalı."""

    def test_order_walls_default_on(self):
        plan = Plan([Wall(0, 0, 1, 0), Wall(10, 10, 11, 10)])
        pg = PathGenerator(plan, step_size=0.5)
        path = pg.generate_path()
        self.assertGreater(len(path), 0)
        # Sıralama açıkken ikinci duvar (10,10) tarafına daha yakın bir noktadan
        # devam edilmiş olmalı; path sırası değişmiş olabilir ama uzunluk mantıklı
        self.assertIsInstance(path[0], tuple)
        self.assertEqual(len(path[0]), 2)

    def test_order_walls_false_preserves_original_order(self):
        w1 = Wall(0.0, 0.0, 1.0, 0.0)
        w2 = Wall(1.0, 0.0, 2.0, 0.0)
        plan = Plan([w1, w2])
        pg = PathGenerator(plan, step_size=0.5, order_walls=False)
        path = pg.generate_path()
        self.assertGreaterEqual(len(path), 2)
        self.assertAlmostEqual(path[0][0], 0.0)
        self.assertAlmostEqual(path[0][1], 0.0)


if __name__ == "__main__":
    unittest.main()
