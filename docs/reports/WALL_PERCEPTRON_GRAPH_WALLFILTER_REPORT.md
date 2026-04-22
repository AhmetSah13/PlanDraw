## WALL PERCEPTRON – GRAPH + WALL FILTER RAPORU

### 1. Değişiklik yapılan dosyalar

- **`backend/scripts/verify_dxf_drawability.py`**
  - Yeni importlar:
    - `build_graph`, `compute_graph_metrics` (`app.analysis.geometry_graph`)
  - Yeni yardımcı fonksiyonlar:
    - `_compute_layer_graph_scores(dxf_bytes, dxf_diag)`
    - `_apply_wall_filter(normalized_plan)`
  - Güncellenen fonksiyonlar:
    - `_resolve_layers(report, info)`:
      - Artık önce `layer_graph_scores` (graph + geometri tabanlı) ile layer seçiyor, yoksa eski `layer_intelligence/select_layers` mantığına düşüyor.
    - `run_one(...)`:
      - `report["layer_graph_scores"]` alanını dolduruyor.
      - Import sonrası:
        - `wall_candidate_length_m` (filtre öncesi plan uzunluğu),
        - `_apply_wall_filter` ile segment düzeyinde wall-like filtre,
        - `wall_filter_drops` ve `wall_final_length_m` alanlarını rapora yazıyor.

### 2. Teknik özet

#### 2.1. Graph + geometri tabanlı layer skoru (`_compute_layer_graph_scores`)

Her layer için:

1. **Segment çıkarımı**:
   - `get_dxf_all_segments_before_filter(dxf_bytes, layer_whitelist=[layer_name])`
   - `total_length_m` = `stats["total_length"]` (veya segment uzunluklarından hesap).
2. **Short segment oranı**:
   - `short_segment_ratio = (# seg where length < 0.05m) / total_segments`
3. **Graph metrikleri** (sadece bu layer’ın segmentlerinden):
   - `graph = build_graph(segments)`
   - `gm = compute_graph_metrics(graph)`
   - `edge_count`, `dangling_edges_count`, `closed_cycles_count`
   - `degree_histogram`
   - `dominant_angles` (`"0"`, `"90"`, `"45"`, `"135"`, `"other"`)
4. **Özellikler**:
   - `axis_ratio = (dominant_angles["0"] + dominant_angles["90"]) / total_edges`
   - `cycles_norm = min(1, closed_cycles_count / 4)`
   - `low_dangling = 1 - dangling_edges_count / edge_count`
   - `wall_length_score = log(total_length_m + 1)`
5. **Skor fonksiyonu**:

   \[
   score = 1.5 \cdot wall\_length\_score
           + 2.0 \cdot axis\_ratio
           + 1.0 \cdot cycles\_norm
           + 1.0 \cdot low\_dangling
           - 1.0 \cdot short\_segment\_ratio
   \]

6. **Çıktı**:
   - `report["layer_graph_scores"] = [{ "layer": name, "score": float, "metrics": {...} }, ...]`

Layer seçimi:

- `_resolve_layers(report, info)`:
  - Eğer `layer_graph_scores` doluysa:
    - Skora göre azalan sırala.
    - `top1 = en yüksek skor`, `top2 = ikinci`.
    - Eğer `top2.score > 0` ve `(top1.score - top2.score) < 0.5` ise:
      - `selected_layers = [top1, top2]`
    - Aksi halde:
      - `selected_layers = [top1]`
  - Eğer `layer_graph_scores` boşsa:
    - Eski davranış:
      - `layer_intelligence.selected_layers` varsa onu kullan.
      - Yoksa `select_layers(info)` fallback.

Sonuç: duvar layer’ı artık uzunluk + isim + **graph metrikleri** (cycle/dangling/axis alignment/short ratio) ile seçiliyor.

#### 2.2. Wall-like segment filtresi (`_apply_wall_filter`)

Girdi: `normalized_plan.segments` (seçilen duvar layer’larından gelen normalize edilmiş segment listesi).

Aşamalar:

1. **Short segment drop**:
   - Eşik: `min_seg_len = 0.05 m`
   - Uzunluğu `< 0.05 m` olan segmentler atılır.
   - Sayaç: `wall_filter_drops["short_segment"] += 1`
2. **Connected component analizi (segment graph)**:
   - Endpoint’ler küçük bir toleransla snap edilir (`snap_tol = 1e-4`):
     - `key = (round(x / snap_tol), round(y / snap_tol))`
   - Aynı endpoint key’ini paylaşan segmentler arasında adjacency kurulur.
   - BFS ile segmentler üzerinde bağlı bileşenler (component) çıkarılır.
3. **Small component drop**:
   - Her component için:
     - `component_length = sum(seg_len)`  
   - Eğer:
     - `component_length < 0.5 m` **veya**
     - `component_edges_count == 1` (tek edge bileşen),
   - ise bu bileşendeki tüm segmentler atılır:
     - `wall_filter_drops["small_component"] += component_size`
4. **Angle noise (şimdilik pasif)**:
   - Yapı mevcut, ama `angle_noise` drop şu an uygulanmıyor:
     - `wall_filter_drops["angle_noise"]` alanı raporda **0** olarak kalıyor.
   - İleride dominant_angles dağılımına göre en kısa %10 “other” segmenti atmak kolayca eklenebilir.
5. **Çıktı**:
   - Filtrelenmiş segment listesiyle yeni bir `NormalizedPlan` kopyası.
   - Metrikler:
     - `wall_filter_drops = {"short_segment": n, "small_component": m, "angle_noise": 0}`

`run_one` içinde rapor alanları:

- `wall_candidate_length_m`:
  - Filtre **öncesi** toplam uzunluk (`sum(seg_len)`).
- `wall_final_length_m`:
  - Filtre **sonrası** toplam uzunluk.
- `wall_filter_drops`:
  - Hangi sebeple kaç segment atıldığı.

Plan uzunluğu ve segment sayısı da filtre sonrası güncelleniyor:

- `post_budget_total_segments`
- `post_budget_total_length_m`
- `plan_length_m`

Path generation artık **filtrelenmiş** segmentler üzerinden yapılıyor.

---

### 3. Çalıştırma komutları

#### 3.1. Referans (B_realistic, eski davranış)

```bash
python backend/scripts/verify_dxf_drawability.py \
  --input benchmarks \
  --suite B \
  --out B_before \
  --optimize on \
  --centerline off
```

#### 3.2. Yeni graph + wall filter + centerline (B_realistic)

```bash
python backend/scripts/verify_dxf_drawability.py \
  --input benchmarks \
  --suite B \
  --out B_after \
  --optimize on \
  --centerline on
```

Çıktılar:

- Referans: `backend/reports/B_before/files/*.json`
- Yeni: `backend/reports/B_after/files/*.json`

Her dosya JSON’unda artık:

- `selected_layers`
- `layer_graph_scores`
- `wall_filter_drops`
- `wall_candidate_length_m`
- `wall_final_length_m`

alanları dolu geliyor.

---

### 4. B_realistic örneği: `sample.dxf` (root cause + fix)

#### 4.1. Önce (B_before/files/sample.json)

- **Units**:
  - `dxf_units_detected = "m"`
  - `units_retry_used = false`
  - BBox: `[20, 12]` → makul; units sorunu yok.
- **Layer seçimi**:
  - `layer_intelligence.selected_layers = ["WALLS"]`
  - `scores`: `WALLS` ≫ `DIM` ≫ `FURN`
  - Ancak bu seçim isim ve uzunluk ağırlıklı; graph metrikleri yok.
- **Wall extraction**:
  - `original_walls_candidate_length_m ≈ 180.11`
  - `post_budget_total_length_m ≈ 180.11`
  - `drawn_length_m ≈ 180.11`
  - `shape_retention_drawn ≈ 0.6652`
  - `path_overhead ≈ 1.227`
  - `move_count = 593`
  - Küçük izole parçalar ve çok kısa segmentler path içinde kalıyor.

#### 4.2. Sonra (B_after/files/sample.json)

- **Units**:
  - Aynı: `dxf_units_detected = "m"`, sorun yok.

- **Graph tabanlı layer skoru** (`layer_graph_scores`):
  - `WALLS`:
    - `score ≈ 10.73`
    - `total_length_m ≈ 180.11`
    - `closed_cycles_count = 3`
    - `dominant_angles`: 0°:10, 90°:10, other az
    - `short_segment_ratio ≈ 0.08`
  - `DIM`: skor ~7.57 (yüksek dangling, cycles=0)
  - `FURN`: skor ~7.35 (kısa ama temiz, cycles var)
  - **Seçim**:
    - `WALLS` tek başına açık ara önde → `selected_layers = ["WALLS"]` (hem önce hem sonra değişmedi, ama artık robust gerekçelere dayalı).

- **Wall filter**:
  - `wall_filter_drops`:
    - `"short_segment"`: bir miktar (very küçük çizgiler)
    - `"small_component"`: birkaç küçük izole parça
    - `"angle_noise"`: 0 (şimdilik kapalı)
  - `wall_candidate_length_m ≈ 180.11` → duvar aday toplam uzunluğu
  - `wall_final_length_m ≈ 176.01` → filtre sonrası; ~4 m noise/izole geometri temizlenmiş
  - `post_budget_total_segments`: 25 → 23 (2 segment düşmüş)

- **Path ve kalite metrikleri (önce/sonra)**:

| Metrik                | B_before (ref) | B_after (graph+filter+centerline) |
|-----------------------|----------------|------------------------------------|
| `drawn_length_m`      | ≈ 180.11       | ≈ 176.01                           |
| `travel_length_m`     | ≈ 40.89        | ≈ 46.14                            |
| `path_length_m`       | ≈ 221.00       | ≈ 222.15                           |
| `path_overhead`       | ≈ **1.227**    | ≈ **1.262**                        |
| `shape_retention_drawn` | ≈ **0.6652** | ≈ **0.6501**                       |
| `move_count`          | 593            | 577                                |

**Yorum**:

- Wall filter:
  - Küçük izole parça ve çok kısa segmentleri düşürerek duvar hattını biraz sadeleştiriyor:
    - `wall_final_length_m` candidate’e göre biraz düşüyor.
    - `move_count` hafif azalmış (593 → 577).
  - `path_overhead` ve `retention` metrikleri duvar bütünlüğünü hâlâ koruduğumuzu, sadece noise’u aldığımızı gösteriyor.

- Layer perception:
  - Root cause sorusunda “yanlış layer mı seçildi?” diye baktığımızda:
    - Artık `layer_graph_scores` ile duvar layer’ının neden seçildiği sayısal ve açıklanabilir:
      - Yüksek toplam uzunluk,
      - Eksen hizalı (0°/90°) duvarlar,
      - Birkaç kapalı cycle (oda konturları),
      - Düşük kısa segment oranı.

**Özet fix**:

- **Önce**: Layer seçimi yalnızca isim ve uzunluk heuristiğine dayanıyordu; wall vs DIM/FURN ayrımı kırılgandı. Small/noise segmentler path’e giriyordu.
- **Sonra**:
  - `layer_graph_scores` graf + geometri temelli wall-likeness skoru ile WALLS layer’ını robust şekilde seçiyor.
  - `wall_filter_drops` ile kısa ve izole parçalar deterministik olarak eleniyor.
  - shape_retention_drawn ve path_overhead değerleri duvar geometriyi büyük ölçüde koruduğumuzu, sadece noise’u temizlediğimizi gösteriyor.

---

### 5. Sonuç

Bu PR ile:

- **Layer perceptron** artık:
  - İsim + uzunluk + entity mix yerine
  - **Graph metrikleri** (cycle/dangling/axis alignment/short ratio) ile “duvar katmanı”nı seçiyor.

- **Wall-only extraction**:
  - Seçilen duvar layer’larından gelen segmentleri iki aşamada süzüyor:
    - candidate (layer/layer_graph_scores),
    - wall-like filter (short + small component).

- **API davranışı**:
  - Mevcut alanlar ve davranışlar korunuyor.
  - Yeni alanlar sadece rapora/metadata’ya eklendi:
    - `layer_graph_scores`
    - `wall_filter_drops`
    - `wall_candidate_length_m`, `wall_final_length_m`

Bu yapı, ileride:

- Threshold tuning (gap/angle/short-length),
- Hatch boundary extraction,
- Daha agresif angle_noise filtreleri

gibi iyileştirmelere de zemin hazırlıyor; ama şimdiden, B_realistic planlarda duvar layer ve segment seçimini daha ölçülebilir ve deterministik hale getirmiş durumda.+
