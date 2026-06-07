#!/usr/bin/env python3
"""
Donanım üzerinde loopback firmware ile SerialDriver duman testi.

Gereksinim: pyserial, firmware `firmware/newbot_loopback_v1/` (115200 baud, profil B).

Kullanım (backend klasöründen):

    python scripts/smoke_test_serial_loopback.py COM3
    python scripts/smoke_test_serial_loopback.py /dev/ttyUSB0 --baudrate 115200
    python scripts/smoke_test_serial_loopback.py COM3 --mode stop
    python scripts/smoke_test_serial_loopback.py COM3 --mode malformed
    python scripts/smoke_test_serial_loopback.py COM3 --mode status

Başarı: ``normal`` / ``stop`` modlarında ``DONE``; ``malformed`` modunda ``ERR``; ``status`` modunda ``STATUS ...`` satırı.
HTTP veya API kullanılmaz.
"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from app.drivers.serial_driver import SerialDriver
from app.drivers.socket_driver import SocketDriver
from app.execution.commands import Command, ForwardCommand, PenCommand, SpeedCommand


def _batch_summary(commands: list[Command]) -> str:
    from app.execution.commands import serialize_commands

    return serialize_commands(commands).replace("\n", " | ")


def _parse_status_kv_line(line: str) -> dict[str, str] | None:
    """
    `STATUS key=value ...` biçimini basitçe ayrıştırır.

    Değerleri string bırakır. Hatalı/uyumsuz satırlarda `None` döner.
    """
    if not line:
        return None
    s = line.strip()
    if not s:
        return None
    if not s.upper().startswith("STATUS "):
        return None

    rest = s[7:].strip()  # "STATUS " = 7 karakter
    if not rest:
        return None

    out: dict[str, str] = {}
    tokens = rest.split()
    for tok in tokens:
        if "=" not in tok:
            # Çok gevşek tutmak yerine, yalnızca `key=value` tokenlarını toplayalım.
            continue
        key, val = tok.split("=", 1)
        if not key:
            continue
        out[key] = val

    return out if out else None


def run_normal(port: str, baudrate: int, timeout_s: float) -> int:
    cmds = [
        SpeedCommand(1.0),
        PenCommand(is_down=False),
        PenCommand(is_down=True),
        ForwardCommand(0.05),
    ]
    print("--- normal mod ---")
    print("Komut özeti:", _batch_summary(cmds))
    drv = SerialDriver(port, baudrate=baudrate, timeout_s=timeout_s)
    drv.connect()
    try:
        drv.send_commands(cmds)
        print("Sonuç: BAŞARILI (MCU DONE)")
        return 0
    except Exception as exc:
        print("Sonuç: BAŞARISIZ:", exc)
        return 1
    finally:
        drv.disconnect()


def run_stop(port: str, baudrate: int, timeout_s: float) -> int:
    cmds = [SpeedCommand(1.0), ForwardCommand(0.02)]
    print("--- stop modu (batch sonrası STOP) ---")
    print("Komut özeti:", _batch_summary(cmds))
    drv = SerialDriver(port, baudrate=baudrate, timeout_s=timeout_s)
    drv.connect()
    try:
        drv.send_commands(cmds)
        print("Batch tamam, STOP gönderiliyor...")
        drv.stop()
        print("Sonuç: BAŞARILI (STOP sonrası DONE)")
        return 0
    except Exception as exc:
        print("Sonuç: BAŞARISIZ:", exc)
        return 1
    finally:
        drv.disconnect()


def run_malformed(port: str, baudrate: int, timeout_s: float) -> int:
    """
    Geçersiz DSL satırı: SerialDriver yerine ham pyserial (çerçeve hatalı gövde).
    Beklenti: firmware ERR parse.
    """
    try:
        import serial
    except ImportError:
        print("pyserial yüklü değil.")
        return 2

    print("--- malformed mod (ham seri, hatalı MOVE) ---")
    payload = b"BEGIN\nMOVE\nEND\n"
    print("Gönderilen (bytes):", payload)
    ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)
    try:
        ser.write(payload)
        raw = ser.readline()
        print("Gelen satır:", raw.decode("utf-8", errors="replace").strip())
        if raw.startswith(b"ERR"):
            print("Sonuç: BAŞARILI (MCU ERR beklenen)")
            return 0
        print("Sonuç: BEKLENMEDİ (ERR yok)")
        return 1
    except Exception as exc:
        print("Sonuç: BAŞARISIZ:", exc)
        return 1
    finally:
        ser.close()


def run_status(port: str, baudrate: int, timeout_s: float) -> int:
    """
    Firmware STATUS sorgusu: tek satır gönder, tek satır oku (SerialDriver batch API'si yok).
    """
    try:
        import serial
    except ImportError:
        print("pyserial yüklü değil.")
        return 2

    print("--- status modu (STATUS -> MCU tek satır yanıt) ---")
    print("Gönderilen: STATUS + satır sonu (LF)")
    ser = serial.Serial(port=port, baudrate=baudrate, timeout=timeout_s)
    try:
        ser.write(b"STATUS\n")
        raw = ser.readline()
        text = raw.decode("utf-8", errors="replace").strip()
        print("Gelen satır:", text)
        if not raw:
            print("Sonuç: BAŞARISIZ (boş yanıt, zaman aşımı veya kesik okuma)")
            return 1
        if text.startswith("STATUS "):
            print("Sonuç: BAŞARILI (MCU STATUS yanıtı)")
            parsed = _parse_status_kv_line(text)
            if parsed is not None:
                print("Ayrıştırılan:", parsed)
            else:
                print("Ayrıştırma: başarısız (biçim beklenen kadar basit değil)")
            return 0
        print("Sonuç: BAŞARISIZ (satır 'STATUS ' ile başlamıyor)")
        return 1
    except Exception as exc:
        print("Sonuç: BAŞARISIZ:", exc)
        return 1
    finally:
        ser.close()


def run_socket_normal(host: str, port: int, timeout_s: float) -> int:
    cmds = [
        SpeedCommand(1.0),
        PenCommand(is_down=False),
        PenCommand(is_down=True),
        ForwardCommand(0.05),
    ]
    print("--- socket normal mod ---")
    print("Komut ozeti:", _batch_summary(cmds))
    drv = SocketDriver(host=host, port=port, timeout_s=timeout_s)
    drv.connect()
    try:
        drv.send_commands(cmds)
        print("Sonuc: BASARILI (responder DONE)")
        return 0
    except Exception as exc:
        print("Sonuc: BASARISIZ:", exc)
        return 1
    finally:
        drv.disconnect()


def run_socket_stop(host: str, port: int, timeout_s: float) -> int:
    cmds = [SpeedCommand(1.0), ForwardCommand(0.02)]
    print("--- socket stop modu (batch sonrasi STOP) ---")
    print("Komut ozeti:", _batch_summary(cmds))
    drv = SocketDriver(host=host, port=port, timeout_s=timeout_s)
    drv.connect()
    try:
        drv.send_commands(cmds)
        print("Batch tamam, STOP gonderiliyor...")
        drv.stop()
        print("Sonuc: BASARILI (STOP sonrasi DONE)")
        return 0
    except Exception as exc:
        print("Sonuc: BASARISIZ:", exc)
        return 1
    finally:
        drv.disconnect()


def _socket_roundtrip(host: str, port: int, timeout_s: float, payload: bytes) -> bytes:
    with socket.create_connection((host, port), timeout=timeout_s) as sock:
        sock.settimeout(timeout_s)
        sock.sendall(payload)
        reader = sock.makefile("rb")
        try:
            return reader.readline()
        finally:
            reader.close()


def run_socket_malformed(host: str, port: int, timeout_s: float) -> int:
    print("--- socket malformed mod (hatali MOVE) ---")
    payload = b"BEGIN\nMOVE\nEND\n"
    print("Gonderilen (bytes):", payload)
    try:
        raw = _socket_roundtrip(host, port, timeout_s, payload)
        print("Gelen satir:", raw.decode("utf-8", errors="replace").strip())
        if raw.startswith(b"ERR"):
            print("Sonuc: BASARILI (responder ERR beklenen)")
            return 0
        print("Sonuc: BEKLENMEDI (ERR yok)")
        return 1
    except Exception as exc:
        print("Sonuc: BASARISIZ:", exc)
        return 1


def run_socket_status(host: str, port: int, timeout_s: float) -> int:
    print("--- socket status modu (STATUS -> responder yaniti) ---")
    drv = SocketDriver(host=host, port=port, timeout_s=timeout_s)
    drv.connect()
    try:
        text = drv.query_status()
        print("Gelen STATUS:", text)
        print("Sonuc: BASARILI (responder STATUS yaniti)")
        return 0
    except Exception as exc:
        print("Sonuc: BASARISIZ:", exc)
        return 1
    finally:
        drv.disconnect()


def main() -> int:
    p = argparse.ArgumentParser(description="Serial loopback firmware duman testi")
    p.add_argument("serial_port", nargs="?", help="COM3, /dev/ttyUSB0, ...")
    p.add_argument("--driver", choices=("serial", "socket"), default="serial")
    p.add_argument("--host", default="127.0.0.1", help="socket driver host")
    p.add_argument("--port", dest="socket_port", type=int, default=9000, help="socket driver port")
    p.add_argument("--baudrate", type=int, default=115200)
    p.add_argument("--timeout", type=float, default=2.0, help="okuma zaman aşımı (s)")
    p.add_argument(
        "--mode",
        choices=("normal", "stop", "malformed", "status"),
        default="normal",
        help=(
            "normal: SerialDriver batch; stop: batch+STOP; malformed: ham ERR testi; "
            "status: STATUS tek satır (manuel firmware doğrulama)"
        ),
    )
    args = p.parse_args()

    if args.driver == "socket":
        print("Driver: socket")
        print("Host:", args.host)
        print("Port:", args.socket_port)
        print("Timeout (s):", args.timeout)
        print("Mod:", args.mode)
        print()
        if args.mode == "malformed":
            return run_socket_malformed(args.host, args.socket_port, args.timeout)
        if args.mode == "status":
            return run_socket_status(args.host, args.socket_port, args.timeout)
        if args.mode == "stop":
            return run_socket_stop(args.host, args.socket_port, args.timeout)
        return run_socket_normal(args.host, args.socket_port, args.timeout)

    if not args.serial_port:
        p.error("serial driver requires serial_port (for socket use --driver socket)")

    print("Port:", args.serial_port)
    print("Baud:", args.baudrate)
    print("Timeout (s):", args.timeout)
    print("Mod:", args.mode)
    print()

    if args.mode == "malformed":
        return run_malformed(args.serial_port, args.baudrate, args.timeout)
    if args.mode == "status":
        return run_status(args.serial_port, args.baudrate, args.timeout)
    if args.mode == "stop":
        return run_stop(args.serial_port, args.baudrate, args.timeout)
    return run_normal(args.serial_port, args.baudrate, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
