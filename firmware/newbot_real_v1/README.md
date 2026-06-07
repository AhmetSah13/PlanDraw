# newbot_real_v1 — Gerçek kart (minimum iskelet)

Bu klasör, mevcut `newbot_loopback_v1` akışını bozmadan **gerçek donanıma geçiş öncesi** minimum bir kart yazılımı iskeleti sağlar.

## Amaç

- `STATUS`, `STOP`, `HOME`, `MOVE` komutlarını parse etmek
- Bir **state machine** ve **hareket taklidi** ile `STATUS` / `DONE` / `ERR <reason>` yanıtlarını deterministik üretmek
- Gerçek motor/servo sürüşüne geçmeden önce, host ↔ kart sözleşmesini ve durum akışını netleştirmek

## `newbot_loopback_v1` ile farkı

- **`newbot_loopback_v1`**: Stage 0–1 seri/protokol doğrulaması için güvenli baseline. Batch (`BEGIN`…`END`) + `DONE/ERR` akışı ile host duman testini doğrular. Gerçek motor yoktur.
- **`newbot_real_v1`**: Gerçek donanıma geçiş öncesi **parser + state machine + hareket taklidi** iskeleti. Amaç, “loopback sonrası” kart yazılımının iç yapısını kontrollü şekilde kurmaktır.

> Not: Donanım gelmeden fiziksel doğrulama yapılmış sayılmaz. Bu klasör yalnızca yazılım tarafı hazırlığıdır.

## Kapsam dışı (bu sürümde yok)

- Gerçek motor sürüşü (PWM/step-dir), enkoder, PID, odometri
- Gerçek kalem aktüatörü (servo) sürüşü
- Gercek motor/servo uzerinde fiziksel dogrulama
- Sürekli telemetri/streaming

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
- `STATUS state=<STATE> fw=newbot_real_v1 motion=stub error=<ERR> queued=<N>`
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
