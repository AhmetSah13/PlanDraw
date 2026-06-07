# PlanDraw / NewBot GPT Uygulama Tanitim Raporu

Bu rapor, bir GPT modeline PlanDraw / NewBot uygulamasini bastan sona tanitmak icin hazirlanmistir. Amaci, modele projenin ne yaptigini, hangi klasorlerin kaynak kabul edildigini, ana kullanici akisini, backend ve frontend mimarisini, API sozlesmelerini, testleri, deneysel alanlari ve dikkat edilmesi gereken sinirlari tek dosyada vermektir.

## 1. Kisa Ozet

PlanDraw, mimari plan dosyalarini robot cizim komutlarina donusturmeyi hedefleyen bir FastAPI + React uygulamasidir.

Temel senaryo sudur:

1. Kullanici DXF, DWG, JSON veya manuel LINE tabanli plan girdisi yukler.
2. Backend plani normalize eder, duvar/geometri verisine cevirir ve cizim yolu uretir.
3. Uretilen komutlar analiz edilir; parser hatalari, carpismalar, yol uzunlugu, hareket sayisi ve tahmini sure raporlanir.
4. Kullanici gerekirse CAD koordinatlari ile saha koordinatlarini hizalar.
5. Komutlar once guvenli simulasyon olarak calistirilir.
6. Istenirse dry-run seri calistirma, canli seri calistirma veya dosya export islemleri yapilir.

Uygulamanin resmi urun yolu su anda web tabanli operator paneli + FastAPI backend zinciridir.

## 2. Repo Kimligi ve Source of Truth

Repo kok dizini:

```text
C:\Users\ahmet\OneDrive\Desktop\NewBot
```

Resmi backend:

```text
backend/
```

Resmi aktif frontend:

```text
webapp/operator-v2/
```

Legacy / dondurulmus alanlar:

```text
webapp/frontend/
webapp/backend/
```

Yeni gelistirme yaparken `webapp/operator-v2/` ve `backend/` esas alinmalidir. `webapp/backend/` deprecated kopyadir. `webapp/frontend/` eski frontend arsividir ve aktif gelistirme icin kaynak kabul edilmemelidir.

## 3. Calistirma Modeli

Kok dizinden tek komutla gelistirme:

```bash
npm run dev
```

Bu komut iki sureci birlikte baslatir:

- Backend: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`

Backend tek basina:

```bash
cd backend
python -m uvicorn app.api.main:app --reload --port 8000
```

Frontend tek basina:

```bash
cd webapp/operator-v2
npm run dev -- --host 127.0.0.1 --port 5173
```

Operator V2 icin resmi yerel standart bu iki adrestir. CORS ve dogrulama akislari bu kombinasyona gore tasarlanmistir.

## 4. Kullanici Akisi

Operator V2 uygulamasinda ana asamalar sunlardir:

```text
plan-yukle -> hizala -> kontrol-et -> calistir -> sonuclar
```

### 4.1 Plan Yukle

Kullanici su kaynaklardan birini secer:

- DXF dosyasi: `/api/import_dxf`
- DWG dosyasi: `/api/import_dwg`
- JSON plan: `/api/import_plan`
- Manuel LINE metni: `/api/compile_plan`

Bu asamada backend su bilgileri uretir:

- `commands_text`: calistirilabilir robot komut DSL'i
- `plan_text`: LINE tabanli plan metni
- `walls`: duvar segmentleri
- `raw_path_points`: onizleme ve simulasyon icin yol noktalari
- `warnings`: plan veya import uyarilari
- `recommended_step_size`: varsa onerilen adim boyutu

Frontend, plan onizlemesini `PlanCanvas` ile gosterir.

### 4.2 Hizala

Kullanici CAD koordinatlari ile saha koordinatlari arasinda kontrol noktalari girer. Backend `/api/alignment/rigid_2d` endpoint'i ile rijit 2D transform hesaplar.

Hizalama ciktisi:

- Donus acisi
- X/Y kayma
- Ortalama residual
- Maksimum residual
- Tolerans asimi varsa `blocked` bilgisi
- Oncesi/sonrasi SVG onizleme verisi

Bu asama robotun dijital plandaki konum sistemi ile fiziksel saha koordinatlarini baglamak icin vardir.

### 4.3 Kontrol Et

Frontend `/api/analyze` endpoint'ine uretilen komut metnini ve duvarlari gonderir.

Analiz sunlari denetler:

- Parser hatalari
- Komutlarin acilmis hali
- Cizim yolu uzunlugu
- Hareket sayisi
- Tahmini sure
- Carpismalar veya duvar kesismeleri
- `blocked` olup olmadigi

Varsayilan frontend cagrisi `collision_mode: "warn"` kullanir; yani bazi carpismalar engelleyici hata yerine uyari olarak raporlanabilir.

### 4.4 Calistir

Calistirma ekrani iki ana yol sunar:

1. Guvenli simulasyon
2. Seri port uzerinden dry-run veya canli calistirma

Guvenli simulasyon akisi:

```text
POST /api/jobs -> job_id
GET /api/jobs/{job_id}/stream -> SSE tick/done/error/ping
POST /api/jobs/{job_id}/stop -> durdurma
```

Seri calistirma akisi:

```text
POST /api/execute_serial
```

`dry_run: true` iken UART acilmaz, sadece artifact ve ozet uretilir. `dry_run: false` iken `SERIAL_PORT` ortam degiskeni gerekir ve gercek seri porta komut gonderilebilir.

Canli seri calistirma UI tarafinda ek onay kutusuna baglidir.

### 4.5 Sonuclar

Sonuclar ekrani `/api/export` endpoint'i ile komutlari dis formatlara cevirir.

Desteklenen export formatlari:

- `robot_v1`
- `gcode_lite`

Export yaniti:

- Dosya adi
- Icerik
- Parser ve analiz diagnostikleri
- Istatistikler
- `blocked` durumu

## 5. Backend Mimarisi

Backend Python 3.11+ hedefli bir FastAPI uygulamasidir.

Ana giris noktasi:

```text
backend/app/api/main.py
```

Baslica paketler:

```text
backend/app/api/             FastAPI endpoint'leri ve Pydantic semalari
backend/app/core/            Plan, Wall gibi temel veri yapilari
backend/app/importers/       DXF/DWG/plan import katmani
backend/app/normalization/   NormalizedPlan ve normalizasyon
backend/app/analysis/        Senaryo analizi, geometri grafi, wall filter/centerline
backend/app/pathing/         PathGenerator ve path optimizer
backend/app/execution/       Komut modelleri, parser/compiler, executor, job runner
backend/app/alignment/       Rigid 2D hizalama
backend/app/preview/         SVG/JSON onizleme
backend/app/drivers/         Null/File/Serial driver soyutlamalari
backend/app/motion/          Yeni motion execution deneysel/yardimci katmani
backend/app/robot/           Mobil robot komutlari ve mission planner
backend/app/layout_ir/       PrintableLayout IR ve dogrulama
backend/app/simulation/      Offline pygame simulator
backend/app/utils/           Geometri, step-size, motion model yardimcilari
```

Resmi web urun hattinda en kritik zincir:

```text
Input -> Normalize -> Path -> Commands -> Analyze -> Simulate/Export
```

DXF/DWG icin daha genis kavramsal zincir:

```text
DXF/DWG upload
  -> import/preprocess
  -> entity/segment cikarma
  -> layer secimi veya filtreleme
  -> normalizasyon
  -> plan_text ve walls
  -> path generation
  -> commands_text
  -> analiz/simulasyon/export
```

## 6. Backend API Haritasi

Saglik ve durum:

- `GET /health`
- `GET /api/status`

Plan import ve derleme:

- `POST /api/import_plan`
- `POST /api/import_dxf`
- `POST /api/import_dwg`
- `POST /api/compile_plan`

Analiz:

- `POST /api/analyze`

Job ve simulasyon:

- `POST /api/jobs`
- `GET /api/jobs/{job_id}/stream`
- `POST /api/jobs/{job_id}/stop`
- `POST /api/simulate`

Export:

- `POST /api/export`

Seri calistirma:

- `POST /api/execute_serial`

Hizalama:

- `POST /api/alignment/rigid_2d`

## 7. Komut ve Veri Modelleri

### 7.1 Plan Girdisi

`/api/import_plan` normalized JSON plan kabul eder:

```json
{
  "version": "v1",
  "units": "mm",
  "scale": 1.0,
  "origin": { "x": 0, "y": 0 },
  "segments": [
    { "x1": 0, "y1": 0, "x2": 10, "y2": 0 }
  ]
}
```

### 7.2 Manuel Plan Metni

Manuel plan icin LINE format kullanilir:

```text
LINE 0 0 10 0
LINE 10 0 10 5
```

### 7.3 Calistirilabilir Komutlar

Backend komutlari `app.execution.commands` icindeki canonical `List[Command]` modeline parse eder. Metin DSL, export formatlari ve driver ciktilari bu canonical komut listesinin turevleridir.

Tipik komut ailesi:

- Hiz ayari
- Kalem indir/kaldir
- Move
- Wait
- Stop veya bitis isaretleri

### 7.4 Export Formatlari

`/api/export` iki format uretir:

- `robot_v1`: robot odakli metin cikti
- `gcode_lite`: hafif G-code benzeri cikti

## 8. Frontend Mimarisi

Resmi frontend:

```text
webapp/operator-v2/
```

Teknolojiler:

- React 18
- Vite
- TypeScript
- Zustand
- TanStack React Query
- React Router
- Zod / React Hook Form altyapisi
- Playwright e2e
- Vitest unit/smoke testleri

Ana dosyalar:

```text
src/app/App.tsx
src/app/AppShell.tsx
src/workflow/model/stages.ts
src/workflow/store/workflowStore.ts
src/data/services/operatorService.ts
src/data/http/apiClient.ts
src/ui/views/PlanYukleView.tsx
src/ui/views/HizalaView.tsx
src/ui/views/KontrolEtView.tsx
src/ui/views/CalistirView.tsx
src/ui/views/SonuclarView.tsx
```

State yonetimi:

- `workflowStore.ts` operator akisini merkezi olarak tutar.
- Plan hazirligi, hizalama, kontrol sonucu, calistirma ozeti, export sonucu ve yerel simulasyon durumu ayni store uzerinden yonetilir.

Backend ile konusan servis:

```text
src/data/services/operatorService.ts
```

Bu dosya endpoint sozlesmelerini frontend tarafinda isimlendirir.

## 9. Driver ve Donanim Siniri

Donanim entegrasyonunda resmi hedef arayuz `List[Command]` modelidir. Driver katmani raw export text yerine canonical komut listesini tuketmelidir.

Mevcut driver'lar:

- `NullDriver`: I/O yapmadan komutlari tutar.
- `FileDriver`: komutlari dosyaya yazar.
- `SerialDriverStub`: gercek serial I/O yapmayan test/dry-run uygulamasi.
- `SerialDriver`: pyserial ile host tarafli seri iletisim.

Seri calistirma endpoint'i:

```text
POST /api/execute_serial
```

Guvenlik ozeti:

- Varsayilan `dry_run: true`.
- `dry_run: false` icin `SERIAL_PORT` gerekir.
- `SERIAL_BAUD` env uzerinden okunur, varsayilan 115200.
- `EXECUTE_SERIAL_ALLOW_REMOTE` truthy degilse endpoint localhost-only davranir.
- `EXECUTE_SERIAL_ADMIN_TOKEN` tanimliysa `X-Execute-Token` header'i gerekir.

Firmware klasoru:

```text
firmware/newbot_loopback_v1/
firmware/newbot_real_v1/
```

`newbot_loopback_v1` protokol loopback/duman testi icindir. `newbot_real_v1` gercek robot firmware iskeletidir; motor/PID/kapali cevrim hareket kontrolu tam urunlesmis kabul edilmemelidir.

## 10. CLI ve Deneysel Akislar

Backend altinda web urun hattindan ayri CLI araclari vardir:

```text
backend/scripts/verify_dxf_drawability.py
backend/scripts/draw_plan_from_dxf.py
backend/scripts/ir_preview_from_dxf.py
backend/scripts/alignment_preview_from_ir.py
backend/scripts/path_plan_from_ir.py
backend/scripts/offline_motion_demo.py
backend/scripts/smoke_test_serial_loopback.py
```

Bu araclar degerlidir ancak her zaman web API ile birebir ayni pipeline'i kullanmaz. Ozellikle wall-only DXF centerline, PrintableLayout IR, mobile mission planner ve bazi benchmark akislari deneysel veya CLI odakli kabul edilmelidir.

GPT bu projede yorum yaparken su ayrimi korumalidir:

- Resmi web/API akisi: `backend/app/api/main.py` + `webapp/operator-v2/`
- CLI/benchmark/research akislari: `backend/scripts/`, `layout_ir/`, `robot/`, bazi `analysis/wall_*` modulleri
- Legacy alanlar: `webapp/frontend/`, `webapp/backend/`

## 11. Test ve Dogrulama

Backend testleri:

```bash
cd backend
pytest tests
```

Varsayilan pytest ayari integration olmayan testleri calistirir:

```text
addopts = "-v -m 'not integration'"
```

Backend test kapsaminda su alanlar vardir:

- DXF/DWG import
- normalized plan
- path generation ve optimizer
- compile/analyze/export
- alignment
- serial protocol ve driver'lar
- file/null driver
- motion runner
- job HTTP file artifact
- official core golden path
- wall centerline ve DXF drawability

Frontend dogrulama:

```bash
cd webapp/operator-v2
npm run build
npm run lint
npm run test
npm run e2e
npm run verify:backend-live
```

Kok package scriptleri:

```bash
npm run dev
npm run dev:backend
npm run dev:frontend
```

## 12. Bilinen Sinirlar ve Riskler

1. `webapp/operator-v2/` resmi frontend olmasina ragmen eski dokumanlarda `webapp/frontend/` gecmis olabilir. Yeni calisma icin Operator V2 esas alinmalidir.
2. Web DXF import yolu ile CLI wall-only/IR benchmark yollari ayni sey degildir.
3. Seri driver host tarafinda vardir, ancak gercek robot hareket kontrolu ve firmware tarafi halen sinirli/iskelet durumdadir.
4. Simulasyon ile gercek donanim calistirma ayni guvenlik seviyesinde gorulmemelidir.
5. `dry_run=false` canli seri calistirma fiziksel cihaza komut gonderebilir; token, localhost ve env kontrolleri dikkate alinmalidir.
6. Export formatlari canonical `List[Command]` modelinin turevidir; donanim entegrasyonu icin ana sozlesme export text degil komut listesidir.
7. `backend/reports/`, `out/`, log dosyalari ve benchmark ciktilari kaynak kod degil artifact olarak ele alinmalidir.

## 13. GPT Icin Calisma Talimatlari

Bu repo uzerinde yardim eden bir GPT su kurallara uymalidir:

- Once kullanicinin istedigi degisikligin resmi urun hattina mi, CLI/deneysel hatta mi ait oldugunu belirle.
- Backend degisikliginde once `backend/app/api/main.py`, `backend/app/api/schemas.py` ve ilgili modulu oku.
- Frontend degisikliginde `webapp/operator-v2/` altinda calis; `webapp/frontend/` veya `webapp/backend/` icine yeni gelistirme ekleme.
- API sozlesmesi degisirse hem Pydantic semalari hem `operatorService.ts` hem de ilgili ekran state'i birlikte guncellenmelidir.
- Komut/driver/donanim islerinde canonical sinirin `List[Command]` oldugunu unutma.
- Canli seri calistirma veya firmware islerinde guvenlik ve fiziksel riskleri acikca belirt.
- UI akisini bozacaksa merkezi Zustand store yapisini kontrol et.
- Test eklerken degisiklik alanina uygun en dar testi yaz; API davranisi degisiyorsa backend testi, ekran akisi degisiyorsa frontend unit/e2e testi dusun.
- Legacy klasorlerde gorulen kodu otomatik olarak gercek urun davranisi sanma.

## 14. GPT'ye Verilebilecek Kisa Prompt

Asagidaki metin, baska bir GPT oturumuna hizli baglam olarak verilebilir:

```text
Bu repo PlanDraw / NewBot uygulamasidir. Amac DXF/DWG/JSON veya manuel LINE plan girdilerini robot cizim komutlarina donusturmek, analiz etmek, simule etmek, opsiyonel seri porta gondermek ve export etmektir. Resmi backend `backend/` altindaki FastAPI uygulamasidir; giris noktasi `backend/app/api/main.py`. Resmi frontend `webapp/operator-v2/` altindaki React/Vite Operator V2 uygulamasidir. `webapp/frontend/` ve `webapp/backend/` legacy kabul edilir.

Ana operator akisi `plan-yukle -> hizala -> kontrol-et -> calistir -> sonuclar` seklindedir. Plan yukleme `/api/import_dxf`, `/api/import_dwg`, `/api/import_plan`, `/api/compile_plan`; analiz `/api/analyze`; simulasyon `/api/jobs` + `/api/jobs/{job_id}/stream`; durdurma `/api/jobs/{job_id}/stop`; seri calistirma `/api/execute_serial`; export `/api/export`; hizalama `/api/alignment/rigid_2d` endpointleriyle yapilir.

Backend pipeline genel olarak Input -> Normalize -> Path -> Commands -> Analyze -> Simulate/Export seklindedir. DXF/DWG import, path generation, komut compiler, analiz, alignment, driver ve export modulleri ayridir. Donanim icin canonical sinir raw text degil `app.execution.commands` icindeki `List[Command]` modelidir. CLI scriptleri ve benchmarklar degerlidir ama web API ile birebir ayni urun hattini temsil etmeyebilir.

Yeni gelistirme yaparken Operator V2 ve backend source-of-truth klasorlerinde calis, legacy kopyalara dokunma. API degisirse Pydantic schema, FastAPI endpoint, frontend service ve ilgili Zustand state/view birlikte kontrol edilmelidir. Seri veya firmware islerinde dry-run/canli ayrimi ve fiziksel riskler acikca korunmalidir.
```

## 15. Hizli Dosya Rehberi

En onemli dosyalar:

```text
README.md
backend/README.md
backend/app/api/main.py
backend/app/api/schemas.py
backend/app/execution/commands.py
backend/app/execution/compiler.py
backend/app/execution/executor.py
backend/app/pathing/path_generator.py
backend/app/pathing/path_optimizer.py
backend/app/importers/dxf_importer.py
backend/app/importers/dwg_converter.py
backend/app/alignment/aligner.py
backend/app/drivers/serial_driver.py
backend/app/drivers/file_driver.py
webapp/operator-v2/src/data/services/operatorService.ts
webapp/operator-v2/src/workflow/store/workflowStore.ts
webapp/operator-v2/src/workflow/model/stages.ts
webapp/operator-v2/src/ui/views/PlanYukleView.tsx
webapp/operator-v2/src/ui/views/HizalaView.tsx
webapp/operator-v2/src/ui/views/KontrolEtView.tsx
webapp/operator-v2/src/ui/views/CalistirView.tsx
webapp/operator-v2/src/ui/views/SonuclarView.tsx
docs/ARCHITECTURE_STATUS.md
docs/DRIVERS.md
docs/CURRENT_STATE_TRUTH_TABLE.md
```

Bu rapor, uygulamanin mevcut yapisini kod ve repo dokumanlarindan cikartilan baglama gore ozetler. En guncel davranis icin her zaman ilgili endpoint, service ve test dosyasi dogrudan kontrol edilmelidir.
