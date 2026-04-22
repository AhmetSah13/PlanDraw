"""
Donanım sürücüleri için resmi sınır (hardware abstraction).

Resmi çekirdek akışta komutlar derlenip veya ayrıştırıldıktan sonra uygulama
içi temsil ``List[Command]`` (``app.execution.commands``) olarak kalır.
Bu protokol, gelecekteki seri port / ROS / dosya vb. sürücülerin **aynı
türü** tüketmesi için tasarlanmıştır.

Metin DSL (``serialize_commands``) ve dışa aktarım formatları
(``export_commands_to_string``: robot_v1, gcode_lite, …) bu listeye
**türetilmiş görünümler**dir; sürücü katmanının birincil girdisi metin
değil, ``List[Command]`` olmalıdır.

İleride daha zengin bir ``DriverResult`` veya durum sözleşmesi eklenebilir;
şu an minimal sözlük dönüşü yeterlidir.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.execution.commands import Command


class RobotDriver(Protocol):
    """Resmi robot sürücü arayüzü (protokol)."""

    def connect(self) -> None:
        """Bağlantı / oturum başlat (gerçek donanımda seri/ROS hazırlığı)."""

    def disconnect(self) -> None:
        """Bağlantıyı kapat."""

    def stop(self) -> None:
        """Acil durdurma veya yürütmeyi kes (uygulama politikasına göre)."""

    def get_status(self) -> dict[str, Any]:
        """Sürücü durumu; en azından tanımlayıcı ve bağlantı bilgisi dönebilir."""

    def send_commands(
        self,
        commands: list[Command],
        *,
        start: tuple[float, float] = (0.0, 0.0),
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Komut listesini ilet; uygulama tek seferde tam gönderir."""
