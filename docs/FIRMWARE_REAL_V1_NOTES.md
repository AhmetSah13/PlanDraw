# Gerçek kart yazılımı (newbot_real_v1) — Kısa notlar

Bu doküman, `firmware/newbot_real_v1/` iskeletinin amacını ve sınırlarını kısa ve dağılmayacak şekilde özetler.

## Neden var?

- `firmware/newbot_loopback_v1/` güvenli bir baseline’dır: Stage 0–1 seri/protokol doğrulaması için.
- `firmware/newbot_real_v1/` ise gerçek donanıma geçiş öncesi **parser + state machine + hareket taklidi** iskeletidir.
- Hedef: Gerçek motor/servo sürüşüne geçmeden önce, host ↔ kart komut/yanıt sözleşmesini ve durum akışını netleştirmek.

## Ne hazır?

- Tek satır komut ayrıştırma (wire girişi) ve deterministik yanıt üretimi (wire çıkışı).
- `STATUS`, `STOP`, `HOME`, `MOVE` akışları.
- Minimum batch uyumluluğu: `BEGIN` … `END` sonrası `DONE`/`ERR` davranışı.

## Ne hâlâ taklit (stub)?

- Gerçek motor sürüşü yok (PWM/step-dir yok).
- Enkoder/odometri/PID yok.
- Kalem aktüatörü sürüşü yok.
- Full queue yok (batch içinde tek motion komutu güvenli).

## Yanıt formatı (wire çıkışı)

- Bilgi: `STATUS state=<STATE> fw=newbot_real_v1 motion=stub error=<ERR> queued=<N>`
- Başarı: `DONE`
- Hata: `ERR <reason>`

Hata tokenları kısa ve İngilizce tutulur:
`unknown`, `invalid_number`, `missing_param`, `busy`, `fault`.

## Batch uyumluluğu (minimum)

Bu iskelet, mevcut host akışının timeout yememesini hedefler:

- `BEGIN`: batch başlatır.
- `END`:
  - hata yok + aktif motion yok → hemen `DONE`
  - motion devam ediyor → motion bitince tek `DONE`
  - batch hata aldı → ek `DONE` yok (ERR ile biter)

Limit:
- Batch içinde ikinci motion komutu desteklenmez: `ERR busy`.

## Donanım gelince ilk test

Host tarafı araçları (kart olmadan “doğrulanmış” sayılmaz):

- `cd backend`
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode status`
- `python scripts/smoke_test_serial_loopback.py <PORT>`
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode stop`
- `python scripts/smoke_test_serial_loopback.py <PORT> --mode malformed`

## İlgili belgeler

- `docs/SERIAL_PROTOCOL_V1.md` (wire sözleşmesi)
- `docs/FIRMWARE_ARCHITECTURE_V1.md` (modül sınırları ve önerilen davranışlar)
- `docs/BRINGUP_STAGE_0_1_CHECKLIST.md` (ilk gün getir-up kontrol listesi)
- `firmware/newbot_loopback_v1/README.md` (baseline doğrulama akışı)
- `firmware/newbot_real_v1/README.md` (bu iskeletin kısa uygulama odaklı açıklaması)

