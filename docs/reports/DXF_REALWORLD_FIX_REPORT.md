# DXF Real World Fix Raporu — Benchmark Spec Uygulaması

Bu rapor, `verify_dxf_drawability.py` ve ilgili kodların sabitlenen spec'e göre güncellenmesini özetler.

---

## 1. Ne değişti? (Dosya listesi)

| Dosya | Değişiklik |
|-------|------------|
| `backend/app/importers/dxf_importer.py` | `get_dxf_all_segments_before_filter()` eklendi: preprocess (INSERT explode + discretize) sonrası, layer filtresi ve segment_budget öncesi tüm segmentleri döndürür. `PREPROESS_SEGMENT_CAP = 999999`. |
| `backend/app/importers/__init__.py` | `get_dxf_all_segments_before_filter` export edildi. |
| `backend/scripts/verify_dxf_drawability.py` | Spec’e göre baştan düzenlendi: `measure_drawn_travel()`, `detect_suite()`, `_seg_len()`; rapora `original_total_*`, `post_budget_*`, `plan_length_m`, `drawn_length_m`, `travel_length_m`, `path_length_m`, `path_overhead`, `shape_retention_plan`, `shape_retention_drawn`, `fail_reason_code`, `suite`, `segment_budget_applied`; NO_PEN_DOWN_COMMANDS ve SEGMENT_BUDGET_TRUNCATED_TOO_MUCH (suite A/B = FAIL, C = WARN); çıktı `backend/reports/<out>/summary.json` ve `backend/reports/<out>/files/<file>.json`; `--suite A|B|C|ALL`. |

---

## 2. Örnek B_realistic FAIL dosyası — adım adım

Dosya: `benchmarks/B_realistic/empty_entities.dxf` (ENTITIES bölümü boş DXF).

| Adım | Alan | Değer / Açıklama |
|------|------|-------------------|
| 1 | `original_total_segments` | 0 (preprocess sonrası hiç segment yok) |
| 2 | `original_total_length_m` | 0.0 |
| 3 | Önizleme | Katman/segment olmadığı için "Önizleme hatası" / "Hiç katman seçilemedi" ile erken çıkış |
| 4 | `post_budget_total_segments` | null (import aşamasına gelinmedi) |
| 5 | `post_budget_total_length_m` | null |
| 6 | `plan_length_m` | null |
| 7 | `drawn_length_m` | 0.0 |
| 8 | `travel_length_m` | 0.0 |
| 9 | `path_length_m` | 0.0 |
| 10 | `path_overhead` | null |
| 11 | `shape_retention_plan` | null |
| 12 | `shape_retention_drawn` | null |
| 13 | `fail_reason_code` | null (bu örnekte sebep: önizleme/katman hatası; kod atanmadı) |
| 14 | `result` | FAIL |
| 15 | `suite` | B (yol `B_realistic` içerdiği için) |

Başarılı bir FAIL örneği (örn. PEN DOWN yok veya segment bütçesi çok kesti): `fail_reason_code` sırasıyla `NO_PEN_DOWN_COMMANDS` veya `SEGMENT_BUDGET_TRUNCATED_TOO_MUCH` olur; `original_*`, `post_budget_*`, `plan_length_m`, drawn/travel ve retention alanları dolu raporlanır.

---

## 3. summary.json — mevcut çıktı (baseline karşılaştırması yok)

Spec sonrası tek çalıştırma çıktısı örneği:

- **Global:** PASS=2, WARN=0, FAIL=1, PASS_AFTER_RETRY=0, FAIL_AFTER_RETRY=0  
- **by_suite:** A: PASS=1, medyan retention_plan/drawn=1.0; B: PASS=1, FAIL=1, medyanlar hesaplanır; C: dosya yok.  
- **budget_too_much_loss_count_C:** 0  
- **fail_reason_codes_top:** [] (bu koşuda fail_reason_code set edilmedi)

Baseline (önceki bir run) kaydedilmediği için “önce/sonra” sayısal karşılaştırma yapılmadı. İleride `compare_benchmarks.py` veya manuel diff ile `backend/reports/baseline/summary.json` vs `backend/reports/current/summary.json` kıyaslanabilir.

---

## 4. Çalıştırma

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out current
```

Çıktılar:

- `backend/reports/current/summary.json`
- `backend/reports/current/files/<dosya_adı>.json`

---

## 5. Spec özeti (referans)

- **original_*:** Preprocess sonrası, layer filtresi ve budget öncesi; `all_segments_before_filter` → `original_total_segments`, `original_total_length_m`.
- **drawn/travel:** Komut listesi MOVE/MOVE_REL/FORWARD/TURN/PEN ile unroll; `measure_drawn_travel(commands, start_xy)`; PEN yoksa `fail_reason_code=NO_PEN_DOWN_COMMANDS`.
- **plan_length_m:** Yalnızca `normalized.segments` toplam uzunluğu.
- **Retention:** `shape_retention_plan = plan_length_m / original_total_length_m`, `shape_retention_drawn = drawn_length_m / original_total_length_m` (eps korumalı).
- **SEGMENT_BUDGET_TRUNCATED_TOO_MUCH:** Suite A/B → FAIL, C → WARN; `recommended_actions` ve `budget_too_much_loss_count_C` summary’de.
- **FAIL_AFTER_RETRY** → final_result her zaman FAIL; **PASS_AFTER_RETRY** → PASS/WARN/FAIL indirgenebilir.
