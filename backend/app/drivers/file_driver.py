"""
``List[Command]`` alıp dosyaya yazan sürücü (donanım yok).

İlk sürümde iki çıktı modu vardır:

- **dsl** (varsayılan): `serialize_commands` ile resmi DSL metni. Aynı çekirdek
  serileştirme; NullDriver’ın DSL ile tutarlı, üst bilgi yok, deterministik.
- **robot_v1**: `export_commands_to_string(..., format="robot_v1")` ile HTTP
  export ile aynı aile üretim; başlık ve analiz satırları içerir.

HTTP veya gerçek donanım yoktur; yalnızca dosya I/O.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from app.execution.commands import Command, serialize_commands

FileDriverOutputMode = Literal["dsl", "robot_v1"]


class FileDriver:
    """Komut listesini verilen yola yazar; `RobotDriver` protokolüne uygundur."""

    def __init__(
        self,
        output_path: str | Path,
        *,
        mode: FileDriverOutputMode = "dsl",
        encoding: str = "utf-8",
    ) -> None:
        self._path = Path(output_path)
        self._mode: FileDriverOutputMode = mode
        self._encoding = encoding
        self._connected = False
        self._stopped = False
        self._last_commands: list[Command] = []
        self._last_start: tuple[float, float] = (0.0, 0.0)
        self._last_metadata: dict[str, Any] | None = None
        self._last_write_succeeded = False
        self._last_error: str | None = None

    def connect(self) -> None:
        self._connected = True
        self._stopped = False

    def disconnect(self) -> None:
        self._connected = False

    def stop(self) -> None:
        self._stopped = True

    def _render_text(self, commands: list[Command], start: tuple[float, float]) -> str:
        if self._mode == "dsl":
            return serialize_commands(commands)
        # Gecikmeli içe aktarma: app.execution yüklenirken döngüyü önler.
        from app.analysis.scenario_analysis import export_commands_to_string

        content, _blocked, _stats, _diags = export_commands_to_string(
            commands,
            start,
            limits=None,
            format="robot_v1",
        )
        return content

    def send_commands(
        self,
        commands: list[Command],
        *,
        start: tuple[float, float] = (0.0, 0.0),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._last_commands = list(commands)
        self._last_start = (float(start[0]), float(start[1]))
        self._last_metadata = dict(metadata) if metadata is not None else None
        text = self._render_text(commands, self._last_start)
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(text, encoding=self._encoding)
            self._last_write_succeeded = True
            self._last_error = None
        except OSError as exc:
            self._last_write_succeeded = False
            self._last_error = str(exc)

    def get_status(self) -> dict[str, Any]:
        return {
            "connected": self._connected,
            "driver_name": "file",
            "last_command_count": len(self._last_commands),
            "output_path": str(self._path),
            "output_mode": self._mode,
            "last_write_succeeded": self._last_write_succeeded,
            "last_error": self._last_error,
            "stopped": self._stopped,
            "last_start": list(self._last_start),
        }

    @property
    def output_path(self) -> Path:
        return self._path
