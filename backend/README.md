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
    analysis/     # scenario_analysis, geometry_graph
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

## Offline motion demo (HTTP yok)

Küçük çizim senaryolarını **yeni motion yürütme yolu** (`execute_command_sequence_motion`) üzerinden çalıştırmak için:

```bash
cd backend
python scripts/offline_motion_demo.py --list
python scripts/offline_motion_demo.py --scenario square
python scripts/offline_motion_demo.py -s l_shape -v
python scripts/offline_motion_demo.py -s square --no-check
python scripts/offline_motion_demo.py -s turn_forward --strict
```

Yerleşik senaryolar için isteğe bağlı **beklenen son poz** özeti yazdırılır (`PASS` / `WARN` / `FAIL`); `--no-check` ile atlanır, `--strict` toleransları yaklaşık yarıya indirir.

Bu araç **eski `CommandExecutor`** veya FastAPI kullanmaz; donanım gerekmez. Holonomik web simülasyonu (`app/simulation/simulator.py`) ile karıştırılmamalıdır. Ayrıntı: `docs/MOTION.md`.

## Geometry Graph Engine

Import sonrası normalize edilmiş segmentlerden **planı anlama** için graf tabanlı metrikler üretilir (`app/analysis/geometry_graph.py`).

- **build_graph(segments, tol)**: Segment uç noktaları `tol` (varsayılan 1e-6) ile grid-snap edilir; node-edge graf üretilir.
- **compute_graph_metrics(graph)**: `node_count`, `edge_count`, bağlantı bileşenleri, derece histogramı, `intersection_count` (derece≥3), `dangling_edges_count`, `closed_cycles_count` (cyclomatic), `cycle_perimeters`, `dominant_angles`, `edge_length_stats`.
- **detect_room_outlines(graph)**: Döngü tabanlı oda konturu adayları (en az N kenar, min çevre).
- **detect_wall_candidates(graph)**: Eksene hizalı uzun segment kümeleri (axis_alignment_score, connectivity_score).

Import pipeline’da `enrich_plan_with_graph_metrics(plan)` ile `normalized.metadata["graph_metrics"]`, `room_candidates`, `wall_candidates` doldurulur. Benchmark raporunda `graph_metrics`, `room_candidates_count`, `wall_candidates_count` ve `GRAPH_REPORT.md` üretilir. Testler: `pytest backend/tests/test_geometry_graph.py`.

## Path optimizasyonu

**Stroke bazlı sıralama** (`app/pathing/path_optimizer.py`): Komut listesi stroke’lara ayrılır (PEN DOWN blokları); NN + isteğe bağlı 2-opt ile stroke sırası ve her stroke’un yönü (normal/ters) seçilir; `join_epsilon_m` içinde uç uca gelen stroke’lar birleştirilir; ardından min_segment, collinear, RDP sadeleştirmesi uygulanır.

**OptimizeConfig:** `enabled`, `join_epsilon_m`, `max_2opt_iterations`, `time_budget_ms`, `preserve_order_for_layers`, `deterministic_seed` (mevcut `min_segment_length`, `collinear_angle_eps_deg`, `rdp_epsilon` ile birlikte).

**Benchmark:** `--optimize none|on` ile pen-up travel ve move sayısı önce/sonra raporlanır (`travel_reduction_pct`, `path_overhead_before_optimize` / `path_overhead_after_optimize`). Segment bazlı yol için `PathGenerator.generate_path_segments()` ve `compile_path_to_commands_from_segments()` kullanılır. Testler: `pytest backend/tests/test_path_optimizer.py`.

## Çalıştırma (kısa)

- Kök dizinden: `npm run dev:backend` (package.json `cd backend` + uvicorn çalıştırır).
- Sadece backend: `cd backend` → `uvicorn app.api.main:app --reload --port 8000`.

## CORS ve resmi yerel standart

Resmi frontend kombinasyonu:

- `http://127.0.0.1:5173`
- `http://localhost:5173`

Backend CORS varsayılanı bu iki origin ile sınırlıdır. Ek origin gerekirse:

- `BACKEND_CORS_ORIGINS_EXTRA="http://ek-origin:port,http://diger-origin:port"`

Not: Operator V2 cutover standardı frontend `127.0.0.1:5173`, backend `127.0.0.1:8000` şeklindedir.

## POST `/api/execute_serial` (seri port / DSL yürütme)

Bu uç, DSL metnini derleyip **`run_command_execution_job`** ile yürütür. **`dry_run=false`** iken gerçek UART üzerinden komut gönderimi yapılabilir; bu yüzden erişim varsayılan olarak kısıtlıdır.

### Ne yapar?

- İstek gövdesindeki `text` alanı DSL olarak parse edilir; isteğe bağlı `start`, `optimize` kullanılabilir.
- **`dry_run` (varsayılan `true`):** Seri port açılmaz; artifact dosyaları ve özet üretilir (güvenli test).
- **`dry_run=false`:** Ortam değişkenlerinde tanımlı **`SERIAL_PORT`** ile gerçek gönderim yapılır; **`SERIAL_BAUD`** yalnızca env’den okunur (istek gövdesinde port/baud **yok**).

### Ortam değişkenleri

| Değişken | Rol |
|----------|-----|
| **`SERIAL_PORT`** | Canlı gönderimde zorunlu (ör. Windows `COM3`, Linux `/dev/ttyUSB0`). |
| **`SERIAL_BAUD`** | İsteğe bağlı; tanımsızsa **115200**. Geçersiz değer → HTTP 400, `error_detail`: `INVALID_SERIAL_BAUD`. |
| **`EXECUTE_SERIAL_ALLOW_REMOTE`** | Varsayılan davranış **`false`** (veya tanımsız): yalnızca yerel (loopback) istemci IP’leri kabul edilir. `true` / `1` / `yes` / `on` ise **IP tabanlı localhost kısıtı kaldırılır**. |
| **`EXECUTE_SERIAL_ADMIN_TOKEN`** | Boş değilse tüm isteklerde **`X-Execute-Token`** başlığı zorunlu; aksi halde HTTP 403, `error_detail`: `EXECUTE_SERIAL_INVALID_TOKEN`. |

İsteğe bağlı: `EXECUTE_SERIAL_ARTIFACT_DIR` — dry_run ve canlı koşularda artifact çıktı dizini.

### Varsayılan güvenlik (localhost-only)

- **`EXECUTE_SERIAL_ALLOW_REMOTE`** truthy değilken kabul edilen kaynaklar: `127.0.0.1`, `::1`, `localhost`, IPv4 eşlemesi `::ffff:127.0.0.1` (ve pytest `TestClient` için `testclient`).
- Yetkisiz kaynak → **HTTP 403**, `error_detail`: **`EXECUTE_SERIAL_LOCALHOST_ONLY`**.

### Ters proxy notu

- Kontrol **`request.client.host`** üzerinden yapılır (Uvicorn’un gördüğü doğrudan bağlantı eşi).
- **`X-Forwarded-For`** veya benzeri başlıklara **güvenilmez**; reverse proxy arkasında “gerçek istemci” bu alanda görünmeyebilir. Proxy kullanıyorsanız güvenlik modelini (ağ kısıtı, token, `ALLOW_REMOTE`) buna göre tasarlayın.

### Güvenlik uyarıları

1. **`EXECUTE_SERIAL_ALLOW_REMOTE=true`** → Yukarıdaki **IP localhost filtresi devre dışı** kalır; uygulamaya ağdan kim ulaşabiliyorsa bu uca da ulaşabilir (sunucu dinlemesine bağlı).
2. **Token tanımlı değilse** ve sunucu uzaktan erişilebilirse → İsteyen herkes (ağ erişimi olan) bu endpoint’e istek atabilir; **üretimde güçlü bir `EXECUTE_SERIAL_ADMIN_TOKEN` + ağ kısıtı (firewall, yalnızca VPN içi dinleme)** birlikte önerilir.
3. İki koruma birlikte açıksa **önce host kontrolü**, **sonra token** değerlendirilir; ikisi de sağlanmalıdır.

### Örnek istekler

**Dry run (varsayılan — UART kapalı):**

```bash
curl -s -X POST "http://127.0.0.1:8000/api/execute_serial" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"SPEED 10\\nMOVE 0 0\\n\", \"dry_run\": true}"
```

**Canlı gönderim** (`SERIAL_PORT` ve geçerli `SERIAL_BAUD` env’de; önce sunucuyu bu env ile başlatın):

```bash
curl -s -X POST "http://127.0.0.1:8000/api/execute_serial" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"SPEED 1\\nMOVE 1 1\\n\", \"dry_run\": false}"
```

**Token koruması açıkken** (`EXECUTE_SERIAL_ADMIN_TOKEN` sunucuda tanımlı):

```bash
curl -s -X POST "http://127.0.0.1:8000/api/execute_serial" \
  -H "Content-Type: application/json" \
  -H "X-Execute-Token: sizin-gizli-token-degeriniz" \
  -d "{\"text\": \"SPEED 1\\nMOVE 0 0\\n\", \"dry_run\": true}"
```

Örnek env satırları için bkz. **`backend/.env.example`**.

## Dokümantasyon

- [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) — Modül haritası, pipeline, test komutları.
