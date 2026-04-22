# Operator V2 Manual Acceptance Checklist

## Kısa Kullanım Notu

- **Ne zaman kullanılmalı:** `operator-v2` için sürüm adayı doğrulamasında, görsel/copy/polish turu sonrası ve teslim öncesi son manuel kapı kontrolünde kullanılmalıdır.
- **Kim kullanmalı:** Ürün sahibi, QA sorumlusu ve operasyon akışını bilen geliştirici birlikte (en az iki göz prensibiyle) uygulamalıdır.
- **Hangi koşullardan sonra uygulanmalı:** En az şu kapılar başarılı olduktan sonra çalıştırılmalıdır:
  - `npm run build`
  - `npm run lint`
  - `npm run test`
  - `npm run e2e`

## 1) Plan Yükle

- [ ] Ekran ilk açıldığında ana görevin plan kaynağını hazırlamak olduğu net biçimde anlaşılıyor.
- [ ] DXF / DWG / JSON / Manuel kaynak seçenekleri açık ve karışıklık yaratmadan seçilebiliyor.
- [ ] Dosya veya metin olmadan ana aksiyon tetiklenirse kullanıcıya anlaşılır bir hata mesajı gösteriliyor.
- [ ] Başarılı hazırlama sonrası “Hizala” adımına geçiş yönlendirmesi net ve görünür.
- [ ] Teknik detaylar varsayılan görünümü boğmadan ikincil alanda tutuluyor.

## 2) Hizala

- [ ] Plan verisi hazır değilken ekran bunu açıkça engel durumu olarak bildiriyor.
- [ ] Kontrol noktası giriş alanları (CAD X/Y, Saha X/Y) anlaşılır etiketlerle sunuluyor.
- [ ] “Hizalamayı doğrula” birincil aksiyon olarak net görünüyor.
- [ ] Sonuç mesajı (hazır / dikkat / engelli) operatöre bir sonraki kararı güvenli şekilde aldırıyor.
- [ ] Uygun durumda “Kontrol Et” adımına geçiş yönlendirmesi açık.

## 3) Kontrol Et

- [ ] Ekran dili “kontrol/analiz” odaklı; yanlış şekilde “optimizasyon” vaadi vermiyor.
- [ ] “Kontrolü çalıştır” birincil aksiyon olarak tutarlı konum ve görsellikle sunuluyor.
- [ ] Sonuç metni “hazır mı, engelli mi, neden” sorularını net yanıtlıyor.
- [ ] Bulgu listesi boşsa bu durum sakin ve anlaşılır bir kullanıcı diliyle belirtiliyor.
- [ ] Uygun sonuçlarda “Çalıştır” adımına geçiş yönlendirmesi net.

## 4) Çalıştır

- [ ] Simülasyon ile canlı gönderim akışları net şekilde ayrışıyor.
- [ ] Riskli aksiyonlar görsel olarak doğru hiyerarşiyle (uyarı/dikkat) ayrıştırılıyor.
- [ ] Ön kontrol mesajları operatörü gereksiz panik yaratmadan yönlendiriyor.
- [ ] Durdur / yeniden bağlan / tekrar dene davranışları ve metinleri tutarlı.
- [ ] İş kimliği, son olay ve durum özeti anlaşılır biçimde gösteriliyor.

## 5) Sonuçlar

- [ ] Ekran sıralaması (özet -> yönlendirme -> teknik detay) operatör odaklı ve anlaşılır.
- [ ] Çıktı biçimi seçimi açık; seçeneklerin ne yaptığı karışmıyor.
- [ ] “Çıktıyı hazırla” sonrası başarı/uyarı/hata mesajları net.
- [ ] Üretilen çıktı bilgisi (dosya adı, içerik önizleme vb.) anlaşılır sunuluyor.
- [ ] Teknik içerik yalnızca ihtiyaç halinde açılacak şekilde ikinci katmanda tutuluyor.

## Genel Handoff Kararı

- [ ] Tüm adımlar geçtiyse: **GO**
- [ ] Kritik adımlardan biri başarısızsa: **NO-GO**

