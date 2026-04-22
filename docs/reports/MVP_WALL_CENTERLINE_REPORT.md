## MVP WALL CENTERLINE RAPORU

### 1. Amaç ve kapsam

- **Amaç**: Double-line (iki paralel çizgi/poliline) ile çizilmiş mimari duvarları tespit edip, bunları tek bir **orta çizgi (centerline)** ile temsil etmek.
- **Kapsam (MVP)**:
  - DXF/DWG → duvar katmanları seçimi → wall-only segment çıkarımı sonrası,
  - yalnızca duvar aday segmentleri üzerinde saf geometri/graph tabanlı orta-çizgi çıkarımı,
  - kapılar, yazılar, ölçüler, hatch ve mobilya çizgileri bu aşamaya zaten girmiyor (önceki wall-only filtresi sayesinde).
- **Güvenlik ilkesi**:
  - Algoritma emin değilse **asla yeni geometri icat etmez**; bu durumda orijinal wall-only segmentlerine fallback yapılır.
  - Girdi aynı ise çıktı deterministiktir (aynı sıralama/toleranslarla aynı sonucun üretilmesi).

Genel akış (DXF tarafı değişmeden kalır):

> DXF/DWG → explode/discretize (ezdxf) → wall-only segmentler (katman zekâsı) → normalize → **CENTERLINE** → path generation

### 2. Dosya ve entegrasyon değişiklikleri

- **Yeni modül**: `backend/app/analysis/wall_centerline.py`
  - `WallCenterlineConfig`: gap/angle/overlap toleransları ve fallback eşiği içeren config dataclass’ı.
  - `extract_wall_centerlines(segments, cfg, unit_unknown)`:
    - Girdi: `List[SegmentIn]` (duvar adayı segmentler).
    - Çıktı: `(centerline_segments: List[SegmentIn], metrics: dict)`.
  - `apply_wall_centerline_to_plan(plan, cfg)`:
    - `NormalizedPlan` alıp segmentlerini orta-çizgi ile değiştirir ve `metadata["centerline_metrics"]` alanını doldurur.

- **verify_dxf_drawability.py entegrasyonu**
  - Yeni CLI bayrağı:
    - `--centerline {off,on}` (varsayılan: `off`).
    - Kapalı iken eski davranış **aynı** kalır; hiçbir centerline hesabı yapılmaz.
  - `run_one(...)` imzası genişledi:
    - `centerline_enabled: bool = False` parametresi eklendi.
  - `main()` içinde:
    - `centerline_enabled = args.centerline == "on"` ile bayrak hesaplanıp,
    - hem ana `run_one` çağrısına, hem de `run_retries` ve units auto-retry sırasında yapılan `run_one` çağrılarına iletiliyor.
  - Import aşamasından hemen sonra:
    - `normalized = enrich_plan_with_graph_metrics(normalized)` sonrası,
    - `centerline_enabled` ise:
      - `normalized, cl_metrics = apply_wall_centerline_to_plan(normalized, cfg=WallCenterlineConfig())`
      - Rapor alanları dolduruluyor:
        - `centerline_metrics`
        - `detected_double_wall_pairs_count`
        - `centerline_segments_count`
        - `dropped_as_non_wall_count`
        - `centerline_success_ratio`
        - `centerline_fallback_used`
        - `centerline_fallback_reason`

- **Yeni testler**: `backend/tests/test_wall_centerline.py`
  - `test_rectangle_double_wall_to_single_centerline_rectangle`
  - `test_single_line_walls_unchanged_with_fallback`
  - `test_near_parallel_noise_not_merged`
  - `test_t_junction_double_wall_pairs_detected`

### 3. Algoritma detayı (wall_centerline.py)

#### 3.1. Girdi / Çıktı

- **Girdi**: `segments: List[SegmentIn]`
  - Bunlar, layer intelligence ve wall-only filtresinden geçmiş duvar segmentleridir.
  - Zaten annotation/noise büyük oranda dışarıda olduğu için bu aşama sadece “duvar hattı” üzerinde çalışır.
- **Çıktı**:
  - `centerline_segments`: Kullanılacak yeni segment listesi (ya orta-çizgiler ya da fallback ile orijinal segmentler).
  - `metrics`: Aşağıdaki alanlarla birlikte ayrıntılı istatistikler.

#### 3.2. Konfigürasyon

`WallCenterlineConfig` alanları:

- `wall_gap_min_m`: Duvar çiftleri için minimum boşluk (varsayılan 0.05 m).
- `wall_gap_max_m`: Maksimum boşluk (varsayılan 0.40 m).
- `parallel_angle_tol_deg`: Paralellik açı toleransı (varsayılan 3°).
- `overlap_min_ratio`: Eksene göre bindirme oranı eşiği (varsayılan 0.60).
- `snap_tol_m`: Graph aşamasında uç noktaları snap ederken kullanılan tolerans (varsayılan 1e-3 m).
- `min_stub_len_m`: Normalize sonrası atılacak minimum segment uzunluğu (varsayılan 0.02 m).
- `min_pairs_for_centerline`: Orta-çizgi üretimi için gereken minimum çift sayısı (varsayılan 2).
- `min_centerline_ratio_vs_input`: Orta-çizgi toplam uzunluğunun girdi uzunluğuna oran eşiği; bunun altına düşerse fallback (varsayılan 0.60).

`unit_unknown=True` durumunda (plan metadata’dan gelen bayrak), aday duvar boşluklarının medyanına göre efektif gap penceresi daraltılır:

- gap medyanı = `med`
- `gap_min_eff = max(wall_gap_min_m, 0.5 * med)`
- `gap_max_eff = min(wall_gap_max_m, 1.5 * med)`

#### 3.3. Aşama A: Uzamsal indeks

- Her segment için bbox ve merkez `(cx, cy)` hesaplanır.
- Hücre boyu: `cell_size = max(wall_gap_max_m, wall_gap_min_m * 2)`.
- Grid anahtarı: `(int(cx / cell_size), int(cy / cell_size))`.
- Grid, bu anahtara karşılık gelen segment indekslerini tutar.

Amaç:
- Olası çift aramalarını sadece aynı/komşu hücrelerdeki segmentlerle sınırlayıp, küçük planlarda O(N²) yerine daha ılımlı bir karmaşıklık sağlamak.

#### 3.4. Aşama B: Paralel adaylar

Her segment için:

- Yön birim vektörü `u = (ux, uy)` elde edilir.
- Komşu 3×3 grid hücresi taranır; her aday `j > i` için:
  - **Açı farkı**:
    - `_angle_between_deg(seg_i, seg_j)` → 0–90° aralığına indirgenmiş fark.
    - `angle <= parallel_angle_tol_deg` değilse atlanır.
  - **Eksene göre bindirme**:
    - `_project_onto_axis` ile her segment uçlarının `t` parametresi bulunur.
    - Kesişim aralığı `overlap` ve kısa segmente oranı `overlap_ratio` hesaplanır.
    - `overlap > 0` ve `overlap_ratio >= overlap_min_ratio` değilse atlanır.
  - **Duvar boşluğu (gap)**:
    - `_line_distance(seg_i, seg_j)` ile ikinci segmentin orta noktasının birincinin doğrusuna dik uzaklığı alınır.
    - Bu değer histogramda (gaps listesi) tutulur.

Sonuç:
- `candidate_pairs`: `{i, j, gap, overlap, min_len}` alanlarına sahip aday çift listesi.

#### 3.5. Gap filtresi

- Eğer `unit_unknown` ise:
  - Gap medyanı `med` hesaplanır.
  - Etkin pencere `[gap_min_eff, gap_max_eff]` belirlenir.
- Değilse:
  - Varsayılan `[wall_gap_min_m, wall_gap_max_m]` kullanılır.
- Bu aralığa girmeyen tüm çiftler atılır.
- Hiç çift kalmazsa:
  - `fallback_used = True, fallback_reason = "NO_DOUBLE_WALL_PAIRS_IN_GAP_RANGE"`,
  - Girdi segmentleri aynen geri döner.

#### 3.6. Aşama C: Skorlama ve greedy eşleştirme

- Gap medyanı (`gap_med`) tekrar hesaplanır (filtrelenmiş çiftler üzerinden).
- Her aday için skor:

  \[
  \text{gap\_score} = \max(0, 1 - |gap - gap\_med| / gap\_med)
  \]
  \[
  \text{score} = overlap \times (1 + gap\_score) + 0.1 \times min\_len
  \]

- Çiftler skor azalan sırada sıralanır.
- Greedy eşleştirme:
  - Sırayla gidilir; her segment en fazla bir kez kullanılacak şekilde `chosen_pairs` oluşturulur.

Metrikler:
- `detected_double_wall_pairs_count = len(chosen_pairs)`
- `centerline_success_ratio = pairs_used / pairs_found`

#### 3.7. Aşama D: Orta çizgi segmenti üretimi

Her seçili çift için:

1. Eksen: birinci segmentin yönü `u = (ux, uy)`.
2. Projeksiyon aralıkları:
   - `a1,b1 = project(seg1)`
   - `a2,b2 = project(seg2)`
3. Kesişim aralığı:
   - `inter_a = max(a1, a2)`
   - `inter_b = min(b1, b2)`
4. Her seg üzerinde verilen t parametresi için nokta hesabı:
   - Uçların projeksiyonları ile orantı kurularak, `s` parametresi `[0,1]` aralığında bulunur.
5. `t = inter_a` ve `t = inter_b` için:
   - `p1(t)` ve `p2(t)` noktaları hesaplanır.
   - Orta nokta: `c(t) = (p1(t) + p2(t)) / 2`.
6. Böylece orta çizgi segmenti `c(inter_a) -> c(inter_b)` elde edilir.

Bu adım, duvarlar farklı yönlerde çizilmiş olsalar bile eksen boyunca bindirmeyi ve simetriyi korur; centerline, iki duvarın tam ortasından ve sadece ortak bindirme aralığında geçirilir.

#### 3.8. Aşama E: Graph/normalize ile birleştirme

Üretilen orta-çizgi segmentleri:

- Küçük sayıda hatayı ve “kırıklı” çizgileri temizlemek için `plan_normalizer` üzerinden geçirilir:
  - `merge_endpoints_tol = snap_tol_m`
  - `merge_collinear = True`
  - `min_segment_len = min_stub_len_m`
  - `segment_budget = None`
  - `recenter = False`

Sonuç:
- Uçları yakın segmentler snap edilir.
- Ardışık kollinear parçalar birleştirilir.
- Çok kısa budaklar (< min_stub_len_m) düşürülür.

Metrik:
- `centerline_total_length_m = sum(len(seg) for seg in centerline_segments_final)`

#### 3.9. Aşama F: Fallback kararı

Fallback koşulları:

- `pairs_used < min_pairs_for_centerline` ise:
  - `fallback_reason = "PAIRS_USED_BELOW_MIN"`.
- veya `centerline_total_length_m < min_centerline_ratio_vs_input * input_total_length_m` ise:
  - `fallback_reason = "CENTERLINE_TOO_SHORT_VS_INPUT"`.

Bu durumlarda:

- `fallback_used = True`
- Çıktı segmentleri **orijinal girdi segmentleri** olarak döndürülür.
- `dropped_as_non_wall_count ≈ len(segments) - 2 * pairs_used` ile orta-çizgide yer almayan duvar adaylarının sayısı raporlanır.

Başarılı durumda:

- `fallback_used = False`
- Çıktı segmentleri, normalize edilmiş orta-çizgi segmentleridir.

### 4. Raporlanan metrikler

Her dosya raporunda (centerline açıkken):

- **centerline_metrics** (metadata + rapor alanı)
  - `detected_double_wall_pairs_count`
  - `centerline_segments_count`
  - `dropped_as_non_wall_count`
  - `centerline_success_ratio`
  - `fallback_used`
  - `fallback_reason`
  - `input_total_length_m`
  - `centerline_total_length_m`
- Kök rapor alanları:
  - `centerline_metrics`
  - `centerline_fallback_used`
  - `centerline_fallback_reason`

Bu metrikler, özellikle aşağıdaki soruları cevaplamak için kullanılabilir:

- Bu dosyada gerçekten double-wall duvarlar var mı (pair sayısı)?
- Algoritma bu dosyada orta-çizgiyi güvenle kullanmış mı (fallback_used=False)?
- Toplam duvar uzunluğuna göre orta-çizgi uzunluğu ne kadar (centerline_total_length_m vs input_total_length_m)?

### 5. Unit testler ve çalışma komutları

#### 5.1. Test senaryoları

`backend/tests/test_wall_centerline.py` dosyasında:

- **rectangle double-wall → single centerline rectangle**
  - Dış ve iç dikdörtgen duvarlar (gap ≈ 0.2 m) veriliyor.
  - En az 4 çift tespit ediliyor; normalize sonrası orta-çizgi dikdörtgeni beklenen bbox aralığında kalıyor.

- **T-junction double-wall**
  - Basit bir “T” şekilli double-wall gövde + tepe kombinasyonu.
  - En az 2 çift tespit ediliyor; centerline_total_length, input_total_length’in anlamlı bir kısmı (> %40).

- **single-line walls unchanged (fallback)**
  - Zaten tek çizgi duvarlardan oluşan bir örnek.
  - Double-wall kriterleri sağlanmıyor, fallback tetikleniyor, girdiyle çıktı uzunluğu/sayısı aynı kalıyor.

- **near-parallel noise not merged**
  - Yaklaşık paralel ama uzak ve kısa gürültü çizgileri içeren örnek.
  - Hiç çift tespit edilmiyor, fallback tetikleniyor; segmentler aynen korunuyor.

#### 5.2. Testleri çalıştırma

Proje kökünden:

```bash
cd backend
python -m pytest backend/tests/test_wall_centerline.py
```

Çıktı (örnek):

- 4 testin tamamı **PASSED**.

### 6. Benchmark ile doğrulama

#### 6.1. Komutlar

Centerline **kapalı** (mevcut davranış, referans):

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out mvp_wall_only_run_ref --optimize on --centerline off
```

Centerline **açık** (MVP centerline hattı):

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out mvp_wall_only_run_centerline --optimize on --centerline on
```

#### 6.2. Beklenen farklar

- **shape_retention_drawn**:
  - Wall-only hattı değişmediği için, orta-çizgi üretimi retention değerini dramatik biçimde değiştirmemelidir.
  - Küçük sapmalar, normalize ve stub temizleme kaynaklı olabilir (özellikle çok kısa detaylar).
- **move_count / travel_length_m**:
  - Centerline açıkken, double-wall planlarda beklenen davranış:
    - Daha az stroke/parça → **daha az hareket**,
    - Duvarlar arası gereksiz “iç/dış” çizimlerin ortadan kalkması ile yol daha sade hale gelir.
  - Fallback kullanılan dosyalarda bu metrikler referansla aynı kalmalıdır.

Bu kıyas, `backend/reports/<run>/files/*.json` içindeki:

- `drawn_length_m`
- `travel_length_m`
- `move_count`
- `centerline_metrics.centerline_total_length_m`
- `centerline_metrics.fallback_used`

alanları üzerinden yapılabilir.

### 7. Riskler ve sonraki adımlar

**Ana riskler**

- Çok karmaşık planlarda (dairesel duvarlar, organik formlar) double-wall heuristikleri yanlış pozitif/negatif üretebilir; fallback mekanizması bu durumda emniyet supabı görevi görüyor.
- Gap/angle/overlap eşikleri çok sıkı veya gevşek seçilirse:
  - Sıkı: Hiç çift bulunamayabilir → sık fallback.
  - Gevşek: Yakın ama aslında duvar olmayan paralel çizgiler yanlış eşleştirilebilir.

**Önerilen sonraki adımlar**

1. **Benchmark tabanlı otomatik threshold kalibrasyonu**
   - B_realistic ve C_stress setleri üzerinde duvar boşluklarının istatistiklerini toplayıp,
   - Proje genelinde daha iyi default aralıklar (örneğin medyan ± faktör) seçmek.

2. **Graph tabanlı oda/duvar bütünlüğü kontrolü**
   - Geometry graph metriklerini (intersection/dangling/cycles) kullanarak:
     - Orta-çizgi setinin orijinal oda konturlarına göre “fazla açık” veya “fazla kapalı” olup olmadığını kontrol etmek.

3. **UI/Insight entegrasyonu**
   - `centerline_metrics` alanlarını frontend’de gösterip, kullanıcıya:
     - Hangi duvarların orta-çizgiye dönüştürüldüğü,
     - Nerelerde fallback yapıldığı
     hakkında görsel ve metinsel geri bildirim sunmak.

