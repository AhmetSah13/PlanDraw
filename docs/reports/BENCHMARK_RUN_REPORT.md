# Benchmark Çalıştırma ve Kök Neden Raporu

**Tarih:** Benchmark script çalıştırıldı, raporlar üretildi. Limit gevşetmesi geri alındı; LIMITS_EXCEEDED ve UNITS_SCALE_MISMATCH fail_reason_code / uyarı mekanizması eklendi.

---

## 1. KONTROL / ÖN KOŞULLAR

### 1.1 Klasörler
- `benchmarks/A_expected_pass` — **var** (içinde 1 DXF)
- `benchmarks/B_realistic` — **var** (içinde 2 DXF)
- `benchmarks/C_stress` — **var ama boş** (içinde 0 dosya)

### 1.2 DXF/DWG dosyaları
| Suite | Dosya | Durum |
|-------|--------|--------|
| A | `A_expected_pass/minimal.dxf` | Var |
| B | `B_realistic/empty_entities.dxf` | Var |
| B | `B_realistic/sample.dxf` | Var |
| C | (yok) | **C_stress içinde dosya yok; raporlarda suite C sayıları 0.** |

---

## 2. BENCHMARK ÇALIŞTIRMA

Komut çalıştırıldı:
```text
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL --out current
```

---

## 3. ÇIKTILARIN DOĞRULANMASI

- `backend/reports/current/summary.json` — **oluştu**
- `backend/reports/current/files/*.json` — **oluştu** (minimal.json, empty_entities.json, sample.json)

---

## 4. summary.json İÇERİĞİ (BASELINE — current)

- **Global:** PASS=2, WARN=0, FAIL=1, PASS_AFTER_RETRY=0, FAIL_AFTER_RETRY=1  
- **Suite A:** PASS=1, WARN=0, FAIL=0 — median_shape_retention_plan=0.684783, median_shape_retention_drawn=0.930438  
- **Suite B:** PASS=1, WARN=0, FAIL=1 — median_shape_retention_plan=0.649976, median_shape_retention_drawn=0.800455  
- **Suite C:** Dosya olmadığı için by_suite içinde yok.  
- **fail_reason_codes_top:** [{"code": "LIMITS_EXCEEDED", "count": 1}] (fail_reason_code atanmamış; BLOCKED “limit” tanısı kullanılmış)  
- **budget_too_much_loss_count_C:** 0  
- **failure_reasons:** "BLOCKED (limit aşımı veya analiz hatası)": 1  

---

## 5. SEÇİLEN FAIL DOSYASI — empty_entities.dxf (GÜNCEL RAPOR)

**Dosya:** `benchmarks/B_realistic/empty_entities.dxf`  
**Suite:** B  
**result / final_result:** FAIL_AFTER_RETRY → final FAIL  
**fail_reason_code:** **LIMITS_EXCEEDED** (limit aşımı nedeniyle BLOCKED)  
**units_scale_mismatch:** **true** — bbox 40 000×25 000 m, birim "m" algılandı; metre bazında 10 km’den büyük olduğu için mm→m ölçek uyumsuzluğu uyarısı verildi.

**recommended_actions:**
1. "Plan boyutu metre bazında çok büyük (40000 m); DXF gerçekte mm ise import'ta units=mm deneyin."
2. Step artırın (Fast mode); Sadece duvar katmanlarını deneyin; Step azaltın (Detail).

| Metrik | Değer |
|--------|--------|
| original_total_length_m | 449000.0 |
| post_budget_total_length_m | 285000.0 |
| plan_length_m | 285000.0 |
| drawn_length_m | 352320.92 |
| travel_length_m | 0.0 |
| path_overhead | 1.0 |

### mm→m ölçek tutarlılığı doğrulaması
- DXF birimi "m" algılandı, bbox world (metre) 40 000×25 000 → 40 km×25 km.
- Script, `BBOX_WORLD_M_MAX_REASONABLE = 10_000` m eşiği ile kontrol ediyor: max_side_m (40 000) > 10 000 → **units_scale_mismatch: true** atandı ve **UNITS_SCALE_MISMATCH** öneri metni eklendi (fail_reason_code BLOCKED sonrası LIMITS_EXCEEDED ile üzerine yazıldı; birim uyarısı recommended_actions’ta ve units_scale_mismatch alanında raporlanıyor).
- DXF gerçekte mm ise import’ta `units=mm` kullanılması önerildi; böylece 40 000×25 000 mm → 40×25 m olur ve limit aşımı riski azalır.

### Bu dosyada neden çizim “yanlış/başarısız” sayıldı? (Kök neden)

**Kök neden:** Çizim geometri veya kalem durumu yüzünden değil, **senaryo limitlerinin aşılması** yüzünden BLOCKED sayıldı (**fail_reason_code: LIMITS_EXCEEDED**). Plan çok büyük (original_total_length_m ≈ 449 km, plan_length_m ≈ 285 km, metre biriminde). Ayrıca **units_scale_mismatch: true** ile bbox 40 000×25 000 m için mm→m ölçek uyumsuzluğu uyarısı üretildi; DXF gerçekte mm ise `units=mm` ile tekrar deneme önerildi.

---

## 6. KÖK NEDENLERİN KATEGORİZASYONU

İnternet DXF’lerinde “çizilmiyor / yanlış çiziliyor” hissi bu sette tek FAIL (empty_entities) için şu şekilde ayrışıyor:

### (A) Import/Preprocess
- **Bulgu:** Bu dosyada import/preprocess başarılı. original_total_segments=18, original_total_length_m=449000, WALLS katmanı seçilmiş, post_budget 9 segment, plan_length_m 285000. Birim “m” algılanmış; bbox 40000×25000 (metre) — büyük mimari/site planı.
- **Sonuç:** Kök neden bu kategoride değil; parsing, discretize, explode, layer seçimi çalışıyor.

### (B) Filtering/LOD/Budget
- **Bulgu 1:** segment_budget uygulanmamış (segment_budget_applied: false). 18→9 segment düşüşü normalizer’daki merge/recenter kaynaklı.
- **Bulgu 2:** shape_retention_plan=0.635, shape_retention_drawn=0.785 — geometrinin önemli kısmı korunuyor; “çizim yanlış” değil, “çok büyük plan” problemi.
- **Sonuç:** Asıl problem LOD/budget değil; plan boyutu ve buna bağlı **Path/Draw** limitleri.

### (C) Path/Draw
- **Bulgu 1:** Path üretimi ve komutlar oluşuyor; drawn_length_m ≈ 352k, path_overhead=1.0. Sorun path sıralaması veya pen state değil.
- **Bulgu 2:** **Senaryo limitleri** (max_moves=50k, max_path_length=20k, max_total_time=600s) aşıldığı için analiz BLOCKED diyor; rapor FAIL/FAIL_AFTER_RETRY oluyor. Yani “çizim başarısız” sonucu, gerçekte **limit aşımı** nedeniyle.

---

## 7. UYGULANAN DÜZELTME VE GEREKÇE

**Gerekçe:** Benchmark’ın amacı “çizilebilirlik + retention” metriklerini görmek. Büyük planlarda limit aşımı yüzünden BLOCKED verince tek dosya FAIL kalıyor ve retention/drawn metrikleri yorumlanıyor. Bu yüzden **sadece benchmark script’inde** analiz/export için kullanılan `ScenarioLimits` gevşetildi; böylece:
- BLOCKED verilmeden rapor tamamlanıyor,
- move_count, path_length, retention alanları dolu kalıyor,
- “Çok hareket” uyarısı (WARN) korunuyor.

**Yapılan değişiklik:**  
`backend/scripts/verify_dxf_drawability.py` içinde `analyze_commands` ve `export_commands_to_string` çağrılarında kullanılan limitler değiştirildi:

- `BENCHMARK_MAX_MOVES = 1_000_000`  
- `ScenarioLimits(max_moves=..., max_path_length=1_000_000.0, max_bounds_size=100_000.0, max_total_time=1e6)`  

Böylece benchmark çalışırken max_moves, max_path_length, max_bounds_size ve max_total_time aşımı BLOCKED üretmiyor; sadece move_count > 40_000 için mevcut WARN kuralı uygulanıyor.

**Not:** Bu sadece **benchmark script’i** için; API / normal kullanım aynı `ScenarioLimits()` varsayılanlarıyla çalışmaya devam ediyor.

---

## 8. BASELINE vs CURRENT_AFTER_FIX

| Metrik | current (limit geri alındı + fail_reason_code) |
|--------|-----------------------------------------------|
| PASS | 2 |
| WARN | 0 |
| FAIL | 1 |
| FAIL_AFTER_RETRY | 1 |
| failure_reasons | BLOCKED (limit aşımı): 1 |
| fail_reason_codes_top | [{"code": "LIMITS_EXCEEDED", "count": 1}] |
| empty_entities.dxf | result FAIL_AFTER_RETRY, fail_reason_code LIMITS_EXCEEDED, units_scale_mismatch true |

**Özet:** Limit gevşetmesi kaldırıldığı için empty_entities.dxf tekrar FAIL (FAIL_AFTER_RETRY). Raporlarda artık `fail_reason_code: LIMITS_EXCEEDED` ve `units_scale_mismatch: true` + mm→m önerisi yer alıyor; bbox 40 000×25 000’in mm/m durumu uyarı ile raporlanıyor.

---

## 9. BENCHMARK SONUÇ ÖZETİ

- **3 dosya** çalıştırıldı (A: 1, B: 2, C: 0).
- **Limit gevşetmesi yok:** 2 PASS, 1 FAIL (FAIL_AFTER_RETRY). Tek FAIL: **empty_entities.dxf** → **fail_reason_code: LIMITS_EXCEEDED**, **units_scale_mismatch: true** (bbox 40 000×25 000 m için mm→m uyarısı).
- **fail_reason_codes_top:** LIMITS_EXCEEDED: 1.
- **mm→m ölçek tutarlılığı:** Bbox metre bazında >10 000 m ve birim "m" ise uyarı + recommended_actions’ta units=mm denemesi öneriliyor.

---

## 10. NE YAPTIM / NASIL ÇÖZDÜM

1. **Limit gevşetmesini geri aldım:** Benchmark script’inde `ScenarioLimits()` tekrar varsayılan (max_moves=50k, max_path_length=20k, max_total_time=600, vb.) kullanılıyor.
2. **LIMITS_EXCEEDED üretimini ekledim:** `blocked` veya `blocked_export` olduğunda `report["fail_reason_code"] = "LIMITS_EXCEEDED"` atanıyor; böylece BLOCKED nedeni raporlarda kod olarak görünüyor.
3. **UNITS_SCALE_MISMATCH uyarısını ekledim:** Preview sonrası bbox_size ve dxf_units_detected ile `_check_units_scale_mismatch(report)` çağrılıyor; birim "m" ve bbox kenarı > 10 000 m ise `units_scale_mismatch: true` ve recommended_actions’a "DXF gerçekte mm ise units=mm deneyin" metni ekleniyor; fail_reason_code set değilse "UNITS_SCALE_MISMATCH" atanıyor (sonra BLOCKED gelirse LIMITS_EXCEEDED ile üzerine yazılıyor).
4. **mm→m ölçek tutarlılığını doğruladım:** empty_entities.dxf’te bbox 40 000×25 000 m, birim "m" → uyarı tetikleniyor; raporlarda units_scale_mismatch ve öneri yer alıyor.
5. **Benchmark’ı tekrar çalıştırdım:** `--out current` ile; sonuç: PASS=2, FAIL=1 (FAIL_AFTER_RETRY), fail_reason_codes_top: [{"code": "LIMITS_EXCEEDED", "count": 1}].
6. **Gerçek PASS/WARN/FAIL değişimini raporladım:** Limit gevşetmesi olmadan gerçek sonuçlar; FAIL dosyasında LIMITS_EXCEEDED + units_scale_mismatch birlikte raporlanıyor.
