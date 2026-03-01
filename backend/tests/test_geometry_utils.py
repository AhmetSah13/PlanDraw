from __future__ import annotations

import unittest
import sys
from pathlib import Path

# backend/tests
_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.utils.geometry_utils import (  # type: ignore
  segment_intersection,
  distance_point_to_segment,
)


class TestGeometryUtils(unittest.TestCase):
  def test_proper_intersection(self):
    # (0,0)-(10,0) ile (5,-5)-(5,5) -> proper kesişim (5,0)
    a = (0.0, 0.0)
    b = (10.0, 0.0)
    c = (5.0, -5.0)
    d = (5.0, 5.0)
    ok, pt, kind = segment_intersection(a, b, c, d)
    self.assertTrue(ok)
    self.assertEqual(kind, "proper")
    self.assertIsNotNone(pt)
    x, y = pt
    self.assertAlmostEqual(x, 5.0, places=6)
    self.assertAlmostEqual(y, 0.0, places=6)

  def test_touch_endpoint(self):
    # (0,0)-(10,0) ile (10,0)-(10,5) -> uç noktada temas (10,0)
    a = (0.0, 0.0)
    b = (10.0, 0.0)
    c = (10.0, 0.0)
    d = (10.0, 5.0)
    ok, pt, kind = segment_intersection(a, b, c, d)
    self.assertTrue(ok)
    self.assertEqual(kind, "touch")
    self.assertIsNotNone(pt)
    x, y = pt
    self.assertAlmostEqual(x, 10.0, places=6)
    self.assertAlmostEqual(y, 0.0, places=6)

  def test_overlap(self):
    # (0,0)-(10,0) ile (5,0)-(15,0) -> kollinear overlap
    a = (0.0, 0.0)
    b = (10.0, 0.0)
    c = (5.0, 0.0)
    d = (15.0, 0.0)
    ok, pt, kind = segment_intersection(a, b, c, d)
    self.assertTrue(ok)
    self.assertEqual(kind, "overlap")
    self.assertIsNone(pt)

  def test_no_intersection(self):
    # Paralel, ayrık
    a = (0.0, 0.0)
    b = (10.0, 0.0)
    c = (0.0, 5.0)
    d = (10.0, 5.0)
    ok, pt, kind = segment_intersection(a, b, c, d)
    self.assertFalse(ok)
    self.assertIsNone(pt)
    self.assertEqual(kind, "")

  def test_distance_point_to_segment(self):
    a = (0.0, 0.0)
    b = (10.0, 0.0)
    # Ortaya dik mesafe 5
    dist = distance_point_to_segment(5.0, 5.0, a[0], a[1], b[0], b[1])
    self.assertAlmostEqual(dist, 5.0, places=6)


if __name__ == "__main__":
  unittest.main()

