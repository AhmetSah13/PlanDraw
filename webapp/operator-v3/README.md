# PlanDraw Operatör V3 (Deneme)

Modern, Türkçe operator arayüzü prototipi. **Resmi aktif arayüz değildir** — `operator-v2` bozulmadan ayrı geliştirilir.

## Çalıştırma

Backend (ayrı terminal):

```powershell
cd backend
python -m uvicorn app.api.main:app --reload --port 8000
```

V3 frontend:

```powershell
cd webapp/operator-v3
npm install
npm run dev
```

Tarayıcı: http://127.0.0.1:5174

Repo kökünden:

```powershell
npm run dev:frontend:v3
```

## API

Vite proxy `/api` ve `/health` isteklerini `127.0.0.1:8000` adresine yönlendirir.

Kullanılan endpoint'ler: `/health`, `/api/status`, `/api/import_dxf`, `/api/import_plan`, `/api/compile_plan`, `/api/analyze`, `/api/execute_serial`, `/api/execute_serial/stop`, `/api/jobs`, `/api/jobs/{id}/stop`.
