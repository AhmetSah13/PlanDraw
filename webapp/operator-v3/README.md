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

## Jüri / demo akışı (donanım olmadan)

1. `npm run dev:v3` ile backend + V3 başlatın.
2. Üstteki **Demo Akışı** panelinden hazır planlardan birini seçin (otomatik yükle + derle).
3. **Komut Akışı** bölümünde BEGIN / PEN / MOVE satırlarını doğrulayın.
4. **Dry-run** veya **Simülasyon** ile yazılım hattını gösterin (fiziksel motor testi gerekmez).

Hazır demo DXF dosyaları: `public/demo/`

| Dosya | Açıklama |
|-------|----------|
| `demo_square_room.dxf` | Basit kare oda |
| `demo_two_segments.dxf` | İki kopuk çizgi (pen-up davranışı) |
| `demo_room_door_gap.dxf` | Kapı boşluklu oda |

DXF yeniden üretmek için: `python scripts/generate_demo_dxfs.py`

Telemetri paneli donanım olmadan dürüst durum gösterir: Firmware compile PASS, motor çıkışları donanım testi bekliyor, canlı mod fiziksel test gerektirir.

```powershell
npm run lint
npm run test
npm run build
```
