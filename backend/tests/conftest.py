# conftest.py — Fallback: editable install yoksa backend/ root'unu sys.path'e ekler;
# böylece repo kökünden "pytest backend/tests" çalışır. pip install -e . sonrası gerekmez.
from __future__ import annotations

import sys
from pathlib import Path

try:
    import app  # noqa: F401
except ImportError:
    _backend_root = Path(__file__).resolve().parents[1]
    if str(_backend_root) not in sys.path:
        sys.path.insert(0, str(_backend_root))
