from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_responder_module():
    script = Path(__file__).resolve().parents[1] / "scripts" / "serial_loopback_responder.py"
    spec = importlib.util.spec_from_file_location("serial_loopback_responder", script)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_profile_b_batch_returns_done() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder()

    assert responder.handle_line("BEGIN") == "OK"
    assert responder.handle_line("SPEED 1") is None
    assert responder.handle_line("PEN DOWN") is None
    assert responder.handle_line("FORWARD 0.05") is None
    assert responder.handle_line("END") == "DONE"
    assert responder.batch_count == 1


def test_malformed_batch_returns_err() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder()

    assert responder.handle_line("BEGIN") == "OK"
    response = responder.handle_line("MOVE")

    assert response is not None
    assert response.startswith("ERR parse")
    assert responder.batch_count == 0
    assert responder.in_batch is False


def test_forced_malformed_mode_returns_err() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder(mode="malformed")

    assert responder.handle_line("BEGIN") == "OK"
    assert responder.handle_line("SPEED 1") is None

    assert responder.handle_line("END") == "ERR forced_malformed"


def test_status_and_stop_responses() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder()

    status = responder.handle_line("STATUS")
    assert status is not None
    assert status.startswith("STATUS ")
    assert "responder=1" in status

    assert responder.handle_line("BEGIN") == "OK"
    assert responder.handle_line("SPEED 1") is None
    assert responder.handle_line("STOP") == "DONE"
    assert responder.in_batch is False
    assert responder.batch_lines == []


def test_queue_full_clears_batch_and_returns_err() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder(max_commands=1)

    assert responder.handle_line("BEGIN") == "OK"
    assert responder.handle_line("SPEED 1") is None
    assert responder.handle_line("PEN UP") == "ERR queue_full"
    assert responder.in_batch is False
    assert responder.batch_lines == []


def test_end_without_begin_returns_state_error() -> None:
    module = _load_responder_module()
    responder = module.LoopbackResponder()

    assert responder.handle_line("END") == "ERR end_without_begin"
