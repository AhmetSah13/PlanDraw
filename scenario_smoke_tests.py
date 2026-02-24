# scenario_smoke_tests.py
from __future__ import annotations

import math
from typing import List, Tuple

from commands import (
    parse_commands,
    CommandParseError,
    Diagnostic,
    MoveCommand,
    MoveRelCommand,
    WaitCommand,
    SpeedCommand,
    PenCommand,
    TurnCommand,
    ForwardCommand,
)

# Eğer scenario_analysis.py eklediysen (dry-run/bounds/istatistik için)
try:
    from scenario_analysis import analyze_commands
except Exception:
    analyze_commands = None  # type: ignore


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def almost(a: float, b: float, eps: float = 1e-6) -> bool:
    return abs(a - b) <= eps


def parse_ok(text: str):
    cmds, diags = parse_commands(text, strict=False)
    # ERROR diagnostic var mı?
    err = [d for d in diags if d.severity == "ERROR"]
    assert_true(len(err) == 0, f"Beklenmeyen ERROR diagnostics: {err}")
    return cmds, diags


def parse_has_errors(text: str) -> List[Diagnostic]:
    cmds, diags = parse_commands(text, strict=False)
    err = [d for d in diags if d.severity == "ERROR"]
    assert_true(len(err) > 0, "ERROR bekleniyordu ama yok")
    return diags


def test_repeat_unroll_count() -> None:
    text = """
    SPEED 100
    REPEAT 3
        MOVE 10 0
        WAIT 0.5
    END
    """
    cmds, _ = parse_ok(text)
    move_count = sum(1 for c in cmds if isinstance(c, MoveCommand))
    wait_count = sum(1 for c in cmds if isinstance(c, WaitCommand))
    assert_true(move_count == 3, f"move_count=3 bekleniyordu, geldi: {move_count}")
    assert_true(wait_count == 3, f"wait_count=3 bekleniyordu, geldi: {wait_count}")


def test_nested_repeat_unroll() -> None:
    text = """
    REPEAT 2
        REPEAT 2
            MOVE 1 1
        END
    END
    """
    cmds, _ = parse_ok(text)
    move_count = sum(1 for c in cmds if isinstance(c, MoveCommand))
    assert_true(move_count == 4, f"nested repeat 4 move bekleniyordu, geldi: {move_count}")


def test_wait_negative_clamped_or_warn() -> None:
    # Senin parser sürümünde negatif WAIT -> WARN ve 0'a çekiliyor
    text = "WAIT -2"
    cmds, diags = parse_commands(text, strict=False)
    # hata değil, warn bekliyoruz
    err = [d for d in diags if d.severity == "ERROR"]
    assert_true(len(err) == 0, f"ERROR olmamalıydı: {err}")
    wait_cmds = [c for c in cmds if isinstance(c, WaitCommand)]
    assert_true(len(wait_cmds) == 1, "1 adet WAIT komutu bekleniyordu")
    assert_true(wait_cmds[0].seconds >= 0, "WAIT negatif kalmamalı")


def test_turn_forward_produces_commands() -> None:
    # TURN/FORWARD artık runtime'da işlenir; parse çıktısı TurnCommand ve ForwardCommand
    text = """
    TURN 90
    FORWARD 10
    """
    cmds, _ = parse_ok(text)
    turns = [c for c in cmds if isinstance(c, TurnCommand)]
    fwds = [c for c in cmds if isinstance(c, ForwardCommand)]
    assert_true(len(turns) == 1, f"1 TURN bekleniyordu, geldi: {len(turns)}")
    assert_true(len(fwds) == 1, f"1 FORWARD bekleniyordu, geldi: {len(fwds)}")
    assert_true(almost(turns[0].deg, 90.0, 1e-6), f"TURN 90 olmalı, geldi: {turns[0].deg}")
    assert_true(almost(fwds[0].dist, 10.0, 1e-6), f"FORWARD 10 olmalı, geldi: {fwds[0].dist}")


def test_call_vs_call_local_heading_effect() -> None:
    # CALL ve CALL_LOCAL aynı komut listesini expand eder (TURN/FORWARD runtime'da).
    # Executor (0,0)'dan çalışınca TURN 90 + FORWARD 10 => (0, 10).
    from executor import CommandExecutor

    text_call = """
    SPEED 20
    DEF right
        TURN 90
    ENDDEF

    CALL right
    FORWARD 10
    """
    cmds, diags = parse_commands(text_call, strict=False)
    errs = [d for d in diags if d.severity == "ERROR"]
    if errs:
        print("SKIP test_call_vs_call_local_heading_effect (macro/CALL yok gibi):", errs[0].message)
        return

    # Expand'de TurnCommand ve ForwardCommand olmalı; executor (0,0) => (0, 10)
    turn_cmds = [c for c in cmds if isinstance(c, TurnCommand)]
    fwd_cmds = [c for c in cmds if isinstance(c, ForwardCommand)]
    assert_true(len(turn_cmds) >= 1 and len(fwd_cmds) >= 1, "TURN ve FORWARD bekleniyordu")
    ex = CommandExecutor(cmds)
    pos = (0.0, 0.0)
    while not ex.finished:
        pos, _ = ex.update(0.5, pos)
    assert_true(almost(pos[0], 0.0, 1e-5), f"CALL: son x ~0, geldi {pos[0]}")
    assert_true(almost(pos[1], 10.0, 1e-5), f"CALL: son y ~10, geldi {pos[1]}")

    text_local = """
    SPEED 20
    DEF right
        TURN 90
    ENDDEF

    CALL_LOCAL right
    FORWARD 10
    """
    cmds2, diags2 = parse_commands(text_local, strict=False)
    errs2 = [d for d in diags2 if d.severity == "ERROR"]
    if errs2:
        print("SKIP test_call_vs_call_local_heading_effect (CALL_LOCAL yok gibi):", errs2[0].message)
        return

    # CALL_LOCAL de aynı expand (heading runtime); (0,0) => (0, 10)
    ex2 = CommandExecutor(cmds2)
    pos2 = (0.0, 0.0)
    while not ex2.finished:
        pos2, _ = ex2.update(0.5, pos2)
    assert_true(almost(pos2[0], 0.0, 1e-5), f"CALL_LOCAL: son x ~0, geldi {pos2[0]}")
    assert_true(almost(pos2[1], 10.0, 1e-5), f"CALL_LOCAL: son y ~10, geldi {pos2[1]}")


def test_strict_mode_raises() -> None:
    bad = "UNKNOWN 123"
    try:
        parse_commands(bad, strict=True)
        raise AssertionError("strict=True iken CommandParseError bekleniyordu")
    except CommandParseError:
        pass


def test_analyze_commands_bounds_if_available() -> None:
    if analyze_commands is None:
        print("SKIP test_analyze_commands_bounds_if_available (scenario_analysis import yok)")
        return

    # Start (0,0), bir kare: sağ 10, yukarı 10, sol 10, aşağı 10
    text = """
    FORWARD 10
    TURN 90
    FORWARD 10
    TURN 90
    FORWARD 10
    TURN 90
    FORWARD 10
    """
    cmds, _ = parse_ok(text)
    stats, _ = analyze_commands(cmds, start=(0.0, 0.0))
    minx, miny, maxx, maxy = stats.bounds
    assert_true(almost(minx, 0.0), f"minx 0 olmalı, geldi {minx}")
    assert_true(almost(miny, 0.0), f"miny 0 olmalı, geldi {miny}")
    assert_true(almost(maxx, 10.0), f"maxx 10 olmalı, geldi {maxx}")
    assert_true(almost(maxy, 10.0), f"maxy 10 olmalı, geldi {maxy}")


def run_all() -> None:
    tests = [
        test_repeat_unroll_count,
        test_nested_repeat_unroll,
        test_wait_negative_clamped_or_warn,
        test_turn_forward_produces_commands,
        test_call_vs_call_local_heading_effect,
        test_strict_mode_raises,
        test_analyze_commands_bounds_if_available,
    ]

    passed = 0
    failed = 0
    for t in tests:
        name = t.__name__
        try:
            t()
            print(f"PASS  {name}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL  {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            failed += 1

    print("-" * 40)
    print(f"TOTAL: {passed} passed, {failed} failed")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run_all()
