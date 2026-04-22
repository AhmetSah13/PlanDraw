# Job simülasyon kuyruğu: isteğe bağlı FileDriver artifact (_run_sim_to_queue).
#
# Not: Starlette TestClient tek istek içinde arka plan asyncio görevini bitirip
# jobs[job_id] kaydını silebildiği için tam HTTP+SSE entegrasyonu burada güvenilir
# değil; kaynak gerçeği _run_sim_to_queue + kuyruk ile doğrulanır.
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


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


def test_run_sim_to_queue_file_artifact_dsl_matches_commands(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOB_FILE_ARTIFACT_ROOT", str(tmp_path))
    from app.api.job_command_prep import prepare_job_commands
    from app.api.main import _run_sim_to_queue
    from app.api.schemas import JobFileArtifactRequest
    from app.execution.commands import serialize_commands

    prep = prepare_job_commands("SPEED 10\nFORWARD 3\n", explicit_start=None, optimize_cfg=None)
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def _run() -> None:
        await _run_sim_to_queue(
            list(prep.commands),
            0.016,
            1.0,
            prep.start_pt,
            queue,
            job_id="test-artifact-job",
            file_artifact_opt=JobFileArtifactRequest(enabled=True, mode="dsl"),
        )

    asyncio.run(_run())
    events = _drain_sim_queue(queue)
    done_rows = [d for e, d in events if e == "done"]
    assert len(done_rows) == 1
    done = done_rows[0]
    assert "file_artifact" in done
    fa = done["file_artifact"]
    assert fa["last_write_succeeded"] is True
    assert fa.get("last_error") in (None, "")
    path = Path(fa["path"])
    assert path.is_file()
    assert path.read_text(encoding="utf-8") == serialize_commands(prep.commands)


def test_run_sim_to_queue_default_no_file_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOB_FILE_ARTIFACT_ROOT", str(tmp_path))
    from app.api.job_command_prep import prepare_job_commands
    from app.api.main import _run_sim_to_queue

    prep = prepare_job_commands("SPEED 10\nFORWARD 3\n", explicit_start=None, optimize_cfg=None)
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def _run() -> None:
        await _run_sim_to_queue(
            list(prep.commands),
            0.016,
            1.0,
            prep.start_pt,
            queue,
            job_id="no-artifact",
            file_artifact_opt=None,
        )

    asyncio.run(_run())
    events = _drain_sim_queue(queue)
    done = next(d for e, d in events if e == "done")
    assert "file_artifact" not in done
    assert not list(tmp_path.iterdir())


def test_run_sim_to_queue_file_artifact_disabled(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("JOB_FILE_ARTIFACT_ROOT", str(tmp_path))
    from app.api.job_command_prep import prepare_job_commands
    from app.api.main import _run_sim_to_queue
    from app.api.schemas import JobFileArtifactRequest

    prep = prepare_job_commands("SPEED 10\nFORWARD 3\n", explicit_start=None, optimize_cfg=None)
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)

    async def _run() -> None:
        await _run_sim_to_queue(
            list(prep.commands),
            0.016,
            1.0,
            prep.start_pt,
            queue,
            job_id="disabled-artifact",
            file_artifact_opt=JobFileArtifactRequest(enabled=False, mode="dsl"),
        )

    asyncio.run(_run())
    events = _drain_sim_queue(queue)
    done = next(d for e, d in events if e == "done")
    assert "file_artifact" not in done
    assert not list(tmp_path.iterdir())


def test_create_job_request_accepts_file_artifact_json() -> None:
    """OpenAPI gövdesi: file_artifact alanı kabul edilir (job yaşam döngüsü bu testte yok)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from app.api.main import app

    client = TestClient(app)
    r = client.post(
        "/api/jobs",
        json={
            "text": "SPEED 1\n",
            "dt": 0.016,
            "file_artifact": {"enabled": True, "mode": "dsl"},
        },
    )
    assert r.status_code == 200
    assert "job_id" in r.json()
