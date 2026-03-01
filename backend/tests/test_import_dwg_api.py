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


if __name__ == "__main__":
    unittest.main()

