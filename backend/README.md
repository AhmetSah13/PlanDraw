# PlanDraw Backend

Modüler Python backend: FastAPI API, import (DXF/DWG), normalizasyon, path üretimi, analiz ve simülasyon.

## Yapı

```
backend/
  app/
    api/          # FastAPI main, schemas
    core/         # Plan, Wall (plan_module)
    execution/    # commands, compiler, executor
    importers/    # dxf_importer, dwg_converter, plan_importer
    normalization/# normalized_plan, plan_normalizer
    pathing/      # path_generator, path_optimizer
    analysis/     # scenario_analysis
    simulation/   # simulator
    utils/        # step_size_utils, geometry_utils, motion_model
  tests/
  requirements.txt
  pyproject.toml
```

## Önerilen geliştirme akışı

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
uvicorn app.api.main:app --reload --port 8000
```

Editable install (`pip install -e .`) sayesinde `app` paketi her yerden import edilebilir; PYTHONPATH gerekmez.

## Testler

- **Birim testleri (minimal bağımlılık):** pydantic/fastapi kurulu olmadan çalışır; varsayılan pytest sadece birim testlerini çalıştırır.

  ```bash
  cd backend
  pytest tests
  ```

- **Entegrasyon testleri:** `pydantic` ve `fastapi` (ve `pip install -r requirements.txt`) gerekir. Sadece entegrasyon testlerini çalıştırmak için:

  ```bash
  cd backend
  pip install -r requirements.txt
  pytest -m integration
  ```

**backend/ içinden (editable install sonrası):**

```bash
cd backend
pytest tests
# veya
python -m unittest discover -s tests -p "test_*.py" -v
```

**Repo kökünden:**

```bash
# Önce bir kez: pip install -e backend (repo kökünde)
pytest backend/tests
# veya
python -m pytest backend/tests
```

Varsayılan `pytest tests` komutu `addopts = "-m 'not integration'"` ile yalnızca birim testlerini toplar; entegrasyon testleri atlanır. Entegrasyon testlerini çalıştırmak için: `pytest -m integration` (bağımlılıklar kurulu olmalı).

`backend/tests/conftest.py`, pytest ile repo kökünden çalıştırıldığında `backend` klasörünü `sys.path`'e ekler (editable install yapılmamışsa).

## DXF Çizilebilirlik Doğrulama

Tek tuşla akışın (yükleme → önizleme → import → analiz → çizim/export) gerçek DXF dosyalarıyla çalıştığını doğrulamak için CLI aracı kullanılır.

**Komutlar (backend kökünden):**

```bash
cd backend
pip install -r requirements.txt   # bir kez
python scripts/verify_dxf_drawability.py --input <dosya_veya_klasör> --out reports --mode auto
```

- **Girdi:** Tek bir `.dxf` dosyası veya içinde (özyinelemeli) `.dxf` bulunan klasör.
- **Çıktı:** `--out` ile verilen klasöre her DXF için `reports/<ad>.json` ve `reports/summary.json`; konsolda özet tablo.

**Sonuçlar:**

| Sonuç | Anlamı |
|-------|--------|
| **PASS** | Analiz SAFE; export başarılı, çizim güvenli. |
| **WARN** | SAFE fakat hareket/çakışma sayısı yüksek; step veya katman seçimini iyileştirin. |
| **FAIL** | BLOCKED veya pipeline hatası; raporlardaki `failure_reason` ve `recommended_actions` alanlarına bakın. |
| **PASS_AFTER_RETRY** | İlk denemede BLOCKED; otomatik strateji (Fast / Walls only / Detail) ile başarılı. |
| **FAIL_AFTER_RETRY** | Tüm retry stratejileri denendi, hâlâ başarısız. |

**Önerilen aksiyonlar (FAIL için):** Katman filtreleme (sadece duvarlar), step artırma (Fast: `step = min(step*2, 0.50)`), step azaltma (Detail: `step = max(step*0.75, 0.05)`). Raporlarda `recommended_actions` listesi yazılır.

**Golden suite:** Örnek DXF’leri `backend/golden_dxfs/` klasörüne koyup aynı komutta `--input golden_dxfs` vererek regresyon olarak çalıştırabilirsiniz. Bkz. `golden_dxfs/README.md`.

**İsteğe bağlı:** `--fail-on-warn` ile WARN veya PASS_AFTER_RETRY durumunda da çıkış kodu 1 alırsınız.

## Çalıştırma (kısa)

- Kök dizinden: `npm run dev:backend` (package.json `cd backend` + uvicorn çalıştırır).
- Sadece backend: `cd backend` → `uvicorn app.api.main:app --reload --port 8000`.

## Dokümantasyon

- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — Modül haritası, pipeline, test komutları.
