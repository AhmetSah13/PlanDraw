# Host ↔ MCU seri protokolü (v1)

**Sürüm:** 1.0 (tasarım)  
**Kapsam:** Python host ile ESP32 / Arduino tarzı denetleyici arasında metin tabanlı komut iletimi.  
**Resmi host sınırı:** `List[Command]` (`app.execution.commands`); wire üzerindeki metin, `serialize_commands(...)` ile üretilen satır bazlı DSL ile uyumludur.

---

## 1. Protokol kapsamı ve varsayımlar

### Taşıma

- Seri UART (TTL veya USB–UART köprüsü); baud örneği 115200 (sabit değil, host/MCU anlaşması).
- **Çerçeveleme:** satır bazlı; her mantıksal kayıt **tek bir satır** + satır sonu.
- **Satır sonu:** host gönderiminde `\n` (LF) yeterli; isteğe bağlı olarak `\r\n` kabul edilebilir (MCU tarafında strip).

### Kodlama

- Metin **UTF-8**. v1 komut gövdesi pratikte ASCII alt kümesidir (`MOVE`, sayılar, `PEN UP/DOWN`).

### Tek satır komut modeli

- Her fiziksel satır = bir komut veya bir protokol kontrol kelimesi (`BEGIN`, `END`, `STOP`, yanıtlar).
- `serialize_commands` çıktısı zaten satır başına bir DSL komutu üretir (`SPEED …`, `MOVE …`, vb.).

### Toplu (batch) yürütme

- **v1:** Evet. Host, isteğe bağlı olarak **`BEGIN`** ile başlayıp **`END`** ile biten bir blok gönderir; MCU `END` sonrası veya satır satır modunda yürütür (aşağıda iki mod).

### Yorum / meta veri

- **`#` ile başlayan satırlar:** v1’de **isteğe bağlı** yorum; MCU yok saymalı (ileride genişletilebilir).
- **`META key=value`:** v1’de **isteğe bağlı**, zorunlu değil. Öneri: `META session=1` gibi; desteklenmeyen `META` satırları yorum gibi atlanabilir veya `ERR` ile reddedilebilir — v1 profilinde **atlamak** daha güvenli (öğrenci firmware).

---

## 2. v1 wire protokolü (tam metin)

### Zorunlu öğeler

- Komut gövdesi: `serialize_commands` ile üretilen satırlar (ör. `SPEED 1.0`, `MOVE 10 20`).
- Yanıtlar: host’un beklediği minimum MCU cevapları (bölüm 3).

### İsteğe bağlı batch çerçevesi

| Satır | Anlam |
|--------|--------|
| `BEGIN` | (İsteğe bağlı) Sonraki satırlar bir batch içindedir. |
| … | DSL komut satırları |
| `END` | Batch bitti; MCU bu noktada kuyruğu işlemeye başlayabilir veya `END` sonrası `DONE` döner. |

**Profil A (önerilen öğrenci projesi):** Host sadece DSL satırlarını gönderir, **`BEGIN`/`END` kullanmaz**; MCU her satırı aldıkça işler ve satır başına `OK` döner (basit ama yavaş).

**Profil B:** Host `BEGIN` … komutlar … `END` gönderir; MCU tüm blok alındıktan sonra tek `DONE` veya hata döner (daha az trafik).

v1 spesifikasyonu **her iki profili** destekleyecek şekilde tanımlar; hangi profilin kullanılacağı host sürücü yapılandırması + firmware ile sabitlenir.

### STOP

- Tek satır: **`STOP`**
- Anlam: Mümkün olan en kısa sürede hareketi kes, kuyruğu temizle veya durdur; ardından **`DONE`** veya **`ERR stop`** (MCU politikası).

### META (isteğe bağlı)

- `META key=value` — v1’de tanınmayan anahtarlar **sessizce yok sayılır** (öneri).

---

## 3. Robot (MCU) yanıtları

Satırlar UTF-8, `\n` ile biter.

| Yanıt | Anlam |
|--------|--------|
| `OK` | Bir satır komut kabul edildi ve işleme alındı (Profil A). |
| `DONE` | Batch veya tek seferlik iş tamamlandı (Profil B veya STOP sonrası). |
| `ERR <kısa mesaj>` | Komut reddedildi veya çalışma hatası; mesaj tek satır, ASCII tercih. |
| `STATUS key=value ...` | **v1 isteğe bağlı**; örn. `STATUS idle=1`. Zorunlu değil. |

**Minimum uyumluluk:** En azından `ERR …` ve `DONE` veya `OK` çiftlerinden biri tutarlı kullanılmalı.

---

## 4. Zaman aşımı ve hata anlamları

### Host beklentisi

- Gönderim sonrası **okuma zaman aşımı** (ör. 0.5–2 s satır başına, batch için daha uzun); yapılandırılabilir.
- Profil A: Her komut satırından sonra `OK` veya `ERR` beklenir.
- Profil B: `END` sonrası `DONE` veya `ERR` beklenir.

### Hatalı komut satırı

- MCU tanımayan DSL veya bozuk satır için: **`ERR parse`** veya **`ERR unknown`**; host loglar, kullanıcıya iletir. Host **motion katmanını** bu protolle karıştırmaz; sadece iletim katmanı hatasıdır.

### Zaman aşımı

- Host: bağlantıyı kapatma veya `STOP` denemesi; **yeniden deneme politikası** uygulama katmanında. Motion simülasyon sonucu ile **birleştirilmez** (ayrı kanal).

### STOP gönderildiğinde

- MCU: durdur, `DONE` veya `ERR stop` döner; host zaman aşımı ile de devam edebilir.

---

## 5. Örnek oturumlar

### Başarılı batch (Profil B, özeti)

```
Host → BEGIN
Host → SPEED 1
Host → MOVE 10 0
Host → END
MCU → DONE
```

### Hatalı komut (Profil A)

```
Host → MOVE not_a_number
MCU → ERR parse
```

### STOP

```
Host → STOP
MCU → DONE
```

### Tek satır + OK (Profil A)

```
Host → PEN DOWN
MCU → OK
Host → FORWARD 1
MCU → OK
```

---

## 6. Sorumluluk ayrımı

### Python host

- `List[Command]` → `serialize_commands` → satırları UTF-8 ile göndermek.
- `BEGIN`/`END`/`STOP` çerçevesini seçmek ve zaman aşımı yönetmek.
- Gelen `ERR`/`DONE`/`OK` satırlarını okumak ve log/üst katmana iletmek.
- **Yapmaz:** diferansiyel kinematik, gerçek zamanlı motion planlama (bunlar `app.motion` veya ayrı araçlar).

### MCU firmware

- UART okuma, satır tamponu, DSL alt kümesini yorumlama, motor/kalem zamanlaması.
- `OK`/`DONE`/`ERR` üretmek.
- **Yapmaz:** Python komut modelinin tam kopyası; sadece wire üzerindeki metni bilir.

### v1 kapsam dışı

- İkili çerçeveleme, CRC zorunluluğu, akış kontrolü (RTS/CTS) — isteğe bağlı ileri sürüm.
- HTTP, export formatları doğrudan gönderimi.
- ACK çakışması giderme (yeniden gönderim stratejileri) — host uygulama politikası.

---

## 7. Önerilen sonraki kod partisi (düşük risk)

**En güvenli sıra:** Önce **protokol satırı için küçük bir test harness** (Python’da MCU’yu taklit eden sahte okuyucu/yazıcı: string tampon üzerinde `BEGIN`…`END`, `OK`/`ERR` üretimi). Böylece gerçek UART eklemeden host tarafındaki çerçeveleme ve zaman aşımı mantığı test edilir.

**Sonra:** **Taşıma soyutlaması** (`write`/`readline`) — tek sınıfta `pyserial` bağlanır.

**En son:** Gerçek **`pyserial`** ile `SerialDriver` (stub’un yerine veya yanında).

Bu repo için **en iyi bir sonraki adım:** *fake transport + protokol çerçevesi unit testleri*; ardından `pyserial`.

---

## 8. Sonraki düşük riskli partı için uygulama istemi (kopyala-yapıştır)

```
NewBot deposunda SERIAL_PROTOCOL_V1.md ile uyumlu host tarafı “protokol katmanı” ekle; gerçek UART yok.

Kısıtlar:
- app/api/main.py, rotalar, executor, compiler, export uçları, deneysel boru hatlarına dokunma.
- pyserial ekleme.
- Kanonik girdi List[Command] kalsın; serialize_commands kullan.

Yapılacaklar:
1) backend/app/drivers/ veya backend/app/execution/ altında ince bir modül (ör. serial_protocol_v1.py): Profil A veya B için satırları birleştirme (BEGIN/END isteğe bağlı), STOP satırı üretimi, son payload UTF-8 bytes.
2) FakeTransport: bellek içi bytes/string kuyruğu; write/readline ile MCU yanıtını testte enjekte et.
3) tests/test_serial_protocol_v1.py: başarılı batch stringi, ERR parse senaryosu, STOP satırı içeren deterministik testler.
4) docs/SERIAL_PROTOCOL_V1.md dosyasına “Host reference implementation” diye bu modülün adını not et.

Amaç: pyserial gelmeden wire sözleşmesini koda dökmek ve SerialDriverStub’un üzerine gerçekçi bir katman koymak.
```

---

MCU tarafı tasarım özeti: **`docs/FIRMWARE_ARCHITECTURE_V1.md`**.

## Host referans uygulaması (kod)

- Çerçeveleme ve yanıt ayrıştırma: `backend/app/drivers/serial_protocol.py` (`frame_dsl_payload`, `frame_stop_line`, `parse_response_line`, `SerialWireProfile` A/B).
- Bellek içi taşıma: `backend/app/drivers/fake_serial_transport.py` (`FakeSerialTransport`).
- Birim testler: `backend/tests/test_serial_protocol_transport.py`.

Gerçek `pyserial` bu partide yoktur; ileride aynı protokol fonksiyonları gerçek UART yazımına bağlanabilir.

---

*Bu belge, mevcut `serialize_commands` çıktısı ve `SerialDriverStub` ile hizalıdır; gerçek seri I/O sonraki partidedir.*
