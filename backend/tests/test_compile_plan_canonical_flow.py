"""compile_plan: tek optimize, analiz ``working`` üzerinde; roundtrip yalnız doğrulama."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.analysis.scenario_analysis import analyze_commands
from app.api.main import compile_plan
from app.api.schemas import CompilePlanRequest, OptimizeConfigOut
from app.execution.commands import parse_commands


def _square_plan_text() -> str:
    return """LINE 0 0 10 0
LINE 10 0 10 10
LINE 10 10 0 10
LINE 0 10 0 0
"""


def test_compile_plan_optimize_off_raw_equals_optimized() -> None:
    req = CompilePlanRequest(
        plan_text=_square_plan_text(),
        step_size=1.0,
        speed=100.0,
        world_scale=1.0,
        world_offset=(0.0, 0.0),
    )
    resp = compile_plan(req)
    assert resp.get("ok") is True
    assert resp["commands_text_raw"] == resp["commands_text_optimized"]
    assert resp["commands_text"] == resp["commands_text_raw"]


def test_compile_plan_stats_match_analyze_on_optimized_serialized_commands() -> None:
    """API istatistikleri, ``commands_text_optimized`` parse edilip tek kez analyze edilenle aynı olmalı."""
    req = CompilePlanRequest(
        plan_text=_square_plan_text(),
        step_size=0.5,
        speed=120.0,
        world_scale=1.0,
        world_offset=(0.0, 0.0),
        optimize=OptimizeConfigOut(
            enabled=True,
            min_segment_length=0.05,
            join_epsilon_m=0.02,
            rdp_epsilon=0.0,
        ),
    )
    resp = compile_plan(req)
    assert resp.get("ok") is True
    walls = resp.get("walls") or []
    opt_text = resp["commands_text_optimized"]
    w_cmds, _ = parse_commands(opt_text, strict=False)
    st_ref, _ = analyze_commands(
        w_cmds,
        start=(0.0, 0.0),
        limits=None,
        optimize_cfg=None,
        walls=walls,
        collision_mode="warn",
    )
    st_api = resp["stats"]
    assert st_api["move_count"] == st_ref.move_count
    assert st_api["path_length"] == pytest.approx(st_ref.path_length)


def test_compile_plan_roundtrip_raw_parse_ok_independent_of_analyze_path() -> None:
    """Ham metin parse'ı yalnızca doğrulama; optimize açık olsa bile ham serileştirme geçerli DSL olmalı."""
    req = CompilePlanRequest(
        plan_text=_square_plan_text(),
        step_size=1.0,
        speed=100.0,
        optimize=OptimizeConfigOut(enabled=True, min_segment_length=0.01, join_epsilon_m=0.001),
    )
    resp = compile_plan(req)
    assert resp.get("ok") is True
    raw = resp["commands_text_raw"]
    _, diags = parse_commands(raw, strict=False)
    assert not any(d.severity == "ERROR" for d in diags)
