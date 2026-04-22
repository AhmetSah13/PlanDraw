## Graph Tabanlı Duvar Traversal Raporu (suite B)

### 1. Amaç

Mevcut optimizer, komut seviyesinde stroke reorder/join yaptığı için:

- `move_count` değerini çok düşürse bile
- `travel_length_m` değerini ciddi şekilde artırıyor,

ve her zaman `optimizer_decision.reason = TRAVEL_WORSE_FALLBACK` ile baseline’a geri dönülüyordu.

Bu PR’ın hedefi: **SUPPORTED_WALL_ONLY** kapsamındaki planlarda, duvar grafı üzerinden uzun, sürekli **PEN-DOWN** stroke’lar üretip **PEN-UP travel** mesafesini azaltmak (gerekirse bir miktar retrace pahasına).

### 2. Algoritma (backend/app/pathing/graph_traversal.py)

- **Graf kurulumu**:
  - Girdi: `NormalizedPlan.segments` (duvar-only, normalize + wall_filter sonrası).
  - Node’lar: `snap_tol = 1e-4` ile snap edilmiş uç noktalar.
  - Kenarlar: her segment bir undirected edge (`u`, `v`, `length`, `p1`, `p2`).
- **Traversal stratejisi (MVP)**:
  - Şimdilik basit ve deterministik **DFS-backtrack** kullanılıyor:
    - Her component için bir başlangıç node’u seçiliyor.
    - Yeni bir edge’e giderken segment geometri çiziliyor (PEN-DOWN).
    - DFS bittiğinde, recursion’dan geri dönerken aynı edge ters yönde **yeniden** çiziliyor (geri dönüşü de stroke’a ekliyor).
  - Böylece:
    - Her connected component için **tek bir sürekli stroke** elde ediliyor.
    - Bütün kenarlar en az bir kez çiziliyor; çoğu kenar iki kez (gidiş + dönüş).
  - Çıktı formatı: `path_segments = [ [(x,y), ...], ... ]`
  - Metrikler:
    - `components_count`: kaç stroke üretildi.
    - `duplicated_edge_length_m ≈ drawn_total - unique_edge_total`.
    - `traversal_mode_used = "dfs_backtrack"`.

### 3. verify_dxf_drawability.py Entegrasyonu

- Yeni CLI parametresi:
  - `--path-mode {baseline, graph}` (varsayılan `baseline`):
    - `baseline`: mevcut `PathGenerator` + segment bazlı path.
    - `graph`: yukarıdaki DFS-backtrack graf traversal’ı.
- `run_one` içinde path aşaması:
  - Her zaman önce **baseline path** üretiliyor:
    - `baseline_segments`, `baseline_commands`, `baseline_dt = measure_drawn_travel(...)`, `baseline_move_count`.
  - Eğer `path_mode = "graph"` ise ayrıca:
    - `graph_segments, graph_metrics = generate_graph_traversal_path(...)`
    - `graph_commands`, `graph_dt`, `graph_move_count` hesaplanıyor.
  - **Gating kriterleri**:
    - `baseline_travel = baseline_dt.travel_length_m`
    - `graph_travel = graph_dt.travel_length_m`
    - `baseline_moves = baseline_move_count`, `graph_moves = graph_move_count`
    - Kabul:
      - `graph_travel <= baseline_travel * 0.6` **veya** `graph_travel <= 10.0`
      - **ve** `graph_moves <= baseline_moves * 1.2`
    - Eğer koşullar sağlanırsa:
      - `commands = graph_commands` (graph path kullanılır).
      - `graph_path_decision = {"used": true, "reason": "GRAPH_PATH_OK", ...}`
    - Aksi halde:
      - `commands = baseline_commands` (baseline fallback).
      - `graph_path_decision = {"used": false, "reason": "TRAVEL_OR_MOVES_WORSE", ...}`
- Rapor alanları:
  - `graph_path_metrics = {components_count, duplicated_edge_length_m, traversal_mode_used}`
  - `graph_path_decision = {used, reason, baseline_travel_m, graph_travel_m, baseline_move_count, graph_move_count}`

### 4. Benchmark Sonuçları (suite B, benchmarks/B_realistic)

Komutlar:

- Baseline:
  - `python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite B --out B_baseline_path --optimize none --path-mode baseline`
- Graph:
  - `python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite B --out B_graph_path --optimize none --path-mode graph`

#### 4.1 empty_entities.dxf

- **Baseline (B_baseline_path)**:
  - `drawn_length_m = 285.0`
  - `travel_length_m = 67.32`
  - `path_overhead = 1.2362`
  - `move_count = 587`
- **Graph (B_graph_path)**:
  - `drawn_length_m = 285.0` (aynı)
  - `travel_length_m = 67.32` (aynı)
  - `path_overhead = 1.2362` (aynı)
  - `move_count = 587` (aynı)
  - `graph_path_metrics`:
    - `components_count = 6` (her duvar hattı için bir stroke)
    - `duplicated_edge_length_m = 0.0` (bu dosyada DFS-backtrack toplamı unique uzunlukla örtüşüyor)
    - `traversal_mode_used = "dfs_backtrack"`
  - `graph_path_decision.used = false`
    - `reason = "TRAVEL_OR_MOVES_WORSE"`
    - `baseline_travel_m ≈ 67.32`, `graph_travel_m ≈ 69.05`
    - `baseline_move_count = 587`, `graph_move_count = 29`
  - **Yorum**:
    - DFS-backtrack stroke sayısını azaltıp move_count’u büyük ölçüde düşürse de, travel kriteri (%40 iyileşme veya ≤10m) sağlanmadığı için gating baseline’a geri dönüyor.

#### 4.2 sample.dxf

- **Baseline (B_baseline_path)**:
  - `drawn_length_m ≈ 180.01`
  - `travel_length_m ≈ 40.91`
  - `path_overhead ≈ 1.2272`
  - `move_count = 587`
- **Graph (B_graph_path)**:
  - `drawn_length_m ≈ 180.01`
  - `travel_length_m ≈ 40.91`
  - `path_overhead ≈ 1.2272`
  - `move_count = 587`
  - `graph_path_metrics`:
    - `components_count = 14`
    - `duplicated_edge_length_m ≈ 180.01`
    - `traversal_mode_used = "dfs_backtrack"`
  - `graph_path_decision.used = false`
    - `reason = "TRAVEL_OR_MOVES_WORSE"`
    - `baseline_travel_m ≈ 40.91`, `graph_travel_m ≈ 99.03`
    - `baseline_move_count = 587`, `graph_move_count = 73`
  - **Yorum**:
    - DFS-backtrack grafı, duvarların karmaşık bileşen yapısı nedeniyle travel mesafesini belirgin şekilde artırıyor; bu yüzden gating, `SUPPORTED_WALL_ONLY` olmasına rağmen baseline path’e geri dönüyor.

### 5. Değerlendirme ve Trade-off’lar

- **Pozitifler**:
  - Graph tabanlı traversal, her component için tek stroke üretebiliyor; `components_count` ve `duplicated_edge_length_m` metrikleri ile bu davranış şeffaf.
  - Gating sayesinde, graph path hiçbir zaman **otonom olarak** travel’ı kötüleştirmeye veya move_count’u aşırı artırmaya izin vermiyor; baseline’a güvenli fallback var.
- **Sınırlamalar (MVP)**:
  - Kullanılan `dfs_backtrack` stratejisi, gerçek bir Chinese Postman / Euler augmentasyonu yapmadığı için:
    - Kenarların çoğunu **iki kez** çiziyor (gidiş + dönüş), bu da `duplicated_edge_length_m`’yi yüksek yapıyor.
    - Travel mesafesini baseline’a göre net şekilde iyileştiremiyor; B_realistic örneklerinde gating her zaman fallback ediyor.
  - Acceptance kriteri (`graph_travel <= baseline_travel * 0.6` veya `<= 10m`, `moves <= 1.2x`) bu MVP implementation ile sağlanamadı; ancak kriterler devrede ve başarısızlık durumunda baseline korunuyor.
- **Sonuç**:
  - Graph tabanlı traversal **altyapısı** ve metrikleri (components, duplicated length, decision) eklendi.
  - Mevcut DFS-backtrack stratejisi, B_realistic örneklerinde travel iyileştirmesi sağlayamadığı için **otomatik olarak baseline’a fallback** ediyor; bu nedenle şu an için “davranışı bozmayan ama deneysel” bir mod olarak değerlendirilmelidir.
  - Bir sonraki adımda:
    - Gerçek bir Euler/Chinese Postman benzeri augmentasyon,
    - Sadece kısa local retrace’lerle travel azaltımı,
    - SUPPORTED_WALL_ONLY planların tipik topolojisine özel heuristikler
    eklenerek acceptance kriterlerini sağlama yönünde geliştirme yapılabilir.

