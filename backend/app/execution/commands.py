from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple, Union, Optional, Literal


@dataclass
class SpeedCommand:
    speed: float


@dataclass
class PenCommand:
    is_down: bool


@dataclass
class MoveCommand:
    x: float
    y: float


@dataclass
class MoveRelCommand:
    dx: float
    dy: float


@dataclass
class WaitCommand:
    seconds: float


@dataclass
class TurnCommand:
    deg: float


@dataclass
class ForwardCommand:
    dist: float


Command = Union[
    SpeedCommand,
    PenCommand,
    MoveCommand,
    MoveRelCommand,
    WaitCommand,
    TurnCommand,
    ForwardCommand,
]


# --- Diagnostics (hata/uyarı) ---

Severity = Literal["ERROR", "WARN"]


@dataclass
class Diagnostic:
    severity: Severity
    line: int
    message: str
    text: str


class CommandParseError(ValueError):
    def __init__(self, diagnostic: Diagnostic) -> None:
        super().__init__(
            f"{diagnostic.severity} line {diagnostic.line}: {diagnostic.message} | {diagnostic.text}",
        )
        self.diagnostic = diagnostic


def serialize_commands(commands: List[Command]) -> str:
    """
    Komut listesini metin temsiline çevirir.

    Not: DEF/ENDDEF gibi macro tanımları serialize edilmez; çünkü parse-time unroll/expand sonrası
    executor zaten düz bir Command listesi görür.
    """
    satirlar: List[str] = []

    for cmd in commands:
        if isinstance(cmd, SpeedCommand):
            satirlar.append(f"SPEED {cmd.speed}")
        elif isinstance(cmd, PenCommand):
            durumu = "DOWN" if cmd.is_down else "UP"
            satirlar.append(f"PEN {durumu}")
        elif isinstance(cmd, MoveCommand):
            satirlar.append(f"MOVE {cmd.x} {cmd.y}")
        elif isinstance(cmd, MoveRelCommand):
            satirlar.append(f"MOVE_REL {cmd.dx} {cmd.dy}")
        elif isinstance(cmd, WaitCommand):
            satirlar.append(f"WAIT {cmd.seconds}")
        elif isinstance(cmd, TurnCommand):
            satirlar.append(f"TURN {cmd.deg}")
        elif isinstance(cmd, ForwardCommand):
            satirlar.append(f"FORWARD {cmd.dist}")
        else:
            continue

    return "\n".join(satirlar)


def parse_commands(text: str, *, strict: bool = False) -> Tuple[List[Command], List[Diagnostic]]:
    """
    Komut metnini parse eder.

    - strict=False: hatalı satırları atlar, diagnostics döndürür
    - strict=True : ilk ERROR'da CommandParseError fırlatır

    Dil özellikleri:

    REPEAT/END:
        REPEAT N
            ...
        END
    Parse aşamasında unroll edilir (executor düz liste görür).

    Macro (DEF/CALL):
        DEF name
            ... komutlar (REPEAT/CALL dahil) ...
        ENDDEF

        CALL name

    Macro çağrıları parse aşamasında expand edilir.
    Recursive macro çağrıları (A->A veya A->B->A) ERROR üretir.
    """

    diagnostics: List[Diagnostic] = []

    # Macro havuzu: name -> (body_commands, def_line)
    macros: Dict[str, Tuple[List[Command], int]] = {}

    def emit(sev: Severity, line: int, msg: str, raw_line: str) -> None:
        d = Diagnostic(severity=sev, line=line, message=msg, text=raw_line.rstrip("\n"))
        if sev == "ERROR" and strict:
            raise CommandParseError(d)
        diagnostics.append(d)

    # --- REPEAT stack yardımcıları ---
    # Stack frame: (repeat_count, collected_commands, start_line)
    RepeatFrame = Tuple[int, List[Command], int]

    def unroll_stack_to_base(stack: List[RepeatFrame]) -> None:
        """Açık kalan REPEAT bloklarını kapatıp unroll eder (WARN)."""
        while len(stack) > 1:
            repeat_n, block_cmds, start_line = stack.pop()
            emit(
                "WARN",
                start_line,
                f"REPEAT bloğu END ile kapanmadı -> otomatik kapatıldı (x{repeat_n})",
                "",
            )
            expanded: List[Command] = []
            for _ in range(repeat_n):
                expanded.extend(block_cmds)
            stack[-1][1].extend(expanded)

    def close_one_repeat(stack: List[RepeatFrame], end_line: int, raw_line: str) -> bool:
        """END geldiğinde tek bir REPEAT bloğunu kapatır. Kapatabildiyse True."""
        if len(stack) <= 1:
            emit("WARN", end_line, "Fazla END (eşleşen REPEAT yok) -> yok sayıldı", raw_line)
            return False
        repeat_n, block_cmds, _start_line = stack.pop()
        expanded: List[Command] = []
        for _ in range(repeat_n):
            expanded.extend(block_cmds)
        stack[-1][1].extend(expanded)
        return True

    def push_repeat(stack: List[RepeatFrame], n: int, line_no: int) -> None:
        stack.append((n, [], line_no))

    def add_cmd_to_stack(stack: List[RepeatFrame], cmd: Command) -> None:
        stack[-1][1].append(cmd)

    # --- Macro expansion ---
    def expand_macro(
        name: str,
        call_line: int,
        call_raw: str,
        call_stack: List[str],
    ) -> List[Command]:
        """Macro'yu expand eder; komut listesini olduğu gibi döndürür (TURN/FORWARD runtime'da işlenir)."""
        if name not in macros:
            emit("ERROR", call_line, f"Tanımsız macro: {name!r}", call_raw)
            return []

        if name in call_stack:
            chain = " -> ".join(call_stack + [name])
            emit("ERROR", call_line, f"Recursive macro CALL tespit edildi: {chain}", call_raw)
            return []

        body, _def_line = macros[name]
        call_stack.append(name)
        expanded: List[Command] = list(body)
        call_stack.pop()
        return expanded

    # --- Parse state: DEF içinde miyiz? ---
    current_def_name: Optional[str] = None
    current_def_line: int = 0
    current_def_stack: Optional[List[RepeatFrame]] = None

    # Root komutları da REPEAT stack ile toplanır
    root_stack: List[RepeatFrame] = [(1, [], 0)]

    lines = text.splitlines()
    for i, satir in enumerate(lines, start=1):
        ham = satir.strip()
        if not ham or ham.startswith("#"):
            continue

        parcalar = ham.split()
        etiket = parcalar[0].upper()

        # Hedef stack: DEF içindeysek current_def_stack, değilsek root_stack
        stack = current_def_stack if current_def_stack is not None else root_stack

        # --- DEF/ENDDEF ---
        if etiket == "DEF":
            if len(parcalar) != 2:
                emit("ERROR", i, "DEF tek argüman ister: DEF name", satir)
                continue
            name = parcalar[1]
            if current_def_name is not None:
                emit("ERROR", i, f"Nested DEF desteklenmiyor (zaten DEF {current_def_name!r} içindesin)", satir)
                continue
            current_def_name = name
            current_def_line = i
            current_def_stack = [(1, [], i)]
            continue

        if etiket == "ENDDEF":
            if len(parcalar) != 1:
                emit("ERROR", i, "ENDDEF tek başına kullanılmalı", satir)
                continue
            if current_def_name is not None and current_def_stack is not None:
                # DEF içindeki açık REPEAT'leri kapat
                unroll_stack_to_base(current_def_stack)
                body_cmds = current_def_stack[0][1]

                # Aynı isimle yeniden tanımlama
                if current_def_name in macros:
                    emit(
                        "WARN",
                        i,
                        f"Macro {current_def_name!r} yeniden tanımlandı -> önceki tanım üzerine yazıldı",
                        satir,
                    )

                macros[current_def_name] = (body_cmds, current_def_line)

                # DEF modundan çık
                current_def_name = None
                current_def_line = 0
                current_def_stack = None
            else:
                emit("WARN", i, "Fazla ENDDEF (eşleşen DEF yok) -> yok sayıldı", satir)
            continue

        # --- CALL ---
        if etiket == "CALL":
            if len(parcalar) != 2:
                emit("ERROR", i, "CALL tek argüman ister: CALL name", satir)
                continue
            name = parcalar[1]

            expanded_cmds = expand_macro(name, i, satir, call_stack=[])
            for cmd in expanded_cmds:
                add_cmd_to_stack(stack, cmd)
            continue

        if etiket == "CALL_LOCAL":
            if len(parcalar) != 2:
                emit("ERROR", i, "CALL_LOCAL tek argüman ister: CALL_LOCAL name", satir)
                continue
            name = parcalar[1]
            expanded_cmds = expand_macro(name, i, satir, call_stack=[])
            for cmd in expanded_cmds:
                add_cmd_to_stack(stack, cmd)
            continue

        # --- REPEAT/END ---
        if etiket == "REPEAT":
            if len(parcalar) != 2:
                emit("ERROR", i, "REPEAT tek argüman ister: REPEAT N", satir)
                continue
            try:
                n = int(parcalar[1])
            except ValueError:
                emit("ERROR", i, f"REPEAT sayısal olmalı, gelen: {parcalar[1]!r}", satir)
                continue
            if n <= 0:
                emit("ERROR", i, f"REPEAT 1 veya daha büyük olmalı, gelen: {n}", satir)
                continue
            push_repeat(stack, n, i)
            continue

        if etiket == "END":
            if len(parcalar) != 1:
                emit("ERROR", i, "END tek başına kullanılmalı", satir)
                continue
            close_one_repeat(stack, i, satir)
            continue

        # --- Normal komutlar (TURN/FORWARD runtime'da executor'da işlenir) ---
        if etiket == "TURN":
            if len(parcalar) != 2:
                emit("ERROR", i, "TURN tek argüman ister: TURN deg", satir)
                continue
            try:
                delta = float(parcalar[1])
            except ValueError:
                emit("ERROR", i, f"TURN sayısal olmalı, gelen: {parcalar[1]!r}", satir)
                continue
            add_cmd_to_stack(stack, TurnCommand(deg=delta))
            continue

        if etiket == "FORWARD":
            if len(parcalar) != 2:
                emit("ERROR", i, "FORWARD tek argüman ister: FORWARD dist", satir)
                continue
            try:
                dist = float(parcalar[1])
            except ValueError:
                emit("ERROR", i, f"FORWARD sayısal olmalı, gelen: {parcalar[1]!r}", satir)
                continue
            add_cmd_to_stack(stack, ForwardCommand(dist=dist))
            continue

        if etiket == "SPEED":
            if len(parcalar) != 2:
                emit("ERROR", i, "SPEED tek argüman ister: SPEED v", satir)
                continue
            try:
                hiz = float(parcalar[1])
            except ValueError:
                emit("ERROR", i, f"SPEED sayısal olmalı, gelen: {parcalar[1]!r}", satir)
                continue
            if hiz < 0:
                emit("WARN", i, f"Negatif SPEED ({hiz}) -> 0'a çekildi", satir)
                hiz = 0.0
            add_cmd_to_stack(stack, SpeedCommand(speed=hiz))
            continue

        if etiket == "PEN":
            if len(parcalar) != 2:
                emit("ERROR", i, "PEN tek argüman ister: PEN UP/DOWN", satir)
                continue
            durum = parcalar[1].upper()
            if durum == "DOWN":
                add_cmd_to_stack(stack, PenCommand(is_down=True))
            elif durum == "UP":
                add_cmd_to_stack(stack, PenCommand(is_down=False))
            else:
                emit("ERROR", i, f"PEN yalnızca UP veya DOWN olabilir, gelen: {parcalar[1]!r}", satir)
            continue

        if etiket == "MOVE":
            if len(parcalar) != 3:
                emit("ERROR", i, "MOVE iki argüman ister: MOVE x y", satir)
                continue
            try:
                x = float(parcalar[1])
                y = float(parcalar[2])
            except ValueError:
                emit(
                    "ERROR",
                    i,
                    f"MOVE koordinatları sayısal olmalı, gelen: {parcalar[1:]}",
                    satir,
                )
                continue
            add_cmd_to_stack(stack, MoveCommand(x=x, y=y))
            continue

        if etiket == "MOVE_REL":
            if len(parcalar) != 3:
                emit("ERROR", i, "MOVE_REL iki argüman ister: MOVE_REL dx dy", satir)
                continue
            try:
                dx = float(parcalar[1])
                dy = float(parcalar[2])
            except ValueError:
                emit(
                    "ERROR",
                    i,
                    f"MOVE_REL koordinatları sayısal olmalı, gelen: {parcalar[1:]}",
                    satir,
                )
                continue
            add_cmd_to_stack(stack, MoveRelCommand(dx=dx, dy=dy))
            continue

        if etiket == "WAIT":
            if len(parcalar) != 2:
                emit("ERROR", i, "WAIT tek argüman ister: WAIT t", satir)
                continue
            try:
                secs = float(parcalar[1])
            except ValueError:
                emit("ERROR", i, f"WAIT sayısal olmalı, gelen: {parcalar[1]!r}", satir)
                continue
            if secs < 0:
                emit("WARN", i, f"Negatif WAIT ({secs}) -> 0'a çekildi", satir)
                secs = 0.0
            add_cmd_to_stack(stack, WaitCommand(seconds=secs))
            continue

        # Bilinmeyen komut
        emit("ERROR", i, f"Bilinmeyen komut: {parcalar[0]!r}", satir)

    # Dosya bitti: açık macro varsa kapat
    if current_def_name is not None and current_def_stack is not None:
        # Macro içindeki açık REPEAT'leri kapat
        unroll_stack_to_base(current_def_stack)
        body_cmds = current_def_stack[0][1]
        emit(
            "WARN",
            current_def_line,
            f"DEF {current_def_name!r} ENDDEF ile kapanmadı -> otomatik kapatıldı",
            "",
        )
        if current_def_name in macros:
            emit(
                "WARN",
                current_def_line,
                f"Macro {current_def_name!r} yeniden tanımlandı -> önceki tanım üzerine yazıldı",
                "",
            )
        macros[current_def_name] = (body_cmds, current_def_line)

        # DEF modundan çık (temizlik)
        current_def_name = None
        current_def_stack = None

    # Root'ta açık REPEAT blokları
    unroll_stack_to_base(root_stack)

    return root_stack[0][1], diagnostics

