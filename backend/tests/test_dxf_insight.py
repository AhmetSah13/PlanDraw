# test_dxf_insight.py — DXF Insight Report, layer scoring, warning codes
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

from app.importers.dxf_importer import (
    inspect_dxf_layers,
    WARNING_CODE_USER_ACTIONS,
    SUPPORTED_ENTITY_TYPES,
)


def _dxf_line_and_arc() -> str:
    """LINE + ARC (desteklenmeyen) içeren DXF."""
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
ARC
  8
WALLS
 10
50
 20
50
 40
25
 50
0
 51
90
  0
ENDSEC
  0
EOF
"""


def _dxf_line_only() -> str:
    """Sadece LINE."""
    return """
  0
SECTION
  2
ENTITIES
  0
LINE
  8
0
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


class TestDxfInsightReport(unittest.TestCase):
    """DXF Insight Report alanlarının varlığını ve yapısını doğrular."""

    def test_insight_report_has_entity_counts(self):
        text = _dxf_line_only()
        info = inspect_dxf_layers(text)
        self.assertIn("entity_counts_total", info)
        self.assertIn("entity_counts_supported", info)
        self.assertIn("entity_counts_unsupported", info)
        self.assertIsInstance(info["entity_counts_total"], dict)
        self.assertIn("LINE", info["entity_counts_total"])
        self.assertEqual(info["entity_counts_supported"].get("LINE"), 1)
        self.assertIsInstance(info["entity_counts_unsupported"], dict)

    def test_insight_report_unsupported_samples_when_arc_present(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("unsupported_samples", info)
        samples = info["unsupported_samples"]
        self.assertGreater(len(samples), 0)
        arc_sample = next((s for s in samples if s["type"] == "ARC"), None)
        self.assertIsNotNone(arc_sample)
        self.assertIn("layer", arc_sample)
        self.assertIn("note", arc_sample)

    def test_insight_report_layer_entity_counts(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("layer_entity_counts", info)
        lec = info["layer_entity_counts"]
        self.assertIn("WALLS", lec)
        self.assertIn("LINE", lec["WALLS"])
        self.assertIn("ARC", lec["WALLS"])

    def test_insight_report_layer_scores(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("layer_scores", info)
        scores = info["layer_scores"]
        self.assertGreater(len(scores), 0)
        for ls in scores:
            self.assertIn("layer", ls)
            self.assertIn("score", ls)
            self.assertIn("reasons", ls)
            self.assertIn("length_m", ls)
            self.assertIn("entity_mix_summary", ls)

    def test_insight_report_suggested_layers_reasons(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("suggested_layers_reasons", info)
        reasons = info["suggested_layers_reasons"]
        self.assertGreaterEqual(len(reasons), 0)
        for r in reasons:
            self.assertIn("layer", r)
            self.assertIn("reason", r)

    def test_insight_report_recommended_action(self):
        text = _dxf_line_only()
        info = inspect_dxf_layers(text)
        self.assertIn("recommended_action", info)
        self.assertIsInstance(info["recommended_action"], str)
        self.assertGreater(len(info["recommended_action"]), 0)


class TestWarningCodes(unittest.TestCase):
    """Reason-coded uyarılar ve user_action önerileri."""

    def test_warning_codes_when_arc_present(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("warning_codes", info)
        codes = info["warning_codes"]
        self.assertIn("UNSUPPORTED_ARC", codes)

    def test_parse_warnings_contains_structured_entries(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        self.assertIn("parse_warnings", info)
        warnings = info["parse_warnings"]
        structured = [w for w in warnings if isinstance(w, dict) and "code" in w]
        self.assertGreater(len(structured), 0)
        for w in structured:
            self.assertIn("code", w)
            self.assertIn("user_action", w)

    def test_user_action_mapping_exists(self):
        for code in ["UNSUPPORTED_INSERT", "UNSUPPORTED_ARC", "UNSUPPORTED_SPLINE", "HAS_HATCH", "HAS_TEXT_DIM", "LAYER_COMPLEXITY_HIGH"]:
            self.assertIn(code, WARNING_CODE_USER_ACTIONS)
            self.assertIsInstance(WARNING_CODE_USER_ACTIONS[code], str)
            self.assertGreater(len(WARNING_CODE_USER_ACTIONS[code]), 0)


class TestLayerScoring(unittest.TestCase):
    """Layer scoring heuristiğinin mantıklı sonuçlar ürettiğini doğrular."""

    def test_wall_keyword_layer_has_higher_score(self):
        text = _dxf_line_and_arc()
        info = inspect_dxf_layers(text)
        scores = info["layer_scores"]
        wall_scores = [s for s in scores if "wall" in s["layer"].lower()]
        if wall_scores:
            self.assertIn("İsim eşleşmesi", str(wall_scores[0]["reasons"]))

    def test_supported_entity_types_constant(self):
        self.assertIn("LINE", SUPPORTED_ENTITY_TYPES)
        self.assertIn("LWPOLYLINE", SUPPORTED_ENTITY_TYPES)
        self.assertIn("POLYLINE", SUPPORTED_ENTITY_TYPES)
        self.assertNotIn("ARC", SUPPORTED_ENTITY_TYPES)
        self.assertNotIn("VERTEX", SUPPORTED_ENTITY_TYPES)


if __name__ == "__main__":
    unittest.main()
