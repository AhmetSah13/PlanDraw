# MCU firmware mimarisi (v1) — SERIAL_PROTOCOL_V1 ile uyum

**Kapsam:** ESP32 / Arduino sınıfı denetleyici; host tarafı `docs/SERIAL_PROTOCOL_V1.md` ve `app.drivers.serial_driver` (varsayılan **profil B**: `BEGIN` … `END`, sonra **`DONE`** / **`ERR`**) ile uyumlu yanıtlar.

**Bu belge tasarımdır;** tam C++/Arduino uygulaması sonraki partidedir. Python deposunda üretim kodu değişikliği gerektirmez.

**İlk loopback uygulaması (motor yok):** `firmware/newbot_loopback_v1/` (Arduino sketch + README).

---

## 1. Firmware mimarisi (modüller)

| Bileşen | Görev |
|--------|--------|
| **Seri satır okuyucu** | UART’tan bayt alır, `\n` veya `\r\n` ile satır tamamlar; satırı UTF-8 metne çevirir (v1 ASCII alt kümesi). |
| **Protokol ayrıştırıcı** | Satırı DSL komutu veya kontrol kelimesi (`BEGIN`, `END`, `STOP`) olarak tanır; tokenize eder. |
| **Komut kuyruğu / program tamponu** | Profil B’de `BEGIN`–`END` arası satırlar burada birikir; `END` sonrası “program hazır” durumuna geçilir. Profil A’da (isteğe bağlı) satır başına anında kuyruk. |
| **Komut yürütücü** | Kuyruktan veya tek satırdan komut alır; birimleri (hız, mesafe, açı) uygular; motor/kalem soyutlamasını çağırır. |
| **Motor / kalem kancaları** | Donanıma özel API (ör. `set_wheel_speeds`, `step_line`, `pen_servo`); gerçek kinematik burada veya alt modülde. |
| **Yanıt yazıcı** | `OK`, `DONE`, `ERR …` satırlarını UART üzerinden host’a gönderir. |

Bağımlılık yönü: seri okuyucu → ayrıştırıcı → (kuyruk) → yürütücü → yanıt yazıcı. **Tek dev “her şeyi yapan” fonksiyon yok.**

---

## 2. Ayrıştırıcı davranışı (v1)

Genel kural: **`#` ile başlayan satır** yorum → yok say, yanıt yok. **`META …`** v1’de tanınmıyorsa yok say (sessiz).

| Satır / komut | Davranış |
|----------------|----------|
| `BEGIN` | Batch moduna geç; tamponu temizle veya yeni batch başlat. |
| `END` | Batch sonu; kuyruğu “yürütülmeye hazır” işaretle; host **profil B** beklediği için yürütme bittikten sonra **`DONE`** (veya hata **`ERR`**). |
| `STOP` | Yürütmeyi kes; kuyruğu temizle veya durdur; **`DONE`** veya `ERR stop` (politika); host `SerialDriver.stop()` ile uyumlu. |
| `SPEED <f>` | Geçerli hız ölçeği; pozitif sayı kabul; aksi **`ERR parse`**. |
| `MOVE <x> <y>` | İki float; değilse **`ERR parse`**. |
| `MOVE_REL <dx> <dy>` | İki float. |
| `TURN <deg>` | Bir float (derece). |
| `FORWARD <dist>` | Bir float (mesafe). |
| `WAIT <s>` | Bir float (saniye); süre dolana kadar bloklama veya zamanlayıcı (aşağıda). |
| `PEN UP` / `PEN DOWN` | Büyük/küçük harf politikası: host `serialize_commands` ile `PEN UP` / `PEN DOWN` üretir; birebir eşle veya case-insensitive kabul et. |
| Bilinmeyen / bozuk satır | **`ERR unknown`** veya **`ERR parse`** (tercih: parse hataları `parse`, sözdizimi dışı `unknown`). |

**Profil B (Python SerialDriver varsayılanı):** `BEGIN` ile `END` arasındaki tüm geçerli satırlar tampona alınır; `END` gelince yürütme başlar ve **tek bir `DONE`** (veya ilk hatada **`ERR`** ve durdurma) host beklentisiyle uyumludur.

---

## 3. Yürütme / durum makinesi

Önerilen durumlar:

| Durum | Açıklama |
|--------|-----------|
| **idle** | Güç açık; batch beklenmiyor veya tamamlandı. |
| **receiving_batch** | `BEGIN` alındı; `END` gelene kadar satırlar tampona. |
| **ready** | `END` alındı; tampon yürütülmeyi bekliyor (veya `END` sonrası hemen **running**’e geçilebilir). |
| **running** | Komutlar sırayla işleniyor. |
| **stopped** | `STOP` veya tamamlanma sonrası; tekrar `BEGIN` veya tek satır komutlarına izin. |
| **fault** | Kurtarılamaz hata; `ERR` gönderildi; `STOP` veya sıfırlama ile çıkış. |

**Geçişler (özet):**

- `idle` + `BEGIN` → **receiving_batch**
- `receiving_batch` + `END` → **running** (veya önce **ready** kısa bir tick)
- **running** + tüm komutlar bitti → **idle** / **stopped** + host’a **`DONE`**
- Herhangi bir yerde **`STOP`** → yürütmeyi kes → **stopped** + **`DONE`**
- Geçersiz satır (batch içinde) → **fault** veya **running** içinde **`ERR`** ve durdurma

Host **SerialDriver** satır satır `OK` beklemez (profil B’de); tek **`DONE`** bekler — firmware batch sonunda **bir kez `DONE`** göndermeli.

---

## 4. Yanıt davranışı (host ile hizalama)

Python **SerialDriver** (varsayılan): gönderimden sonra `readline` ile **`DONE`** veya **`ERR …`** bekler; ara satırlarda **`OK`** / **`STATUS`** / bilinmeyen atlanır.

**Firmware v1 önerisi (profil B):**

- Batch işlendikten ve başarıyla bittikten sonra: **`DONE\n`**
- Hata: **`ERR <kısa mesaj>\n`** (ör. `ERR parse`, `ERR limit`)
- İsteğe bağlı ara **`STATUS`** — host yok sayabilir; zorunlu değil.

**Profil A** (ileride): her komut sonrası **`OK\n`**; son **`DONE\n`** — host tarafı farklı `SerialDriver` ayarı gerektirir.

---

## 5. Bloklama vs non-blocking

**Öğrenci prototipi için pratik model:**

- **Ana döngü (`loop`):** (1) UART’tan mevcut baytları oku ve satırları tamamla. (2) Tamamlanan satırları ayrıştırıcıya ver. (3) **Yürütücü** için kısa bir zaman dilimi (ör. bir “adım” veya `WAIT` için kalan süre kontrolü).
- **Uzun `MOVE` / `FORWARD`:** ya bloklayıcı (basit ama seri okumayı geciktirir) ya da **durum makinesi + küçük adımlar** ile her `loop`’ta biraz ilerle (tercih: **non-blocking adım**; seri okuma her zaman fırsat bulsun).
- **STOP:** UART tamponunda veya yürütücüde yüksek öncelik: mümkün olan en kısa sürede motorları durdur ve **`DONE`** gönder; seri satırı **`STOP`** ile gelirse aynı öncelik.

**Blocking forever:** Ham `read()` ile tek satırda sonsuz bekleme yapmayın; timeout veya `readline` + non-blocking UART kullanımı tercih edin.

---

## 6. Önerilen ilk firmware partisi (düşük risk)

**En güvenli ilk dilim:** **Ayrıştırıcı + kuyruk + loopback yürütücü** (motor yok, **sadece `DONE`/`ERR` üretimi**).

- **Gerekçe:** Host–MCU protokol uçtan uca doğrulanır; kinematik hatası yok.
- **Sonraki part:** Motor kancaları için stub (gerçek PWM yok, sayaç artırma).
- **Sonraki:** Gerçek adım motor + pen.

---

## 7. Anti-pattern uyarıları

- Tüm ayrıştırma + motor + seri tek “dev” fonksiyonda.
- **Bellekte sınırsız** tampon; `END` ile uzunluk sınırı veya maksimum komut sayısı yok.
- `read()` ile **sonsuz bloklama**; `STOP` gelene kadar başka iş yok.
- İlk günden **FreeRTOS görev fırtınası** / ROS benzeri soyutlama.
- Host’tan gelen **export/robot_v1 metnini** ham olarak çalıştırmak (sınır **DSL satırları** olmalı).

---

## 8. Sonraki düşük riskli firmware partı için uygulama istemi (kopyala-yapıştır)

```
Hedef: NewBot SERIAL_PROTOCOL_V1 ve Python SerialDriver (profil B) ile uyumlu ESP32 veya Arduino firmware “ilk dilim”.

Kısıtlar:
- Python deposunu ve HTTP API’yi değiştirme.
- Gerçek motor sürücü / PWM yok; loopback yürütme yeterli.

Yapılacaklar:
1) UART başlat (115200), satır okuyucu: LF ile satır tamamla.
2) BEGIN … END arası satırları en fazla N komutluk tampona al (N sabit, örn. 256).
3) END sonrası: her satırı parse et (SPEED, MOVE, MOVE_REL, TURN, FORWARD, WAIT, PEN); hata varsa tek satır ERR … gönder ve çık.
4) Hata yoksa: motor çağrısı yok; sadece UART’a DONE yolla.
5) STOP satırı: tamponu temizle, DONE gönder.
6) # ile başlayan satırları yok say.

Test: Python ile SerialDriver + serial_connection fake veya gerçek USB-UART ile tek batch gönder; DONE alındığını doğrula.

Çıktı: tek .ino veya PlatformIO projesi; README’de host komut örneği.
```

---

*Bu belge, `docs/SERIAL_PROTOCOL_V1.md` ve `app.drivers.serial_driver` (varsayılan profil B) ile birlikte okunmalıdır.*
