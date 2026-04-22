# test_official_core_golden_path.py — Resmi FastAPI çekirdeği: import_plan → analyze → (export) uçtan uca duman testi
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("pydantic")
pytest.importorskip("httpx")

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi.testclient import TestClient

from app.api.main import app


def _diag_error_count(items: list) -> int:
    return sum(1 for x in items if isinstance(x, dict) and x.get("severity") == "ERROR")


def _minimal_import_plan_body() -> dict:
    return {
        "version": "v1",
        "units": "m",
        "scale": 1.0,
        "origin": {"x": 0.0, "y": 0.0},
        "segments": [{"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 0.0}],
        "normalize": True,
        "return_commands_text": True,
        "return_plan_text": True,
        "step_size": 0.1,
        "speed": 120.0,
    }


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_golden_path_import_plan_then_analyze(client: TestClient) -> None:
    """JSON → normalize → enrich → path → commands; ardından analyze (resmi çekirdek)."""
    r1 = client.post("/api/import_plan", json=_minimal_import_plan_body())
    assert r1.status_code == 200
    data = r1.json()
    assert data.get("ok") is True, data.get("error")
    assert isinstance(data.get("commands_text"), str) and len(data["commands_text"]) > 0
    assert data.get("normalized") is not None
    ct = data["commands_text"]
    assert "SPEED" in ct
    assert "MOVE" in ct

    r2 = client.post(
        "/api/analyze",
        json={
            "commands_text": ct,
            "walls": data.get("walls"),
            "start": [0.0, 0.0],
        },
    )
    assert r2.status_code == 200
    a = r2.json()
    assert a.get("blocked") is False
    stats = a.get("stats") or {}
    assert float(stats.get("path_length", 0.0)) > 0.0
    assert _diag_error_count(a.get("parser") or []) == 0
    assert _diag_error_count(a.get("analysis") or []) == 0


def test_golden_path_export_robot_v1(client: TestClient) -> None:
    """Aynı komut metni ile export (robot_v1) duman testi."""
    r1 = client.post("/api/import_plan", json=_minimal_import_plan_body())
    assert r1.status_code == 200
    data = r1.json()
    assert data.get("ok") is True
    ct = data["commands_text"]
    assert ct

    r3 = client.post(
        "/api/export",
        json={
            "text": ct,
            "start": [0.0, 0.0],
            "format": "robot_v1",
        },
    )
    assert r3.status_code == 200
    ex = r3.json()
    assert ex.get("ok") is True
    assert ex.get("blocked") is False
    assert isinstance(ex.get("content"), str) and len(ex["content"]) > 0
