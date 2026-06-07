# NewBot Command Center (Operator V3)

Deneysel **Robot Command Center** arayüzü. Resmi aktif UI değildir (`operator-v2` korunur).

## Çalıştırma

```powershell
# Backend (ayrı terminal)
cd backend
python -m uvicorn app.api.main:app --reload --port 8000

# V3 Command Center
cd webapp/operator-v3
npm install
npm run dev
```

http://127.0.0.1:5174

Repo kökünden: `npm run dev:v3` veya `npm run dev:frontend:v3`

## Tasarım

- Karanlık mission-control teması
- CAD → Robot pipeline stepper
- Canvas plan önizleme
- Terminal komut akışı
- Telemetri + canlı STOP

## API

Vite proxy: `/api`, `/health` → `127.0.0.1:8000`
