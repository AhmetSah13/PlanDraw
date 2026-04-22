# NewBot İlk Donanım Getirimi (Stage 0–1) Kontrol Listesi

Bu doküman, fiziksel ilk prototip gelince masada adım adım ilerlemek için hazırlanmıştır.

- Stage 0: kart/seri bağlantısı doğru mu (motor hareketi beklenmez).
- Stage 1: mevcut loopback firmware ile host tarafı seri komut/yanıt doğrulaması (smoke testler).

Kapsam: `firmware/newbot_loopback_v1/` ve `backend/scripts/smoke_test_serial_loopback.py` ile uyumludur.

## Stage 0 — Masa/tezgah (kart ve seri port)

1. Kartı bağla
   - Yapılacak: Kartı USB ile bilgisayara bağla.
   - Başarı: Aygıt yöneticisinde port görünüyor.
   - Yaygın hata: Port hiç görünmüyor (kablo/USB adaptör sorunu).

2. Doğru portu bul
   - Yapılacak: COM portunu not et (ör. `COM3`).
   - Başarı: Port adını doğru kullanabiliyorsun.
   - Yaygın hata: Yanlış port -> smoke testte bağlantı hatası/timeout.

3. (İsteğe bağlı) Seri yazdırma sanity kontrolü
   - Yapılacak: Seri monitörde (115200 baud) gelen metin “anlaşılır” mı bak.
   - Başarı: Çöp/kırık metin yok (baud uyumu muhtemel).
   - Yaygın hata: Bozuk karakterler -> `baudrate` uyumsuz (hem firmware hem host 115200 olmalı).

4. Seri portu “kilitleyen” uygulama yok
   - Yapılacak: Seri monitör/tabanlı bir program açık ise kapat.
   - Başarı: smoke test portu açabiliyor.
   - Yaygın hata: “port kullanılıyor / erişilemiyor” tarzı hata.

5. Gerekirse pyserial doğrula
   - Yapılacak:
     - `python -c "import serial; print('pyserial OK')"`
   - Başarı: Import ediliyor.
   - Yaygın hata: `pyserial yüklü değil.` (script exit code 2).

## Stage 1 — Loopback firmware ile host-doğrulama (smoke test)

Önkoşul: `firmware/newbot_loopback_v1/` kart yazılımı karta yüklü olmalı.

1. Çalışma klasörüne geç
   - Yapılacak:
     - `cd backend`

2. STATUS doğrulaması (manuel ve hızlı)
   - Yapılacak:
     - `python scripts/smoke_test_serial_loopback.py <PORT> --mode status`
   - Başarı:
     - Ham satır `STATUS ` ile başlıyor
     - Konsolda `Sonuç: BAŞARILI (MCU STATUS yanıtı)`
     - Komut exit code `0`
   - Yaygın hata örnekleri:
     - Timeout/boş okuma -> `Sonuç: BAŞARISIZ (boş yanıt, zaman aşımı veya kesik okuma)` (exit kodu 1)
     - Yanlış port veya baud -> ya boş yanıt ya da `satır 'STATUS ' ile başlamıyor`

3. Normal smoke test (batch + DONE)
   - Yapılacak:
     - `python scripts/smoke_test_serial_loopback.py <PORT>`
   - Başarı:
     - `Sonuç: BAŞARILI (MCU DONE)`
     - exit code `0`
   - Yaygın hata:
     - `DONE` gelmiyor -> timeout/ERR ve exit code != 0

4. Stop smoke test (batch + STOP)
   - Yapılacak:
     - `python scripts/smoke_test_serial_loopback.py <PORT> --mode stop`
   - Başarı:
     - `Sonuç: BAŞARILI (STOP sonrası DONE)`
     - exit code `0`

5. Malformed smoke test (hatalı DSL -> ERR)
   - Yapılacak:
     - `python scripts/smoke_test_serial_loopback.py <PORT> --mode malformed`
   - Başarı:
     - `Sonuç: BAŞARILI (MCU ERR beklenen)`
     - exit code `0`
   - Yaygın hata:
     - `ERR ...` beklenirken farklı satır gelirse exit code `1`

## Kısa sorun giderme (en sık görülenler)

- Yanlış COM/tty portu: Portu doğrula ve farklı bir değer dene.
- Baud uyumsuzluğu: Firmware `SERIAL_BAUD` ve script `--baudrate` aynı olmalı (varsayılan 115200).
- Kart açılırken reset: Bazı kartlar port açınca resetler; ilk denemede timeout olursa `--timeout 3` deneyebilirsin.
- Seri port kilidi: Seri monitörü/terminal başka programda açık kalmış olabilir; kapat.
- pyserial eksik: `malformed` ve `status` modları `pyserial` import etmeye çalışır; yoksa `pip install pyserial`.

