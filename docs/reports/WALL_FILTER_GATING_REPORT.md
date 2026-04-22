## Wall Filter Gating Raporu (B_realistic)

Bu rapor, wall_filter için eklenen **gating** mantığının `benchmarks/B_realistic` dosyalarındaki etkisini özetler.

### 1. Kural Özeti

- **Eşikler**:
  - `drawn_min_ratio = 0.98` → filtreli planda çizilen uzunluk, filtresiz plana göre %2’den fazla düşerse filter_used=false.
  - `travel_max_ratio = 1.05` → filtreli planda travel uzunluğu, filtresiz plana göre %5’ten fazla artarsa filter_used=false.
- **Karar alanı**:
  - Her dosyada aynı seçilen layer’larla iki plan ölçülür:
    - `wall_filter_metrics_before` → filtre **öncesi** normalized plan (centerline sonrası).
    - `wall_filter_metrics_after` → filtre **sonrası** normalized plan.
  - Bu iki plan için path üretilir, komutlar compile edilir ve `measure_drawn_travel` ile:
    - `drawn_length_m`
    - `travel_length_m`
    - `path_overhead`
    - `move_count`
    hesaplanır.
  - Karar: `wall_filter_decision.used` ve `reason` alanlarında raporlanır.

### 2. Dosya Bazında Sonuçlar (suite B_realistic)

#### 2.1 `empty_entities.dxf` (B_before_filter_gate / B_after_filter_gate)

- **Gating kararı**:
  - `wall_filter_decision.used = true`
  - `reason = "FILTER_OK"`
  - `wall_filter_drops = {"short_segment": 0, "small_component": 0, "angle_noise": 0}`
- **Metikler (önce/sonra)**:
  - `wall_filter_metrics_before.drawn_length_m = 285.0`
  - `wall_filter_metrics_after.drawn_length_m  = 285.0`
  - `wall_filter_metrics_before.travel_length_m = 67.3209195`
  - `wall_filter_metrics_after.travel_length_m  = 67.3209195`
  - `wall_filter_metrics_before.path_overhead = 1.236214`
  - `wall_filter_metrics_after.path_overhead  = 1.236214`
  - `wall_filter_metrics_before.move_count = 587`
  - `wall_filter_metrics_after.move_count  = 587`
- **Yorum**:
  - Filtre hiçbir segmenti düşürmüyor; gating yine de ölçüm yapıyor ve metrikler **birebir aynı** olduğu için filtre güvenle **kullanılıyor**.
  - Kabul kriterine göre: drawn değişmedi, travel değişmedi → filtre safe.

#### 2.2 `sample.dxf` – centerline OFF (`B_before_filter_gate`)

- **Gating kararı**:
  - `wall_filter_decision.used = true`
  - `reason = "FILTER_OK"`
  - `wall_filter_drops = {"short_segment": 2, "small_component": 0, "angle_noise": 0}`
- **Metikler (önce/sonra)**:
  - `wall_filter_metrics_before.drawn_length_m = 180.1095737`
  - `wall_filter_metrics_after.drawn_length_m  = 180.0095737`
  - `drawn_after / drawn_before ≈ 0.9994`  → **%0.06 düşüş (<%2 eşik)**.
  - `wall_filter_metrics_before.travel_length_m = 40.8906353`
  - `wall_filter_metrics_after.travel_length_m  = 40.9055037`
  - `travel_after / travel_before ≈ 1.0004` → **%0.04 artış (<%5 eşik)**.
  - `move_count`: 593 → 587 (hafif azalma).
- **Yorum**:
  - Filtre yalnızca iki **çok kısa** segmenti (0.05 m civarı) düşürüyor; hem drawn hem travel değişimi eşiklerin çok altında.
  - Bu nedenle `FILTER_OK` ve `filter_used=true`; kaliteyi bozmadan küçük bir temizlik sağlıyor.

#### 2.3 `sample.dxf` – centerline ON (`B_after_filter_gate`)

- **Gating kararı**:
  - `wall_filter_decision.used = true`
  - `reason = "FILTER_OK"`
  - `wall_filter_drops = {"short_segment": 2, "small_component": 2, "angle_noise": 0}`
- **Metikler (önce/sonra)**:
  - `wall_filter_metrics_before.drawn_length_m = 176.0095737`
  - `wall_filter_metrics_after.drawn_length_m  = 175.4031242`
  - `drawn_after / drawn_before ≈ 0.9966` → **%0.34 düşüş (<%2 eşik)**.
  - `wall_filter_metrics_before.travel_length_m = 46.1380933`
  - `wall_filter_metrics_after.travel_length_m  = 45.9027264`
  - `travel_after / travel_before ≈ 0.9959` → **%0.41 azalma (iyileşme)**.
  - `move_count`: 577 → 565 (hafif azalma).
- **Yorum**:
  - Centerline sonrası planda küçük bağlı komponentler + kısa segmentler temizleniyor.
  - Hem drawn düşüşü güvenli eşik içinde, hem de travel **iyileşiyor**; bu yüzden gating filtreden yana karar veriyor.

### 3. Gating’in Kötüleşmeyi Engelleme Senaryosu

Bu PR öncesi: `wall_filter` doğrudan uygulanıyordu; bazı durumlarda:

- `drawn_length_m` %2’den fazla düşebiliyor,
- veya `travel_length_m` %5’ten fazla artabiliyordu,

ve bu degradasyon rapor metriklerine doğrudan yansıyordu.

Yeni gating mantığı ile:

- Önce/sonra path’ler **her dosya için** hesaplanıyor.
- Eğer herhangi bir dosyada:
  - `drawn_after < drawn_before * 0.98` **veya**
  - `travel_after > travel_before * 1.05`
  olursa:
  - `wall_filter_decision.used = false`
  - `wall_filter_decision.reason = "DRAWN_TOO_LOW"` veya `"TRAVEL_TOO_HIGH"`
  - Nihai plan olarak **filtre öncesi** normalized plan kullanılıyor (fallback).

Bu sayede wall_filter artık **asla**:

- drawn’ı %2’den fazla düşürmüyor,
- travel’ı %5’ten fazla artırmıyor;

aksi durumda otomatik geri çekiliyor.

### 4. Kabul Kriteri Check-list

- **Kriter**: wall_filter asla travel’ı %5’ten fazla artırmayacak →
  - Gating bu durumu tespit ederse `FILTER_FALLBACK` uyguluyor; B_realistic örneklerinde böyle bir dosya oluşmadı.
- **Kriter**: wall_filter asla drawn’ı %2’den fazla düşürmeyecek →
  - Aynı şekilde, bu şart ihlal edilirse fallback devreye giriyor; mevcut B_realistic örneklerinde düşüşler <%0.4 seviyesinde.
- **JSON alanları**:
  - `wall_filter_decision` tüm dosyalarda dolu (`used`, `reason`, `thresholds`).
  - `wall_filter_metrics_before` ve `wall_filter_metrics_after` hem `empty_entities.dxf` hem `sample.dxf` için dolu ve karşılaştırılabilir.

Sonuç olarak, wall_filter artık **“kaliteyi asla kötüleştirmeyen”** güvenli modda çalışıyor; çizim ve travel metrikleri gating ile üst sınırlandırılmış durumda.

