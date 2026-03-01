# PlanDraw

Backend (FastAPI) + Frontend (Vite/React) ile senaryo analizi ve canlı çizim.

## Proje yapısı

- **backend/** — Modüler Python backend (FastAPI)
  - `app/api/` — Ana uygulama (main.py, schemas.py)
  - `app/core/` — Plan, Wall (plan_module)
  - `app/execution/` — commands, compiler, executor
  - `app/importers/` — DXF/DWG, plan_importer
  - `app/normalization/` — normalized_plan, plan_normalizer
  - `app/pathing/` — path_generator, path_optimizer
  - `app/analysis/` — scenario_analysis
  - `app/simulation/` — simulator
  - `app/utils/` — step_size_utils, geometry_utils, motion_model
- **webapp/frontend/** — Vite/React arayüz
- **docs/** — [ARCHITECTURE.md](docs/ARCHITECTURE.md), PIPELINE_ANALYSIS.md, AUDIT_REPORT.md

## Kod kalitesi (pre-commit)

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files   # Tüm backend dosyalarında ruff lint + format
```

Backend için Ruff (lint + format) yapılandırması `backend/pyproject.toml` içindedir.

## Tek komutla çalıştırma (dev)

Repo **kök dizininde** (root):

```bash
npm i
npm run dev
```

- **Backend:** http://127.0.0.1:8000 (backend/ içinden uvicorn, `app.api.main:app`)
- **Frontend:** http://127.0.0.1:5173 (Vite; terminalde URL çıkar)

Durdurmak için tek **Ctrl+C** yeterli.

### Ayrı ayrı çalıştırma

- Sadece backend: `npm run dev:backend` (backend/ klasörüne geçip uvicorn çalıştırır)
- Sadece frontend: `npm run dev:frontend`

### Mac / Linux

Script'ler Windows CMD için yazılı (cd + uvicorn/npm). Mac/Linux'ta aynı anda çalıştırmak için `scripts/dev-backend.sh` ve `scripts/dev-frontend.sh` kullanılabilir veya `dev:backend` / `dev:frontend` komutları ortama göre (bash) düzenlenebilir.
