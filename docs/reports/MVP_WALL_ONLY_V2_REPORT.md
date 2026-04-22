## MVP WALL-ONLY V2 RAPORU

### 1. Yeni metrikler (wall-only adaleti)

- **original_total_length_m**: Tüm DXF içindeki çizilebilir toplam uzunluk (duvar + annotation; benchmark önceki sürümle geriye uyumlu).
- **original_walls_candidate_length_m**: Sadece `layer_intelligence.selected_layers` içindeki, wall-only drawable entity’lerden (LINE/LWPOLYLINE/POLYLINE + discretize ARC/SPLINE) gelen toplam uzunluk; budget/normalize öncesi.
- **original_drawable_length_m**: Wall-only filtreden geçen tüm segmentlerin (tüm katmanlar) toplam uzunluğu; budget/normalize öncesi.
- **retention_vs_all**: `drawn_length_m / original_total_length_m` — tüm DXF’e göre ne kadarını çizdik (annotation dahil).
- **retention_vs_walls_candidate**: `drawn_length_m / original_walls_candidate_length_m` — sadece “seçilen duvar layer’ları”na göre retention (MVP kalite metriği).
- **retention_vs_drawable**: `drawn_length_m / original_drawable_length_m` — wall-only pipeline içi kaybı ölçen metrik.

Bu sayede DIM/FURN/GRID gibi annotation katmanları **retention_vs_walls_candidate** hesabını şişirmiyor; MVP kalite artık gerçekten “duvar” üzerinden değerlendiriliyor.

### 2. Optimizer raporu ve karar mantığı

Benchmark artık path optimizer için iki ayrı metrik seti ve açık karar bilgisi üretiyor:

- **commands_baseline_metrics**: Gerçekte yürütülen komutların ölçümleri
  - drawn_length_m, travel_length_m, path_length_m, path_overhead, has_pen_down.
- **commands_optimized_metrics**: Optimize edilmiş aday komutların ölçümleri
  - Aynı alanlar; sadece stroke sıralaması/değişimi sonrası.
- **optimizer_decision**:
  - `used`: true/false
  - `reason`: `"TRAVEL_IMPROVED"` veya `"TRAVEL_WORSE_FALLBACK"`

Karar kuralı:

- Eğer `commands_optimized_metrics.travel_length_m` **<** `commands_baseline_metrics.travel_length_m` ise:
  - optimizer_decision.used = true, reason = `"TRAVEL_IMPROVED"`
  - yürütmede optimize edilmiş komutlar kullanılıyor.
- Aksi halde:
  - optimizer_decision.used = false, reason = `"TRAVEL_WORSE_FALLBACK"`
  - yürütmede baseline komutlar kullanılıyor (optimizasyon sadece raporlanıyor).

Ek olarak:

- **travel_length_before_optimize / after_optimize** ve **path_overhead_before_optimize / after_optimize** bu iki senaryoyu sayısal olarak karşılaştırıyor.
- **travel_reduction_pct** artık her zaman `optimized`e göre hesaplanıyor (negatif değerler “aslında travel kötüleşirdi” anlamına geliyor, ancak karar optimizer_decision üzerinden okunuyor).

### 3. Benchmark özeti (mvp_wall_only_run_v2 / summary.json)

- **Genel sonuçlar**
  - Toplam dosya: **3**
  - PASS: **3**, WARN: **0**, FAIL: **0**
  - PASS_AFTER_RETRY: **0**, FAIL_AFTER_RETRY: **0**

- **Suite bazında retention (eski shape_retention\_*)**
  - **A_expected_pass (A)**:
    - PASS: 1, WARN: 0, FAIL: 0
    - median_shape_retention_plan: **0.684783**
    - median_shape_retention_drawn: **0.684783**
  - **B_realistic (B)**:
    - PASS: 2, WARN: 0, FAIL: 0
    - median_shape_retention_plan: **0.649976**
    - median_shape_retention_drawn: **0.649976**

### 4. Örnek dosya analizi (B_realistic / empty_entities.dxf)

- **Genel bilgiler**
  - result: **PASS**, analyze_result: **SAFE**
  - dxf_units_detected: `"m"` (units retry ile `"mm"` seçildi)
  - bbox_size (world): **[40.0, 25.0]**
  - selected_layers: `["WALLS"]`

- **Yeni uzunluk metrikleri**
  - original_total_length_m: **449.0 m**
  - original_drawable_length_m: **449.0 m**  
    (Bu dosyada tüm drawable geometri zaten wall-only filtreden geçiyor.)
  - original_walls_candidate_length_m: **285.0 m**  
    (Sadece `WALLS` layer’ındaki duvar kandidatı çizgiler.)
  - drawn_length_m: **285.0 m**
  - **retention_vs_all**: 0.634744  
    → Toplam DXF uzunluğunun yaklaşık %63’ü çizildi (annotation dahil).
  - **retention_vs_walls_candidate**: **1.0**  
    → Seçilen duvar layer’ındaki geometri **eksiksiz** çizildi (MVP için ideal durum).
  - **retention_vs_drawable**: 0.634744  
    → Wall-only pipeline, tüm drawable DXF uzunluğunun %63’ünü duvar olarak kabul etmiş durumda.

- **Units auto-retry**
  - units_retry_used: **True**, units_retry_reason: `"UNITS_SCALE_MISMATCH"`
  - units_candidates: `["m", "mm"]`, units_chosen: `"mm"`
  - **Karşılaştırma**:
    - m:
      - bbox_size: `[40000.0, 25000.0]`
      - path_length_m: **352320.92**
      - move_count: **760020**
      - analyze_result: **BLOCKED**
    - mm:
      - bbox_size: `[40.0, 25.0]`
      - path_length_m: **352.32**
      - move_count: **587**
      - analyze_result: **SAFE**
  - **Yorum**: BBox ve limitler açısından `m` yorumu fiziksel olarak anlamsız olduğu için, mm yorumu deterministik olarak seçildi; bu seçim hem `units_retry_metrics` hem de `dxf_diagnostics.units` altında açıkça görülebiliyor.

- **Layer intelligence**
  - candidate_layers: `["WALLS", "WINDOWS", "HATCH_BOUNDARY"]`
  - selected_layers: `["WALLS"]`
  - scores:
    - WALLS: 17.5602
    - WINDOWS: 9.1051
    - HATCH_BOUNDARY: 8.4076
    - GRID: 8.0822
  - **Yorum**: Layer zekâsı, isim + uzunluk + entity mix ile WALLS katmanını açık ara duvar katmanı olarak seçiyor; yeni retention_vs_walls_candidate metrikleri bu seçimin doğruluğunu sayısallaştırıyor.

- **Path optimizer kararı**
  - commands_baseline_metrics:
    - drawn_length_m: **285.0 m**
    - travel_length_m: **67.32 m**
    - path_overhead: **1.236214**
  - commands_optimized_metrics:
    - drawn_length_m: **317.02 m**
    - travel_length_m: **175.01 m**
    - path_overhead: **1.552047**
  - optimizer_decision:
    - used: **false**
    - reason: **"TRAVEL_WORSE_FALLBACK"**
  - travel_reduction_pct: **-159.96**
  - **Yorum**: Optimizer teorik olarak daha fazla duvar üzerinden geçerek path’i uzatıyor ve travel’ı kötüleştiriyor; bu yüzden karar **fallback**. Metrikler üzerinden, “denenen ama kullanılmayan” bir optimizasyon olduğunu açıkça görmek mümkün.

### 5. Kısa değerlendirme

- Yeni **wall-only odaklı uzunluk metrikleri** sayesinde, retention artık duvar layer’ı seviyesinde adil bir şekilde ölçülüyor; annotation / grid / ölçü layer’ları retention_vs_walls_candidate’ı etkilemiyor.
- **Optimizer raporu**; baseline vs optimized yolun hem travel hem de overhead açısından nasıl davrandığını net gösteriyor ve kararın (`used`/`fallback`) nedeni her dosya için deterministik şekilde kaydediliyor.
- Mevcut benchmark setinde (A + B) FAIL olmaması, hem units retry hem de layer intelligence + wall-only pipeline kombinasyonunun MVP hedefi olan “basit DXF planlarda duvarları güvenilir çizmek” için yeterince stabil çalıştığını gösteriyor.

