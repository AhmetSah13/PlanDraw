# test_dxf_segment_budget_warning.py — ezdxf yolu: segment bütçesi uyarısı (birim test, integration değil)
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.importers.dxf_importer import dxf_bytes_to_normalized_plan


def test_segment_budget_adds_warning_code_and_parse_warning_dict():
    """Limit dolunca warning_codes ve parse_warnings içinde SEGMENT_BUDGET_APPLIED açık kayıt."""
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new()
    msp = doc.modelspace()
    for i in range(30):
        msp.add_line((float(i), 0.0), (float(i + 1), 0.0))
    sio = io.StringIO()
    doc.write(sio)
    raw = sio.getvalue().encode("ascii", errors="replace")
    plan = dxf_bytes_to_normalized_plan(raw, target_max_segments=5)
    assert "SEGMENT_BUDGET_APPLIED" in plan.metadata.get("warning_codes", [])
    pw = plan.metadata.get("parse_warnings", [])
    codes = [p.get("code") for p in pw if isinstance(p, dict)]
    assert "SEGMENT_BUDGET_APPLIED" in codes
    assert plan.metadata.get("extraction_summary", {}).get("segment_budget_applied") is True
