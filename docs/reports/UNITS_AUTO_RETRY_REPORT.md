# Units Auto-Retry Raporu

Bu rapor, DXF import pipeline’a eklenen **units auto-retry** mekanizmasını ve benchmark sonuçlarını özetler.

---

## 1. Root cause (units mismatch)

**Belirti:** İnternetten gelen veya bazı CAD’lerden export edilen DXF’lerde sık görülen durum:

- `bbox` ≈ 40 000 × 25 000 (world koordinat)
- `dxf_units_detected` = `"m"` (dosya header’da INSUNITS metre)
- `original_total_length_m` ≈ 449 000 m
- Path analizinde **LIMITS_EXCEEDED** (max_moves, max_path_length, max_total_time aşımı)

**Yorum:** Sayısal olarak plan “40 km × 25 km” gibi yorumlanıyor; çoğu mimari/teknik çizim ise **mm** cinsindendir (40 m × 25 m). Yani DXF fiziksel olarak **mm** iken sistem **metre** gibi okuyor; birim belirsizliği (mm vs m) en yaygın başarısızlık nedenlerinden biri.

Teşhis alanları:

- `fail_reason_code` = **LIMITS_EXCEEDED**
- `units_scale_mismatch` = **true** (mevcut heuristic: bbox world > 10 000 m)

---

## 2. Implement edilen retry mekanizması

### 2.1 Tetikleyici

- **Sadece** `units_scale_mismatch == true` **ve** `dxf_units_detected == "m"` ise çalışır.
- Normal DXF’lerde (mismatch yok) pipeline değişmez; ek bir çalıştırma yapılmaz.

### 2.2 Retry stratejisi

1. Mevcut pipeline **units = m** (dosya birimi) ile çalıştırılır → **report_m**.
2. Aynı dosya **units = "mm"** override ile tekrar çalıştırılır:  
   preview → import → normalize → path → analyze (export dahil) → **report_mm**.

### 2.3 Seçim kriterleri (hangisi kullanılacak)

İki rapor arasında sırayla:

1. **LIMITS_EXCEEDED olmayan** tercih edilir.
2. **bbox_reasonable** olan tercih edilir: world bbox her iki boyutta  
   `0.5 m < boyut < 200 m`.
3. **Retention** daha yüksek olan tercih edilir (`shape_retention_drawn`).

Seçilen rapor (m veya mm) nihai rapor olarak kullanılır; üzerine units retry alanları eklenir.

### 2.4 Rapor alanları

Benchmark (ve pipeline) raporuna eklenen alanlar:

| Alan | Açıklama |
|------|----------|
| `units_retry_used` | `true` / `false` |
| `units_retry_reason` | `"UNITS_SCALE_MISMATCH"` (retry yapıldıysa) |
| `units_candidates` | `["m", "mm"]` |
| `units_chosen` | `"m"` veya `"mm"` |
| `units_retry_metrics` | `m` ve `mm` için: `bbox_size`, `path_length_m`, `move_count`, `shape_retention_plan`, `shape_retention_drawn`, `analyze_result` |

### 2.5 FAIL / WARN / PASS davranışı

- Retry sonrası **LIMITS_EXCEEDED kalkıyorsa** (seçilen units ile analiz SAFE) → **PASS** veya **WARN** (mevcut move/collision eşiklerine göre).
- **Her iki units** sonucu da LIMITS_EXCEEDED ise → **FAIL**, `fail_reason_code` = **LIMITS_EXCEEDED**.

### 2.6 Kod konumları

- **verify_dxf_drawability.py**
  - `run_one(..., units_override=None)`: preview, `get_dxf_all_segments_before_filter`, `_import_dxf` için `units=units_override` kullanılır.
  - `_import_dxf(..., units=None)`: `dxf_bytes_to_normalized_plan(..., units=units)`.
  - `_bbox_reasonable()`, `_extract_units_metrics()`, `_choose_units_result()`, `_merge_units_retry_report()`: seçim ve merge.
  - **main():** `units_scale_mismatch` ve `dxf_units_detected == "m"` ise `run_one(..., units_override="mm")` çağrılır, `_merge_units_retry_report(report_m, report_mm)` ile nihai rapor oluşturulur.

---

## 3. Before vs After benchmark farkı

Komut (after):

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out current_after_units_retry
```

### 3.1 Özet

| Metrik | Before (current) | After (current_after_units_retry) |
|--------|-------------------|-----------------------------------|
| PASS | 2 | **3** |
| WARN | 0 | 0 |
| FAIL | 1 | **0** |
| FAIL_AFTER_RETRY | 1 | 0 |
| fail_reason_codes_top | [{"code": "LIMITS_EXCEEDED", "count": 1}] | **[]** |
| failure_reasons | BLOCKED (limit aşımı): 1 | **{}** |

### 3.2 Suite bazlı

- **A:** Before 1 PASS, After 1 PASS (değişim yok).
- **B:** Before 1 PASS, 1 FAIL → After **2 PASS**, 0 FAIL.  
  Fail olan **empty_entities.dxf** units retry ile **mm** seçilip **PASS** oldu.

---

## 4. empty_entities.dxf detay analizi

### 4.1 units = m sonucu (ilk çalıştırma)

- **bbox_size:** [40000, 25000] m → 40 km × 25 km
- **path_length_m:** 352 320
- **move_count:** 760 009
- **analyze_result:** BLOCKED
- **fail_reason_code:** LIMITS_EXCEEDED
- **shape_retention_plan / _drawn:** 0.635, 0.785

### 4.2 units = mm sonucu (retry)

- **bbox_size:** [40, 25] m → 40 m × 25 m (makul)
- **path_length_m:** 352.32
- **move_count:** 576
- **analyze_result:** SAFE
- **fail_reason_code:** null
- **shape_retention_plan / _drawn:** 0.635, 0.785 (aynı)

### 4.3 Hangi units seçildi?

- **units_chosen:** `"mm"`
- **units_retry_used:** true  
- Sebep: m koşusu LIMITS_EXCEEDED, mm koşusu SAFE ve bbox_reasonable → kriter 1 ve 2 ile **mm** seçildi.

### 4.4 Final result

- **result:** PASS  
- **fail_reason_code:** null  
- **units_retry_metrics:** m ve mm için yukarıdaki metrikler raporlanıyor.

---

## 5. Trade-offs (performans / risk)

### Performans

- Units retry **yalnızca** `units_scale_mismatch` ve `dxf_units_detected == "m"` olduğunda tetiklenir.
- Bu durumda pipeline **iki kez** çalışır (m + mm); büyük dosyalarda süre kabaca ikiye çıkabilir.
- Benchmark setinde yalnızca empty_entities.dxf tetikledi; toplam süre kabul edilebilir.

### Risk

- **Yanlış birim seçimi:** Nadir durumda gerçekten 40 km plan (metre) ise mm retry yanlış ölçek üretebilir. Seçim kriteri (LIMITS_EXCEEDED yok + bbox_reasonable) çoğu “mm yanlışlıkla m okunmuş” senaryosunda mm’i seçer; gerçek çok büyük metre planları genelde yine LIMITS_EXCEEDED verir ve m kalır.
- **Davranış değişikliği:** Sadece mismatch varken devreye girer; normal DXF’lerde davranış aynı kalır.

### Özet

- **Amaç:** Mm vs m belirsizliğini kullanıcı müdahalesi olmadan azaltmak.
- **Sonuç:** empty_entities.dxf örneğinde FAIL → PASS; fail_reason_codes_top boşaldı.
- **Maliyet:** Sadece mismatch durumunda ek bir tam pipeline çalıştırması.
