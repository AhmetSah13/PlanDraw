## Component-Order Path Raporu (suite B)

### 1. Amaç

Graph tabanlı DFS traversal denemesinde:

- `sample.dxf` için baseline travel ≈ **40 m**, graph traversal travel ≈ **99 m**,
- `duplicated_edge_length ≈ 180 m`,

gibi sonuçlar gördük. Kök neden: duvar grafı Eulerian olmadığı için DFS backtracking aynı kenarları defalarca çiziyor.

Bu adımda hedef, grafın iç yapısına agresifçe müdahale etmek yerine:

- Her **connected component**’i bir “stroke kümesi” olarak ele almak,
- Component’lerin **merkezlerine** göre sırayı optimize ederek component’ler arası **PEN-UP travel** mesafesini azaltmak,
- İçerideki stroke’ların sırasını basitçe korumak (DFS/PathGenerator ne veriyorsa onu kullanmak).

### 2. Algoritma (Component-Order Path)

#### 2.1 Component tespiti

- `graph_traversal.compute_component_centroids(segments, snap_tol=1e-4)`:
  - `_build_graph` ile segment uç noktalarından undirected node/edge grafı kuruyor.
  - Node bazında BFS ile **connected component** kümelerini buluyor.
  - Her component için centroid:
    - `cx = mean(node_positions[n].x)`
    - `cy = mean(node_positions[n].y)`
  - Çıktı: `[(cx, cy), ...]` — component centroid’leri.

#### 2.2 Baseline stroke’ların componente atanması

- `run_one` içinde önce her zaman **baseline path** üretiliyor:
  - `baseline_segments = _generate_path(plan, step)` → `[polyline1, polyline2, ...]`.
  - Her `polyline` için centroid hesaplanıyor (noktaların ortalaması).
  - Her polyline, **en yakın component centroid**’ine atanıyor:
    - `best_idx = argmin_i ||poly_centroid - component_centroid_i||^2`.
  - Sonuç: `comp_groups[idx] = [poly1, poly2, ...]` map’i.

#### 2.3 Component sırasının optimize edilmesi

- Componentler arası sıralama için basit **nearest-neighbor** heuristic kullanılıyor:
  - Başlangıç component: orijine (0,0) en yakın centroid’e sahip olan.
  - Sonraki component: mevcut component centroid’ine en yakın centroid.
  - Çıktı: `order = [c0, c1, c2, ...]`.

#### 2.4 Yeni path ve metrikler

- Yeni path:
  - `reordered_segments = []`
  - `for idx in order: reordered_segments.extend(comp_groups[idx])`
  - İçerideki polyline sırası değişmiyor; sadece component bloklarının sırası değişiyor.
- Komutlar:
  - `comp_commands = compile_path_to_commands_from_segments(reordered_segments, speed=SPEED_DEFAULT)`
  - `comp_dt = measure_drawn_travel(comp_commands, start_xy=first_point)`
  - `comp_move_count` benzer şekilde hesaplanıyor.
- Metrikler:
  - `component_path_metrics`:
    - `component_count`: sıralanan component sayısı (stroke içerenler).
    - `avg_component_length_m`: her componentteki stroke’ların toplam uzunluğunun ortalaması.
    - `pen_up_between_components_distance_m`: ardışık component’lerin **son → ilk** noktaları arasındaki yaklaşık toplam mesafe.

#### 2.5 Gating

Baseline metrikleri (`baseline_dt`) kullanılarak:

- `baseline_travel = baseline_dt.travel_length_m`
- `comp_travel = comp_dt.travel_length_m`

şu koşul ile karar veriliyor:

- Eğer `comp_travel <= baseline_travel * 0.9` **veya** `comp_travel <= 10.0` ise:
  - `component_path_decision.used = true`
  - Graph-based component-order path **kullanılıyor**.
- Aksi halde:
  - `component_path_decision.used = false`, `reason = "TRAVEL_TOO_HIGH"`
  - **Baseline path’e fallback** ediliyor.

Bu gating, travel metriklerini **asla kötüleştirmeme** garantisi veriyor.

### 3. Benchmark Sonuçları (suite B — benchmarks/B_realistic)

Komut:

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite B --out B_component_path --optimize none --path-mode component
```

#### 3.1 empty_entities.dxf

- **Baseline (karşılaştırma)**:
  - `drawn_length_m = 285.0`
  - `travel_length_m ≈ 67.32`
  - `path_overhead ≈ 1.2362`
  - `move_count = 587`
- **Component path (B_component_path)**:
  - `drawn_length_m = 285.0`
  - `travel_length_m ≈ 67.32` (baseline ile aynı)
  - `path_overhead ≈ 1.2362`
  - `move_count = 587`
  - `component_path_metrics`:
    - `component_count = 5`
    - `avg_component_length_m ≈ 57.0`
    - `pen_up_between_components_distance_m ≈ 110.48`
  - `component_path_decision`:
    - `used = false`
    - `reason = "TRAVEL_TOO_HIGH"`
    - `baseline_travel_m ≈ 67.32`
    - `component_travel_m ≈ 229.20`
    - `baseline_move_count = 587`
    - `component_move_count = 587`

**Yorum**: Component’ler arası sıralama değişse de, path üretim şekli baseline ile aynı olduğu için travel ciddi derecede iyileşmiyor; hatta bu örnekte component sıralamasının etkisi travel’ı artırarak gating’i tetikliyor ve baseline’a fallback ediliyor.

#### 3.2 sample.dxf

- **Baseline (karşılaştırma)**:
  - `drawn_length_m ≈ 180.01`
  - `travel_length_m ≈ 40.91`
  - `path_overhead ≈ 1.2272`
  - `move_count = 587`
- **Component path (B_component_path)**:
  - `drawn_length_m ≈ 180.01`
  - `travel_length_m ≈ 40.91`
  - `path_overhead ≈ 1.2272`
  - `move_count = 587`
  - `component_path_metrics`:
    - `component_count = 13`
    - `avg_component_length_m ≈ 13.85`
    - `pen_up_between_components_distance_m ≈ 82.31`
  - `component_path_decision`:
    - `used = false`
    - `reason = "TRAVEL_TOO_HIGH"`
    - `baseline_travel_m ≈ 40.91`
    - `component_travel_m ≈ 142.18`
    - `baseline_move_count = 587`
    - `component_move_count = 587`

**Yorum**: Burada da component centroid sıralaması travel’ı azaltmak yerine artırıyor; gating sayesinde baseline path’e fallback ediliyor.

### 4. Sonuç ve Değerlendirme

- Component-order path modu artık:
  - Connected component centroid’lerini hesaplıyor,
  - Baseline stroke’ları bu component’lere atıyor,
  - Component’ler arası sırayı nearest-neighbor ile optimize ediyor,
  - Travel metriğini **gating** ile baseline’a göre kontrol ediyor.
- B_realistic örneklerinde (empty_entities.dxf, sample.dxf):
  - Acceptance kriteri (`new_travel <= 0.9 * baseline` veya `<= 10m`) **sağlanmadığı** için component yolu **kullanılmıyor**, baseline path korunuyor.
  - Buna karşılık, `component_path_metrics` ve `component_path_decision` alanları sayesinde:
    - Kaç component olduğu,
    - Ortalama component uzunluğu,
    - Componentler arası pen-up mesafesi
    - Gating kararının travel bazlı nedeni
    net şekilde görülebiliyor.
- Bu aşamada component-order path, **deneysel** bir mod olarak güvenli şekilde entegre edildi; gerçek travel iyileştirmeleri için bir sonraki adımda:
  - Component içi stroke generasyonunu component topolojisine göre daha akıllı yapmak,
  - Sadece uzak componentler arası sıralamayı değiştirmek,
  - Çok kısa componentleri birleşik cluster’lara toplamak
  gibi iyileştirmelerle acceptance kriterlerine yaklaşılabilir.

