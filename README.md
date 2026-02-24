# PlanDraw

Backend (FastAPI) + Frontend (Vite/React) ile senaryo analizi ve canlı çizim.

## Tek komutla çalıştırma (dev)

Repo **kök dizininde** (root):

```bash
npm i
npm run dev
```

- **Backend:** http://127.0.0.1:8000 (uvicorn, reload)
- **Frontend:** http://127.0.0.1:5173 (Vite; terminalde URL çıkar, tarayıcıda açılabilir)

Durdurmak için tek **Ctrl+C** yeterli.

### Ayrı ayrı çalıştırma

- Sadece backend: `npm run dev:backend`
- Sadece frontend: `npm run dev:frontend`

### Mac / Linux

Script’ler Windows CMD için yazılı (cd + uvicorn/npm). Mac/Linux’ta aynı anda çalıştırmak için `scripts/dev-backend.sh` ve `scripts/dev-frontend.sh` kullanılabilir veya `dev:backend` / `dev:frontend` komutları ortama göre (bash) düzenlenebilir.
