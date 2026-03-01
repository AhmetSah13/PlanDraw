# Golden DXF Suite

Bu klasör, DXF çizilebilirlik doğrulayıcısı için örnek / regresyon DXF dosyalarınızı koyabileceğiniz yerdir.

## Kullanım

1. Bu klasöre test etmek istediğiniz `.dxf` dosyalarını (veya alt klasörlere) kopyalayın.
2. Backend kökünden doğrulayıcıyı çalıştırın:

   ```bash
   cd backend
   python scripts/verify_dxf_drawability.py --input golden_dxfs --out reports
   ```

3. Raporlar `reports/` klasörüne yazılır: her dosya için `reports/<dosya_adı>.json` ve özet için `reports/summary.json`.

## Sonuçlar

- **PASS** — Çizim güvenli; export başarılı.
- **WARN** — Güvenli fakat hareket sayısı veya çakışma eşiği yüksek; ayar iyileştirmesi önerilir.
- **FAIL** — BLOCKED veya pipeline hatası; önerilen aksiyonlar raporlarda listelenir.
- **PASS_AFTER_RETRY** — İlk denemede BLOCKED; otomatik strateji (Fast / Walls only / Detail) ile başarılı.
- **FAIL_AFTER_RETRY** — Tüm retry stratejileri sonrası hâlâ başarısız.

Bu klasör varsayılan olarak boş commit edilir; kendi DXF dosyalarınızı ekleyerek regresyon suite'inizi oluşturabilirsiniz. İsteğe bağlı olarak `minimal.dxf` gibi tek bir örnek dosya bırakılmış olabilir.
