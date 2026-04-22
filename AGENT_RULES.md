# Agent Çalışma Kuralları

Bu repo üzerinde çalışan agent aşağıdaki kurallara uymak zorundadır.

## 1. Genel ilke
- Mevcut sistemi “kendi kafana göre iyileştirme”.
- Her büyük değişiklikten önce kısa plan ver.
- Onay beklenmeyen görevlerde bile önce ne yapacağını yaz, sonra uygula.
- Sessizce mimari yön değiştirme.

## 2. Source of truth
- Backend source of truth: `backend/`
- Aktif frontend source of truth: agent her görev başında açıkça belirtmek zorunda.
- Legacy klasörleri aktif ürün gibi kullanma.
- Eski yapı ile yeni yapı aynı anda geliştirilmemeli.

## 3. Backend kontratı
- Backend endpoint isimlerini keyfi değiştirme.
- Request/response shape’lerini sessizce değiştirme.
- Frontend tarafında backend kontratını kıran değişiklik yapma.
- Her frontend işi sonunda gerçek endpoint eşleşmesini doğrula.

## 4. Frontend değişiklik kuralları
- Patch üstüne patch yapma.
- Eski kırık UI mantığını makyajlama.
- Yeni UI gerekiyorsa yeni ürün akışı mantığıyla kur.
- Kullanıcı metinleri tamamen Türkçe olacak.
- İngilizce kullanıcı metni bırakma.
- Teknik detaylar ilk katmanda gösterilmeyecek.

## 5. Görev yürütme formatı
Her görev şu sırayla yürütülür:
1. Kısa teşhis
2. Değişecek dosyalar
3. Uygulama planı
4. Kod değişikliği
5. Build/lint/test
6. Kısa rapor

## 6. Rapor formatı
Her iş sonunda şunları yaz:
- Değişen dosyalar
- Neden değişti
- Backend kontratına etkisi
- Build sonucu
- Lint sonucu
- Test sonucu
- Kalan riskler

## 7. Yasaklar
- Onay almadan geniş kapsamlı bağımlılık ekleme
- Aktif olmayan legacy klasörlerde gereksiz değişiklik yapma
- Çalışmayan şeyi çalışıyor gibi sunma
- Build geçti diye işi tamamlandı sayma
- Runtime contract doğrulaması olmadan “tamam” deme

## 8. Başarı kriteri
Başarılı iş demek:
- çalışma kontratı bozulmamış,
- kod anlaşılır,
- scope dışına çıkılmamış,
- kullanıcı deneyimi net iyileşmiş,
- rapor doğrulanabilir.
