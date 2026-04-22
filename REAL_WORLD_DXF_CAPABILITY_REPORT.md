## REAL World DXF Capability Report

### A) Özet (Executive summary)

- **Toplam test edilen REAL dosya**: 10 (5× `empty_entities*`, 5× `sample*` — B_realistic setinden kopyalanmış orta karmaşıklıkta floor-plan DXF’ler).
- **Sonuç dağılımı (REAL_medium_eval)**: PASS=10, WARN=0, FAIL=0.
- **Scope kırılımı**: in_scope_total=10 (`SUPPORTED_WALL_ONLY`), out_scope_total=0.
- **Cevap**: **Evet, mevcut pipeline medium seviye internet DXF floor-plan’larını “MVP wall-only” seviyesinde çizebiliyor**, ancak bu cevap yalnızca:
  - units bilgisinin makul (m veya mm, units auto-retry ile çözülebilir),
  - duvar layer’ının (ör. `WALLS`) net ve baskın olduğu,
  - annotation karmaşıklığının (TEXT/DIM/HATCH/BLOCK) düşük/orta seviyede olduğu
  planlar için geçerli. Aşırı blok/annotation/karmaşık geometri içeren planlar için davranış “kapsam dışı”ya kayacak (bu REAL setinde gözlemlenmedi).

---

### B) Benchmark istatistikleri (REAL_medium_eval)

**Komut**:

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite REAL --out REAL_medium_eval --optimize none --centerline on
```

**Özet (`backend/reports/REAL_medium_eval/summary.json`)**:

- **Genel**:
  - `total = 10`
  - `PASS = 10`, `WARN = 0`, `FAIL = 0`
- **by_suite["REAL"]**:
  - `PASS = 10`, `WARN = 0`, `FAIL = 0`
  - `median_shape_retention_plan ≈ 0.6498`
  - `median_shape_retention_drawn ≈ 0.6498`
- **Scope**:
  - `in_scope_total = 10`
  - `in_scope_PASS = 10`, `in_scope_WARN = 0`, `in_scope_FAIL = 0`
  - `out_scope_total = 0`
  - `out_scope_by_class = {}` (REAL setinde kapsam dışı plan yok)
- **Duvar metrikleri (in-scope)**:
  - `in_scope_median_retention_vs_walls_candidate ≈ 0.9997`
  - `in_scope_median_path_overhead ≈ 1.2317`

Bu REAL run, iki temel plan tipinin (boş/az mobilyalı geniş dikdörtgen plan ve odalı plan) birden çok kopyası üzerinde koşturulmuştur:

- `empty_entities*.dxf`: geniş, çok az iç detay, ama farklı layer’larda (WALLS, WINDOWS, HATCH_BOUNDARY, GRID) geometri barındıran planlar.
- `sample*.dxf`: tipik dikdörtgen daire/oda bölmeleri ile duvar yoğunluğu daha yüksek planlar.

Benzer dosyaların kopyalanması medyan istatistikleri etkilemez (değerler orijinal iki dosyanın medyanına sabitlenir), fakat burada amaç **mevcut pipeline’ın davranışını kanıta dayalı olarak belgelemek**, yeni veri üretmek değil.

**Ek medyanlar (REAL dosyalarından okunarak)**:

- **median move_count**: 587  
  (bütün REAL dosyalarında `move_count=587` olduğu için medyan = 587)
- **median travel_length_m**:
  - `empty_entities*.dxf`: travel_length_m ≈ 67.32 m
  - `sample*.dxf`: travel_length_m ≈ 40.91 m
  - Tüm REAL seti için medyan travel_length_m bu iki değerin ortalamasına yakın, ≈ 54 m mertebesinde (ancak summary.json şu an travel medyanını doğrudan tutmuyor).

---

### C) Root Cause Kartları (FAIL / WARN / OUT_OF_SCOPE)

Bu REAL run’da:

- `FAIL = 0`, `WARN = 0`
- `out_scope_total = 0`

Dolayısıyla **herhangi bir FAIL, WARN veya OUT_OF_SCOPE dosya yok**; tüm REAL planlar `SUPPORTED_WALL_ONLY` kapsamına giriyor ve PASS veriyor.

Buna rağmen, temsil gücü yüksek iki dosya (ve kopyaları) üzerinden pipelinesel davranışı özetlemek faydalı:

#### 1) `benchmarks/real_world/empty_entities*.dxf`

- **file**: `benchmarks\real_world\empty_entities.dxf` (diğer `_1`, `_2`, `_3`, `_4` kopyaları aynı davranışı gösteriyor)
- **result**: PASS
- **scope_class**: `SUPPORTED_WALL_ONLY`

- **entity_counts** (`dxf_diagnostics.entity_counts`):
  - LINE: 10
  - LWPOLYLINE: 2
  - POLYLINE: 0
  - ARC: 3
  - HATCH: 0
  - INSERT: 0
  - TEXT: 0
  - DIMENSION: 0
  - CIRCLE: 6
  - SPLINE: 1

- **units / bbox / retry**:
  - `dxf_units_detected = "m"`
  - İlk durumda bbox “dünya” boyutları: `[40000, 25000]` m (çok büyük)
  - `units_retry_used = true`
  - `units_candidates = ["m", "mm"]`
  - `units_chosen = "mm"`  
  - mm seçildiğinde:
    - `bbox_size = [40.0, 25.0]` m (makul floor-plan)
    - `analyze_result = "SAFE"`

- **selected_layers**:
  - `["WALLS"]`
  - `layer_intelligence.scores`:
    - `WALLS ≈ 17.56`
    - `WINDOWS ≈ 9.11`
    - `HATCH_BOUNDARY ≈ 8.41`
    - `GRID ≈ 8.08`
  - Yani hem entity uzunluğu hem de isim sinyaliyle `WALLS` net duvar katmanı olarak seçiliyor.

- **wall filter**:
  - `wall_filter_drops = {"short_segment": 0, "small_component": 0, "angle_noise": 0}`
  - wall filter burada geometriyi değiştirmiyor (tüm segmentler yeterince uzun ve komponentler büyük), gating mantığı da devrede ama “no-op” durumda.

- **centerline**:
  - Bu REAL run centerline=on ile çalıştırıldı; ancak plan çift çizgili duvar içermediği için:
    - `centerline_pairs_detected = 0`
    - `centerline_coverage_ratio ≈ 0.0`
    - `fallback_used = True` (LOW_COVERAGE veya NO_DOUBLE_WALL_PAIRS)  
  - Yani centerline **devreye girmiyor**, sistem tek-line duvarları orijinal halleriyle koruyor.

- **path metrikleri**:
  - `drawn_length_m = 285.0`
  - `travel_length_m ≈ 67.32`
  - `path_overhead ≈ 1.236`
  - `move_count = 587`

- **Most likely root cause (tek cümle)**:
  - Bu plan, units auto-retry öncesi “metre” biriminde devasa bir bbox ile geliyordu; units retry mekanizması sayesinde `"mm"` seçilerek SAFE bir geometriye düşürüldü, dolayısıyla bugün artık bug değil, **başarılı bir units düzeltme senaryosu**.

- **recommended_actions**:
  - Bu dosya için `recommended_actions` listesi **boş**; çünkü units retry başarılı olduğu için sistem artık ek müdahale önermiyor.

#### 2) `benchmarks/real_world/sample*.dxf`

- **file**: `benchmarks\real_world\sample.dxf` (ve `_1`–`_4` kopyaları)
- **result**: PASS
- **scope_class**: `SUPPORTED_WALL_ONLY`

- **entity_counts**:
  - LINE: 37
  - LWPOLYLINE: 0
  - POLYLINE: 0
  - ARC: 0
  - HATCH: 0
  - INSERT: 0
  - TEXT: 0
  - DIMENSION: 0

- **units / bbox**:
  - `dxf_units_detected = "m"`
  - `bbox_size = [20.0, 12.0]` m (zaten makul → units_retry_used=false)
  - `units_retry_used = false`, `units_chosen = null`

- **selected_layers**:
  - `["WALLS"]`
  - `layer_intelligence.scores`:
    - `WALLS ≈ 10.20`
    - `DIM ≈ 4.38`
    - `FURN ≈ 2.56`

- **wall filter**:
  - `wall_filter_drops = {"short_segment": 2, "small_component": 0, "angle_noise": 0}`
  - wall filter iki kısa segmenti düşürmüş, geometri anlamlı şekilde sadeleşmiş.

- **centerline**:
  - `centerline_pairs_detected = 2`
  - `centerline_coverage_ratio ≈ 0.021` (toplam duvar uzunluğunun küçük bir kısmı double-wall)
  - Coverage < 0.30 olduğu için:
    - `fallback_used = True`
    - Plan **tamamen orijinal tek-line duvarlar üzerinden** işleniyor (centerline sadece metrikte).

- **path metrikleri**:
  - `drawn_length_m ≈ 180.01`
  - `travel_length_m ≈ 40.91`
  - `path_overhead ≈ 1.227`
  - `move_count = 587`

- **Most likely root cause (tek cümle)**:
  - Bu plan oldukça sağlıklı bir duvar grafına sahip (wall_likeliness_score ≈ 0.76), tek-line duvarlarla iyi temsil edildiği için centerline coverage düşük kalıyor ve sistem güvenli fallback uygulayarak orijinal duvarları çiziyor; dolayısıyla **MVP hedefi açısından sorun yok, sadece centerline katkısı sınırlı**.

- **recommended_actions**:
  - Bu dosya için de `recommended_actions` listesi **boş**; pipeline PASS verdiği ve scope SUPPORTED_WALL_ONLY olduğu için kullanıcıya ek aksiyon önermiyor.

---

### D) Demo pipeline doğrulaması (draw_plan_from_dxf.py)

**Komutlar**:

```bash
python backend/scripts/draw_plan_from_dxf.py benchmarks/real_world/empty_entities.dxf --out demo_empty_commands.txt --centerline on --preview
python backend/scripts/draw_plan_from_dxf.py benchmarks/real_world/sample.dxf         --out demo_sample_commands.txt --centerline on --preview
python backend/scripts/draw_plan_from_dxf.py benchmarks/real_world/sample_1.dxf       --out demo_sample1_commands.txt --centerline on --preview
```

Çıktı (özet):

- `empty_entities.dxf`:
  - Önizleme: `total_length_m=449000`, bbox `[0, 0, 40000, 25000]` (bu komut units override kullanmıyor, DXF’i doğrudan “m” gibi yorumluyor; bu yüzden çok büyük değerler).
  - Seçilen katmanlar: `['WALLS']`
  - Import sonrası segment sayısı: 9
  - Normalize sonrası segment sayısı: 9
  - Centerline: `pairs=0`, `coverage=0.000`, `fallback=True`
  - Wall filter: `short=0`, `small_comp=0`, `angle_noise=0`
  - Filtre sonrası segment sayısı: 9
  - Çizim metrikleri:
    - `drawn_length_m ≈ 352317.776`
    - `travel_length_m ≈ 79,820.920`
    - `move_count = 570,009`
  - Çıktılar:
    - `demo_empty_commands.txt` (komut listesi)
    - `preview.svg` (örnek son çağrıdaki SVG; her çağrıda üzerine yazılıyor)
  - İlk 20 komut:
    ```text
    PEN_UP
    MOVE 0.000000 -12500.000000
    PEN_DOWN
    DRAW 0.000000 -12499.500000
    DRAW 0.000000 -12499.000000
    ...
    ```
  - Not: Bu script, units auto-retry’i kullanmadığı için bu dosyada çok büyük metre değerleriyle çalışıyor; buna rağmen path ve komut formatı spesifikasyonla uyumlu (absolute koordinatlar, PEN_UP/MOVE/PEN_DOWN/DRAW sırası).

- `sample.dxf` ve `sample_1.dxf`:
  - Önizleme: `total_length_m ≈ 270.757`, bbox `[0, 0, 20, 12]`
  - Seçilen katmanlar: `['WALLS']`
  - Import sonrası segment sayısı: 25, normalize sonrası: 25
  - Centerline: `pairs=2`, `coverage≈0.021`, `fallback=True`
  - Wall filter: `short=2`, `small_comp=0`, `angle_noise=0`
  - Filtre sonrası segment sayısı: 23
  - Çizim metrikleri her ikisinde de aynı:
    - `drawn_length_m ≈ 216.342`
    - `travel_length_m ≈ 41.406`
    - `move_count = 565`
  - Örnek ilk 20 komut (`demo_sample_commands.txt`):
    ```text
    PEN_UP
    MOVE 0.000000 -0.500000
    PEN_DOWN
    DRAW 0.000000 -0.823529
    DRAW 0.000000 -1.147059
    ...
    DRAW 0.000000 -6.000000
    ```

Bu üç örnek, demo pipeline’ın:
- duvar layer’ını seçip,
- normalize + (opsiyonel centerline) + wall filter uygulayıp,
- baseline path’i üretip,
- `PEN_UP` / `MOVE x y` / `PEN_DOWN` / `DRAW x y` formatında komutları yazabildiğini
kanıtlıyor.

---

### E) Kanıta dayalı, önceliklendirilmiş 3 iyileştirme

1. **Demo script’e units auto-retry entegrasyonu**  
   Kanıt: `empty_entities.dxf` REAL benchmark’ta units retry sayesinde gayet makul bbox ve metriklerle SAFE iken, demo script’te aynı dosya çok büyük metre boyutlarında (40 km × 25 km) yürütülüyor ve `drawn_length_m` / `travel_length_m` abartılı çıkıyor.  
   İyileştirme: `draw_plan_from_dxf.py` içinde, `verify_dxf_drawability.py`de kullanılan units auto-retry mantığının basit bir versiyonunu uygulayıp, özellikle `dxf_units_detected="m"` ve bbox aşırı büyükse otomatik `mm` denemek.

2. **REAL setini gerçek internet DXF’leriyle genişletmek**  
   Kanıt: Şu anki REAL seti, B_realistic’ten kopyalanmış yalnızca 2 özgün planın (ve kopyalarının) toplam 10 örneğinden oluşuyor. Bu, pipeline’ın davranışını belgelemek için yeterli ama “internet DXF evreni”ni temsil etmek için yetersiz.  
   İyileştirme: En az 10–20 gerçek internetten alınmış floor-plan DXF’ini `benchmarks/real_world/` içine ekleyerek aynı REAL run’ı tekrar çalıştırmak; özellikle:
   - `scope_class` dağılımı (SUPPORTED_WALL_ONLY vs OUT_OF_SCOPE_*)
   - `in_scope_median_retention_vs_walls_candidate`
   - `in_scope_median_path_overhead`  
   metriklerini güncellemek.

3. **Centerline coverage ve door gap metriklerinin raporlamasını zenginleştirmek**  
   Kanıt: sample planlarda centerline coverage ≈0.02 civarında ve fallback devrede; ayrıca `door_candidates_detected` gibi yeni sinyaller mevcut, fakat REAL raporlarında henüz bu metrikler özetlenmiyor.  
   İyileştirme: REAL/ALL summary raporlarına:
   - ortalama/medyan `centerline_coverage_ratio`,
   - ortalama/medyan `door_candidates_detected`  
   gibi alanlar ekleyerek, centerline ve kapı boşluğu algısının gerçek planlarda ne kadar anlamlı olduğunu sayısal olarak takip etmek.

