## Component Endpoint Path Raporu (suite B)

### 1. Özet

Amaç: Centroid tabanlı component sıralama denemesinden sonra, **gerçek pen-up travel**’ın centroid değil, component giriş/çıkış **uç noktalarına** bağlı olduğunu gözlemledik. Bu raporda, endpoint tabanlı component sıralama algoritmasını ve `benchmarks/B_realistic` altındaki `empty_entities.dxf` ve `sample.dxf` üzerindeki etkisini özetliyoruz.

Önemli nokta: Yeni endpoint tabanlı sıralama, travel’ı iyileştiremediği durumlarda **gating sayesinde tamamen devre dışı** bırakılıyor; dolayısıyla mevcut davranışı bozmayıp sadece debug/analiz sinyali sağlıyor.

### 2. Algoritma (Endpoint Tabanlı Component Order)

#### 2.1 Component ve aday uç noktalar

- `build_components_with_candidates(segments, snap_tol=1e-4, k=6)`:
  - Normalized duvar segmentlerinden node/edge grafı kurulur (`_build_graph`).
  - Node bazında BFS ile connected component kümeleri bulunur.
  - Her component için:
    - **Centroid**:
      - Node pozisyonlarının ortalaması \((cx, cy)\).
    - **Derece**:
      - `degree[node] = len(neighbors(node))`.
    - **Aday uç noktalar**:
      - Önce `degree == 1` (dangling endpoint) olan node’lar seçilir.
      - Eğer hiç `degree == 1` yoksa, centroid’e en uzak node’lardan en fazla `k` tanesi seçilir.
      - Her component için maksimum `k=6` adet aday uç nokta tutulur: `candidates[i] = [(x, y), ...]`.

#### 2.2 Stroke → component eşleme

- Baseline path (`baseline_segments`) üretildikten sonra:
  - Her polyline için centroid hesaplanır.
  - Polyline, `build_components_with_candidates` çıktısındaki en yakın component centroid’ine atanır.
  - Böylece `comp_groups[idx] = [poly1, poly2, ...]` map’i elde edilir.

#### 2.3 Componentler arası cost ve sıralama

- İki component arasındaki cost:

  \[
  cost(A \rightarrow B) = \min\_{a \in cand(A), b \in cand(B)} \|a - b\|
  \]

  - Ayrıca bu min mesafeyi veren \((a^\*, b^\*)\) çifti de saklanır.
- Nearest-neighbor sıralama:
  - Başlangıç component: centroid’i orijine en yakın olan component.
  - Ardışık adımlarda, son component \(C\) için `cost(C -> J)` en küçük olan J seçilir.
  - Çıktı: `order = [c0, c1, c2, ...]`.

#### 2.4 Yeni path ve gating

- Yeni path (`reordered_segments`) yalnızca **component sırası** açısından farklı; component içi stroke sıralaması baseline’dan alınır.
- Yeni komutlar: `comp_commands = compile_path_to_commands_from_segments(reordered_segments, ...)`.
- `comp_dt = measure_drawn_travel(comp_commands, start_xy=...)` ile gerçek travel ve drawn ölçülür.
- Metrikler:
  - `baseline_travel_length_m` (baseline path için)
  - `component_travel_length_m` (component-order path için)
  - `component_order_travel_reduction_pct = (1 - comp_travel / baseline_travel) * 100`
  - `component_count`
  - `avg_component_length_m`
  - `pen_up_between_components_distance_m`: ardışık componentler arasındaki \(\|a^\* - b^\*\|\) mesafelerinin toplamı.
  - `transitions`: her transition için `{from_component, to_component, from_point, to_point, distance_m}`.
- **Gating**:
  - Sadece şu koşul sağlanırsa component path kullanılır:
    - `component_travel_length_m <= baseline_travel_length_m * 0.9` **veya**
    - `component_travel_length_m <= 10.0` (mutlak travel eşiği).
  - Aksi halde:
    - `component_path_decision.used = false`, `reason = "TRAVEL_TOO_HIGH"`
    - Komutlar baseline path’ten alınır.

### 3. Benchmark Sonuçları (suite B — B_component_endpoint_path)

Komut:

```bash
python backend/scripts/verify_dxf_drawability.py \
  --input benchmarks --suite B \
  --out B_component_endpoint_path \
  --optimize none --path-mode component
```

#### 3.1 empty_entities.dxf

- **Baseline path (karşılaştırma)**:
  - `baseline_travel_length_m ≈ 67.3209`
  - `drawn_length_m = 285.0`
  - `path_overhead ≈ 1.2362`
  - `move_count = 587`
- **Endpoint component path**:
  - `component_travel_length_m ≈ 221.1872`
  - `component_order_travel_reduction_pct ≈ -228.56` (yani travel ciddi oranda **kötüleşmiş**)
  - `component_count = 5`
  - `avg_component_length_m ≈ 57.0`
  - `pen_up_between_components_distance_m ≈ 49.45`
  - `transitions` örnekleri:
    - 0 → 4: from `(-20.0, -12.5)` to `(-20.0, -4.5)` (8.0 m)
    - 4 → 5: from `(-20.0, -4.5)` to `(-20.0, 3.5)` (8.0 m)
    - 5 → 1: from `(-20.0, 3.5)` to `(-10.0, 12.5)` (≈13.45 m)
    - 1 → 3: from `(-10.0, -12.5)` to `(10.0, -12.5)` (20.0 m)
  - `component_path_decision`:
    - `used = false`
    - `reason = "TRAVEL_TOO_HIGH"`
    - `baseline_travel_m ≈ 67.32`
    - `component_travel_m ≈ 221.19`
    - `baseline_move_count = 587`, `component_move_count = 587`

**Yorum**: Endpoint tabanlı sıralama, componentler arası mesafeleri minimize etmeye çalışsa da, baseline path zaten oldukça iyi durumda olduğundan travel iyileşmesi sağlamıyor; aksine travel artmış durumda ve gating doğru şekilde baseline’a fallback ediyor.

#### 3.2 sample.dxf

- **Baseline path**:
  - `baseline_travel_length_m ≈ 40.9055`
  - `drawn_length_m ≈ 180.01`
  - `path_overhead ≈ 1.2272`
  - `move_count = 587`
- **Endpoint component path**:
  - `component_travel_length_m ≈ 154.9238`
  - `component_order_travel_reduction_pct ≈ -278.74`
  - `component_count = 13`
  - `avg_component_length_m ≈ 13.85`
  - `pen_up_between_components_distance_m ≈ 24.53`
  - `transitions` örnekleri:
    - 3 → 4: `(0.0, -0.5) → (0.0, 0.5)` (1.0 m)
    - 4 → 6: `(0.0, 0.5) → (0.0, 2.0)` (1.5 m)
    - 6 → 5: `(5.0, -3.0) → (5.0, -4.0)` (1.0 m)
    - 5 → 8: `(5.0, -4.0) → (10.0, -2.0)` (≈5.39 m)
    - ... (toplam 12 transition, toplam ≈24.53 m)
  - `component_path_decision`:
    - `used = false`
    - `reason = "TRAVEL_TOO_HIGH"`
    - `baseline_travel_m ≈ 40.91`
    - `component_travel_m ≈ 154.92`
    - `baseline_move_count = 587`, `component_move_count = 587`

**Yorum**: `sample.dxf` için de baseline path zaten kompakt olduğu için, component sıralaması travel’ı net şekilde iyileştiremiyor; gating component path’i devre dışı bırakıp baseline çizgiyi koruyor.

### 4. Sonuç ve Sonraki Adımlar

- Endpoint tabanlı component-order path modu şu anda:
  - Component uç noktalarını degree==1 ve/veya “en uzak” node’lar üzerinden belirliyor.
  - Componentler arası cost’u bu uç noktalar üzerinden hesaplıyor.
  - Travel metriğini `measure_drawn_travel` ile gerçekte **ölçüp** baseline ile kıyaslıyor.
  - Travel kriterini sağlamadığı **tüm** B_realistic örneklerinde baseline’a güvenli fallback yapıyor.
- Bu sayede:
  - Path modu **deneysel** kalsa bile, mevcut davranışı bozmadan komponent bazlı pen-up analizi yapılabiliyor.
  - Raporlar, component bazlı travel metriklerini ve seçilen entry/exit çiftlerini ayrıntılı olarak gösterdiği için, ileride daha akıllı component içi traversal (örneğin gerçek Chinese Postman / Euler augmentasyonu) tasarlamak için sağlam bir gözlem tabanı sağlıyor.

Şu anki B_realistic örneklerinde acceptance kriteri (`component_travel <= baseline_travel * 0.9` veya `<= 10m`) sağlanmadığı için, **hiçbir dosyada** component path devreye girmiyor; bu da MVP’in “kaliteyi asla kötüleştirmeme” hedefine uyumlu.

