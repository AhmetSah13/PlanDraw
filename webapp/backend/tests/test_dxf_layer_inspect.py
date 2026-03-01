from __future__ import annotations

import unittest
import sys
from pathlib import Path
import math

_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from dxf_importer import inspect_dxf_layers


def _dxf_two_layers() -> str:
    """WALLS ve DIM katmanlarında iki LINE."""
    return """
  0
SECTION
  2
ENTITIES
  0
LINE
  8
WALLS
 10
0
 20
0
 11
100
 21
0
  0
LINE
  8
DIM
 10
0
 20
0
 11
1
 21
0
  0
ENDSEC
  0
EOF
"""


def _dxf_polyline_wall_layer() -> str:
    """POLYLINE katmanı POLYLINE'dan alınmalı, VERTEX'ten değil."""
    return """
  0
SECTION
  2
ENTITIES
  0
POLYLINE
  8
WALL
 70
1
 66
1
  0
VERTEX
 10
0
 20
0
  0
VERTEX
 10
100
 20
0
  0
SEQEND
  0
ENDSEC
  0
EOF
"""


def _dxf_single_line_for_transform() -> str:
    """Tek LINE; scale/origin testleri için."""
    return """
  0
SECTION
  2
ENTITIES
  0
LINE
  8
WALLS
 10
0
 20
0
 11
100
 21
0
  0
ENDSEC
  0
EOF
"""


class TestDxfLayerInspect(unittest.TestCase):
    def test_two_layers_wall_suggested_first(self):
        text = _dxf_two_layers()
        info = inspect_dxf_layers(text)
        layers = info["layers"]
        self.assertIn("WALLS", layers)
        self.assertIn("DIM", layers)
        walls_len = layers["WALLS"]["total_length"]
        dim_len = layers["DIM"]["total_length"]
        self.assertGreater(walls_len, dim_len)
        suggested = info["suggested_layers"]
        self.assertGreaterEqual(len(suggested), 1)
        self.assertEqual(suggested[0], "WALLS")

    def test_polyline_layer_taken_from_polyline(self):
        text = _dxf_polyline_wall_layer()
        info = inspect_dxf_layers(text)
        layers = info["layers"]
        self.assertIn("WALL", layers)
        # Kapalı polyline: 2 vertex, closed=1 => 2 segment
        self.assertEqual(layers["WALL"]["segments"], 2)
        # Diğer katman olmamalı
        self.assertEqual(len(layers.keys()), 1)

    def test_scale_and_origin_applied(self):
        text = _dxf_single_line_for_transform()
        info = inspect_dxf_layers(text, scale=2.0, origin=(10.0, 20.0))
        layers = info["layers"]
        walls = layers["WALLS"]
        # Uzunluk 100 * 2 = 200 olmalı
        self.assertAlmostEqual(walls["total_length"], 200.0)
        # Bbox ölçek + origin'i yansıtmalı
        bbox = walls["bbox"]
        self.assertIsNotNone(bbox)
        minx, miny, maxx, maxy = bbox
        self.assertAlmostEqual(minx, 10.0)
        self.assertAlmostEqual(miny, 20.0)
        self.assertAlmostEqual(maxx, 210.0)
        self.assertAlmostEqual(maxy, 20.0)
        # Global bbox da aynı olmalı
        gbbox = info["bbox"]
        self.assertEqual(gbbox, bbox)


if __name__ == "__main__":
    unittest.main()

