# test_dxf_importer.py — ASCII DXF importer unittest
from __future__ import annotations

import pytest
pytest.importorskip("pydantic")
pytestmark = pytest.mark.integration

import unittest
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.importers.dxf_importer import parse_dxf_ascii, dxf_to_normalized_plan
from app.normalization.normalized_plan import NormalizedPlan


def _minimal_dxf_with_line() -> str:
    """Tek bir LINE içeren minimal ASCII DXF."""
    return """
  0
SECTION
  2
HEADER
  9
$INSUNITS
 70
4
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
  8
0
 10
0.0
 20
0.0
 11
100.0
 21
50.0
  0
ENDSEC
  0
EOF
"""


def _dxf_lwpolyline_four_vertices(closed: bool = False) -> str:
    """4 köşeli LWPOLYLINE (closed=0 veya 1)."""
    flag = "1" if closed else "0"
    return """
  0
SECTION
  2
ENTITIES
  0
LWPOLYLINE
  8
0
 90
4
 70
""" + flag + """
 10
0
 20
0
 10
100
 20
0
 10
100
 20
100
 10
0
 20
100
  0
ENDSEC
  0
EOF
"""


def _dxf_polyline_four_vertices(closed: bool = False) -> str:
    """POLYLINE + 4 VERTEX + SEQEND."""
    flag = "1" if closed else "0"
    return """
  0
SECTION
  2
ENTITIES
  0
POLYLINE
  8
0
 70
""" + flag + """
 66
1
  0
VERTEX
 10
10
 20
10
  0
VERTEX
 10
110
 20
10
  0
VERTEX
 10
110
 20
110
  0
VERTEX
 10
10
 20
110
  0
SEQEND
  0
ENDSEC
  0
EOF
"""


def _dxf_only_unsupported() -> str:
    """Sadece desteklenmeyen entity'ler (CIRCLE, ARC)."""
    return """
  0
SECTION
  2
ENTITIES
  0
CIRCLE
  8
0
 10
50
 20
50
 40
25
  0
ARC
  10
0
 20
0
 40
10
 50
0
 51
90
  0
ENDSEC
  0
EOF
"""


def _dxf_header_insunits(value: int) -> str:
    """HEADER'da $INSUNITS=value ve tek LINE."""
    return """
  0
SECTION
  2
HEADER
  9
$INSUNITS
 70
""" + str(value) + """
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
 10
1
 20
2
 11
3
 21
4
  0
ENDSEC
  0
EOF
"""


def _dxf_with_999_comment_prefix() -> str:
    """LibreCAD/dxfrw tarzı: dosya başında group code 999 (yorum) ile başlayan DXF."""
    return """
999
dxfrw 0.6.3
  0
SECTION
  2
HEADER
  9
$INSUNITS
 70
4
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
  8
0
 10
0.0
 20
0.0
 11
100.0
 21
50.0
  0
ENDSEC
  0
EOF
"""


def _dxf_999_then_entities_only_no_header() -> str:
    """999 + ENTITIES only (HEADER yok); tek LINE. LibreCAD tarzı minimal."""
    return """999
dxfrw 0.6.3
0
SECTION
2
ENTITIES
0
LINE
10
0
20
0
11
100
21
50
0
ENDSEC
0
EOF
"""


def _dxf_with_blank_lines_between_pairs() -> str:
    """Group code/value çiftleri arasında boş satırlar; yine de parse edilmeli."""
    return """
  0

SECTION
  2

HEADER
  9
$INSUNITS
 70
4
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
 10
0
 20
0
 11
100
 21
50
  0
ENDSEC
  0
EOF
"""


def _dxf_header_with_stray_dimaso_then_entities() -> str:
    """HEADER içinde tamsayı olmayan satır ($DIMASO); resync ile devam edilmeli."""
    return """
  0
SECTION
  2
HEADER
  9
$INSUNITS
 70
4
$DIMASO
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
 10
0
 20
0
 11
100
 21
50
  0
ENDSEC
  0
EOF
"""


class TestParseDxfAscii(unittest.TestCase):
    """parse_dxf_ascii testleri."""

    def test_minimal_dxf_parses_and_has_entities(self):
        text = _minimal_dxf_with_line()
        out = parse_dxf_ascii(text)
        self.assertIn("header", out)
        self.assertIn("entities", out)
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["type"], "LINE")
        self.assertEqual(out["header"]["insunits"], 4)

    def test_insunits_mapping_mm(self):
        text = _dxf_header_insunits(4)
        out = parse_dxf_ascii(text)
        self.assertEqual(out["header"]["insunits"], 4)

    def test_empty_raises(self):
        with self.assertRaises(ValueError) as ctx:
            parse_dxf_ascii("")
        self.assertIn("boş", ctx.exception.args[0].lower())

    def test_missing_entities_section_raises(self):
        text = """
  0
SECTION
  2
HEADER
  0
ENDSEC
  0
EOF
"""
        with self.assertRaises(ValueError) as ctx:
            parse_dxf_ascii(text)
        self.assertIn("ENTITIES", ctx.exception.args[0])

    def test_dxf_with_999_comment_prefix_parses_and_entities_read(self):
        """Group code 999 (comment) dosya başında olsa bile parse başarılı ve ENTITIES okunur."""
        text = _dxf_with_999_comment_prefix()
        out = parse_dxf_ascii(text)
        self.assertIn("header", out)
        self.assertIn("entities", out)
        self.assertEqual(out["header"]["insunits"], 4)
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["type"], "LINE")

    def test_dxf_trailing_999_no_value_parses(self):
        """Dosya sonunda value'suz 999 (tek satır) olsa bile parse başarılı."""
        text = _minimal_dxf_with_line().rstrip() + "\n999\n"
        out = parse_dxf_ascii(text)
        self.assertIn("entities", out)
        self.assertEqual(len(out["entities"]), 1)

    def test_dxf_999_then_entities_only_no_header_parses_one_line(self):
        """999 + ENTITIES only (HEADER yok) DXF parse edilir ve tek LINE entity üretilir."""
        text = _dxf_999_then_entities_only_no_header()
        out = parse_dxf_ascii(text)
        self.assertIn("entities", out)
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["type"], "LINE")
        self.assertIsNone(out["header"]["insunits"])

    def test_dxf_with_blank_lines_between_pairs_parses(self):
        """Group code/value çiftleri arasında boş satırlar olsa bile parse başarılı."""
        text = _dxf_with_blank_lines_between_pairs()
        out = parse_dxf_ascii(text)
        self.assertIn("entities", out)
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["type"], "LINE")
        self.assertEqual(out["header"]["insunits"], 4)

    def test_dxf_stray_dimaso_resync_parses(self):
        """HEADER'da tamsayı olmayan satır ($DIMASO) sonrası resync ile parse devam eder."""
        text = _dxf_header_with_stray_dimaso_then_entities()
        out = parse_dxf_ascii(text)
        self.assertIn("entities", out)
        self.assertEqual(len(out["entities"]), 1)
        self.assertEqual(out["entities"][0]["type"], "LINE")
        self.assertIn("resynced", " ".join(out.get("warnings", [])).lower())


class TestDxfToNormalizedPlan(unittest.TestCase):
    """dxf_to_normalized_plan testleri."""

    def test_one_line_creates_one_segment(self):
        text = _minimal_dxf_with_line()
        plan = dxf_to_normalized_plan(text)
        self.assertIsInstance(plan, NormalizedPlan)
        self.assertEqual(len(plan.segments), 1)
        seg = plan.segments[0]
        self.assertAlmostEqual(seg.x1, 0.0)
        self.assertAlmostEqual(seg.y1, 0.0)
        # 100 mm → 0.1 m, 50 mm → 0.05 m
        self.assertAlmostEqual(seg.x2, 0.1)
        self.assertAlmostEqual(seg.y2, 0.05)
        self.assertEqual(plan.units, "mm")
        self.assertEqual(plan.metadata.get("source"), "dxf")
        self.assertEqual(plan.metadata.get("entity_counts", {}).get("LINE"), 1)

    def test_lwpolyline_four_vertices_open_creates_three_segments(self):
        text = _dxf_lwpolyline_four_vertices(closed=False)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(len(plan.segments), 3)

    def test_lwpolyline_four_vertices_closed_creates_four_segments(self):
        text = _dxf_lwpolyline_four_vertices(closed=True)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(len(plan.segments), 4)

    def test_polyline_vertex_four_open_creates_three_segments(self):
        text = _dxf_polyline_four_vertices(closed=False)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(len(plan.segments), 3)

    def test_polyline_vertex_four_closed_creates_four_segments(self):
        text = _dxf_polyline_four_vertices(closed=True)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(len(plan.segments), 4)

    def test_unsupported_entities_ignored_error_if_none_supported(self):
        text = _dxf_only_unsupported()
        with self.assertRaises(ValueError) as ctx:
            dxf_to_normalized_plan(text)
        self.assertIn("desteklenen", ctx.exception.args[0].lower())

    def test_insunits_mm(self):
        text = _dxf_header_insunits(4)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.units, "mm")
        # 1 mm, 2 mm → metre cinsinden (DXF koordinatı mm kabul edilir)
        self.assertAlmostEqual(plan.segments[0].x1, 0.001)
        self.assertAlmostEqual(plan.segments[0].y1, 0.002)

    def test_insunits_cm(self):
        text = _dxf_header_insunits(5)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.units, "cm")

    def test_insunits_m(self):
        text = _dxf_header_insunits(6)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.units, "m")

    def test_insunits_inches_scaled_to_mm(self):
        text = _dxf_header_insunits(1)
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.units, "mm")
        # 1 inch = 0.0254 m
        self.assertAlmostEqual(plan.segments[0].x1, 1.0 * 0.0254)
        self.assertAlmostEqual(plan.segments[0].y1, 2.0 * 0.0254)

    def test_origin_offset_applied(self):
        text = _minimal_dxf_with_line()
        plan = dxf_to_normalized_plan(text, origin=(10.0, 20.0))
        seg = plan.segments[0]
        # Koordinatlar metre cinsinden; origin de dünya biriminde (m).
        self.assertAlmostEqual(seg.x1, 10.0)
        self.assertAlmostEqual(seg.y1, 20.0)
        self.assertAlmostEqual(seg.x2, 10.0 + 0.1)
        self.assertAlmostEqual(seg.y2, 20.0 + 0.05)

    def test_scale_applied(self):
        text = _minimal_dxf_with_line()
        plan = dxf_to_normalized_plan(text, scale=2.0)
        seg = plan.segments[0]
        # base 100 mm, 50 mm → 0.1 m, 0.05 m; scale=2.0 ile 0.2 m, 0.1 m
        self.assertAlmostEqual(seg.x1, 0.0)
        self.assertAlmostEqual(seg.y1, 0.0)
        self.assertAlmostEqual(seg.x2, 0.2)
        self.assertAlmostEqual(seg.y2, 0.1)

    def test_metadata_entity_counts(self):
        text = _minimal_dxf_with_line()
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.metadata["entity_counts"]["LINE"], 1)
        self.assertEqual(plan.metadata["insunits"], 4)

    def test_dxf_with_999_comment_prefix_to_normalized_plan(self):
        """999 yorum öneki ile DXF dxf_to_normalized_plan ile işlenir; segment doğru üretilir."""
        text = _dxf_with_999_comment_prefix()
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(len(plan.segments), 1)
        seg = plan.segments[0]
        self.assertAlmostEqual(seg.x1, 0.0)
        self.assertAlmostEqual(seg.y1, 0.0)
        self.assertAlmostEqual(seg.x2, 0.1)
        self.assertAlmostEqual(seg.y2, 0.05)

    def test_mm_10000_width_becomes_10_meters(self):
        """INSUNITS=mm ve 10000 genişlik -> 10.0 metre olmalı."""
        dxf_text = """
  0
SECTION
  2
HEADER
  9
$INSUNITS
 70
4
  0
ENDSEC
  0
SECTION
  2
ENTITIES
  0
LINE
 10
0
 20
0
 11
10000
 21
0
  0
ENDSEC
  0
EOF
"""
        plan = dxf_to_normalized_plan(dxf_text)
        self.assertEqual(plan.units, "mm")
        self.assertEqual(len(plan.segments), 1)
        seg = plan.segments[0]
        width_m = seg.x2 - seg.x1
        self.assertAlmostEqual(width_m, 10.0)

    def test_unitless_defaults_to_mm_with_warning(self):
        """HEADER/INSUNITS yoksa unitless kabul edilir; mm varsayımı + uyarı beklenir."""
        text = _dxf_999_then_entities_only_no_header()
        plan = dxf_to_normalized_plan(text)
        self.assertEqual(plan.units, "mm")
        warnings = plan.metadata.get("parse_warnings", [])
        joined = " ".join(warnings).lower()
        self.assertIn("insunits", joined)

    def test_units_override_m_on_unitless_keeps_width_in_meters(self):
        """units_override='m' + unitless DXF: koordinatlar metre kabul edilir."""
        text = _dxf_999_then_entities_only_no_header()
        plan = dxf_to_normalized_plan(text, units="m")
        self.assertEqual(plan.units, "m")
        self.assertEqual(len(plan.segments), 1)
        seg = plan.segments[0]
        # DXF koordinatları doğrudan metre kabul edilir (0 -> 100).
        self.assertAlmostEqual(seg.x1, 0.0)
        self.assertAlmostEqual(seg.x2, 100.0)


if __name__ == "__main__":
    unittest.main()
