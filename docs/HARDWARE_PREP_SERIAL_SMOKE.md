# Hardware Prep — Serial Loopback Smoke

Bu belge, Patch 4 öncesi **host serial yolu** ve **firmware protokol** doğrulaması için smoke prosedürünü netleştirir.

## Test katmanları (ayrım)

| Katman | Ne doğrular | Gerçek serial? | Firmware? |
|--------|-------------|----------------|-----------|
| `pytest tests/test_serial_loopback_responder.py` | Python responder mantığı (in-memory) | Hayır | Hayır |
| `pytest tests/test_socket_driver.py` | Socket driver + TCP responder | Hayır (TCP) | Hayır |
| Socket smoke (`--driver socket`) | Host `SerialDriver`/`SocketDriver` + TCP responder | Hayır | Hayır |
| COM smoke + `serial_loopback_responder.py` | Host `SerialDriver` → gerçek UART → Python responder | **Evet** | Hayır |
| COM smoke + firmware sketch | Host → UART → **firmware** (`newbot_loopback_v1` / `newbot_real_v1`) | **Evet** | **Evet** |

**Önemli:**

- Python in-memory test **gerçek serial test değildir**.
- Socket loopback **COM testinin yerini tutmaz**; yalnızca host protokol katmanını doğrular.
- COM loopback (sanal çift veya USB-serial) **host serial yolunu** test eder.
- Gerçek karta yüklenmiş firmware smoke **MCU protokol davranışını** test eder.

## Ön koşul: backend venv

```powershell
cd backend
.\.venv\Scripts\python.exe -m serial.tools.list_ports -v
```

Windows PowerShell:

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
```

## A) Socket loopback (COM gerekmez)

Terminal 1 — responder:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\socket_loopback_responder.py --host 127.0.0.1 --port 9000
```

Terminal 2 — smoke (her mod için exit code 0 beklenir):

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --host 127.0.0.1 --port 9000 --timeout 3 --mode status
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --host 127.0.0.1 --port 9000 --timeout 3 --mode normal
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --host 127.0.0.1 --port 9000 --timeout 3 --mode stop
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --driver socket --host 127.0.0.1 --port 9000 --timeout 3 --mode malformed
```

## B) Sanal COM çifti (com0com)

Gerçek kart yokken host serial yolunu doğrulamak için sanal null-modem çifti gerekir.

Örnek hedef:

- Host smoke: `COM10`
- Responder: `COM11`

Kurulum sonrası portlar **görünmeden** smoke başlatmayın.

Terminal 1 — responder:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\serial_loopback_responder.py COM11 --baudrate 115200
```

Terminal 2 — smoke:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode status
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode normal
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode stop
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py COM10 --baudrate 115200 --timeout 2 --mode malformed
```

`COM10` / `COM11` sistemde yoksa bu bölüm **PASS iddiası** üretilemez.

## C) Gerçek kart smoke

1. `firmware/BUILD.md` — compile/upload (FQBN + port net olmalı).
2. Sketch: önce `newbot_loopback_v1`, sonra `newbot_real_v1`.
3. Baud: **115200**.
4. `<PORT>` = kartın gerçek COM portu.

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py <PORT> --baudrate 115200 --timeout 3 --mode status
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py <PORT> --baudrate 115200 --timeout 3 --mode normal
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py <PORT> --baudrate 115200 --timeout 3 --mode stop
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py <PORT> --baudrate 115200 --timeout 3 --mode malformed
```

### Manuel senaryolar (firmware)

| Senaryo | Gönderim | Beklenen |
|---------|----------|----------|
| STATUS | `STATUS\n` | `STATUS state=... fw=newbot_real_v1 ... queued=N` |
| Boş BEGIN/END | `BEGIN\nEND\n` | `OK` sonra `DONE` |
| Normal batch | `--mode normal` | `DONE` |
| STOP (batch sonrası) | `--mode stop` | `DONE` (STOP sonrası) |
| Malformed | `--mode malformed` | `ERR ...` |
| STOP batch receive | `BEGIN` + satırlar + `STOP\n` | `DONE`, kuyruk temiz |
| Queue full | `BEGIN` + 257+ komut satırı | `ERR queue_full` |
| Long line | 160+ karakter satır | `ERR line_too_long` |

Queue full ve long line için hazır smoke modu yok; ham seri veya özel script gerekir.

## Başarı kriterleri

- Script exit code **0**
- Konsolda `Sonuç: BAŞARILI` / `Sonuc: BASARILI`
- `normal` / `stop`: `DONE`
- `malformed`: `ERR` satırı
- `status`: `STATUS ` ile başlayan satır

## Script yardımı

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\serial_loopback_responder.py --help
.\.venv\Scripts\python.exe scripts\smoke_test_serial_loopback.py --help
.\.venv\Scripts\python.exe scripts\socket_loopback_responder.py --help
```

## İlgili belgeler

- `docs/HARDWARE_PREP_SERIAL_RESPONDER.md` — Python responder detayı
- `firmware/BUILD.md` — arduino-cli build/upload
- `docs/HARDWARE_PREP_LOOPBACK_EXECUTION_REPORT.md` — önceki port keşfi kaydı
