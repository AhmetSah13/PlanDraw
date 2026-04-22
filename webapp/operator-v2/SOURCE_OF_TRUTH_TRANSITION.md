# Operator V2 Source of Truth Geçiş Planı

## Amaç
`operator-v2`, eski frontend ağacına yeni geliştirme eklemeden resmi ürün frontend'i olarak devralınacaktır.

## Geçiş sırası
1. Yeni iş yalnızca `webapp/operator-v2/` altında geliştirilir.
2. `webapp/frontend/` yalnızca referans ve acil hata inceleme alanı olarak tutulur.
3. Operatör akışının beş ana ekranı `operator-v2` içinde gerçek backend kontratıyla tamamlanır.
4. Build, lint, unit test ve Playwright E2E aynı kökte zorunlu geçiş kapısı olur.
5. Çevre yönlendirmesi ve dağıtım entrypoint'i doğrulama sonrası `operator-v2`'ye alınır.

## Geçiş kapıları
- Plan Yükle, Hizala, Kontrol Et, Çalıştır ve Sonuçlar ekranları gerçek endpoint'lerle çalışıyor olmalı.
- Tüm kullanıcı metinleri Türkçe olmalı.
- `npm run build`, `npm run lint`, `npm run test`, `npm run e2e` başarılı olmalı.
- Backend kontratı değiştirilmeden akış tamamlanmalı.

## Legacy durumu
- `webapp/frontend/`: legacy / referans
- `webapp/operator-v2/`: aktif resmi aday source of truth

## Son karar
Aşağıdaki koşullar sağlandığında resmi source of truth kararı `webapp/operator-v2/` için uygulanır:
- ana akışlar üretim öncesi test kapısını geçerse,
- legacy frontend'e yeni özellik eklenmezse,
- runtime giriş noktası `operator-v2` dağıtımından servis edilirse.
