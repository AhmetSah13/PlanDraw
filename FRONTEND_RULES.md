# Frontend Kuralları

## 1. Ürün hedefi
Bu frontend bir “demo paneli” değil, operatör odaklı ürün arayüzüdür.

## 2. Dil
- Tüm kullanıcı metinleri Türkçe olacak.
- İngilizce/Türkçe karışık kullanım yasak.
- Teknik olmayan metinler sade ve yönlendirici olacak.

## 3. Kullanıcı akışı
Ana akış:
1. Plan Yükle
2. Hizala
3. Kontrol Et
4. Çalıştır
5. Sonuçlar

Bu isimler kullanıcıya gösterilecek.
Prepare / Align / Plan / Execute / Monitor kullanıcı metni olarak kullanılmayacak.

## 4. UX ilkeleri
- Her ekranda tek ana iş
- Her ekranda tek primary action
- “Şimdi ne yapmalıyım?” sorusuna net cevap
- “Hazır mıyım?” sorusuna net cevap
- “Neden hazır değilim?” sorusuna net cevap
- Riskli aksiyonlar açıkça ayrılmalı
- Teknik detaylar ikincil katmanda olmalı

## 5. Görsel ilkeler
- Güçlü hiyerarşi
- Az renk, net vurgu
- Az border
- Az kutu kalabalığı
- Profesyonel input ve file upload
- Default tarayıcı görünümü yasak
- Tutarlı spacing ve typography

## 6. Mimari ilkeler
- Aktif frontend tek source of truth olacak
- Legacy frontend üstüne yeni katman eklenmeyecek
- Data layer ayrı olacak
- Workflow/state ayrı olacak
- Execution lifecycle ayrı olacak
- UI primitives ayrı olacak

## 7. Teknik standart
- React
- TypeScript
- Vite
- TanStack Query
- React Hook Form
- Zod
- Zustand veya eşdeğer net workflow modeli
- Test edilebilir service katmanı
- En az smoke E2E

## 8. Dosya yükleme standardı
DXF / DWG / JSON alanlarında:
- sürükle bırak desteği
- kabul edilen format bilgisi
- yükleme durumu
- hata sebebi
- tekrar dene
- başarılı yükleme özeti
zorunludur.

## 9. Çalışma şekli
Yeni frontend gerekiyorsa ayrı v2 uygulama olarak kurulmalı.
Eski frontend üzerinde makyaj/refactor ile ilerlenmeyecek.

## 10. Done kriteri
Bir ekran tamamlandı sayılmaz:
- kullanıcı akışı net değilse
- Türkçe copy tamam değilse
- backend kontratı doğrulanmadıysa
- build/lint/test geçmediyse
- ekran hâlâ operatöre ne yapacağını söylemiyorsa
