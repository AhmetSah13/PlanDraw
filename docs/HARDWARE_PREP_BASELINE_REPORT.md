# Hardware Prep Baseline Report

## Date

2026-05-05

## Scope

Bu rapor yalnizca PlanDraw / NewBot yazilim baseline dogrulamasini kapsar.

Bu rapor gercek donanim testi degildir. Gercek seri port calistirilmadi, `dry_run=false` kullanilmadi ve robota komut gonderilmedi.

Resmi urun hatti kapsaminda dogrulanan alanlar:

- `backend/`
- `webapp/operator-v2/`

Legacy kabul edilen ve dokunulmayan alanlar:

- `webapp/frontend/`
- `webapp/backend/`

## Commands Run

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests
```

Frontend:

```powershell
cd webapp/operator-v2
npm run build
npm run lint
npm run test
npm run e2e
npm run verify:backend-live
npm run e2e:real
```

## Results

| Komut | Sonuc | Ozet |
| --- | --- | --- |
| `cd backend && .\.venv\Scripts\python.exe -m pytest tests` | PASS | `201 passed, 87 deselected, 11 warnings` |
| `cd webapp/operator-v2 && npm run build` | PASS | Vite production build basarili |
| `cd webapp/operator-v2 && npm run lint` | PASS | ESLint hata bildirmedi |
| `cd webapp/operator-v2 && npm run test` | PASS | `10 passed` |
| `cd webapp/operator-v2 && npm run e2e` | PASS | `1 passed, 1 skipped` |
| `cd webapp/operator-v2 && npm run verify:backend-live` | PASS | Gercek backend smoke dogrulamasi basarili; `/api/execute_serial` yalniz dry-run olarak cagrildi |
| `cd webapp/operator-v2 && npm run e2e:real` | PASS | Gercek backend E2E akisi basarili |

## Safety Confirmation

- `dry_run=false` calistirilmadi.
- Gercek seri port kullanilmadi.
- Firmware degistirilmedi.
- Robota komut gonderilmedi.
- Legacy klasorlere dokunulmadi.
- `webapp/frontend/` altinda islem yapilmadi.
- `webapp/backend/` altinda islem yapilmadi.

## Final Verdict

BASELINE PASS

## Recommended Next Step

Asama 1: Dry-run serial dogrulama
