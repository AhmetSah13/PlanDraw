# test_commands_robustness.py — Komut ayrıştırıcı: NaN/Inf sonlu sayı doğrulaması
from __future__ import annotations

import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import parse_commands


def test_move_rejects_nan_coordinates():
    """MOVE koordinatları NaN ise ERROR ve komut üretilmez."""
    cmds, diags = parse_commands("MOVE nan 1.0", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" and "sonlu" in d.message.lower() for d in diags)


def test_move_rejects_inf_coordinates():
    """MOVE koordinatları Inf ise ERROR."""
    cmds, diags = parse_commands("MOVE 0 inf", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)


def test_speed_rejects_nan():
    """SPEED NaN ise ERROR (sessizce ilerlememeli)."""
    cmds, diags = parse_commands("SPEED nan", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)


def test_forward_rejects_inf():
    """FORWARD Inf ise ERROR."""
    cmds, diags = parse_commands("FORWARD inf", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)


def test_turn_rejects_nan():
    """TURN NaN ise ERROR."""
    cmds, diags = parse_commands("TURN nan", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)


def test_wait_rejects_inf():
    """WAIT Inf ise ERROR."""
    cmds, diags = parse_commands("WAIT inf", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)


def test_move_rel_rejects_nan():
    """MOVE_REL NaN ise ERROR."""
    cmds, diags = parse_commands("MOVE_REL nan 0", strict=False)
    assert cmds == []
    assert any(d.severity == "ERROR" for d in diags)
