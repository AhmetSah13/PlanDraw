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
- **webapp/operator-v2/** — **Resmi aktif frontend (source of truth)**
- **webapp/frontend/** — **LEGACY / FROZEN** frontend arşivi (geliştirme yapılmaz)
- **webapp/backend/** — **LEGACY / DEPRECATED** backend kopyası (çalıştırmayın; source of truth değildir)
- **docs/** — [ARCHITECTURE.md](docs/ARCHITECTURE.md), PIPELINE_ANALYSIS.md, AUDIT_REPORT.md
- **Mimari sınırlar (resmi çekirdek vs deneysel / legacy):** [ARCHITECTURE_STATUS.md](docs/ARCHITECTURE_STATUS.md)
- **benchmarks/** — DXF/DWG benchmark setleri
  - `A_expected_pass/` — Basit ve temiz, geçmesi beklenen planlar
  - `B_realistic/` — Gerçek dünyadan, orta karmaşıklıkta mimari planlar
  - `C_stress/` — Çok ağır/bozuk/stress amaçlı dosyalar

## Demo: DXF → duvar-only robot çizimi

Bu bölüm, MVP wall-only pipeline'ını uçtan uca denemek için en hızlı yolu anlatır.

### 1) Benchmark çalıştır (MVP güvence)

Benchmarks klasöründeki tüm suite'leri (A/B/C) çalıştırmak için:

```bash
python backend/scripts/verify_dxf_drawability.py --input benchmarks --suite ALL
```

Bu komut her dosya için:
- **PASS/WARN/FAIL**
- **units auto-retry** (mm ↔ m denemeleri)
- **layer_intelligence** (duvar katmanı seçimi)
- **scope_class** (SUPPORTED_WALL_ONLY vs OUT_OF_SCOPE_*)
- **wall filter + centerline + path metrikleri**

gibi alanları JSON raporlara (`backend/reports/current/`) yazar.

### 2) Tek bir DXF planı çizime dönüştür

Elindeki bir DXF floor-plan dosyasını iki farklı komut formatına çevirebilirsin:

#### 2.a) Basit çizim komutları (generic drawing)

```bash
python backend/scripts/draw_plan_from_dxf.py plan.dxf --out robot_commands.txt --centerline on --preview
```

- `--centerline on`: double-line duvarlardan orta çizgi çıkarımı (single-line duvarlar korunur).
- `--preview`: aynı klasöre `preview.svg` üretir.
- Çıktı dosyası `robot_commands.txt` aşağıdaki gibi **generic çizim komutları** içerir:

  ```text
  PEN_UP
  MOVE 10.0 5.0
  PEN_DOWN
  DRAW 12.0 5.0
  DRAW 12.0 8.0
  DRAW 10.0 8.0
  DRAW 10.0 5.0
  PEN_UP
  ```

Bu format, herhangi bir “kalemli plotter / çizer” için uygundur; sadece kalemi indir/kaldır ve absolute koordinatlara git/draw mantığı vardır.

#### 2.b) Mobil robot görev komutları (mobile robot mission)

Gerçek bir mobil zemin-çizim robotu (Dusty Robotics benzeri) için, aynı planı **mobil görev formatında** almak için:

```bash
python backend/scripts/draw_plan_from_dxf.py plan.dxf \
  --out robot_commands.txt \
  --centerline on \
  --preview \
  --mobile-robot-format on \
  --optimize-mobile-mission on
```

Bu modda `robot_commands.txt` aşağıdaki gibi **yüksek seviye görev komutları** içerir:

```text
SET_ORIGIN 0.000000 0.000000
SET_HEADING 0.000000
PEN_UP
MOVE_TO 10.000000 5.000000
PEN_DOWN
DRAW_TO 12.000000 5.000000
DRAW_TO 12.000000 8.000000
...
PEN_UP
END
```

- `SET_ORIGIN` / `SET_HEADING`: robotun dünya koordinat sistemindeki başlangıç pozunu tanımlar.
- `MOVE_TO`: kalem yukarı, hedef pozisyona git.
- `DRAW_TO`: kalem aşağı, hedef pozisyona git ve çiz.
- `END`: görevin bittiğini belirtir.

Bu komut seti, akademik bir mobil robot kontrol katmanının doğrudan tüketebileceği bir “misyon betiği” olarak tasarlanmıştır; alttaki motor/pose kontrolü bu seviyenin altında kalır.
`--optimize-mobile-mission on` iken, path/stroke listesi mobil robot açısından greedy bir “mission planner” ile yeniden sıralanır (stroke sırası ve yönü); **Varsayılan mod `travel_first`**: önce minimum travel mesafesine göre seçim yapılır; travel açısından yakın adaylar arasında heading değişimi en küçük olan seçilir (tie-break). Bu mod travel güvenliğini önceliklendirir. `--mobile-planner-mode weighted` ile eski weighted davranış (deneysel) kullanılabilir. **Degradation guard**: optimize edilmiş travel, naive planın `--mobile-travel-degradation-limit` (varsayılan 1.05) katını aşarsa otomatik olarak naive plana fallback yapılır; böylece planner açıkken bariz travel kötüleşmesi engellenir.

Komutlar çalıştığında CLI loglarında ayrıca şu metrikler yazılır:
- segment sayıları (import / normalize / filtre sonrası)
- `drawn_length_m` (kalem aşağı toplam çizim)
- `travel_length_m` (kalem yukarı toplam gezi)
- `move_count` (MOVE/DRAW veya MOVE_TO/DRAW_TO sayısı)
- `--optimize-mobile-mission on` iken: `planner_mode`, `naive_total_travel_m`, `optimized_total_travel_m`, `fallback_used`, `travel_improvement_ratio`

### 3) Önizlemeyi görüntüle

```bash
open preview.svg      # macOS
start preview.svg     # Windows
xdg-open preview.svg  # Linux
```

SVG içinde:
- **Gri**: duvar segmentleri (normalize sonrası, centerline/filter öncesi)
- **Mavi**: centerline segmentleri (double-wall tespit edilen yerler)
- **Kırmızı**: robotun gerçek çizim path’i (PEN_UP/PEN_DOWN sırası ile)

Bu sayede robota göndermeden önce plan ve path görsel olarak doğrulanabilir.

### Pipeline mimarisi (MVP wall-only)

Aşağıdaki şema, tek bir DXF dosyasının duvar-only çizim komutlarına nasıl dönüştüğünü özetler:

```text
       DXF / DWG
           │
           ▼
  DXF importer (ezdxf)
  - INSERT explode (virtual_entities)
  - HATCH boundary extraction
           │
           ▼
  Layer intelligence
  - dxf_diagnostics
  - entity mix + keyword + length
  - graph tabanlı wall_layer_score
           │
           ▼
  Wall-only segments
  - sadece LINE / LWPOLYLINE / POLYLINE
  - ARC / SPLINE flatten (discretize)
           │
           ▼
  Normalize
  - snap endpoints
  - merge collinear
  - recenter
           │
           ▼
  Wall filter (gated)
  - çok kısa segmentleri at (<0.05 m)
  - küçük komponentleri at (<0.5 m)
  - kalite gating:
      drawn_length ve travel_length
      kötüleşiyorsa FILTER_FALLBACK
           │
           ▼
  Centerline extraction (opsiyonel)
  - double-wall eşleştirme (paralel + overlap + gap 0.05–0.40 m)
  - coverage düşükse güvenli fallback
           │
           ▼
  Path generation (baseline)
  - PathGenerator (segmentlerden stroke üretimi)
           │
           ▼
  Robot commands
  - PEN_UP / PEN_DOWN
  - MOVE x y
  - DRAW x y
```

Bu pipeline, internetteki basit 2D floor-plan DXF planlarını “wall-only, centerline odaklı” bir çizim yoluna dönüştürmek için optimize edilmiştir; metin/ölçü/mobilya gibi annotation öğeleri çizilmez, sadece neden elendikleri raporlanır.

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
- **Frontend (resmi):** http://127.0.0.1:5173 (`webapp/operator-v2`)

### Source of truth notu

Backend için **tek gerçek kaynak** `backend/` klasörüdür. `webapp/backend/` klasörü legacy/deprecated’tir; demo ve geliştirme akışında kullanılmamalıdır.

Durdurmak için tek **Ctrl+C** yeterli.

### Ayrı ayrı çalıştırma

- Sadece backend: `npm run dev:backend` (backend/ klasörüne geçip uvicorn çalıştırır)
- Sadece frontend: `npm run dev:frontend`

### Mac / Linux

Script'ler Windows CMD için yazılı (cd + uvicorn/npm). Mac/Linux'ta aynı anda çalıştırmak için `scripts/dev-backend.sh` ve `scripts/dev-frontend.sh` kullanılabilir veya `dev:backend` / `dev:frontend` komutları ortama göre (bash) düzenlenebilir.
## Frontend Cutover Notu

- Resmi aktif frontend source of truth: `webapp/operator-v2/`
- Resmi yerel çalışma standardı: frontend `127.0.0.1:5173`, backend `127.0.0.1:8000`
- Repo kökündeki `npm run dev` `webapp/operator-v2` çalıştırır.
- `webapp/frontend/` legacy/frozen kabul edilir.
- Yeni geliştirme yalnızca `webapp/operator-v2/` altında devam etmelidir.
