# newbot_loopback_v1 — SERIAL_PROTOCOL_V1 loopback (motor yok)

**Amaç:** Profil B (`BEGIN` … `END`) ile komutları sırayla **simüle** eder; gerçek motor/PWM yok. Host `SerialDriver` (varsayılan) `DONE` veya `ERR` bekler.

## Kurulum

- **Arduino IDE:** `newbot_loopback_v1` klasörünü sketch olarak açın; kart olarak ESP32 veya Arduino seçin.
- **Seri:** 115200 baud (kod içi `SERIAL_BAUD`).

## Dahili durum (motor yok)

Yürütme sırasında firmware küçük bir **soyut durum** tutar (PWM/encoder yok):

| Alan | Anlam |
|------|--------|
| `speed` | Son işlenen `SPEED` değeri; başlangıç **1.0** (henüz `SPEED` yoksa). |
| `pen` | Son işlenen `PEN UP` / `PEN DOWN` ile **UP** veya **DOWN**; başlangıç **UP**. |
| `last` | Son tamamlanan komutun tipi (`SPEED`, `MOVE`, `PEN`, …) veya batch başında **NONE**. |

Hareket (`MOVE`, `FORWARD`, `TURN`, …) hâlâ **stub**: tekerlek veya kinematik yok; komutlar yalnızca kuyruktan tüketilir.

## STATUS sorgusu (isteğe bağlı)

Host, batch dışında veya yürütme sırasında tek satır **`STATUS`** gönderebilir (büyük/küçük harf: `STATUS`). MCU yanıtı **tek satır**, `SERIAL_PROTOCOL_V1` ile uyumlu önek:

```text
STATUS speed=1.0000 pen=DOWN state=RUNNING queued=2 last=FORWARD
```

- `state`: `IDLE` \| `RECEIVING` \| `RUNNING`
- `queued`: bekleyen komut sayısı (alım tamponunda veya yürütmede kalan)
- Python `SerialDriver` batch beklerken ara **`STATUS`** satırlarını yok sayar; duman testi yalnızca `DONE`/`ERR` beklediği için davranış değişmez.

## Davranış özeti

| Durum | Açıklama |
|--------|-----------|
| Batch | `BEGIN` sonrası satırlar tampona; `END` ile yürütme başlar. |
| Yürütme | Loopback: komutlar sırayla tüketilir; `SPEED`/`PEN` dahili duruma işlenir; `WAIT` için **non-blocking** `millis()` beklemesi. |
| STOP | Tampon veya yürütme sırasında kuyruk temizlenir, **`DONE`** gönderilir (temiz durdurma). |
| Hata | Geçersiz satır → **`ERR …`** (batch içinde). |

## Host duman testi (Python)

Betik: `backend/scripts/smoke_test_serial_loopback.py` — `backend` klasöründen çalıştırın.

### Önerilen sıra (gerçek donanım)

1. **Sketch’i karta yükle** — `newbot_loopback_v1.ino` derlenip yüklenmiş olsun.
2. **Portu netleştir** — Windows’ta Aygıt Yöneticisi’nden doğru COM portunu (ör. `COM3`) not et.
3. **İlk test (normal):**
   ```bash
   cd backend
   python scripts/smoke_test_serial_loopback.py COM3
   ```
   Beklenen: başarılı bağlantı, batch gönderimi, `DONE`, çıkış kodu **0**. İlk denemede gerekirse:
   ```bash
   python scripts/smoke_test_serial_loopback.py COM3 --timeout 3
   ```
4. **Stop testi:**
   ```bash
   python scripts/smoke_test_serial_loopback.py COM3 --mode stop
   ```
   Beklenen: ilk batch tamamlanır, ardından `stop()` ile ikinci olumlu yanıt, çıkış kodu **0**.
5. **Malformed testi:**
   ```bash
   python scripts/smoke_test_serial_loopback.py COM3 --mode malformed
   ```
   Beklenen: `ERR ...` satırı, betik bunu başarı olarak raporlar, çıkış kodu **0**.
6. **STATUS sorgusu (isteğe bağlı):**
   ```bash
   python scripts/smoke_test_serial_loopback.py COM3 --mode status
   ```
   Beklenen: host `STATUS\n` gönderir; MCU tek satır `STATUS speed=... pen=...` döner; betik çıkış kodu **0** (satır `STATUS ` ile başlamalıdır).

Not: Donanım ilk geldiğinde masada line-by-line takip etmek için ayrıca `docs/BRINGUP_STAGE_0_1_CHECKLIST.md` dokümanına bak.

### Test sırasında gözlem notları

- Kart seri açılınca **reset** atıyor mu?
- **İlk gönderimde** zaman aşımı oluyor mu?
- **DONE** beklenenden geç mi geliyor?
- **Stop** modunda ikinci yanıt gerçekten geliyor mu?
- **Malformed** modunda `ERR` her seferinde tutarlı mı?

### Sık görülen ilk sorunlar

- Yanlış **COM** portu
- **Baud** uyumsuzluğu (sketch ve host 115200 olmalı)
- USB bağlantısında kartın **reset** olması
- UART’a düşen **boot / debug** mesajlarının ilk satırı kirletmesi
- **`--timeout`** süresinin kısa kalması — ilk denemede `--timeout 3` veya daha yüksek kullanmak mantıklıdır.

## Sonraki part

Motor/kalem kancaları (PWM/servo), encoder, gerçek kinematik — bu sketch’te hâlâ yok; yalnızca loopback + hafif durum takibi.
