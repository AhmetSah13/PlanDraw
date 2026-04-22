## MVP WALL CENTERLINE (HYBRID) RAPORU

### 1. Ne değişti? (Full fallback → hybrid)

Önceki sürümde centerline davranışı:

- Double-wall çiftleri bulunup orta-çizgi üretildikten sonra:
  - Eğer `centerline_total_length_m / input_total_length_m` çok küçükse
    → **komple fallback** (tüm plan eski wall-only segmentlere dönüyordu).
  - Bu, double-wall toplamının az olduğu ama yine de anlamlı olduğu planlarda centerline’ın hiç devreye girmemesine yol açıyordu.

Yeni **hybrid** davranış:

- Double-wall eşlemesi yapılan segmentler için **centerline** üretilip kullanılıyor.
- Çifte girmeyen wall segmentleri **aynen korunuyor**.
- Normalize sadece centerline segmentleri üzerinde uygulanıyor (snap/merge/stub temizleme), sonra hibrid listeye ekleniyor:
  - `hybrid_segments = normalize(centerlines) + unmatched_original_segments`
- Artık coverage düşük olduğu için komple fallback yok; yalnızca:
  - Hiç çift bulunamadığında (`NO_DOUBLE_WALL_PAIRS`, `NO_DOUBLE_WALL_PAIRS_IN_GAP_RANGE`)
  - Veya centerline üretimi tamamen başarısız olduğunda (`CENTERLINE_GENERATION_FAILED`)
  - fallback yapılıyor.

Böylece:

- Planın küçük bir kısmı bile double-wall ise, o kısım için orta çizgi üretiliyor; geri kalanın single-line duvarları olduğu gibi kalıyor.
- `centerline_enabled = off` iken path tamamen eski davranışla birebir aynı; CLI bayrağıyla tam geri uyumluluk korunuyor.

---

### 2. Yeni metrikler (centerline_metrics)

`centerline_metrics` içine eklenen ve rapora yansıyan yeni alanlar:

- `double_wall_coverage_ratio`  
  - Tanım: `centerline_total_length_m / input_total_length_m`  
  - Yorum: Planın toplam duvar uzunluğunun ne kadarı double-wall centerline’a dönüştürülebilir durumda.

- `hybrid_applied_centerline_length_m`
  - Tanım: Normalize edilmiş centerline segmentlerinin toplam uzunluğu.
  - Hibritte kullanılan centerline uzunluğunu gösterir.

- `hybrid_applied_ratio`
  - Tanım: `hybrid_applied_centerline_length_m / input_total_length_m`  
  - Yorum: Hibrit olarak gerçekten uygulanan centerline oranı (coverage ile aynı, çünkü normalize sonrası hepsi kullanılıyor).

- `hybrid_used: bool`
  - `true`: Centerline + orijinal segmentler birlikte kullanıldı (hibrit aktif).
  - `false`: Hiç çift bulunamadı veya üretim tamamen başarısız; tam fallback (eski wall-only).

Mevcut alanlar (aynı şekilde devam ediyor):

- `detected_double_wall_pairs_count`
- `centerline_segments_count`
- `centerline_success_ratio`
- `fallback_used` / `fallback_reason`
- `input_total_length_m`
- `centerline_total_length_m`

---

### 3. Double-wall benchmark sonuçları (A_expected_pass)

Koşulan komutlar:

```bash
# Referans (centerline kapalı)
python backend/scripts/verify_dxf_drawability.py \
  --input benchmarks --suite ALL --out ref_hybrid --optimize on --centerline off

# Hybrid centerline açık
python backend/scripts/verify_dxf_drawability.py \
  --input benchmarks --suite ALL --out cl_hybrid --optimize on --centerline on
```

Double-wall test DXF’ler: `benchmarks/A_expected_pass/` içine eklendi:

- `double_wall_rectangle.dxf`
- `double_wall_L_shape.dxf`
- `double_wall_T_junction.dxf`

#### 3.1. double_wall_rectangle.dxf (tam dikdörtgen)

- **Referans (ref_hybrid)**:
  - `drawn_length_m`: 62.40
  - `travel_length_m`: 0.28
  - `move_count`: 819
  - `centerline` yok (off)

- **Hybrid (cl_hybrid)**:
  - `centerline_metrics`:
    - `detected_double_wall_pairs_count`: 4
    - `centerline_total_length_m`: 30.40
    - `input_total_length_m`: 62.40
    - `double_wall_coverage_ratio`: ≈ 0.487
    - `hybrid_used`: true
    - `fallback_used`: false
  - Çizim metrikleri:
    - `drawn_length_m`: 30.40  (artık sadece orta-çizgi uzunluğu)
    - `travel_length_m`: 0.42  (biraz arttı, ama hala çok düşük)
    - `path_overhead`: ≈ 1.014
    - `move_count`: 399  (819 → 399, yaklaşık %50 azalma)

**Yorum**:  
Tüm duvarlar net double-wall olduğundan, coverage ≈ %48 (dış + iç konturlara karşı orta-çizgi) ve hibrit devrede:

- Orta-çizgi perimetresi 30.4 m (iç/orta dikdörtgen),
- Dış/inner iki kontur yerine tek düzgün centerline üretilmiş,
- Hareket sayısı neredeyse yarıya inmiş; robot için çok daha sade path elde edilmiş.

#### 3.2. double_wall_L_shape.dxf (L formu)

- **Hybrid (cl_hybrid)**:
  - `centerline_metrics`:
    - `detected_double_wall_pairs_count`: 6
    - `centerline_total_length_m`: 30.0
    - `input_total_length_m`: 62.4
    - `double_wall_coverage_ratio`: ≈ 0.481
    - `hybrid_used`: true
    - `fallback_used`: false
  - Çizim metrikleri:
    - `drawn_length_m`: 30.0  (L’nin orta-çizgisi)
    - `move_count`: 399  (önce 831 idi, yaklaşık yarı yarıya)
    - `travel_length_m`: 0.71 → path_overhead ≈ 1.02

**Yorum**:  
L şeklindeki iki paralel poliline, her kolda doğru şekilde eşleşmiş; coverage ≈ %48 ve hibrit devrede.  
Sonuç: L duvar konturu single centerline olarak çiziliyor, path çok daha sade ve deterministik hale geliyor.

#### 3.3. double_wall_T_junction.dxf (T kavşağı)

- **Hybrid (cl_hybrid)**:
  - `centerline_metrics`:
    - `detected_double_wall_pairs_count`: 2
    - `centerline_total_length_m`: 14.0
    - `input_total_length_m`: 28.0
    - `double_wall_coverage_ratio`: 0.5
    - `hybrid_used`: true
    - `fallback_used`: false
  - Çizim metrikleri:
    - `drawn_length_m`: 14.0  (T’nin gövde + tepesinin orta-çizgisi)
    - `move_count`: 283  (önce 567 idi)
    - `travel_length_m`: 3.47 (yaklaşık aynı, path hattı daha kısa ama bağlantılar benzer)

**Yorum**:  
T kavşağında dört duvar segmenti çiftlere ayrılıp tek centerline T konturu üretiliyor.  
Çizgi uzunluğu yarıya düşüyor (28 → 14), hareket sayısı da yarı yarıya azalıyor; topolojik yapı (T şekli) korunuyor.

#### 3.4. Single-line plan (minimal.dxf)

- `centerline_metrics`:
  - `detected_double_wall_pairs_count`: 0
  - `centerline_total_length_m`: 0.0
  - `double_wall_coverage_ratio`: 0.0
  - `hybrid_used`: false
  - `fallback_used`: true, `fallback_reason`: `"NO_DOUBLE_WALL_PAIRS"`
- Çizim metrikleri:
  - `drawn_length_m`, `travel_length_m`, `move_count` → referansla **birebir aynı**.

**Yorum**:  
Bu plan baştan single-line olduğundan centerline devreye girmiyor; tüm davranış tamamen referans (wall-only) hattı ile aynı kalıyor.

---

### 4. Hybrid ne zaman devreye giriyor?

Özet kural:

- **Hybrid devre dışı (tam fallback)**:
  - `detected_double_wall_pairs_count == 0` ise:
    - `fallback_used = true`, `fallback_reason ∈ {"NO_DOUBLE_WALL_PAIRS", "NO_DOUBLE_WALL_PAIRS_IN_GAP_RANGE"}`
    - `hybrid_used = false`
    - Örnek: `minimal.dxf`, `empty_entities.dxf` (hem referans benchmarktan gelen single-line duvarlar, hem de double-wall içermeyen gerçek planlar).
  - Veya centerline üretimi tamamen başarısız (numerik/normalize hatası vs) ise:
    - `fallback_reason = "CENTERLINE_GENERATION_FAILED"`, `hybrid_used = false`.

- **Hybrid devrede**:
  - En az bir çift bulunduysa ve centerline üretilebildiyse:
    - `fallback_used = false`
    - `hybrid_used = true`
    - `hybrid_applied_centerline_length_m > 0`
    - Örnek: üç double-wall test dosyasının hepsinde (`double_wall_rectangle`, `double_wall_L_shape`, `double_wall_T_junction`) bu durum görülüyor.

Bu sayede tek bir dosya raporundan:

1. **Units doğru mu?**
   - `units_retry_used`, `units_chosen`, `units_retry_metrics["mm"/"m"].bbox_size` ve `analyze_result`.
2. **Layer seçimi doğru mu?**
   - `layer_intelligence.selected_layers` ve `scores`.
3. **Centerline gerçekten uygulandı mı, yoksa sadece wall-only mı çalıştı?**
   - `centerline_fallback_used` / `centerline_fallback_reason`
   - `double_wall_coverage_ratio`, `hybrid_applied_centerline_length_m`, `hybrid_applied_ratio`

ile soruya çok hızlı ve deterministik cevap verebiliyoruz.

---

### 5. Riskler ve nasıl ölçülecek?

**Olası false positive riskleri**

- Yakın ve paralel ama aslında duvar olmayan çizgiler (örneğin grid veya mobilya detayları) double-wall gibi algılanabilir:
  - Bunu sınırlamak için:
    - Sadece wall-only filtreden geçmiş, `selected_layers` içindeki segmentler üzerinde çalışıyoruz.
    - Gap/angle/overlap eşikleri sıkı:
      - Gap: `[wall_gap_min_m, wall_gap_max_m]` (ör. 0.05–0.40 m)
      - Angle: `parallel_angle_tol_deg` (varsayılan 3°)
      - Overlap: `overlap_min_ratio` (varsayılan 0.60+)

**Nasıl ölçülür / izlenir?**

- Double-wall coverage ve hibrit oranı:
  - `double_wall_coverage_ratio`
  - `hybrid_applied_ratio`
  - Beklenti:
    - Tipik mimari double-wall planlarda bu oranlar anlamlı (örn. 0.3–0.8) seviyesinde olmalı.
    - Single-line veya karışık/noisy planlarda ise 0 veya çok düşük kalabilir; bu durumda fallback/hibrit davranış zaten path’i çok değiştirmez.

- Benchmark tabanlı regresyon:
  - Her yeni DXF seti için `--centerline off` ve `--centerline on` koşularını birlikte çalıştırmak:
    - PASS/WARN/FAIL sayıları,
    - `move_count`, `travel_length_m`, `shape_retention_drawn`,
    - `centerline_metrics.double_wall_coverage_ratio` dağılımı
  - Özellikle B_realistic ve C_stress setlerinde:
    - Coverage çok yüksek (örneğin > 0.8) olup da görsel olarak hatalı path üretilen dosyalar “false positive” candidate olarak işaretlenebilir.

**Kontrollü rollout stratejisi**

- Prod’da:
  - Varsayılanı bir süre `--centerline off` bırakıp sadece benchmark/QA ortamında `--centerline on` ile ölçüm yapmak.
  - Metrikler stabil ve görsel doğrulamalar tatmin edici olduğunda:
    - UI/flag üzerinden centerline’ı opsiyonel bir “Duvar Centerline (beta)” modu olarak açmak.


