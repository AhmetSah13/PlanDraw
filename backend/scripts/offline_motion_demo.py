#!/usr/bin/env python3
"""
Offline mini çizim senaryoları — yalnızca motion facade (HTTP / donanım / eski executor yok).

``execute_command_sequence_motion`` ile rotate-then-go simülasyonu; geliştirici ve öğrenci demoları için.

Kullanım (``backend`` klasöründen)::

    python scripts/offline_motion_demo.py --list
    python scripts/offline_motion_demo.py --scenario square
    python scripts/offline_motion_demo.py -s l_shape -v
    python scripts/offline_motion_demo.py -s square --no-check
    python scripts/offline_motion_demo.py -s turn_forward --strict

Beklenen poz kontrolü: senaryoda tanımlıysa ve ``--no-check`` verilmediyse özetten sonra PASS/FAIL yazdırılır
(toleranslar rotate-then-go simülasyonuna göre gevşek tutulur; tam eşitlik yok).
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.execution.commands import (
    Command,
    ForwardCommand,
    MoveCommand,
    PenCommand,
    SpeedCommand,
    TurnCommand,
    serialize_commands,
)
from app.motion.command_to_segments import wrap_angle_difference_deg
from app.motion.execution_facade import MotionExecutionResult, execute_command_sequence_motion


@dataclass(frozen=True)
class ExpectedPose:
    """İsteğe bağlı beklenen son poz; ``theta_deg`` None ise başlık kontrol edilmez."""

    x: float
    y: float
    theta_deg: Optional[float] = None
    pos_tol_m: float = 0.12
    heading_tol_deg: float = 5.0


@dataclass(frozen=True)
class ScenarioConfig:
    build: Callable[[], List[Command]]
    expected: Optional[ExpectedPose] = None


def _scenario_square() -> List[Command]:
    """Birim kare (köşeler mutlak MOVE), başlangıç (0,0)."""
    return [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(1.0, 0.0),
        MoveCommand(1.0, 1.0),
        MoveCommand(0.0, 1.0),
        MoveCommand(0.0, 0.0),
        PenCommand(is_down=False),
    ]


def _scenario_rectangle() -> List[Command]:
    """2x1 dikdörtgen."""
    return [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(2.0, 0.0),
        MoveCommand(2.0, 1.0),
        MoveCommand(0.0, 1.0),
        MoveCommand(0.0, 0.0),
        PenCommand(is_down=False),
    ]


def _scenario_l_shape() -> List[Command]:
    """L: (0,0)→(2,0)→(2,1)."""
    return [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        MoveCommand(2.0, 0.0),
        MoveCommand(2.0, 1.0),
        PenCommand(is_down=False),
    ]


def _scenario_turn_forward() -> List[Command]:
    """Dön–ileri–dön–ileri (başlık 0’dan)."""
    return [
        SpeedCommand(1.0),
        PenCommand(is_down=True),
        TurnCommand(deg=90.0),
        ForwardCommand(dist=1.0),
        TurnCommand(deg=-90.0),
        ForwardCommand(dist=0.5),
        PenCommand(is_down=False),
    ]


# Beklenen pozlar simülasyon toleransına göre gevşek; tam kapanış yoktur.
SCENARIOS: Dict[str, ScenarioConfig] = {
    "square": ScenarioConfig(
        _scenario_square,
        ExpectedPose(0.0, 0.0, None, pos_tol_m=0.12, heading_tol_deg=5.0),
    ),
    "rectangle": ScenarioConfig(
        _scenario_rectangle,
        ExpectedPose(0.0, 0.0, None, pos_tol_m=0.15, heading_tol_deg=5.0),
    ),
    "l_shape": ScenarioConfig(
        _scenario_l_shape,
        ExpectedPose(2.0, 1.0, None, pos_tol_m=0.12, heading_tol_deg=5.0),
    ),
    "turn_forward": ScenarioConfig(
        _scenario_turn_forward,
        ExpectedPose(0.5, 1.0, 0.0, pos_tol_m=0.15, heading_tol_deg=6.0),
    ),
}


def _print_summary(
    name: str,
    r: MotionExecutionResult,
    cmds: List[Command],
    *,
    verbose: bool,
) -> None:
    print("--- özet ---")
    print("Senaryo:", name)
    print("Komut sayısı (işlenen):", r.commands_executed)
    print("Bitti:", r.done)
    print("Durum:", r.stop_reason)
    print("Son poz (x, y, theta_deg):", f"({r.final_pose.x:.4f}, {r.final_pose.y:.4f}, {r.final_pose.theta_deg:.4f})")
    print("Kalem aşağı:", r.pen_down)
    print("Hız çarpanı:", r.current_speed)
    print("Simüle süre (s):", r.simulated_time_s)
    print("Entegrasyon adımı:", r.motion_integration_steps)
    if verbose:
        print("--- komut özeti (DSL) ---")
        print(serialize_commands(cmds))


def _apply_strict(exp: ExpectedPose, strict: bool) -> ExpectedPose:
    if not strict:
        return exp
    return ExpectedPose(
        x=exp.x,
        y=exp.y,
        theta_deg=exp.theta_deg,
        pos_tol_m=exp.pos_tol_m * 0.5,
        heading_tol_deg=exp.heading_tol_deg * 0.5,
    )


def _check_expected(
    r: MotionExecutionResult,
    exp: ExpectedPose,
) -> Tuple[str, List[str]]:
    """
    SKIP: kontrol yok.
    FAIL: yürütme bitmedi veya tolerans dışı.
    WARN: yürütme bitti; en az bir eksen (1x, 2x] tol bandında.
    PASS: tamam.
    """
    lines: List[str] = []
    if exp.theta_deg is None:
        lines.append("Beklenen başlık: (kontrol yok)")
    else:
        lines.append(f"Beklenen başlık (deg): {exp.theta_deg:.4f} (+/- {exp.heading_tol_deg})")

    lines.append(f"Beklenen konum (x,y): ({exp.x:.4f}, {exp.y:.4f}) (pos_tol={exp.pos_tol_m} m)")

    if not r.done:
        lines.append("Sonuç: FAIL (yürütme tamamlanmadı)")
        return "FAIL", lines

    ax, ay, ath = r.final_pose.x, r.final_pose.y, r.final_pose.theta_deg
    pos_err = max(abs(ax - exp.x), abs(ay - exp.y))
    lines.append(f"Gerçek konum (x,y): ({ax:.4f}, {ay:.4f})")
    lines.append(f"Konum hata (Linf, m): {pos_err:.4f}")

    pos_ok = pos_err <= exp.pos_tol_m
    pos_warn = pos_err <= 2.0 * exp.pos_tol_m

    h_ok = True
    h_warn = True
    h_err = 0.0
    if exp.theta_deg is not None:
        h_err = abs(wrap_angle_difference_deg(ath, exp.theta_deg))
        lines.append(f"Gerçek başlık (deg): {ath:.4f}")
        lines.append(f"Başlık hata (min açı, deg): {h_err:.4f}")
        h_ok = h_err <= exp.heading_tol_deg
        h_warn = h_err <= 2.0 * exp.heading_tol_deg

    if pos_ok and h_ok:
        lines.append("Sonuç: PASS")
        return "PASS", lines

    if pos_warn and h_warn:
        lines.append("Sonuç: WARN (toleransın ~2x bandında, kontrol edin)")
        return "WARN", lines

    lines.append("Sonuç: FAIL (tolerans dışı)")
    return "FAIL", lines


def _print_expectation_block(
    r: MotionExecutionResult,
    exp: ExpectedPose,
    strict: bool,
) -> int:
    exp2 = _apply_strict(exp, strict)
    label, lines = _check_expected(r, exp2)
    print("--- beklenen sonuc ---")
    for ln in lines:
        print(ln)
    if label == "PASS":
        return 0
    if label == "WARN":
        return 0
    return 1


def main() -> int:
    p = argparse.ArgumentParser(description="Offline motion facade mini senaryolar")
    p.add_argument("--list", action="store_true", help="Senaryo adlarını listele")
    p.add_argument("-s", "--scenario", type=str, help="Çalıştırılacak senaryo adı")
    p.add_argument("-v", "--verbose", action="store_true", help="DSL özetini yazdır")
    p.add_argument("--max-steps", type=int, default=100_000, help="Motion adım üst sınırı")
    p.add_argument(
        "--no-check",
        action="store_true",
        help="Beklenen poz doğrulamasını atla",
    )
    p.add_argument(
        "--strict",
        action="store_true",
        help="Beklenen poz toleranslarini yaklasik yariya indir",
    )
    args = p.parse_args()

    if args.list:
        print("Kullanılabilir senaryolar:")
        for k in sorted(SCENARIOS):
            spec = SCENARIOS[k]
            tag = " [beklenen poz]" if spec.expected is not None else ""
            print(" ", k + tag)
        return 0

    if not args.scenario:
        p.error("--scenario veya --list gerekli (yardım: -h)")

    key = args.scenario.strip().lower()
    if key not in SCENARIOS:
        print("Bilinmeyen senaryo:", args.scenario, file=sys.stderr)
        print("Geçerli:", ", ".join(sorted(SCENARIOS)), file=sys.stderr)
        return 2

    spec = SCENARIOS[key]
    cmds = spec.build()
    r = execute_command_sequence_motion(cmds, max_motion_steps_total=args.max_steps)
    _print_summary(key, r, cmds, verbose=args.verbose)

    exit_code = 0 if r.done else 1

    if spec.expected is not None and not args.no_check:
        check_rc = _print_expectation_block(r, spec.expected, strict=args.strict)
        if check_rc != 0:
            exit_code = max(exit_code, check_rc)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
