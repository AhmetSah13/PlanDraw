"""
Bellek içi sahte UART: gerçek port yok; test ve protokol doğrulama için.

Yazılan baytlar birikir; ``readline`` önceden kuyruğa konmuş yanıt satırlarını döner.
Kuyruk boşsa ``readline`` boş bayt döner (bekleyen veri yok / zaman aşımı benzeri).
"""

from __future__ import annotations

from collections import deque
from typing import Deque


class FakeSerialTransport:
    """Yaz/oku hatları ayrı: host ``write`` ile gönderir, MCU yanıtı ``enqueue_line`` ile simüle edilir."""

    def __init__(self) -> None:
        self._written: bytearray = bytearray()
        self._read_queue: Deque[bytes] = deque()

    def write(self, data: bytes) -> int:
        """Gönderilen baytları içeride saklar (gerçek UART yok)."""
        n = len(data)
        self._written.extend(data)
        return n

    def readline(self) -> bytes:
        """
        Önceden kuyruğa eklenmiş bir satır döner (``\\n`` ile biter).

        Kuyruk boşsa ``b\"\"`` döner (okunacak satır yok).
        """
        if not self._read_queue:
            return b""
        return self._read_queue.popleft()

    def enqueue_line(self, line: str) -> None:
        """MCU yanıtını tek satır olarak kuyruğa ekler (sonuna ``\\n`` konur)."""
        if not line.endswith("\n"):
            line = line + "\n"
        self._read_queue.append(line.encode("utf-8"))

    def clear(self) -> None:
        """Testler arası sıfırlama."""
        self._written.clear()
        self._read_queue.clear()

    @property
    def written_bytes(self) -> bytes:
        """Host tarafından yazılmış toplam baytlar."""
        return bytes(self._written)

    def written_text(self, *, encoding: str = "utf-8") -> str:
        """Yazılan baytları metin olarak (UTF-8 varsayılan)."""
        return self._written.decode(encoding)
