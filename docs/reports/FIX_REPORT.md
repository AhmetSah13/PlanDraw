## Units Retry ve Scope Class Fix Raporu

### 1. Bug: units_retry + scope_class tutarsızlığı

- **Belirti**: `empty_entities.dxf` için:
  - `units_retry_used = true`, `units_chosen = "mm"`
  - `units_retry_metrics["mm"].bbox_size = [40.0, 25.0]` → `_bbox_reasonable = true`
  - `units_retry_metrics["mm"].analyze_result = "SAFE"`
  - Buna rağmen raporda `units_scale_mismatch = true` ve `scope_class = OUT_OF_SCOPE_UNITS_UNCERTAIN` idi.
- **Kök neden**:
  - `_merge_units_retry_report` fonksiyonu, units retry sonrasında da `out["units_scale_mismatch"] = True` bırakıyordu; seçilen adayın (`m`/`mm`) bbox ve analiz sonucuna bakmıyordu.
  - `_classify_scope` ise sadece `units_retry_used` ve `units_scale_mismatch` bayraklarına bakarak her units retry durumunu **otomatik** `OUT_OF_SCOPE_UNITS_UNCERTAIN` sınıfına itebiliyordu.
- **Çözüm**:
  - `_merge_units_retry_report` güncellendi:
    - Seçilen adayın (`chosen = "m" | "mm"`) `bbox_size` ve `analyze_result` değerleri üzerinden:
      - `chosen_bbox_ok = _bbox_reasonable(bbox_size)`
      - `chosen_analyze_ok = analyze_result != "BLOCKED"`
      - `units_scale_mismatch = not (chosen_bbox_ok and chosen_analyze_ok)`
    - Böylece başarılı units retry sonrasında `units_scale_mismatch = false` oluyor.
  - `_classify_scope` güncellendi:
    - `successful_retry = chosen_bbox_ok and chosen_analyze_ok` tanımlandı.
    - Yalnızca **başarısız retry** durumunda `SCOPE_UNITS (OUT_OF_SCOPE_UNITS_UNCERTAIN)` atanıyor.
    - Başarılı retry durumunda scope sınıflaması normal akışa bırakılıyor (duvar skorları, retention vb.).
- **Son durum (B_scope_after_units_fix)**:
  - `empty_entities.dxf`:
    - `units_scale_mismatch = false`
    - `scope_class = SUPPORTED_WALL_ONLY`
  - `sample.dxf`:
    - `scope_class = SUPPORTED_WALL_ONLY`
  - `summary.json`:
    - `in_scope_total = 2`, `out_scope_total = 0`
    - `in_scope_median_retention_vs_walls_candidate ≈ 0.9997`
    - `in_scope_median_path_overhead ≈ 1.2317`

### 2. Bug: Optimize metriklerinin null olması

- **Belirti**:
  - `--optimize none` koşularında beklendiği gibi optimizer alanları boştu (flag kapalı).
  - Önceki benchmarklarda `--optimize on` kullanıldığı halde bazı raporlarda `commands_baseline_metrics`, `commands_optimized_metrics`, `optimizer_decision` alanları null göründü; bu, eski sürümde optimizer çağrısının daha erken aşamada (örneğin path/analiz hatası) short-circuit olması ve metriklerin hiç set edilmemesinden kaynaklanıyordu.
- **Mevcut davranış (fix sonrası kod)**:
  - `verify_dxf_drawability.py` içinde:
    - `run_one(..., optimize_enabled=(args.optimize == "on"), ...)`
    - `if optimize_enabled:` bloğu yalnızca path ve komut üretimi **başarılı** olduktan sonra çalışıyor.
  - Bu blokta **her zaman**:
    - `commands_baseline_metrics = measure_drawn_travel(commands, start_xy=start)`
    - `commands_optimized_metrics = measure_drawn_travel(commands_opt, start_xy=start)`
    - `optimizer_decision = {"used": True/False, "reason": ...}`
    dolduruluyor.
  - Eğer optimizer travel’ı kötüleştirirse:
    - `optimizer_decision.used = false`
    - `optimizer_decision.reason = "TRAVEL_WORSE_FALLBACK"`
    - Komutlar fallback ile baseline’da kalıyor; metrikler yine dolu.
- **Doğrulama (B_opt_none vs B_opt_on)**:
  - `python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite B --out B_opt_none --optimize none`
  - `python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite B --out B_opt_on --optimize on`
  - `empty_entities.dxf`:
    - Optimize none:
      - `move_count = 587`
      - `travel_length_m = 67.3209`
      - `path_overhead = 1.236214`
      - Optimize alanları null (beklenen).
    - Optimize on:
      - `commands_baseline_metrics.travel_length_m = 67.3209`
      - `commands_optimized_metrics.travel_length_m = 175.0076`
      - `optimizer_decision = {"used": false, "reason": "TRAVEL_WORSE_FALLBACK"}`
      - `move_count_before_optimize = 587`, `move_count_after_optimize = 31`
      - Yani optimizer devreye giriyor, travel kötüleştiği için fallback ediyor; metrikler dolu.
  - `sample.dxf`:
    - Optimize none:
      - `move_count = 587`
      - `travel_length_m = 40.9055`
      - `path_overhead = 1.227241`
      - Optimize alanları null.
    - Optimize on:
      - `commands_baseline_metrics.travel_length_m = 40.9055`
      - `commands_optimized_metrics.travel_length_m = 126.3594`
      - `optimizer_decision = {"used": false, "reason": "TRAVEL_WORSE_FALLBACK"}`
      - `move_count_before_optimize = 587`, `move_count_after_optimize = 82`
      - Burada da optimizer deneniyor, ancak travel kötüleştiği için kullanılmıyor; tüm optimize metrikleri dolu.

### 3. Özet Sayılar (önce / sonra)

- **Scope / in-scope sayıları** (B_realistic, benchmarks/B):
  - Önce (B_real_scope_run, problemli sürüm):
    - `in_scope_total = 1` (sadece `sample.dxf`)
    - `out_scope_total = 1` (`empty_entities.dxf` → `OUT_OF_SCOPE_UNITS_UNCERTAIN`)
  - Sonra (B_scope_after_units_fix):
    - `in_scope_total = 2` (`empty_entities.dxf` + `sample.dxf` ikisi de `SUPPORTED_WALL_ONLY`)
    - `out_scope_total = 0`
- **Optimize metrikleri**:
  - `B_opt_none`:
    - `commands_*` ve `optimizer_decision` alanları **null** (flag kapalı).
  - `B_opt_on`:
    - Her iki dosyada da:
      - `commands_baseline_metrics` DOLU
      - `commands_optimized_metrics` DOLU
      - `optimizer_decision` DOLU (`used=false`, `reason="TRAVEL_WORSE_FALLBACK"`)
    - Hareket ve travel özeti (baseline → candidate):
      - `empty_entities.dxf`: travel `67.32 → 175.01`, move `587 → 31`
      - `sample.dxf`: travel `40.91 → 126.36`, move `587 → 82`
    - Her iki dosyada da optimizer travel’ı kötüleştirdiği için fallback ediyor; bu da `optimizer_decision` ile açıkça raporlanıyor.

### 4. Değişen Dosyalar

- `backend/scripts/verify_dxf_drawability.py`:
  - `_merge_units_retry_report`:
    - `units_scale_mismatch` artık seçilen adayın bbox ve analiz durumuna göre hesaplanıyor.
  - `_classify_scope`:
    - Başarılı units retry durumunda `OUT_OF_SCOPE_UNITS_UNCERTAIN` tetiklenmiyor; dosya normal wall-perception heuristikleri ile sınıflanıyor.
  - `run_one`:
    - `--optimize on` durumunda optimizer metrikleri (baseline/optimized + decision) her zaman dolduruluyor.

Bu değişiklikler ile hem **units retry / scope_class** tutarlılığı sağlandı, hem de optimizer metrikleri `--optimize on` verildiğinde hiçbir dosyada null kalmıyor.

