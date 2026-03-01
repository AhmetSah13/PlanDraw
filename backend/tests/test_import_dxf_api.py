# test_import_dxf_api.py — POST /api/import_dxf (multipart) unittest
from __future__ import annotations

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("fastapi")
pytestmark = pytest.mark.integration

import io
import json
import unittest
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
_backend_root = Path(__file__).resolve().parents[1]
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))


class _MockUploadFile:
    """Test için UploadFile benzeri; .read() ve .file.read() destekler."""

    def __init__(self, content: bytes):
        self._content = content
        self.file = io.BytesIO(content)

    def read(self) -> bytes:
        return self._content


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


def _dxf_two_layers_wall_dim() -> str:
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


def _call_import_dxf(dxf_content: bytes, options_json: str | None = None):
    """import_dxf endpoint handler'ını doğrudan çağırır (TestClient/httpx yok)."""
    from app.api.main import import_dxf
    mock_file = _MockUploadFile(dxf_content)
    return import_dxf(file=mock_file, options_json=options_json)


class TestImportDxfAPI(unittest.TestCase):
    """POST /api/import_dxf endpoint testleri (handler doğrudan çağrılıyor)."""

    def test_upload_valid_dxf_returns_ok_and_plan_text_commands_walls(self):
        dxf_text = _minimal_dxf_with_line()
        options = {
            "return_plan_text": True,
            "return_commands_text": True,
            "normalize": True,
            "step_size": 5.0,
            "speed": 120.0,
        }
        response = _call_import_dxf(
            dxf_text.encode("utf-8"),
            options_json=json.dumps(options),
        )
        self.assertTrue(response.ok, msg=getattr(response, "error", None))
        self.assertIsNotNone(response.normalized)
        norm = response.normalized
        self.assertIn("segments", norm)
        self.assertGreaterEqual(len(norm["segments"]), 1)
        self.assertIsNotNone(response.plan_text)
        self.assertIn("LINE", response.plan_text)
        self.assertIsNotNone(response.commands_text)
        self.assertTrue(len(response.commands_text) > 0)
        self.assertIn("PEN", response.commands_text)
        self.assertIsNotNone(response.walls)
        self.assertEqual(len(response.walls), len(norm["segments"]))

    def test_upload_valid_dxf_no_options_json_uses_defaults(self):
        dxf_text = _minimal_dxf_with_line()
        response = _call_import_dxf(dxf_text.encode("utf-8"))
        self.assertTrue(response.ok)
        self.assertIn("LINE", response.plan_text or "")
        self.assertTrue(len(response.commands_text or "") > 0)

    def test_upload_binary_or_invalid_dxf_returns_ok_false(self):
        response = _call_import_dxf(
            b"\x00\xff\xfe\x00",
            options_json="{}",
        )
        self.assertFalse(response.ok)
        self.assertIn("error", response.model_dump())
        err = response.error or ""
        self.assertTrue("ASCII" in err.upper() or "UTF-8" in err, msg=err)

    def test_upload_dxf_missing_entities_section_returns_ok_false(self):
        dxf_no_entities = """
  0
SECTION
  2
HEADER
  0
ENDSEC
  0
EOF
"""
        response = _call_import_dxf(dxf_no_entities.encode("utf-8"), options_json="{}")
        self.assertFalse(response.ok)
        self.assertIn("ENTITIES", response.error or "")

    def test_import_dxf_preview_layers_returns_layers_and_suggestions(self):
        from app.api.main import import_dxf

        dxf_text = _dxf_two_layers_wall_dim()
        options = {
            "preview_layers": True,
        }
        mock_file = _MockUploadFile(dxf_text.encode("utf-8"))
        response: ImportDxfResponse = import_dxf(
            file=mock_file,
            options_json=json.dumps(options),
        )
        self.assertTrue(response.ok, msg=getattr(response, "error", None))
        self.assertIsNone(response.normalized)
        self.assertIsNone(response.commands_text)
        self.assertIsNotNone(response.layers)
        layer_names = {l.name for l in response.layers or []}
        self.assertIn("WALLS", layer_names)
        self.assertIn("DIM", layer_names)
        self.assertIsNotNone(response.suggested_layers)
        self.assertGreaterEqual(len(response.suggested_layers or []), 1)
        self.assertEqual(response.suggested_layers[0], "WALLS")

    def test_import_dxf_selected_layers_filters_output(self):
        from app.api.main import import_dxf

        dxf_text = _dxf_two_layers_wall_dim()
        options_all = {
            "return_plan_text": True,
            "return_commands_text": False,
            "normalize": False,
        }
        # Önce tüm layer'lar ile
        resp_all = import_dxf(
            file=_MockUploadFile(dxf_text.encode("utf-8")),
            options_json=json.dumps(options_all),
        )
        self.assertTrue(resp_all.ok, msg=getattr(resp_all, "error", None))
        walls_all = resp_all.walls or []
        self.assertGreaterEqual(len(walls_all), 2)

        # Sadece WALLS layer'ını seçerek
        options_wall = {
            "return_plan_text": True,
            "return_commands_text": False,
            "normalize": False,
            "selected_layers": ["WALLS"],
        }
        resp_wall = import_dxf(
            file=_MockUploadFile(dxf_text.encode("utf-8")),
            options_json=json.dumps(options_wall),
        )
        self.assertTrue(resp_wall.ok, msg=getattr(resp_wall, "error", None))
        walls_wall = resp_wall.walls or []
        self.assertEqual(len(walls_wall), 1)

    def test_import_dxf_preview_layers_recommended_step_size(self):
        from app.api.main import import_dxf

        dxf_text = _minimal_dxf_with_line()
        options = {
            "preview_layers": True,
            "auto_step_target_moves": 1000,
        }
        resp = import_dxf(
            file=_MockUploadFile(dxf_text.encode("utf-8")),
            options_json=json.dumps(options),
        )
        self.assertTrue(resp.ok, msg=getattr(resp, "error", None))
        self.assertIsNotNone(resp.recommended_step_size)
        self.assertGreater(resp.recommended_step_size, 0.0)

    def test_import_dxf_selected_layers_nonexistent_returns_ok_false(self):
        """Seçilen katmanlar dosyada yoksa veya filtre sonrası segment kalmazsa ok=False ve anlamlı hata."""
        dxf_text = _dxf_two_layers_wall_dim()
        options = {
            "return_plan_text": True,
            "return_commands_text": True,
            "selected_layers": ["NONEXISTENT_LAYER"],
        }
        response = _call_import_dxf(
            dxf_text.encode("utf-8"),
            options_json=json.dumps(options),
        )
        self.assertFalse(response.ok, msg=getattr(response, "error", None))
        self.assertIsNotNone(response.error)
        self.assertTrue(
            "desteklenen" in (response.error or "").lower() or "segment" in (response.error or "").lower(),
            msg=f"error should mention entity/segment: {response.error}",
        )


class TestImportDxfOptionsDefaults(unittest.TestCase):
    """ImportDxfOptions varsayılan değerleri (API uyumluluğu)."""

    def test_auto_step_target_moves_default_is_800(self):
        from app.api.schemas import ImportDxfOptions
        opts = ImportDxfOptions()
        self.assertEqual(opts.auto_step_target_moves, 800)


class TestPreviewRecommendedStepSizeBboxClamp(unittest.TestCase):
    """Preview recommended_step_size bbox ile clamp ediliyor mu?"""

    def test_bbox_10x6_raw_inside_range(self):
        from app.utils.step_size_utils import preview_recommended_step_size
        # total_length=87.1, target_moves=800 → raw ≈ 0.1089
        # bbox [0,0,10,6] → scale=10, adaptive_min=0.05, adaptive_max=0.50 → clamp devreye girmez
        recommended = preview_recommended_step_size(87.1, 800, [0.0, 0.0, 10.0, 6.0])
        self.assertIsNotNone(recommended)
        self.assertGreaterEqual(recommended, 0.05)
        self.assertLessEqual(recommended, 0.50)
        self.assertAlmostEqual(recommended, 87.1 / 800, delta=0.01)

    def test_bbox_large_scale_min_max_swap(self):
        from app.utils.step_size_utils import preview_recommended_step_size
        # scale=200 → adaptive_min=max(0.05, 1.0)=1.0, adaptive_max=min(0.50, 10)=0.50 → min>max
        # güvenlik swap → 0.05–0.50; raw 0.1089 → recommended 0.1089
        recommended = preview_recommended_step_size(87.1, 800, [0.0, 0.0, 200.0, 100.0])
        self.assertIsNotNone(recommended)
        self.assertGreaterEqual(recommended, 0.05)
        self.assertLessEqual(recommended, 0.50)
        self.assertAlmostEqual(recommended, 87.1 / 800, delta=0.01)


if __name__ == "__main__":
    unittest.main()
