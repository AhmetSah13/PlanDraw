# Mevcut durum truth table (tek kaynak özeti)

**Amaç:** Hangi özelliğin nerede yaşadığı, hangi girişin hangi modülden geçtiği ve web / CLI / HTTP / sürücü sınırlarını tek tabloda toplamak.

**Son güncelleme notu:** Bu tablo, aşağıda listelenen dosyaların içeriğine dayanır; çalıştırma testi yapılmadan yazılmıştır.

**Taranan / kanıt dosyaları (özet):**

- `backend/app/api/main.py` (import zinciri, endpoint’ler, `create_job`, `_run_sim_to_queue`, `import_dxf`, `alignment_rigid_2d`, `compile_path_to_commands` kullanımları)
- `backend/app/execution/executor.py` (dolaylı: `main.py` içinde `CommandExecutor` kullanımı)
- `backend/app/execution/compiler.py` (dolaylı: `main.py` import `compile_path_to_commands`)
- `backend/app/execution/path_compiler.py` (dolaylı: `tests/test_path_command_compiler.py` üzerinden `compile_planned_path_to_commands`)
- `backend/scripts/ir_preview_from_dxf.py`, `alignment_preview_from_ir.py`, `path_plan_from_ir.py` (docstring + importlar)
- `backend/scripts/smoke_test_serial_loopback.py` (docstring + `SerialDriver` importu)
- `backend/tests/test_path_command_compiler.py`, `test_file_driver.py`
- `docs/DRIVERS.md` (dispatch / HTTP sınırı)
- `webapp/frontend/src/api.js`, `app/App.jsx`, `features/prepare/usePreparePlanState.js`, `features/align/useAlignPageState.js`, `features/plan/usePlanPageState.js`, `features/execute/useExecutePageState.js`, `features/monitor/useMonitorPageState.js` (grep ile API kullanımı)
- `firmware/newbot_loopback_v1/README.md`, `firmware/newbot_real_v1/README.md` (kapsam özeti)
- `docs/ARCHITECTURE_STATUS.md` (frozen vs deneysel sınır — referans)

**Kesinlik sütunu:** *Kesin* = ilgili dosyada doğrudan kanıt; *Muhtemel* = yapısal çıkarım veya bu belge kapsamında dosya okunmadı.

---

## Ana truth table

| Feature / Akış | Kullanıcı girişi | Entry point | Ana dosyalar / modüller | Pipeline zinciri | Input | Output / artifact | Frontend bağlı mı | Backend endpoint var mı | CLI var mı | Test var mı | Durum | Kesinlik | Not / risk |
|----------------|------------------|-------------|-------------------------|------------------|-------|-------------------|-------------------|-------------------------|------------|-------------|-------|----------|------------|
| Web DXF/DWG import + preview | DXF/DWG dosyası, katman seçenekleri | `POST /api/import_dxf`, `POST /api/import_dwg` | `backend/app/api/main.py`, `app/importers/dxf_importer.py`, `app/importers/dwg_converter.py` | Upload → bytes → `dxf_*_to_normalized_plan` / DWG→DXF → `normalized_to_plan*` → `plan_text`, `commands_text`, `walls`… | Multipart file + `options_json` | JSON: `ImportDxfResponse` (preview_layers modunda katman listesi) | Evet: `webapp/frontend/src/api.js` `importDxf` / `importDwg`; `usePreparePlanState.js` | Evet | Hayır | Evet: `backend/tests/test_import_dxf_api.py`, `test_import_dwg_api.py` | Çalışıyor | Kesin | `main.py` içinde `layout_ir.compiler` yok — bu hattın PrintableLayoutIR ile aynı olmadığı ayrı satırda. |
| Web Prepare | Plan kaynağı, içe aktarma, LINE/JSON | Tarayıcı `/prepare` | `webapp/frontend/src/features/prepare/PreparePage.jsx`, `usePreparePlanState.js`, `prepareSession.js` | UI → API (`import_*`, `compilePlan` dolaylı diğer ekranlarla) → `sessionStorage` snapshot | Dosya / metin / seçenekler | `savePrepareSnapshot`; komut metni üretimi | Evet | Kısmen (import/compile çağrıları) | Hayır | Dolaylı: import API testleri; Prepare sayfasına özel frontend testi yok | Çalışıyor | Kesin | Operasyonel durum oturumda; backend’e her tıklamada gitmeyebilir. |
| Web Align | Duvar listesi + kontrol noktaları + tolerans | Tarayıcı `/align` → `POST /api/alignment/rigid_2d` | `useAlignPageState.js`, `backend/app/api/main.py` (`alignment_rigid_2d`), `app/alignment/aligner.py`, `app/alignment/walls_to_layout.py`, `app/preview/preview_svg.py` | `walls` → `walls_list_to_printable_layout` → `align_printable_layout_rigid_2d` → JSON + SVG | JSON body (`AlignRigid2dRequest`) | `alignment`, `pre_svg`, `post_svg` | Evet | Evet | Hayır | Evet: `backend/tests/test_alignment_rigid.py` | Çalışıyor | Kesin | Sonuç frontend `sessionStorage` ile taşınır; HTTP job ile zorunlu bağ yok. |
| Web Plan | Plan anlığı, derleme, analiz | Tarayıcı `/plan` | `usePlanPageState.js`, `PlanPage.jsx` | `compilePlan` → `/api/compile_plan`; `analyzeScenario` → `/api/analyze` | `plan_text`, seçenekler; `commands_text` + `walls` analiz için | Güncellenmiş komut/analiz özeti; `savePlanSnapshot` | Evet | Evet (`/api/compile_plan`, `/api/analyze`) | Hayır | Backend’de compile/analyze testleri var; Plan sayfası UI testi yok | Çalışıyor | Kesin | — |
| Web Execute | Komut metni, job seçenekleri | Tarayıcı `/execute` → `POST /api/jobs` + SSE | `useExecutePageState.js`, `ExecutePage.jsx`, `api.js` `createJob` / `getJobStream` | `parse_commands` → `analyze_commands` → blocked ise 409; değilse `_run_sim_to_queue` + SSE | DSL metin + `walls`, `optimize`, `motion`, … | SSE: `tick` / `done` / `error` | Evet | Evet | Hayır | Dolaylı: job/analyze parser testleri | Çalışıyor | Kesin | `RobotDriver` / seri bu uçta yok (`docs/DRIVERS.md`). |
| Web Monitor | (salt okunur) oturum + son job | Tarayıcı `/monitor` | `MonitorPage.jsx`, `useMonitorPageState.js`, `prepareSession.js` `loadMonitorSession` / `loadExecuteLastRun` / `loadAlignSnapshot` | `sessionStorage` okuma; periyodik yenileme; UI | Kayıtlı bundle / lastRun / execution snapshot / align snapshot | Özet UI; hizalama kartı | Evet | Hayır (dedicated Monitor API yok) | Hayır | Hayır (frontend test yok) | Çalışıyor | Kesin | Veri kaynağı tamamen istemci oturumu + Execute’ın yazdığı snapshot’lar. |
| CLI `ir_preview_from_dxf.py` | DXF dosya yolu | `python backend/scripts/ir_preview_from_dxf.py` | `compile_dxf_to_printable_layout`, `validate_printable_layout`, `preview_svg`, `preview_json` | DXF → `PrintableLayout` → validation → SVG + JSON | DXF path, CLI args | `reports/layout_ir/` altında `.svg`, `.layout_ir.json` (varsayılan) | Hayır | Hayır | Evet | Muhtemel: doğrudan bu script için tek başına test aranmadı; `layout_ir` modülleri başka testlerde geçer | Çalışıyor | Kesin (script docstring) | Web `import_dxf` bu derleyiciyi kullanmaz (`main.py` grep: `compile_dxf_to_printable_layout` yok). |
| CLI `alignment_preview_from_ir.py` | DXF + kontrol noktası JSON | `python backend/scripts/alignment_preview_from_ir.py` | `compile_dxf_to_printable_layout`, `align_printable_layout_rigid_2d`, `preview_svg` | DXF → layout → align → pre/post SVG + alignment JSON | DXF path, `--control-points` JSON dosyası | SVG + `alignment.json` (script içi yollar) | Hayır | Hayır | Evet | Muhtemel: script-e2e testi bu belgede doğrulanmadı | Çalışıyor | Kesin (akış docstring) | Path plan / komut yok (script notu). |
| CLI `path_plan_from_ir.py` | DXF + kontrol noktası JSON | `python backend/scripts/path_plan_from_ir.py` | `compile_dxf_to_printable_layout`, `align_printable_layout_rigid_2d`, `plan_path_from_aligned_layout` | DXF → layout → align → `PlannedStroke` planı | DXF path, kontrol noktası JSON | Plan JSON artifact (script) | Hayır | Hayır | Evet | Evet: `backend/tests/test_path_planner.py` (planner modülü) | Çalışıyor | Kesin (script docstring: execution yok) | Üretilen planın web job DSL’ine otomatik bağlandığı yok. |
| PlannedPath → `List[Command]` | `PlannedPath` / `PlannedStroke` verisi | Python API: `compile_planned_path_to_commands` | `backend/app/execution/path_compiler.py` (test import yolu) | IR plan modeli → komut listesi + rapor | `PlannedPath`, `PlannedPathCompileOptions` | `list[Command]` + compile raporu | Hayır (doğrudan) | Hayır | Hayır | Evet: `backend/tests/test_path_command_compiler.py` | Çalışıyor | Kesin | `main.py` web hattı `PathGenerator` + `compile_path_to_commands` kullanır; bu derleyici **ayrı** yol. |
| HTTP job SSE simülasyonu (`create_job` zinciri) | DSL komut metni | `POST /api/jobs` → `create_job` | `main.py` `create_job`, `_run_sim_to_queue`, `app/execution/executor.py` `CommandExecutor` | `parse_commands` → `analyze_commands` → kuyruk → `CommandExecutor.update` döngüsü → SSE | `SimulateRequest` gövdesi | SSE olayları; job bellekte `jobs` dict | Evet | Evet | Hayır | Dolaylı | Çalışıyor | Kesin | Repoda `run_command_execution_job` adlı sembol aranmadı; eşdeğer akış bu isimlerdir. |
| FileDriver execution | `List[Command]` + hedef dosya | Python: `FileDriver.send_commands` | `app/drivers/file_driver.py`, `app/execution/driver_dispatch.py` | `dispatch_commands` veya doğrudan sürücü: dosyaya DSL/robot_v1 yazımı | Komut listesi, path, mod | Dosya içeriği; `get_status()` | Hayır | Hayır | Hayır | Evet: `backend/tests/test_file_driver.py`; bridge: `tests/test_motion_dispatch_bridge_file_integration.py` | Çalışıyor | Kesin | `docs/DRIVERS.md`: HTTP’ye bağlı değil. |
| SerialDriver / serial smoke | Seri port, loopback kart | `python backend/scripts/smoke_test_serial_loopback.py <PORT>` | `app/drivers/serial_driver.py`, `app/drivers/serial_protocol` (dolaylı) | Stub komut listesi → `serialize_commands` / protokol çerçevesi → port | CLI args, fiziksel veya sanal COM | Konsol çıktısı; DONE/ERR/STATUS beklentisi | Hayır | Hayır | Evet | Evet: `backend/tests/test_serial_driver.py`, `test_serial_protocol_transport.py` (birim; donanım şart değil) | Çalışıyor / ortam bağımlı | Kesin (script; gerçek port gerekir) | Script açıkça HTTP kullanmaz. |
| firmware `newbot_loopback_v1` | UART üzerinden profil B batch | MCU’ya flash | `firmware/newbot_loopback_v1/newbot_loopback_v1.ino`, `README.md` | BEGIN…END → komut tüketimi → DONE/ERR | Seri hat, host protokolü | MCU yanıt satırları | Hayır | Hayır | Hayır (firmware) | Hayır (MCU testi bu belgede yok) | Çalışıyor (yazılım tasarımına göre) | Muhtemel (fiziksel doğrulanmadı) | README: motor yok; host `SerialDriver` ile eşleşir. |
| firmware `newbot_real_v1` | UART, parser komutları | MCU’ya flash | `firmware/newbot_real_v1/*.ino`, `*.cpp`, `README.md` | Parse → state machine → stub motion | Protokol satırları | STATUS/DONE/ERR | Hayır | Hayır | Hayır | Hayır | Kısmi / iskelet | Kesin (README kapsam dışı listesi) | Gerçek motor/PID yok. |
| **Karşılaştırma:** Web DXF hattı vs PrintableLayoutIR hattı | Aynı DXF dosyası iki farklı yol | Web: `import_dxf`; CLI: `ir_preview_from_dxf.py` vb. | Web: `dxf_importer` → `NormalizedPlan` → …; IR: `layout_ir/compiler.py` | **Farklı** giriş modelleri ve doğrulama; IR reddetme listesi / PrintabilityReport web import’ta yok (bu tablo kapsamında `main.py` kanıtı) | DXF bytes | Web: normalized + komut; IR: layout + rapor | Evet / Hayır | Evet / Hayır | Evet (sadece IR tarafı) | Her iki tarafta ayrı testler | Ayrık | Kesin | `docs/ARCHITECTURE_STATUS.md` aynı uyarıyı yapar; CLI ≠ web aynı ön işleme. |
| **Karşılaştırma:** HTTP job akışı vs driver/firmware zinciri | Komut metni | Web job SSE vs `dispatch_commands` / seri script | `main.py` executor yolu; `driver_dispatch`, `SerialDriver`, firmware | SSE: in-process simülasyon; sürücü: wire/file | DSL / Command list | SSE olayları vs dosya/seri yanıtı | Evet (sadece SSE) | Evet (sadece SSE) | Evet (sürücü tarafı) | Ayrı test setleri | Ayrık | Kesin | `docs/DRIVERS.md`: dispatch FastAPI’de yok; firmware ile pratik zincir script seviyesinde. |

---

## Ek: Resmi web “compile” iç yolu (komut üretimi)

`main.py` içinde `PathGenerator` + `compile_path_to_commands` birçok yerde kullanılır (ör. `compile_plan`, import sonrası yol üretimi — satır grep: ~301, 524, 740, 1332+). Bu, **nokta yolu → DSL** üretimidir; `compile_planned_path_to_commands` (**PlannedPath** kaynaklı) ile karıştırılmamalıdır.

---

## 1) Bugün gerçekten çalışan parçalar (kod sözleşmesine göre)

- FastAPI uçları: import plan/dxf/dwg, analyze, compile_plan, export, simulate, jobs+SSE, alignment rigid_2d (`main.py` + `api.js` eşlemesi).
- Yeni operasyon konsolu rotaları: `webapp/frontend/src/app/App.jsx`.
- CLI IR / hizalama / path plan scriptleri (kendi docstring’lerindeki sınırlar içinde).
- `compile_planned_path_to_commands` birim testleri.
- `FileDriver` ve `SerialDriver` birim + script duman (ortam bağlı).
- Loopback firmware dokümantasyonu ve host script beklentisi.

## 2) Kısmi / ayrık / deneysel parçalar

- `newbot_real_v1`: iskelet; gerçek tahrik yok (README).
- `PlannedPath` → komut: testte ve modülde var; **HTTP job varsayılan yolu değil**.
- `layout_ir` tam derleme + validation: **CLI ağırlıklı**; web `import_dxf` zincirinde görülmedi (`main.py`).
- `motion_dispatch_bridge` + FileDriver entegrasyonu: testte; **HTTP yok** (`DRIVERS.md`).

## 3) Legacy / duplicate riskleri

- `webapp/backend/`: README ile deprecated ikinci backend ağacı.
- `webapp/frontend/src/App.jsx`: legacy monolit; `LegacyRoute` ile yüklenir; aynı `api.js`.
- Kök `scenario_smoke_tests.py` / `test_optimizer.py`: paket yolu bu belgede doğrulanmadı; **muhtemel** eski/kırık giriş noktaları.

## 4) En kritik entegrasyon boşluğu

**HTTP job (SSE) simülasyonu ile `RobotDriver` / seri / firmware yürütme zincirinin tek uçta birleşmemesi** — `docs/DRIVERS.md` ve `main.py` içeriği ile uyumlu.

## 5) Bir sonraki tek entegrasyon hedefi (öneri — 1 adet)

**`POST /api/jobs` başarılı analiz sonrası üretilen `List[Command]` için isteğe bağlı `FileDriver` çıktısı** (aynı komut listesinin diske yazılması): mevcut `dispatch_commands` / `FileDriver` ile en düşük sürprizli köprü; firmware gerektirmez, HTTP sözleşmesine küçük bir alan eklenmesini gerektirir (bu belge yalnızca öneri; uygulama yok).

---

*Bu dosya `docs/CURRENT_STATE_TRUTH_TABLE.md` olarak tek kaynak özetidir; detaylı mimari anlatım için `docs/ARCHITECTURE.md` ve sınır için `docs/ARCHITECTURE_STATUS.md` kullanılmalıdır.*
