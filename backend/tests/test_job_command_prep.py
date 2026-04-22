"""Canonical job komut hazırlığı: parse + optimize tek yerde."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.analysis.scenario_analysis import analyze_commands
from app.api.job_command_prep import prepare_job_commands
from app.api.main import _optimize_cfg_from_request, _run_sim_to_queue
from app.api.schemas import JobFileArtifactRequest, OptimizeConfigOut
from app.pathing.path_optimizer import OptimizeConfig


def _drain_sim_queue(queue: asyncio.Queue) -> list[tuple]:
    events: list[tuple] = []

    async def _go() -> None:
        while True:
            et, data = await queue.get()
            if et is None:
                break
            events.append((et, data))

    asyncio.run(_go())
    return events


def test_prepare_without_optimize_no_metadata():
    prep = prepare_job_commands(
        "SPEED 10\nFORWARD 2\n",
        explicit_start=None,
        optimize_cfg=None,
    )
    assert prep.original_move_count is None
    assert prep.optimized_move_count is None
    assert prep.reduction_ratio is None
    assert len(prep.commands) >= 1


def test_prepare_with_optimize_sets_reduction_fields():
    body = """SPEED 120
MOVE 0 0
MOVE 0.0001 0
"""
    oc = _optimize_cfg_from_request(
        OptimizeConfigOut(
            enabled=True,
            min_segment_length=0.5,
            join_epsilon_m=0.01,
            rdp_epsilon=0.0,
        )
    )
    assert oc is not None
    prep0 = prepare_job_commands(body, explicit_start=(0.0, 0.0), optimize_cfg=None)
    prep1 = prepare_job_commands(body, explicit_start=(0.0, 0.0), optimize_cfg=oc)
    assert prep1.original_move_count is not None
    assert prep1.optimized_move_count is not None
    assert prep1.reduction_ratio is not None
    # Toplam komut sayısı kalem eklemiyle artabilir; eşleme MOVE/REL/FORWARD sayısı üzerinden.
    assert prep1.optimized_move_count <= prep1.original_move_count


def test_analyze_on_prep_without_double_optimize():
    oc = OptimizeConfig(
        enabled=True,
        collinear_angle_eps_deg=1.0,
        min_segment_length=0.01,
        rdp_epsilon=0.0,
        preserve_pen_lifts=True,
        join_epsilon_m=0.001,
        max_2opt_iterations=50,
        time_budget_ms=5000.0,
        preserve_order_for_layers=False,
        deterministic_seed=None,
    )
    text = "SPEED 10\nFORWARD 1\nFORWARD 1\n"
    prep = prepare_job_commands(text, explicit_start=(0.0, 0.0), optimize_cfg=oc)
    n0 = len(prep.commands)
    analyze_commands(prep.commands, start=prep.start_pt, limits=None, optimize_cfg=None)
    assert len(prep.commands) == n0


def test_analyze_executor_fileartifact_command_count_consistent(tmp_path: Path, monkeypatch):
    """Dry-run analiz listesi = executor/FileDriver ``len(commands)``."""
    monkeypatch.setenv("JOB_FILE_ARTIFACT_ROOT", str(tmp_path))
    text = "SPEED 10\nFORWARD 3\n"
    prep = prepare_job_commands(text, explicit_start=None, optimize_cfg=None)
    analyze_commands(
        prep.commands,
        start=prep.start_pt,
        limits=None,
        optimize_cfg=None,
    )
    n_cmds = len(prep.commands)

    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def _go() -> None:
        await _run_sim_to_queue(
            list(prep.commands),
            0.016,
            1.0,
            prep.start_pt,
            queue,
            job_id="consistency-job",
            file_artifact_opt=JobFileArtifactRequest(enabled=True, mode="dsl"),
        )

    asyncio.run(_go())
    events = _drain_sim_queue(queue)
    done = next(d for e, d in events if e == "done")
    assert done["file_artifact"]["last_command_count"] == n_cmds


def test_optimize_on_prep_fileartifact_matches_optimized_length(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("JOB_FILE_ARTIFACT_ROOT", str(tmp_path))
    oc = _optimize_cfg_from_request(
        OptimizeConfigOut(enabled=True, min_segment_length=0.5, join_epsilon_m=0.01, rdp_epsilon=0.0)
    )
    assert oc is not None
    body = """SPEED 120
MOVE 0 0
MOVE 0.0001 0
"""
    prep = prepare_job_commands(body, explicit_start=(0.0, 0.0), optimize_cfg=oc)
    n_cmds = len(prep.commands)

    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def _go() -> None:
        await _run_sim_to_queue(
            list(prep.commands),
            0.016,
            1.0,
            prep.start_pt,
            queue,
            job_id="opt-job",
            file_artifact_opt=JobFileArtifactRequest(enabled=True, mode="dsl"),
        )

    asyncio.run(_go())
    events = _drain_sim_queue(queue)
    done = next(d for e, d in events if e == "done")
    assert done["file_artifact"]["last_command_count"] == n_cmds
    assert prep.original_move_count is not None
