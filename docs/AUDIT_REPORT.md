# PlanDraw / NewBot — Hata ve Kenar Durumu Denetim Raporu

## 1) Findings (Tespitler)

### Backend
- **dxf_importer.py**: Geçersiz group code satırı ($DIMASO gibi) zaten resync ile ele alınıyor; test `test_dxf_stray_dimaso_resync_parses` mevcut. Ek sorun yok.
- **dxf_importer.py / inspect_dxf_layers**: Dönüşte `total_length`, `suggested_layers`, `layers` alanları var; `preview_layers` modu script derlemesi yapmıyor, sadece bu alanları döndürüyor. Doğrulandı.
- **dwg_converter.py**: `DwgConversionError`, timeout, stderr, çıktı yoksa anlamlı mesajlar fırlatıyor. Test: `test_converter_not_configured_returns_ok_false_with_clear_message`.
- **plan_normalizer.py**: Sıfır segment, segment_budget, recenter sonrası ValueError veya uyarılar tutarlı. NaN kontrolü yok; segment koordinatları float ve normalize sadece birleştirme/kaydırma yapıyor (NaN üretmez).
- **plan_importer.py / normalized_plan.py**: Kullanım yerleri main.py ve testler; tekrarlayan yardımcı yok. NormalizedPlan.segments min_length=1 ile boş plan kabul etmiyor.
- **main.py**:
  - **import_plan / import_dxf / import_dwg**: `raw_path` boşsa `ok=False` ve "Plan çizilebilir nokta üretmedi" mesajı dönüyordu. **compile_plan** için bu kontrol eksikti → eklendi.
  - **preview_layers**: Sadece `inspect_dxf_layers` çağrılıyor; normalized/commands_text/walls dönülmüyor. Doğrulandı.
- **scenario_analysis.py**: MAX_BOUNDS_SIZE ve MAX_MOVES teşhislerinde kullanıcıya "Öneri: recenter/scale" ve "step_size/segment_budget" metinleri yoktu → Diagnostic `text` alanına eklendi.
- **Limits**: ScenarioLimits (max_total_time, max_path_length, max_moves, max_bounds_size, max_abs_coord) analyze/jobs/export tarafında kullanılıyor; UI’a 409 + analysis_diags ile iletilir. Frontend’de bu mesajların kategorize edilmesi için formatImportError genişletildi.

### Frontend
- **App.jsx**: Dosya seçince otomatik full import kaldırılmış; seçilen dosya `selectedDxfFile` / `selectedDwgFile` state’te. Input temizlense bile state’teki dosya adı gösterilmiyordu → "Seçili dosya: X" satırı eklendi.
- **formatImportError**: Sadece format / çizilemez ayrımı vardı; ağ, limit (max_bounds, max_moves, max_path, max_time) ve “ne yapılmalı” kategorileri eksikti → genişletildi.
- **recommended_step_size**: Açıklama metni yoktu → "(yol noktaları arası mesafe; büyük değer daha az hareket)" eklendi.
- **previewBusy / importBusy**: Butonlar `importBusy` iken devre dışı; önizleme sırasında sadece `previewBusy` kullanılıyor, çakışma yok.

### Test ortamı
- Backend testleri `webapp/backend` dizininden çalıştırıldığında proje kökü (`NewBot`) ve bağımlılıklar (fastapi, pydantic) yok; `ModuleNotFoundError` alınıyor. Çözüm: sanal ortamda `pip install -r requirements.txt` ve `PYTHONPATH=<proje_kökü>` ile test çalıştırmak.

---

## 2) Patch plan (Uygulanan değişiklikler)

1. **scenario_analysis.py**: MAX_BOUNDS_SIZE teşhisine `text="Öneri: recenter veya scale_override kullanın; büyük koordinatlı planlarda önce merkezleme açın."` eklendi. MAX_MOVES teşhisine `text="Öneri: step_size değerini artırın veya segment_budget kullanın."` eklendi.
2. **main.py**: `compile_plan` içinde `raw_path` boşsa HTTP 200 + `ok: false` ve `error: "Plan çizilebilir nokta üretmedi; plan boş veya step_size değerini kontrol edin."` döndürülüyor.
3. **App.jsx**: `formatImportError` genişletildi (ağ, format/encoding, limit, çizilemez plan; Türkçe öneriler). DXF/DWG panellerinde `selectedFile` varken "Seçili dosya: {name}" gösterimi eklendi. Önerilen step_size için açıklama metni eklendi.
4. **test_normalized_plan.py**: `TestCompilePlanEmptyPath.test_empty_plan_text_returns_ok_false` eklendi (boş plan metni ile compile_plan → ok=False).
5. **test_import_dxf_api.py**: `test_import_dxf_selected_layers_nonexistent_returns_ok_false` eklendi (seçilen katman yoksa ok=False ve anlamlı hata).

---

## 3) Cleanup plan (Güvenli silme / refaktör)

### Silinebilecek dosyalar (kanıt)
- **ARCHITECTURE.md**, **PIPELINE_ANALYSIS.md**: Kod veya diğer dosyalar tarafından referans edilmiyor (`grep ARCHITECTURE, PIPELINE_ANALYSIS` boş). İsterseniz silebilirsiniz; dokümantasyon amaçlı kalabilir de.
- Başka modül/import ile kullanılmayan dosya tespit edilmedi; `dxf_importer`, `dwg_converter`, `plan_normalizer`, `plan_importer`, `normalized_plan` hepsi `main.py` veya testlerden kullanılıyor.

### Tutulacak; küçük refaktör önerisi
- **schemas.py** içindeki `SegmentIn` / `OriginIn` ile **normalized_plan.py** içindekiler ayrı (API vs. core); mevcut yapı geriye dönük uyumluluk için bırakıldı, birleştirme zorunlu değil.
- **scenario_analysis.py** içinde `from webapp.backend.app.geometry_utils import ...` kullanılıyor; proje kökü `sys.path`’te olduğu sürece çalışıyor. Değiştirilmedi.

### Bağımlılıklar
- **requirements.txt**: fastapi, uvicorn, pydantic, python-multipart kullanımda (main.py File/Form/UploadFile). Kaldırılmadı.
- **package.json**: react, react-dom, vite, @vitejs/plugin-react kullanımda. Kaldırılmadı.

---

## 4) Commands to run (Çalıştırma komutları)

### Windows PowerShell (Backend testleri)
Sanal ortam kullanıyorsanız önce etkinleştirin; bağımlılıklar yoksa yükleyin:

```powershell
cd c:\Users\ahmet\OneDrive\Desktop\NewBot\webapp\backend
# Opsiyonel: .\.venv\Scripts\Activate.ps1
# pip install -r requirements.txt
$env:PYTHONPATH = "c:\Users\ahmet\OneDrive\Desktop\NewBot"
python -m unittest discover -v -s tests -p "test_*.py"
```

### Bash (Linux/macOS)
```bash
cd /path/to/NewBot/webapp/backend
# source .venv/bin/activate
# pip install -r requirements.txt
export PYTHONPATH=/path/to/NewBot
python -m unittest discover -v -s tests -p "test_*.py"
```

### Frontend build
```powershell
cd c:\Users\ahmet\OneDrive\Desktop\NewBot\webapp\frontend
npm run build
```

```bash
cd /path/to/NewBot/webapp/frontend
npm run build
```

---

## 5) Final verification (Başarı kriterleri)

- **Backend**: Yukarıdaki komutla testler yeşil (venv + PYTHONPATH ile). Özellikle: test_import_dxf_api, test_import_dwg_api, test_normalized_plan, test_dxf_importer, test_geometry_utils, test_export, test_motion_model, test_collision_analysis.
- **Frontend**: `npm run build` hatasız biter.
- **UI akışı (DXF)**:
  1. W3 Plan → DXF seç → Dosya seç → Sadece önizleme (katman listesi) gelir, otomatik import çalışmaz.
  2. "Seçili dosya: X.dxf" görünür; "Seçili katmanlarla içe aktar" veya "Hızlı içe aktar (katman seçmeden)" ile import tetiklenir.
  3. İçe aktarma sonrası W2’ye geçilip "Çiz (W2)" ile çizim çalıştırılabilir.
- **Hata mesajları**: Binary DXF, ENTITIES yok, seçilen katmanlarda segment kalmaması, boş plan ile compile → ok=False ve Türkçe/anlamlı hata. Limit aşımlarında (MAX_BOUNDS_SIZE, MAX_MOVES) öneri metni analysis diag’ta görünür.
