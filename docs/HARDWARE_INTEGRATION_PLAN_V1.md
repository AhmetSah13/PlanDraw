# NewBot Öğrenci Prototipi Donanım Entegrasyon Planı (V1)

Bu doküman, `newbot` yazılım/seri protokol altyapısını bozmadan, ilk gerçek fiziksel prototip için en düşük riskli donanım yaklaşımını tarif eder.

Hedef: Basit zemin üzerinde kalemle temel şekilleri çizebilen (ilk etapta düz çizgi ve yaklaşık kare) küçük bir öğrenci prototipi.

Bu plan; yazılımın şu anki durumunu varsayar:
- İstemci tarafı `backend/app/drivers/serial_driver.py` üzerinden seri protokol (v1) ile komut gönderir.
- Denetleyici (kart yazılımı) komutları ayrıştırır, `SPEED` ve `PEN UP/DOWN` gibi komutlarda dahili durum tutar ve batch sonunda `DONE`/hata durumunda `ERR` döner.
- Şimdiki `STATUS` komutu manuel doğrulama içindir (ana akışta zorunlu değil).

## 1) Minimum fiziksel robot hedefi

### Prototip kapsamı (ilk aşama)
- Kullanıcıdan gelen çizim yolunu (en basit örneklerle) zemin üzerinde takip ederek işaretleme.
- İlk denemelerde “yüksek doğruluk” yerine “çalışıyor mu?” önceliği.
- Yalnızca kalemle çizim: motorlar hareketi, bir mekanizma da kalem temasını kontrol eder.

### Tahrik tipi
- **Diferansiyel tahrik** önerilir (iki tahrikli teker + önde arkada tek serbest teker).
- Bunun nedeni: yazılım komutlarında `TURN <deg>` ve `FORWARD <dist>` / `MOVE` / `MOVE_REL` yaklaşımı; ayrıca seri protokol DSL zaten bu hareket mantığını besliyor.

## 2) Önerilen donanım mimarisi (v1)

### Denetleyici kart
- **ESP32 veya Arduino sınıfı** bir kart (mevcut döngü-geri kart yazılımı ile aynı aile).
- Seri port üzerinden 115200 baud (mevcut döngü-geri kart yazılımı `SERIAL_BAUD`).
- Seri protokol v1’in `BEGIN`/`END` / `STOP` / `DONE` / `ERR` akışını yorumlayacak şekilde kart yazılımı genişletilecek.

### Motor sürücü kategorisi
- Diferansiyel tahrik için iki DC motoru sürebilen bir **H-köprü tabanlı sürücü** (ileri/geri + hız).
- Darbe genişliği modülasyonu destekli; denetleyicinin üreteceği darbe genişliği/yön sinyallerini kabul eden sürücü.
- Akım kapasitesi: seçilen dişli motorların “anlık tepe akımı” dikkate alınmalı.

### Motorlar ve tekerlekler
- **Dişli DC motor** (en azından orta torklu) × 2.
- **Tekerlek çapı** ve gövde geometrisi: `FORWARD` mesafesi ile yazılımın ileri gitme hedefi arasındaki ölçek için kritik.
- İlk prototipte enkoder kullanımı:
  - **V1 (zorunlu değil):** Enkoder olmadan da mekanik olarak hareket edilir, ancak çizgi doğruluğu sınırlı olur.
  - **Önerilen (v1.1 veya paralel):** İki tekerde enkoder ile odometri yapılabilir (kalem şekilleri daha düzenli çıkar).

### Enkoder varsayımı (opsiyon / risk yönetimi)
- Enkoder yoksa: hareket “açık çevrim” olur, tekerlek kayması hatayı büyütür.
- Enkoder varsa: `TURN` ve `FORWARD` için geri besleme ile hata azalır; ancak kart yazılımı tarafında ek eylem gerektirir (bu doküman bunun planını verir, yazılım kodu burada genişletilmez).

## 3) Kalem yukarı/aşağı (PEN UP/DOWN)

### Önerilen aktüatör seçenekleri
- En kolay ve öğrenci dostu: küçük bir **servo motor** ile kalemi temas ettir/ayır.
- Alternatif (mekanik bakım kolaylığı daha düşük olabilir): küçük bir doğrusal mekanizma + yay + yay tahliye (solenoid) vb.

### Mekanik montaj notu (çizgi kalitesi için)
- Kalem ucu yere net ve tekrarlanabilir bir açıyla oturmalı.
- Kalemin yatayda “salınım” yapmaması için basit bir kılavuz tercih edilmeli.
- Kalem ağırlığı ve yay kuvveti ayarı; ilk denemelerde en çok zaman alan konulardan biridir.

## 4) Şasi / gövde önerisi

### Öğrenciye uygun yaklaşım
- Alüminyum profil (kolay delme + sağlamlık) veya basit 3D baskı + takviye parça kombinasyonu.
- Motorlar ve tekerler titreşimi azaltacak şekilde rijit montajlanmalı.
- Öndeki/arkadaki serbest teker: kablo çekişi ve çizim sırasında sürtünmeyi azaltmak için seçilmeli.

### Sallanma riskleri
- Zemin düz değilse ve şasi sallanıyorsa kalem temas kuvveti değişir ve çizgiler dalgalanır.

## 5) Güç / batarya ve regülasyon

### Güç gereksinimi (kategorik yaklaşım)
- Motor sürücü için daha yüksek bir hat (motorların ihtiyacına göre) ve denetleyici kartı/servo için 3.3V/5V regülasyon gerekir.
- En kritik konu: motorlar çalışırken voltaj düşmesi; denetleyici kartının reset atmasına neden olabilir.

### Önerilen düzen
- Bataryadan motor sürücüye doğrudan veya uygun sigorta/anahtar üzerinden besleme.
- Denetleyici kartı/servo için ayrı regülatörler (ve ortak toprak).
- Kablo kesiti ve konnektör kalitesi: ilk prototipte bile reset riskini ciddi azaltır.

## 6) Sensör gereksinimleri

### V1 (minimum)
- Seri bağlantı (bilgisayar-seri dönüştürücü) ve denetleyici kartının doğru baud hızı.

### Opsiyonel (erken doğruluk için önerilir)
- Enkoderler (iki teker): açık çevrim yerine kapalı çevrim yaklaşımına geçilir.
- Basit kalem temas sensörü (opsiyon): kalemin gerçekten temas edip etmediği anlaşılır.
- Batarya voltaj izleme (opsiyon): reset nedenlerini daha hızlı teşhis etmeyi sağlar.

## 7) Yazılım–donanım eşlemesi (mevcut altyapı ile)

### Seri protokol bağlantısı
- İstemci tarafı `SerialDriver` ile batch modunda komut gönderir:
  - `BEGIN` → DSL komut satırları (`SPEED`, `PEN UP/DOWN`, `MOVE`, `TURN`, `FORWARD`, …) → `END`.
  - Batch bitince denetleyici `DONE` döner.
- Manuel doğrulama için `STATUS` tek satır gönderilir:
  - İstemci bekler, dönen satır `STATUS speed=... pen=... state=... queued=... last=...` formatında okunur.

### Mevcut döngü-geri kart yazılımından gerçek kart yazılımına geçiş
- Döngü-geri şu an sadece “kuyruk tüketme + dahili durum güncelleme” yapar; kalem/motor yoktur.
- Gerçek prototipte:
  - `SPEED` → motor sürücünün hız ölçeği/komutuna map edilir.
  - `PEN UP/DOWN` → servo açısı veya kalem mekanizmasının konum komutu olur.
  - `TURN` ve `FORWARD` → diferansiyel tahrik için sol/sağ teker hızlarına dönüştürülür.
  - Batch sonu → `DONE` döner, hata olursa `ERR`.

## 8) İlk fiziksel demo hedefi

En düşük maliyetle “çizim yapıyor” hissini veren demo akışı:
- Önce kalem temasını ayarla (PEN mekanizması).
- Ardından tek bir `FORWARD` ile düz bir iz.
- Sonra `TURN 90` benzeri kısa dönüş + `FORWARD` ile basit bir köşe.
- Son olarak `square` benzeri temel formun görsel konturu.

## 9) Aşamalı inşa planı (Stage 0–5)

### Stage 0: Masa/tezgah seri test (mekanik yok)
- Denetleyici kartı bilgisayar-seri dönüştürücü üzerinden bağlanır.
- İstemci tarafında seri bağlantı kurulup `STATUS` yanıtı görülür.
- Amaç: protokol ve baud uyumu.

### Stage 1: Döngü-geri kart yazılımı doğrulama (tampon + DONE/ERR)
- Döngü-geri kart yazılımı kartta çalıştırılır.
- İstemci:
  - `normal` modunda `DONE` beklenir.
  - `stop` modunda `STOP` sonrası `DONE` beklenir.
  - `malformed` modunda `ERR` beklenir.

### Stage 2: Motorlar kablolu, çizim yok
- Motor sürücüler takılır.
- Kalem mekanizması yukarıda kalır (çizim yok).
- Basit hareket denemeleri ile:
  - `TURN` ve `FORWARD` dönüşümünün mekanikte düzgün olup olmadığı gözlenir.

### Stage 3: Kalem aktüatörü (PEN) tek başına doğrulanır
- Servo ile `PEN UP` / `PEN DOWN` konumları ayarlanır.
- Kalemin yere temas kuvveti/konumu tekrarlanabilir olana kadar mekanik ayar yapılır.

### Stage 4: İlk çizgi
- Kalem aşağı konumda:
  - Kısa bir `FORWARD` denemesi ile düz bir çizgi hedeflenir.
- Eğer çizgi dalgalıysa:
  - zemin, teker kayması, pen sürtünmesi, şasi rijitliği gözden geçirilir.

### Stage 5: İlk kare (yaklaşık)
- `square` benzeri komut dizisi ile dört kenarlı temel form denenir.
- Enkoder yoksa bile “benzer şekil” hedeflenir; mutlak ölçü doğruluğu ikinci önceliktir.

## 10) Minimum malzeme listesi (kategori listesi)

Marka/model yazmadan, öğrencinin tedarik edebileceği kategori listesi:
- Denetleyici kartı: ESP32 veya Arduino sınıfı (seri port destekli)
- Seri bağlantı: bilgisayar-seri dönüştürücü / doğru kablo
- Motor sürücü: iki DC motoru süren H-köprü tabanlı sürücü + darbe genişliği modülasyonu girişli
- Motorlar: dişli DC motor × 2 (torklu)
- Tekerler: diferansiyel teker seti + yönlendirme için serbest teker
- Enkoder (opsiyon): iki teker için enkoder (v1.1 veya erken)
- Kalem aktüatörü: küçük servo (veya benzeri) + montaj braketleri
- Güç: batarya (motor hattı) + denetleyici kartı/servo için regülatör(ler)
- Sigorta / anahtar / kablolama: uygun kesit + güvenlik elemanları
- Şasi montaj malzemeleri: profil/dirsek/vida/ray, kablo kelepçeleri
- Test ekipmanı: yedek kablo, pensi ayarlamak için basit ölçüm aracı

## 11) Risk notları (öğrenci prototipi için pratik)

- Enkoder yoksa doğruluk düşer: teker kayması kareyi bozabilir.
- Güç yetersizliği: motor akımları denetleyiciyi resetleyebilir; regülasyon ve kablo kesiti kritik.
- Kalem montajı: kalem “sallanırsa” çizgiler çok kötü olur; mekanik kılavuz gerekir.
- Şasi rijitliği: yürürken titreşim kaleme dalga bindirir; rijit montaj şart.
- Tekerlek ölçeği: `FORWARD` mesafesi gerçek dünyaya aynı şekilde çevrilmez; tekerlek çapı/ölçek ilk kalibrasyonda ayarlanmalı.

