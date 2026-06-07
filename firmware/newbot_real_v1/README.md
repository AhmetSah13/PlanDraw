# newbot_real_v1 — Gerçek kart (minimum iskelet)

Bu klasör, mevcut `newbot_loopback_v1` akışını bozmadan **gerçek donanıma geçiş öncesi** minimum bir kart yazılımı iskeleti sağlar.

## Donanım modeli (Patch 4A)

| Bileşen | Planlanan |
|---------|-----------|
| Kontrol kartı | ESP32-S3 DevKitC-1 N16R8 |
| Hareket | 2× NEMA17 step motor |
| Sürücü | 2× TMC2208 (STEP/DIR/EN; UART config yok) |
| Kalem | 1× servo (yukarı/aşağı) |

Pinler ve servo açıları **henüz kesin değil** — `robot_config.h` içinde `PIN_UNASSIGNED` (-1) placeholder kullanılır.

## Actuator abstraction (Patch 4A)

- `robot_config.h` — kart/motor/servo/safety sabitleri
- `actuator_safe.cpp` — config odaklı, **varsayılan disabled** actuator katmanı
- Pin atanmadıysa STEP/DIR/EN/servo **fiziksel çıkış üretmez**
- `REQUIRE_EXPLICIT_ACTUATOR_ENABLE` — motor enable açık onay gerektirir
- `SAFE_BOOT_PEN_UP` / `SAFE_BOOT_MOTORS_DISABLED` — boot güvenliği
- `hardStop` / `STOP` yolu `actuatorHardStop()` ile motor disable + pen up

Servo gerçek sürüşü (attach/PWM) Patch 4B; şu an yalnızca arayüz ve güvenli mantıksal durum.

## Amaç

- `STATUS`, `STOP`, `HOME`, `MOVE` komutlarını parse etmek
- Bir **state machine** ve **hareket taklidi** ile `STATUS` / `DONE` / `ERR <reason>` yanıtlarını deterministik üretmek
- Gerçek motor/servo sürüşüne geçmeden önce, host ↔ kart sözleşmesini ve durum akışını netleştirmek

## `newbot_loopback_v1` ile farkı

- **`newbot_loopback_v1`**: Stage 0–1 seri/protokol doğrulaması için güvenli baseline. Batch (`BEGIN`…`END`) + `DONE/ERR` akışı ile host duman testini doğrular. Gerçek motor yoktur.
- **`newbot_real_v1`**: Gerçek donanıma geçiş öncesi **parser + state machine + hareket taklidi** iskeleti. Amaç, “loopback sonrası” kart yazılımının iç yapısını kontrollü şekilde kurmaktır.

> Not: Donanım gelmeden fiziksel doğrulama yapılmış sayılmaz. Bu klasör yalnızca yazılım tarafı hazırlığıdır.

## Kapsam dışı (Patch 4A)

- Gerçek pin mapping (Patch 4B)
- Fiziksel motor/servo testi
- TMC2208 UART ayarı
- Enkoder, PID, odometri
- Motion planner ile gerçek step üretimi bağlantısı (Patch 4B/5)

## Desteklenen komutlar (wire girişi)

- `STATUS` (her durumda yanıt verir)
- `STOP` (her durumda kabul; BUSY ise iptal eder)
- `HOME` (taklit; BUSY → IDLE kapanışı)
- `MOVE X=<float> Y=<float>` (taklit; BUSY → IDLE kapanışı)
- Uyum için minimal parse (host DSL ile çakışmaması için):
  - `BEGIN`, `END`
  - `SPEED <float>`
  - `PEN UP` / `PEN DOWN`
  - `FORWARD <float>`, `TURN <float>`, `WAIT <float>`

## Yanıt formatı (wire çıkışı)

Wire yanıt sözleşmesi:
- `STATUS state=<STATE> fw=newbot_real_v1 motion=stub error=<ERR> queued=<N> actuator=... motors=... pen=... left_pin=... right_pin=... pen_pin=...`
- Başarı: `DONE`
- Hata: `ERR <reason>`

### Hata tokenları (kısa ve İngilizce)

- `unknown`
- `invalid_number`
- `missing_param`
- `busy`
- `fault`

## State machine özeti

Durumlar:
- `BOOT` → kısa süre sonra `IDLE`
- `IDLE` → komutla `BUSY`
- `BUSY` → taklit hareket bitince `IDLE` + `DONE`
- `STOPPED` → `STOP` sonrası kısa süre; sonra `IDLE`
- `FAULT` → bu sürümde sınırlı (gelecek iş)

## Batch uyumluluğu özeti (minimum)

Amaç: Mevcut host akışının (`BEGIN` … komutlar … `END` sonrası `DONE`) timeout yememesidir.

- `BEGIN`: batch başlatır.
- `END`:
  - batch içinde hata yoksa ve aktif hareket yoksa **hemen `DONE`**
  - hareket devam ediyorsa, hareket bitince **tek `DONE`**
  - batch hata aldıysa **ek `DONE` yok** (ERR ile biter)

Patch 2 note:
- Supported DSL lines between `BEGIN` and `END` are now queued FIFO and do not start motion immediately.
- `END` starts queued execution; exactly one final `DONE` is emitted after the whole queue completes.
- Empty `BEGIN`/`END` returns `DONE`.
- Queue overflow returns `ERR queue_full` and enters the safe hard-stop path.
- The queue is still stub-motion only; real PWM/encoder/PID is not implemented.

Eski Patch 1 limitasyonu (Patch 2 notu guncel davranistir):
- Batch içinde **tek** motion komutu güvenli kabul edilir.
- Batch içinde ikinci motion komutu şu an desteklenmez: **`ERR busy`**.

## Donanım geldiğinde yapılacaklar (Patch 4B öncesi checklist)

1. `robot_config.h` — sol/sağ STEP, DIR, EN pinlerini gir
2. `robot_config.h` — `PEN_SERVO_PIN` ve kalibre `PEN_UP_ANGLE` / `PEN_DOWN_ANGLE`
3. `firmware/BUILD.md` — FQBN netleştir, compile + upload
4. Yerden kesik düşük hız step testi (off-ground)
5. `STOP` ve `hardStop` saha doğrulaması
6. `docs/HARDWARE_PREP_SERIAL_SMOKE.md` — serial smoke modları

## Donanım geldiğinde ilk test adımları (manuel)

Bu adımlar fiziksel kart olmadan doğrulanmış sayılmaz; kart geldiğinde uygulanır:

1) `STATUS`:
- `cd backend`
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode status`

2) Normal:
- `python scripts/smoke_test_serial_loopback.py <PORT>`

3) Stop:
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode stop`

4) Malformed:
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode malformed`

İlgili belgeler:
- `firmware/BUILD.md` — arduino-cli compile/upload (FQBN placeholder; hedef kart netleştirilmeli)
- `docs/HARDWARE_PREP_SERIAL_SMOKE.md` — serial/socket smoke prosedürü
- `docs/SERIAL_PROTOCOL_V1.md`
- `docs/FIRMWARE_ARCHITECTURE_V1.md`
- `docs/BRINGUP_STAGE_0_1_CHECKLIST.md`
