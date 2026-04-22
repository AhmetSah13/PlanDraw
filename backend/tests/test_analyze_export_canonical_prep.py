"""Analyze/export uçlarının prepare_job_commands ile uyumu (tek optimize)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from fastapi.testclient import TestClient

from app.analysis.scenario_analysis import export_commands_to_string
from app.api.job_command_prep import prepare_job_commands
from app.api.main import _limits_from_text, _optimize_cfg_from_request, app
from app.api.schemas import OptimizeConfigOut
from app.execution.commands import serialize_commands


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_analyze_commands_unrolled_matches_canonical_prep(client: TestClient) -> None:
    text = "SPEED 10\nFORWARD 2\n"
    prep = prepare_job_commands(text, explicit_start=None, optimize_cfg=None)
    r = client.post("/api/analyze", json={"commands_text": text})
    assert r.status_code == 200
    data = r.json()
    assert data["commands_unrolled"] == serialize_commands(prep.commands)


def test_analyze_optimize_stats_align_with_prep(client: TestClient) -> None:
    dsl = """SPEED 120
MOVE 0 0
MOVE 0.0001 0
"""
    opt = {
        "enabled": True,
        "min_segment_length": 0.5,
        "join_epsilon_m": 0.01,
        "rdp_epsilon": 0.0,
    }
    oc = _optimize_cfg_from_request(OptimizeConfigOut(**opt))
    assert oc is not None
    prep = prepare_job_commands(dsl, explicit_start=(0.0, 0.0), optimize_cfg=oc)
    r = client.post(
        "/api/analyze",
        json={"commands_text": dsl, "start": [0.0, 0.0], "optimize": opt},
    )
    assert r.status_code == 200
    st = r.json().get("stats") or {}
    assert st.get("original_move_count") == prep.original_move_count
    assert st.get("optimized_move_count") == prep.optimized_move_count
    assert r.json()["commands_unrolled"] == serialize_commands(prep.commands)


def test_export_content_matches_prep_without_double_optimize(client: TestClient) -> None:
    text = "SPEED 10\nMOVE 0 0\nMOVE 10 0\n"
    prep = prepare_job_commands(text, explicit_start=(0.0, 0.0), optimize_cfg=None)
    limits = _limits_from_text(text)
    expected, _, _, _ = export_commands_to_string(
        prep.commands,
        prep.start_pt,
        limits=limits,
        format="robot_v1",
        optimize_cfg=None,
    )
    r = client.post(
        "/api/export",
        json={"text": text, "start": [0.0, 0.0], "format": "robot_v1"},
    )
    assert r.status_code == 200
    assert r.json()["content"] == expected


def test_export_with_optimize_matches_single_prep_pass(client: TestClient) -> None:
    dsl = """SPEED 120
MOVE 0 0
MOVE 0.0001 0
"""
    opt = {
        "enabled": True,
        "min_segment_length": 0.5,
        "join_epsilon_m": 0.01,
        "rdp_epsilon": 0.0,
    }
    oc = _optimize_cfg_from_request(OptimizeConfigOut(**opt))
    assert oc is not None
    prep = prepare_job_commands(dsl, explicit_start=(0.0, 0.0), optimize_cfg=oc)
    limits = _limits_from_text(dsl)
    expected, _, _, _ = export_commands_to_string(
        prep.commands,
        prep.start_pt,
        limits=limits,
        format="robot_v1",
        optimize_cfg=None,
    )
    r = client.post(
        "/api/export",
        json={"text": dsl, "start": [0.0, 0.0], "format": "robot_v1", "optimize": opt},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["content"] == expected
    st = body.get("stats") or {}
    assert st.get("original_move_count") == prep.original_move_count
    assert st.get("optimized_move_count") == prep.optimized_move_count
