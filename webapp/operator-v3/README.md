# LayoutBot Command Center (Operator V3)

LayoutBot projesinin deneysel **Robot Command Center** arayüzü. Resmi aktif UI değildir (`operator-v2` korunur).

## Çalıştırma

```powershell
# Backend + V3 (önerilen)
npm run dev:v3

# Yalnızca V3
npm run dev:frontend:v3
```

- Frontend: http://127.0.0.1:5174
- Backend: http://127.0.0.1:8000

## API (Vite proxy)

`/health`, `/api/*` → `127.0.0.1:8000`

Kullanılan endpoint'ler: `GET /health`, `GET /api/status`, `POST /api/import_dxf`, `POST /api/import_plan`, `POST /api/compile_plan`, `POST /api/analyze`, `POST /api/execute_serial`, `POST /api/execute_serial/stop`, `POST /api/jobs`, `POST /api/jobs/{id}/stop`.
