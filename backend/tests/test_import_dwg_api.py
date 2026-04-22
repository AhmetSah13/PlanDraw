from __future__ import annotations

import pytest
pytest.importorskip("pydantic")
pytest.importorskip("fastapi")
pytestmark = pytest.mark.integration

import io
import os
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


def _call_import_dwg(dwg_content: bytes, options_json: str | None = None):
    """import_dwg endpoint handler'ını doğrudan çağırır."""
    from app.api.main import import_dwg

    mock_file = _MockUploadFile(dwg_content)
    return import_dwg(file=mock_file, options_json=options_json)


class TestImportDwgAPI(unittest.TestCase):
    """POST /api/import_dwg endpoint testleri (handler doğrudan çağrılıyor)."""

    def test_converter_not_configured_returns_ok_false_with_clear_message(self):
        # Ortamda dönüştürücü yapılandırılmamışsa, kullanıcıya DXF yüklemesini
        # önerecek okunabilir bir mesaj dönmeli.
        os.environ.pop("DWG_CONVERTER_PATH", None)
        response = _call_import_dwg(b"dummy dwg bytes", options_json="{}")

        self.assertFalse(response.ok)
        self.assertIsNotNone(response.error)
        # Mesaj spesifik metni içermeli ki kullanıcı ne yapacağını bilsin.
        self.assertIn(
            "DWG conversion not configured. Please upload DXF or export DWG to DXF.",
            response.error,
        )

    def test_import_dwg_uses_converter_and_reuses_dxf_pipeline(self):
        """DWG adapter, converter çıktısını DXF bytes olarak DXF pipeline'a verir."""
        import json
        import app.api.main as api_main

        # Minimal tek LINE içeren ASCII DXF (test_import_dxf_api ile uyumlu).
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

        def fake_convert(dwg_bytes: bytes, timeout_seconds: float = 60.0) -> bytes:  # type: ignore[override]
            # Gerçek dönüştürüyü çağırmak yerine sabit DXF döndür.
            return dxf_text.encode("utf-8")

        orig = api_main.convert_dwg_bytes_to_dxf_bytes
        api_main.convert_dwg_bytes_to_dxf_bytes = fake_convert  # type: ignore[assignment]
        try:
            options = {
                "return_plan_text": True,
                "return_commands_text": True,
                "normalize": True,
            }
            response = _call_import_dwg(
                b"dummy dwg",
                options_json=json.dumps(options),
            )
            self.assertTrue(response.ok, msg=getattr(response, "error", None))
            self.assertIsNotNone(response.plan_text)
            self.assertIn("LINE", response.plan_text or "")
        finally:
            api_main.convert_dwg_bytes_to_dxf_bytes = orig  # type: ignore[assignment]


if __name__ == "__main__":
    unittest.main()

