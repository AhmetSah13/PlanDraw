"""
SERIAL_PROTOCOL_V1: host tarafı çerçeveleme ve MCU yanıt satırı ayrıştırma.

Taşıma (UART) burada yok; yalnızca metin/bayt üretimi ve satır ayrıştırması.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal

# Spesifikasyon: host gönderiminde LF yeterli
LINE_END = "\n"


class SerialWireProfile(str, Enum):
    """Profil A: düz DSL satırları. Profil B: BEGIN / DSL / END."""

    A = "A"
    B = "B"


@dataclass(frozen=True)
class ParsedResponse:
    """Tek bir MCU yanıt satırının ayrıştırılmış hali."""

    kind: Literal["ok", "done", "err", "status", "unknown"]
    text: str | None = None
    """ERR/STATUS için ek metin; bilinmeyen satırın tamamı için."""


def frame_dsl_payload(dsl_text: str, *, profile: SerialWireProfile | str = SerialWireProfile.A) -> str:
    """
    ``serialize_commands`` çıktısını v1 satır sonlarıyla normalize eder.

    - Profil A: yalnızca DSL satırları (BEGIN/END yok).
    - Profil B: ``BEGIN``, DSL satırları, ``END`` — her kayıt ``LINE_END`` ile biter.
    """
    prof = SerialWireProfile(profile) if isinstance(profile, str) else profile
    core = dsl_text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    lines = core.split("\n") if core else []

    if prof == SerialWireProfile.A:
        if not lines:
            return ""
        return LINE_END.join(lines) + LINE_END

    if not lines:
        return "BEGIN" + LINE_END + "END" + LINE_END
    return "BEGIN" + LINE_END + LINE_END.join(lines) + LINE_END + "END" + LINE_END


def frame_stop_line() -> str:
    """Tek satırlık STOP komutu (satır sonu dahil)."""
    return "STOP" + LINE_END


def wire_text_to_bytes(text: str) -> bytes:
    """UTF-8 wire baytları."""
    return text.encode("utf-8")


def parse_response_line(raw: str | bytes) -> ParsedResponse:
    """
    MCU'dan gelen tek satırı ayrıştırır (``\\n`` öncesi gövde).

    ``OK``, ``DONE``, ``ERR ...``, ``STATUS ...``; diğerleri ``unknown``.
    """
    if isinstance(raw, bytes):
        try:
            line = raw.decode("utf-8")
        except UnicodeDecodeError:
            return ParsedResponse(kind="unknown", text=repr(raw))
    else:
        line = raw
    s = line.strip("\r\n")

    if s == "OK":
        return ParsedResponse(kind="ok", text=None)
    if s == "DONE":
        return ParsedResponse(kind="done", text=None)
    upper = s.upper()
    if upper.startswith("ERR"):
        rest = s[3:].strip()
        if rest.startswith(" "):
            rest = rest[1:]
        return ParsedResponse(kind="err", text=rest or None)
    if upper.startswith("STATUS"):
        rest = s[6:].strip()
        if rest.startswith(" "):
            rest = rest[1:]
        return ParsedResponse(kind="status", text=rest or None)
    return ParsedResponse(kind="unknown", text=s)
