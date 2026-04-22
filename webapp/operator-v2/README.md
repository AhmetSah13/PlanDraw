# PlanDraw Operator V2 (Resmi Frontend)

Bu klasör cutover sonrası resmi frontend kaynağıdır.

## Resmi yerel çalışma standardı

- Frontend host/port: **`http://127.0.0.1:5173`**
- Backend host/port: **`http://127.0.0.1:8000`**

Bu standart dışında farklı port kullanımına izin verilmez; CORS ve script akışları bu kombinasyona göre sabitlenmiştir.

## Geliştirme

```bash
cd webapp/operator-v2
npm install
npm run dev
```

Backend:

```bash
cd backend
python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

## Doğrulama kapıları

```bash
npm run build
npm run lint
npm run test
npm run e2e
npm run verify:backend-live
```

## Not

`webapp/frontend` legacy ve dondurulmuştur; aktif geliştirme için kullanılmamalıdır.
