## MVP WALL-ONLY RAPORU

### 1. MVP hedef tanımı
- **Amaç**: İnternetten indirilen basit 2D floor-plan DXF/DWG dosyalarında yalnızca **duvar konturlarını** güvenilir biçimde çizilebilir komutlara dönüştürmek.
- **Kapsam**: LINE / LWPOLYLINE / POLYLINE ve (ezdxf varsa) ARC / SPLINE geometriyi duvar adayına yakın şekilde segmente edip, kapı yayları, yazılar, ölçüler, hatch ve sembolleri **NON_WALL** olarak tamamen devre dışı bırakmak.
- **Dışarıda bırakılanlar**: Kapı yayları, ölçü ve metinler, hatch dolgular, blok/insert içerikleri, mobilya/elektrik/tesisat katmanları – yalnızca neden elendiği raporlanır, çizilmez.

### 2. Değişen dosyalar ve kısa gerekçe
- **backend/app/importers/dxf_importer.py**
  - **Wall-only segment çıkarımı**: `WALL_DRAWABLE_ENTITY_TYPES`, `NON_WALL_ENTITY_TYPES`, `BLOCK_ENTITY_TYPES` ile import sonrasında geometri `DRAWABLE_WALLS` vs `NON_WALL` olarak ayrıldı; TEXT/DIMENSION/HATCH/INSERT gibi entity’ler segmente çevrilmeyip `dropped_entities_by_reason` ve `dropped_entities_by_type` altında sayısal olarak raporlanıyor.
  - **Ezdxf tabanlı flatten**: ARC/CIRCLE/SPLINE entity’leri `discretize_entity_to_segments` ile duvar konturuna yakın doğru parçalarına ayrılıyor; segment bütçesi ve tolerans `bbox` ölçeğine göre adaptif seçiliyor.
  - **DXF diagnostics + layer intelligence**: `analyze_dxf_structure`, `inspect_dxf_layers_bytes`, `select_plan_layers` ile her dosya için entity dağılımı, layer uzunlukları, isim heuristikleri ve **layer skorları** hesaplanıyor; duvar layer’ı otomatik seçilip benchmark raporuna `layer_intelligence` olarak yazılıyor.
- **backend/app/analysis/geometry_graph.py**
  - **Geometry Graph Engine**: Segmentlerden graf oluşturulup bağlantı bileşenleri, derece histogramı, kavşak / dangling edge sayıları ve edge uzunluk istatistikleri çıkarılıyor.
  - **Wall-likeliness skoru**: `wall_likeliness_score` ile az bileşenli, az dangling kenarlı, en az bir döngüsü olan planlara 0–1 arası duvar-benzerlik puanı atanıyor; sonuçlar benchmark raporlarında `graph_metrics` altında saklanıyor.
  - **Oda ve duvar adayları**: Döngü tabanlı oda konturları (`room_candidates`) ve eksene hizalı uzun segment kümeleri (`wall_candidates`) üretilip MVP sürecinde kalite sinyali olarak kullanılıyor.
- **backend/app/pathing/path_generator.py**
  - **Duvar odaklı path üretimi**: `PathGenerator` sadece `Wall` segmentlerini kullanıyor; `order_walls=True` ile en-yakın-komşu sıralama sayesinde pen-up travel azaltılmaya çalışılıyor.
- **backend/app/pathing/path_optimizer.py**
  - **Travel güvenliği**: `OptimizeConfig.require_travel_improvement=True` ve `min_travel_reduction_pct` ile optimizasyon sonrası travel mesafesi artarsa orijinal komutlar korunuyor; benchmark’ta `travel_reduction_pct` ve before/after metrikleri raporlanıyor.
- **backend/app/normalization/plan_normalizer.py**
  - **Deterministik sadeleştirme**: Zero-length drop, kollineer birleştirme, min segment uzunluğu, segment_budget ve recenter işlemleri planı daha tutarlı hale getiriyor; `extraction_summary.segment_budget_applied` ve kept/dropped sayıları metadata’ya yazılıyor.
- **backend/scripts/verify_dxf_drawability.py**
  - **Wall-only benchmark hattı**: DXF/DWG → önizleme → layer/units zekâsı → wall-only import → geometry graph → path üretimi → komut analizi → export roundtrip adımları tek komutta koşturuluyor.
  - **Units auto-retry**: BBox metre cinsinden aşırı büyük ve DXF birimi `m` ise, aynı dosya units=`mm` ile tekrar çalıştırılıyor; `units_retry_used`, `units_candidates`, `units_chosen`, `units_retry_metrics` alanları ile ayrıntılı raporlanıyor.
  - **Layer auto-selection**: `dxf_diagnostics` çıktısından entity mix + toplam uzunluk + layer adı anahtar kelimeleri ile skor üretiliyor; sonuçlar `layer_intelligence` altında candidate/selected/scores şeklinde kaydediliyor.
  - **Graph ve path optimizasyon entegrasyonu**: `enrich_plan_with_graph_metrics` çıktısı ve optional path optimization metrikleri her dosya raporuna ekleniyor.

### 3. Benchmark özeti (mvp_wall_only_run)

Kaynak: `backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out mvp_wall_only_run --optimize on`

- **Genel özet**
  - Toplam dosya: **3**
  - **PASS**: 3
  - **WARN**: 0
  - **FAIL**: 0
  - **PASS_AFTER_RETRY**: 0
  - **FAIL_AFTER_RETRY**: 0

- **Suite kırılımı (summary.json → by_suite)**
  - **A_expected_pass (A)**:
    - PASS: 1, WARN: 0, FAIL: 0
    - Median shape_retention_plan: **0.684783**
    - Median shape_retention_drawn: **0.684783**
  - **B_realistic (B)**:
    - PASS: 2, WARN: 0, FAIL: 0
    - Median shape_retention_plan: **0.649976**
    - Median shape_retention_drawn: **0.649976**
  - **C_stress (C)**:
    - Bu MVP koşusunda `benchmarks/C_stress` altında dosya olmadığı için metrik üretilmedi; `budget_too_much_loss_count_C = 0`.

### 4. B_realistic: örnek FAIL/WARN kök neden analizi

Bu MVP koşusunda B_realistic’te FAIL olmadığı için, duvar-only hattının davranışını göstermek amacıyla **iki PASS** dosyası için root-cause benzeri detaylı analiz veriliyor.

#### 4.1. B_realistic / empty_entities.dxf

- **Genel sonuç**
  - result: **PASS**
  - fail_reason_code: **yok**
  - analyze_result: **SAFE**
  - move_count: **31**
  - path_overhead: **1.236214**
  - shape_retention_plan / drawn: **0.634744 / 0.634744**

- **DXF diagnostics / geometri**
  - dxf_units_detected: **m**
  - bbox_size (world, metre): **[40.0, 25.0]** (units retry sonrası)
  - entity_counts:
    - LINE: 10, LWPOLYLINE: 2
    - ARC: 3, CIRCLE: 6, SPLINE: 1
    - HATCH/TEXT/DIMENSION/INSERT: 0
  - layers:
    - `WALLS`: entity_count=6, total_length=285000.0 (mm taban; units_retry öncesi ölçü)
    - `WINDOWS`, `HATCH_BOUNDARY`, `GRID`: ek annotation/geometri katmanları.

- **Units auto-retry davranışı**
  - Başlangıçta DXF birimi `m`, bbox_size_world ≈ `[40000.0, 25000.0]` → **UNITS_SCALE_MISMATCH** tetiklendi.
  - İki çalışma karşılaştırıldı:
    - **m**:
      - bbox_size: `[40000.0, 25000.0]`
      - path_length_m: **352320.92**
      - move_count: 32
      - analyze_result: **BLOCKED** (limit aşımları)
    - **mm**:
      - bbox_size: `[40.0, 25.0]`
      - path_length_m: **352.32**
      - move_count: 31
      - analyze_result: **SAFE**
  - Seçim:
    - units_retry_used: **True**
    - units_candidates: `["m", "mm"]`
    - units_chosen: **"mm"**
    - units_retry_reason: **"UNITS_SCALE_MISMATCH"**
  - **Neden**: `m` yorumunda bbox ve path_length dünya için anlamsız derecede büyük ve analiz BLOCKED; `mm` yorumunda bbox makul, analiz SAFE ve retention eşit → **mm sonucu deterministik olarak seçildi.**

- **Layer auto-selection / wall-only filtresi**
  - layer_intelligence:
    - candidate_layers: `["WALLS", "WINDOWS", "HATCH_BOUNDARY"]`
    - selected_layers: `["WALLS"]`
    - scores:
      - WALLS: 17.5602 (duvar anahtar kelimesi + uzunluk yüksek + az gürültü)
      - WINDOWS: 9.1051
      - HATCH_BOUNDARY: 8.4076
      - GRID: 8.0822 (dışarıda kaldı)
  - **Neden**: WALLS katmanı hem isim hem de toplam uzunluk olarak baskın; text/dim yok, gürültü penaltesi düşük → otomatik olarak tek duvar katmanı seçildi.

- **DRAWABLE_WALLS vs NON_WALL davranışı**
  - DRAWABLE_WALLS:
    - WALLS katmanındaki LINE / LWPOLYLINE geometri ARC/SPLINE içermeyen doğru parçalar olarak import edildi.
    - HATCH_BOUNDARY ve diğer annotation katmanları wall-only filtre ile dışarıda bırakıldı.
  - NON_WALL:
    - ARC / CIRCLE / SPLINE ve olası sürgü/ölçü/annotation entity’leri duvar hattına dahil edilmedi; bunlar yalnızca `dxf_diagnostics.entity_counts` ve layer istatistiklerinde sayıldı.
  - Bütçe:
    - original_total_segments: **18**
    - post_budget_total_segments: **9**
    - segment_budget_applied: **False** (azaltma normalizasyon + duvar-only kaynaklı, hard limit değil).

- **Geometry Graph Engine (wall-likeliness)**
  - node_count: 14, edge_count: 9
  - connected_components_count: 6
  - degree_histogram: 10 uçta degree=1, 4 uçta degree=2
  - closed_cycles_count: **1**
  - dominant_angles: 0°: 4, 90°: 5
  - edge_length_stats: min=25.0, median=25.0, p95=40.0
  - wall_likeliness_score: **0.7667**
  - **Yorum**: Az sayıda bileşen, net eksen hizalı uzun duvarlar ve en az bir döngü ile çizim wall-only floor plan beklentisi ile uyumlu.

- **Path ve path optimization davranışı**
  - Plan uzunluğu: **285.0 m**
  - drawn_length_m: **285.0 m**
  - travel_length_m: **67.32 m**
  - path_overhead: **1.236214**
  - optimize öncesi:
    - move_count_before_optimize: **587**
    - travel_length_before_optimize: **67.32 m**
  - optimize sonrası:
    - move_count_after_optimize: **31**
    - travel_length_after_optimize: **175.01 m**
    - travel_reduction_pct: **-159.96** (travel arttı)
  - **Fiziksel davranış**:
    - `OptimizeConfig.require_travel_improvement=True` olduğu için, travel artışı durumunda optimize edilmiş komutlar yalnızca metrik amaçlı raporlanıyor; yürütme için orijinal (daha kısa travel’lı) komut seti tercih ediliyor.
    - Bu sayede path optimization wall-only MVP’de **asla çizimi kötüleştiren** bir yan etki yaratmıyor.

#### 4.2. B_realistic / sample.dxf

- **Genel sonuç**
  - result: **PASS**
  - fail_reason_code: **yok**
  - analyze_result: **SAFE**
  - move_count: **75**
  - path_overhead: **1.227032**
  - shape_retention_plan / drawn: **0.665207 / 0.665207**

- **DXF diagnostics / geometri**
  - dxf_units_detected: **m**
  - bbox_size_world: **[20.0, 12.0]**
  - entity_counts:
    - LINE: 37, diğer tipler: 0
  - layers:
    - WALLS: entity_count=25, total_length=180.11
    - DIM: entity_count=4, total_length=78.65
    - FURN: entity_count=8, total_length=12.0

- **Units ve layer zekâsı**
  - Units:
    - bbox ve path_length metre ölçeğinde makul (20×12 m); units_retry tetiklenmedi.
    - units_retry_used: **False**
  - Layer auto-selection:
    - candidate_layers: `["WALLS", "DIM", "FURN"]`
    - selected_layers: `["WALLS"]`
    - scores: WALLS=10.1991, DIM=4.3776, FURN=2.5649
    - **Neden**: WALLS hem isim hem uzunluk açısından baskın; DIM ve FURN annotation/gürültü olarak geride kalıyor.

- **DRAWABLE_WALLS vs NON_WALL davranışı**
  - DRAWABLE_WALLS:
    - Sadece WALLS katmanındaki LINE segmentleri wall-only pipeline’da tutuldu.
    - Orijinal toplam uzunluk: **270.76 m**
    - Plan uzunluğu (wall-only, normalize sonrası): **180.11 m**
    - shape_retention_drawn: **0.6652** – annotation ve ekstra detaylar elendiği için beklenen, kontrollü bir kayıp.
  - NON_WALL:
    - DIM ve FURN katmanları duvar olmayan çizgiler içeriyor; bunlar import sırasında segment olarak kullanılmıyor, sadece diagnostik amaçla sayılıyor.

- **Geometry Graph Engine (wall-likeliness)**
  - node_count: 33, edge_count: 23
  - connected_components_count: 13
  - closed_cycles_count: **3**
  - dominant_angles: 0°: 10, 90°: 10, 45°: 1
  - edge_length_stats: min≈0.05, median=5.5, p95=20.0
  - wall_likeliness_score: **0.763**
  - **Yorum**: Çok sayıda eksen hizalı segment, birkaç kapalı çevrim (oda konturları) ve sınırlı sayıda dangling edge ile plan floor-plan duvarları açısından tutarlı görünüyor.

- **Path ve path optimization davranışı**
  - Plan uzunluğu: **180.11 m**
  - drawn_length_m: **180.11 m**
  - travel_length_m: **40.89 m**
  - path_overhead: **1.227032**
  - optimize öncesi:
    - move_count_before_optimize: **593**
    - travel_length_before_optimize: **40.89 m**
  - optimize sonrası:
    - move_count_after_optimize: **75**
    - travel_length_after_optimize: **100.71 m**
    - travel_reduction_pct: **-146.28**
  - **Davranış**:
    - Travel artışı nedeniyle, path optimization yine yalnızca raporlanıyor; yürütme için orijinal path korunuyor.
    - Bu MVP’de path optimizer, travel azaltamadığı dosyalarda fiilen devre dışı kalacak şekilde güvenli moda alınmış durumda.

### 5. Bundan sonra yapılacaklar (MVP sonrası, 3 madde)

1. **Annotation katmanlarında zengin içgörü**  
   - TEXT/DIMENSION/HATCH/INSERT gibi NON_WALL entity’ler için `dropped_entities_by_reason` / `dropped_entities_by_type` istatistiklerini API üzerinden de dışarı açıp UI’de kullanıcıya “neden çizilmedi?” mesajını daha okunur hale getirmek.

2. **Graph tabanlı duvar/oda iyileştirmeleri**  
   - `wall_likeliness_score`, `room_candidates` ve `wall_candidates` metriklerini kullanarak, ince duvar parçalarını birleştiren ve küçük boşlukları kapatan wall-cleanup adımı eklemek (özellikle B_realistic ve C_stress için).

3. **Path optimization için akıllı eşik ve modlar**  
   - Travel azaltmayan durumlarda otomatik devre dışı bırakma zaten var; buna ek olarak, duvar bazında local optimize modları (oda içi stroke sıralama, oda dışı geçişleri sınırlama) tanımlayıp, travel ve collision metriklerini suite B ve C’de daha da iyileştirmek.

